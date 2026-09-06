"""Orchestrator Agent — ADK Multi-Agent Composition coordinating all specialists.

Composed using Google Agent Development Kit (ADK):
  1. SequentialAgent (Main Orchestrator Workflow)
     - generate_agent (ADK GenerateOptionsAgent with generate_options_tool)
     - parallel_evaluator (ADK ParallelAgent running 4 specialist sub-agents concurrently)
     - synthesis_agent (ADK SynthesisAgent with calibrate_and_synthesize_tool)
  2. Executed through ADK Runner (Runner.run_async) in the live production request pipeline.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import logging
import os
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from google.adk import Agent, Runner
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.events.event import Event
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.function_tool import FunctionTool
from google.genai import types

import case_store
from agents import budget_sentinel, compliance, continuity_memory, schedule_optimizer
from models import CaseState, EvidenceRow, MCPCall, RecoveryOption
from scoring import score_options
from services import clickhouse_client, gemini_client, justification_service, mcp_client

logger = logging.getLogger("continuity.agents.orchestrator")

SEVERITY_COST_MULT = {"low": 0.85, "medium": 1.0, "high": 1.15}


# ---------------------------------------------------------------------------
# ADK Tools for Orchestration Stages
# ---------------------------------------------------------------------------
async def generate_options_tool(
    production_id: str,
    disruption_type: str,
    affected_day: int,
    affected_cast_id: Optional[str] = None,
    affected_location_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generates initial candidate recovery options for a disrupted production schedule.

    Args:
        production_id: Unique production identifier.
        disruption_type: Disruption classification.
        affected_day: Disrupted shoot day index (1-based).
        affected_cast_id: ID of disrupted cast member if applicable.
        affected_location_id: ID of disrupted location if applicable.
    """
    bundle = await clickhouse_client.get_current_schedule(production_id)
    if bundle is None:
        return {"options": [], "affected_scene_ids": []}

    from models import DisruptionReport, new_case
    report = DisruptionReport(
        production_id=production_id,
        disruption_type=disruption_type,
        affected_day=affected_day,
        affected_cast_id=affected_cast_id,
        affected_location_id=affected_location_id,
    )
    case = new_case(report)
    options = schedule_optimizer.generate_schedule_options(case, bundle)
    return {
        "options": [o.model_dump() for o in options],
        "affected_scene_ids": case.affected_scene_ids,
        "count": len(options),
    }


