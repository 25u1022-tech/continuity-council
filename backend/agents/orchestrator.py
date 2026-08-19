"""Orchestrator Agent — typed async state machine coordinating all specialists.

Flow (per app_flow.md):
  CASE_CREATED -> AGENTS_INVESTIGATING
    step 1: load schedule bundle (ClickHouse)
    step 2: Schedule Optimizer + Budget Sentinel in parallel
    step 3: Continuity Memory + Compliance in parallel (need options)
    step 4: merge evidence -> estimates -> TRD weighted scoring -> ranking
  -> OPTIONS_READY
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import case_store
from agents import budget_sentinel, compliance, continuity_memory, schedule_optimizer
from models import CaseState
from scoring import score_options
from services import clickhouse_client, gemini_client

logger = logging.getLogger("continuity.agents.orchestrator")

SEVERITY_COST_MULT = {"low": 0.85, "medium": 1.0, "high": 1.15}


async def run_investigation(case_id: str) -> None:
    case = case_store.get(case_id)
    if case is None:
        return
    try:
        await _run(case)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Investigation failed for %s", case_id)
        case.status = "error"
        case.error = str(exc)[:400]
        for key, agent in case.agents.items():
            if agent.status == "running":
                case.agent_error(key, f"Aborted: {str(exc)[:160]}")


async def _run(case: CaseState) -> None:
    import time

    t_start = time.perf_counter()
    case.status = "investigating"
    case.touch_stage("AGENTS_INVESTIGATING")
    case.agent_start("orchestrator", "Loading current schedule from ClickHouse…")

    t_fetch_start = time.perf_counter()
    bundle = await clickhouse_client.get_current_schedule(case.production_id)
    t_fetch = time.perf_counter() - t_fetch_start
    if bundle is None:
        raise RuntimeError(f"Production {case.production_id} not found in ClickHouse")

    d = case.disruption
    case.agents["orchestrator"].summary = (
        f"Case {case.case_id}: {d.disruption_type} on Day {d.affected_day}. "
        f"Dispatching specialist agents…"
    )

    # ---- Steps 2+3: ALL FOUR specialists in PARALLEL ----
    options = schedule_optimizer.generate_schedule_options(case, bundle)

    case.agent_start("schedule_optimizer", "Analyzing scene/cast/location constraints…")
    case.agent_start("budget_sentinel", "Querying disruption history via ClickHouse MCP…")
    case.agent_start("continuity_memory", "Checking costume, dependency and narrative continuity…")
    case.agent_start("compliance", "Validating availability, day limits and working hours…")

    timings = {}

    async def run_schedule():
        t0 = time.perf_counter()
        await schedule_optimizer.polish_descriptions(case, options, bundle)
        timings["schedule_optimizer"] = time.perf_counter() - t0
        case.agent_complete(
            "schedule_optimizer",
            f"Proposed {len(options)} recovery options · {len(case.affected_scene_ids)} affected scene(s)",
            "; ".join(o.name for o in options),
        )

    async def run_budget():
        t0 = time.perf_counter()
        await budget_sentinel.run(case)
        timings["budget_sentinel"] = time.perf_counter() - t0
        n_calls = len([c for c in case.mcp_calls if c.status == 'success'])
        total_cases = sum(e.past_cases for e in case.evidence_rows)
        case.agent_complete(
            "budget_sentinel",
            f"{n_calls} MCP quer{'ies' if n_calls != 1 else 'y'} · {total_cases:,} historical cases analyzed",
            case.evidence_narrative,
        )

    async def run_continuity():
        t0 = time.perf_counter()
        summary = await continuity_memory.run(case, options, bundle)
        timings["continuity_memory"] = time.perf_counter() - t0
        case.agent_complete("continuity_memory", summary)

    async def run_compliance():
        t0 = time.perf_counter()
        summary = await compliance.run(case, options, bundle)
        timings["compliance"] = time.perf_counter() - t0
        case.agent_complete("compliance", summary)

    t_spec_start = time.perf_counter()
    await asyncio.gather(run_schedule(), run_budget(), run_continuity(), run_compliance())
    t_specialists = time.perf_counter() - t_spec_start

    # ---- Step 4: rate-card bottom-up pricing + live signals + historical calibration ----
    evidence_by_strategy = {e.resolution_strategy: e for e in case.evidence_rows}
    overall_avg_delay = (
        sum(e.avg_delay_hours for e in case.evidence_rows) / len(case.evidence_rows)
        if case.evidence_rows else 6.0
    )
    mult = SEVERITY_COST_MULT.get(case.disruption.severity, 1.0)

    # Perform bottom-up pricing and live signal calibration
    await budget_sentinel.calibrate_option_economics(case, options, bundle)

    for o in options:
        ev = evidence_by_strategy.get(o.strategy)
        o.evidence = ev
        base_delay = ev.avg_delay_hours if ev else overall_avg_delay
        o.estimated_delay_hours = round(base_delay * mult, 1)

    case.options = score_options(options)

    # One combined Gemini call: evidence brief + recommendation rationale
    recommended = next((o for o in case.options if o.recommended), None)
    t_synth_start = time.perf_counter()
    if recommended:
        deterministic_rationale = (
            f"'{recommended.name}' has the best weighted score ({recommended.score:.2f}): "
            f"lowest grounded cost estimate (${recommended.estimated_cost_usd:,}) and "
            f"{recommended.estimated_delay_hours}h expected delay while passing all compliance checks."
        )
        evidence_lines = "; ".join(
            f"{e.resolution_strategy}: ${e.avg_cost_overrun_usd:,.0f} avg overrun, "
            f"{e.avg_delay_hours:.1f}h avg delay, {e.past_cases} cases"
            for e in case.evidence_rows[:6]
        )
        option_lines = "; ".join(
            f"{o.name} (rank {o.rank}, ${o.estimated_cost_usd:,}, {o.estimated_delay_hours}h, "
            f"{'valid' if o.compliance_valid else 'BLOCKED: ' + (o.compliance_warnings[0] if o.compliance_warnings else 'constraint')})"
            for o in case.options
        )
        data = await gemini_client.generate_json(
            "You are the Orchestrator of a film production recovery council. "
            f"Disruption: {case.disruption.disruption_type}, severity {case.disruption.severity}, "
            f"Day {case.disruption.affected_day}. "
            f"ClickHouse historical evidence — {evidence_lines}. "
            f"Ranked options — {option_lines}. Recommended: {recommended.name}. "
            "Return JSON {\"evidence_brief\": \"2 sentences comparing strategies with numbers\", "
            "\"rationale\": \"2 sentences why recommended option wins\"}.",
            timeout=6.0,
            max_tokens=300,
        )
        if isinstance(data, dict):
            brief = (data.get("evidence_brief") or "").strip()
            rationale = (data.get("rationale") or "").strip()
            if 30 < len(brief) < 800:
                case.evidence_narrative = brief
            case.recommendation_rationale = rationale if 30 < len(rationale) < 800 else deterministic_rationale
        else:
            case.recommendation_rationale = deterministic_rationale
    t_synthesis = time.perf_counter() - t_synth_start

    t_total = time.perf_counter() - t_start
    mcp_total = sum(c.latency_ms for c in case.mcp_calls) / 1000.0

    logger.info(
        "INVESTIGATION TIMING [%s]: total=%.2fs | schedule_fetch=%.2fs | parallel_specialists=%.2fs "
        "(schedule_opt=%.2fs, budget=%.2fs, mcp_sum=%.2fs, continuity=%.2fs, compliance=%.2fs) | synthesis=%.2fs",
        case.case_id, t_total, t_fetch, t_specialists,
        timings.get("schedule_optimizer", 0), timings.get("budget_sentinel", 0), mcp_total,
        timings.get("continuity_memory", 0), timings.get("compliance", 0),
        t_synthesis,
    )

    case.agent_complete(
        "orchestrator",
        f"Ranked {len(case.options)} options — recommending '{recommended.name if recommended else 'n/a'}'",
        case.recommendation_rationale,
    )
    case.status = "options_ready"
    case.llm_mode = "deterministic" if gemini_client.quota_hit() or not gemini_client.is_configured() else "gemini"
    case.touch_stage("OPTIONS_READY")
    case.touch_stage("PRODUCER_REVIEWING")