async def calibrate_and_synthesize_tool(
    case_data: Dict[str, Any],
    options_data: List[Dict[str, Any]],
    bundle_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Calibrates option economics, scores candidate recovery options, and generates executive rationale.

    Args:
        case_data: Serialized CaseState dictionary.
        options_data: Serialized candidate RecoveryOption dictionaries.
        bundle_data: Serialized schedule bundle dictionary.
    """
    case = CaseState(**case_data)
    options = [RecoveryOption(**o) for o in options_data]

    # Perform bottom-up rate card pricing and live signal calibration
    await budget_sentinel.calibrate_option_economics(case, options, bundle_data)

    evidence_by_strategy = {e.resolution_strategy: e for e in case.evidence_rows}
    overall_avg_delay = (
        sum(e.avg_delay_hours for e in case.evidence_rows) / len(case.evidence_rows)
        if case.evidence_rows else 6.0
    )
    mult = SEVERITY_COST_MULT.get(case.disruption.severity, 1.0)

    for o in options:
        ev = evidence_by_strategy.get(o.strategy)
        o.evidence = ev
        base_delay = ev.avg_delay_hours if ev else overall_avg_delay
        o.estimated_delay_hours = round(base_delay * mult, 1)

    ranked_options = score_options(options)
    case.options = ranked_options

    recommended = next((o for o in case.options if o.recommended), None)
    deterministic_rationale = (
        f"'{recommended.name}' has the best weighted score ({recommended.score:.2f}): "
        f"lowest grounded cost estimate (${recommended.estimated_cost_usd:,}) and "
        f"{recommended.estimated_delay_hours}h expected delay while passing all compliance checks."
    ) if recommended else "No viable options available."

    if recommended:
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
        try:
            data = await gemini_client.generate_json(
                "You are the Orchestrator of a film production recovery council. "
                f"Disruption: {case.disruption.disruption_type}, severity {case.disruption.severity}, "
                f"Day {case.disruption.affected_day}. "
                f"ClickHouse historical evidence: {evidence_lines}. "
                f"Ranked options: {option_lines}. Recommended: {recommended.name}. "
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
                case.recommendation_rationale = (
                    rationale if 30 < len(rationale) < 800 else deterministic_rationale
                )
            else:
                case.recommendation_rationale = deterministic_rationale
        except Exception:
            case.recommendation_rationale = deterministic_rationale
    else:
        case.recommendation_rationale = deterministic_rationale

    if case.options:
        try:
            await justification_service.generate_justifications(case.options, case.evidence_rows)
        except Exception as exc:
            logger.warning("Justification service call in calibrate_and_synthesize_tool failed: %s", exc)

    return {
        "ranked_options": [o.model_dump() for o in case.options],
        "recommended_option_id": recommended.option_id if recommended else None,
        "recommendation_rationale": case.recommendation_rationale,
        "evidence_narrative": case.evidence_narrative,
    }


# ---------------------------------------------------------------------------
# ADK Specialist Agent Implementations for Production Pipeline
# ---------------------------------------------------------------------------
class GenerateOptionsAgent(BaseAgent):
    """ADK Agent generating candidate recovery options from current schedule."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        case_id = ctx.session.state.get("case_id")
        case = case_store.get(case_id)
        bundle = ctx.session.state.get("bundle")
        if not case or not bundle:
            return

        logger.info("[ADK] [generate_agent] Generating candidate options for case %s", case_id)
        case.agent_start("schedule_optimizer", "Analyzing scene/cast/location constraints…")
        options = schedule_optimizer.generate_schedule_options(case, bundle)
        ctx.session.state["options"] = [o.model_dump() for o in options]
        ctx.session.state["affected_scene_ids"] = case.affected_scene_ids

        summary_text = f"Proposed {len(options)} recovery options · {len(case.affected_scene_ids)} affected scene(s)"
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=summary_text)]),
        )


class BudgetSentinelAgent(BaseAgent):
    """ADK Agent querying ClickHouse historical disruption metrics via MCP."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        case_id = ctx.session.state.get("case_id")
        case = case_store.get(case_id)
        if not case:
            return

        logger.info("[ADK] [budget_sentinel_agent] Querying disruption history via ClickHouse MCP for case %s", case_id)
        case.agent_start("budget_sentinel", "Querying disruption history via ClickHouse MCP…")
        await budget_sentinel.run(case)
        ctx.session.state["evidence_rows"] = [e.model_dump() for e in case.evidence_rows]
        ctx.session.state["evidence_narrative"] = case.evidence_narrative
        ctx.session.state["mcp_calls"] = [c.model_dump() for c in case.mcp_calls]

        n_calls = len([c for c in case.mcp_calls if c.status == "success"])
        total_cases = sum(e.past_cases for e in case.evidence_rows)
        summary = f"{n_calls} MCP quer{'ies' if n_calls != 1 else 'y'} · {total_cases:,} historical cases analyzed"
        case.agent_complete("budget_sentinel", summary, case.evidence_narrative)
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=summary)]),
        )


class ContinuityMemoryAgent(BaseAgent):
    """ADK Agent evaluating narrative sequence order, dependencies, and costume splits."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        case_id = ctx.session.state.get("case_id")
        case = case_store.get(case_id)
        bundle = ctx.session.state.get("bundle")
        options_data = ctx.session.state.get("options", [])
        if not case or not bundle:
            return

        logger.info("[ADK] [continuity_memory_agent] Evaluating continuity risks for case %s", case_id)
        case.agent_start("continuity_memory", "Checking costume, dependency and narrative continuity…")
        options = [RecoveryOption(**o) for o in options_data]
        summary = await continuity_memory.run(case, options, bundle)
        ctx.session.state["options"] = [o.model_dump() for o in options]
        case.agent_complete("continuity_memory", summary)
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=summary)]),
        )


class ComplianceAgent(BaseAgent):
    """ADK Agent evaluating union rules, location permits, and 100mi transit constraints."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        case_id = ctx.session.state.get("case_id")
        case = case_store.get(case_id)
        bundle = ctx.session.state.get("bundle")
        options_data = ctx.session.state.get("options", [])
        if not case or not bundle:
            return

        logger.info("[ADK] [compliance_agent] Validating operational compliance for case %s", case_id)
        case.agent_start("compliance", "Validating availability, day limits and working hours…")
        options = [RecoveryOption(**o) for o in options_data]
        summary = await compliance.run(case, options, bundle)
        ctx.session.state["options"] = [o.model_dump() for o in options]
        case.agent_complete("compliance", summary)
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=summary)]),
        )


class ScheduleOptimizerPolishAgent(BaseAgent):
    """ADK Agent polishing candidate recovery option descriptions."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        case_id = ctx.session.state.get("case_id")
        case = case_store.get(case_id)
        bundle = ctx.session.state.get("bundle")
        options_data = ctx.session.state.get("options", [])
        if not case or not bundle:
            return

        logger.info("[ADK] [schedule_optimizer_agent] Polishing recovery option descriptions for case %s", case_id)
        options = [RecoveryOption(**o) for o in options_data]
        await schedule_optimizer.polish_descriptions(case, options, bundle)
        ctx.session.state["options"] = [o.model_dump() for o in options]
        summary = f"Proposed {len(options)} recovery options · {len(case.affected_scene_ids)} affected scene(s)"
        case.agent_complete("schedule_optimizer", summary, "; ".join(o.name for o in options))
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=summary)]),
        )


class SynthesisAgent(BaseAgent):
    """ADK Agent calibrating bottom-up rate card economics, TRD scoring, and executive synthesis."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        case_id = ctx.session.state.get("case_id")
        case = case_store.get(case_id)
        bundle = ctx.session.state.get("bundle")
        options_data = ctx.session.state.get("options", [])
        if not case or not bundle:
            return

        logger.info("[ADK] [synthesis_agent] Calibrating economics and generating executive synthesis for case %s", case_id)
        case.agent_start("orchestrator", "Calibrating rate-card economics and scoring options…")
        synthesis_payload = await calibrate_and_synthesize_tool(
            case.model_dump(),
            options_data,
            bundle,
        )
        case.options = [RecoveryOption(**o) for o in synthesis_payload.get("ranked_options", [])]
        case.recommendation_rationale = synthesis_payload.get("recommendation_rationale", "")
        if synthesis_payload.get("evidence_narrative"):
            case.evidence_narrative = synthesis_payload["evidence_narrative"]

        recommended = next((o for o in case.options if o.recommended), None)
        summary = f"Ranked {len(case.options)} options: recommending '{recommended.name if recommended else 'n/a'}'"
        case.agent_complete("orchestrator", summary, case.recommendation_rationale)
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=summary)]),
        )


# ---------------------------------------------------------------------------
# ADK Multi-Agent Composition Factories
# ---------------------------------------------------------------------------
def create_generate_agent(model_name: Optional[str] = None) -> BaseAgent:
    """Instantiate the Generate Agent."""
    return GenerateOptionsAgent(name="generate_agent")


def create_parallel_evaluator_agent() -> ParallelAgent:
    """Instantiate the Parallel Evaluator running all four specialists concurrently."""
    return ParallelAgent(
        name="parallel_evaluator",
        sub_agents=[
            BudgetSentinelAgent(name="budget_sentinel_agent"),
            ContinuityMemoryAgent(name="continuity_memory_agent"),
            ComplianceAgent(name="compliance_agent"),
            ScheduleOptimizerPolishAgent(name="schedule_optimizer_agent"),
        ],
    )


def create_synthesis_agent(model_name: Optional[str] = None) -> BaseAgent:
    """Instantiate the Synthesis Agent."""
    return SynthesisAgent(name="synthesis_agent")


def create_orchestrator_agent(model_name: Optional[str] = None) -> SequentialAgent:
    """Instantiate the complete ADK Sequential Orchestrator Agent."""
    return SequentialAgent(
        name="orchestrator_agent",
        sub_agents=[
            create_generate_agent(model_name),
            create_parallel_evaluator_agent(),
            create_synthesis_agent(model_name),
        ],
    )


# ---------------------------------------------------------------------------
# Investigation Result Cache (TTL 10m: instant second view)
# ---------------------------------------------------------------------------
_INVESTIGATION_CACHE: Dict[Tuple[str, str], Tuple[float, Dict[str, Any]]] = {}
_INVESTIGATION_CACHE_TTL = 600.0  # 10 minutes


def compute_disruption_hash(disruption: Any) -> str:
    raw = (
        f"{disruption.disruption_type}:{disruption.affected_day}:"
        f"{getattr(disruption, 'affected_cast_id', '') or ''}:"
        f"{getattr(disruption, 'affected_location_id', '') or ''}:{disruption.severity}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def get_cached_investigation(production_id: str, disruption: Any) -> Optional[Dict[str, Any]]:
    d_hash = compute_disruption_hash(disruption)
    key = (production_id, d_hash)
    entry = _INVESTIGATION_CACHE.get(key)
    if entry and (time.time() - entry[0]) < _INVESTIGATION_CACHE_TTL:
        return copy.deepcopy(entry[1])
    return None


def store_cached_investigation(production_id: str, disruption: Any, case: CaseState) -> None:
    d_hash = compute_disruption_hash(disruption)
    key = (production_id, d_hash)
    cached_data = {
        "options": [o.model_dump() for o in case.options],
        "evidence_rows": [e.model_dump() for e in case.evidence_rows],
        "evidence_narrative": case.evidence_narrative,
        "evidence_footnote": case.evidence_footnote,
        "evidence_cohort": case.evidence_cohort,
        "studio_id": case.studio_id,
        "recommendation_rationale": case.recommendation_rationale,
        "affected_scene_ids": list(case.affected_scene_ids),
        "mcp_calls": [m.model_dump() for m in case.mcp_calls],
        "llm_mode": case.llm_mode,
    }
    _INVESTIGATION_CACHE[key] = (time.time(), cached_data)


def hydrate_case_from_cache(case: CaseState, cached: Dict[str, Any], elapsed_ms: int = 0) -> None:
    """Hydrates a CaseState instantly from a warm cached investigation."""
    case.options = [RecoveryOption(**o) for o in cached.get("options", [])]
    case.evidence_rows = [EvidenceRow(**e) for e in cached.get("evidence_rows", [])]
    case.evidence_narrative = cached.get("evidence_narrative", "")
    case.evidence_footnote = cached.get("evidence_footnote", "")
    case.evidence_cohort = cached.get("evidence_cohort", "global")
    case.studio_id = cached.get("studio_id", "global")
    case.recommendation_rationale = cached.get("recommendation_rationale", "")
    case.affected_scene_ids = list(cached.get("affected_scene_ids", []))
    case.mcp_calls = [MCPCall(**m) for m in cached.get("mcp_calls", [])]
    case.llm_mode = cached.get("llm_mode", "gemini")
    case.status = "options_ready"
    for k in case.agents:
        case.agent_complete(k, "Loaded from warm investigation cache (TTL 10m)")
    case.touch_stage("AGENTS_INVESTIGATING")
    case.touch_stage("OPTIONS_READY")
    case.touch_stage("PRODUCER_REVIEWING")
    case.meta = {
        "cached": True,
        "timing": {
            "mcp_connect_ms": 0,
            "per_agent": {k: 0 for k in ["schedule_optimizer", "budget_sentinel", "continuity_memory", "compliance"]},
            "synthesis_ms": 0,
            "total_ms": elapsed_ms,
        },
        "mcp_connect": 0.0,
        "per_agent": {k: 0 for k in ["schedule_optimizer", "budget_sentinel", "continuity_memory", "compliance"]},
        "synthesis": 0.0,
        "total": round(elapsed_ms / 1000.0, 3),
    }


# ---------------------------------------------------------------------------
# Production Orchestrator Investigation Runner (Genuinely Driven by ADK Runner)
# ---------------------------------------------------------------------------
async def run_investigation(case_id: str) -> None:
    """Coordinates the full async recovery investigation lifecycle via ADK Runner."""
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
    t_start = time.perf_counter()

    # Check 10-min in-memory investigation cache first (instant second view)
    cached = get_cached_investigation(case.production_id, case.disruption)
    if cached is not None:
        t_hit_ms = int((time.perf_counter() - t_start) * 1000)
        hydrate_case_from_cache(case, cached, t_hit_ms)
        logger.info(
            "INVESTIGATION STAGE TIMINGS [%s]: total=%.2fs | mcp_connect=0.00s | per_agent=%s | synthesis=0.00s (WARM CACHE HIT)",
            case.case_id, t_hit_ms / 1000.0, case.meta["per_agent"],
        )
        return

    case.status = "investigating"
    case.touch_stage("AGENTS_INVESTIGATING")
    case.agent_start("orchestrator", "Loading current schedule from ClickHouse…")

    # Warm MCP session if needed and measure connect time
    t_mcp0 = time.perf_counter()
    if not mcp_client.is_mcp_warm():
        await mcp_client.start_mcp_client()
    mcp_connect_ms = int((time.perf_counter() - t_mcp0) * 1000)

    t_fetch_start = time.perf_counter()
    bundle = await clickhouse_client.get_current_schedule(case.production_id)
    t_fetch = time.perf_counter() - t_fetch_start
    if bundle is None:
        raise RuntimeError(f"Production {case.production_id} not found in ClickHouse")

    d = case.disruption
    case.agents["orchestrator"].summary = (
        f"Case {case.case_id}: {d.disruption_type} on Day {d.affected_day}. "
        f"Dispatching ADK multi-agent workflow…"
    )

    # 1. Initialize ADK In-Memory Session & Runner
    session_service = InMemorySessionService()
    app_name = "continuity_council"
    user_id = f"user_{case.case_id}"
    session_id = f"session_{case.case_id}"

    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        state={
            "case_id": case.case_id,
            "production_id": case.production_id,
            "bundle": bundle,
        },
    )

    orchestrator_agent = create_orchestrator_agent()
    runner = Runner(
        app_name=app_name,
        agent=orchestrator_agent,
        session_service=session_service,
    )

    logger.info(
        "[ADK] Executing SequentialAgent '%s' via ADK Runner for case %s (Production: %s)",
        orchestrator_agent.name, case.case_id, case.production_id,
    )

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=f"Investigate disruption case '{case.case_id}' for production '{case.production_id}'.")],
    )

    # 2. Genuinely execute the entire multi-agent hierarchy through ADK Runner
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message,
    ):
        author = getattr(event, "author", "unknown")
        logger.debug("[ADK Event] author=%s", author)

    if case.options and any(not getattr(o, "justification", "") for o in case.options):
        try:
            await justification_service.generate_justifications(case.options, case.evidence_rows)
        except Exception as exc:
            logger.warning("Justification generation before options_ready failed: %s", exc)

    case.status = "options_ready"
    case.llm_mode = "deterministic" if gemini_client.quota_hit() or not gemini_client.is_configured() else "gemini"
    case.touch_stage("OPTIONS_READY")
    case.touch_stage("PRODUCER_REVIEWING")

    # Measure per-agent and synthesis timings
    per_agent = {
        k: (case.agents[k].duration_ms if case.agents.get(k) and case.agents[k].duration_ms is not None else 0)
        for k in ["schedule_optimizer", "budget_sentinel", "continuity_memory", "compliance"]
    }
    synthesis_ms = (
        case.agents["orchestrator"].duration_ms
        if case.agents.get("orchestrator") and case.agents["orchestrator"].duration_ms is not None
        else 0
    )
    t_total = time.perf_counter() - t_start
    total_ms = int(t_total * 1000)

    case.meta = {
        "cached": False,
        "timing": {
            "mcp_connect_ms": mcp_connect_ms,
            "per_agent": per_agent,
            "synthesis_ms": synthesis_ms,
            "total_ms": total_ms,
        },
        "mcp_connect": round(mcp_connect_ms / 1000.0, 3),
        "per_agent": per_agent,
        "synthesis": round(synthesis_ms / 1000.0, 3),
        "total": round(t_total, 3),
    }

    # Store in 10-min cache
    store_cached_investigation(case.production_id, case.disruption, case)

    logger.info(
        "INVESTIGATION STAGE TIMINGS [%s]: total=%.2fs | mcp_connect=%dms | per_agent=%s | synthesis=%dms | ranked_options=%d",
        case.case_id, t_total, mcp_connect_ms, per_agent, synthesis_ms, len(case.options),
    )
