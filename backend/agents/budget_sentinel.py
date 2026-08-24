"""Budget Sentinel Agent — the ClickHouse-powered agent (ADK Agent).

Queries the `strategy_performance_mv` materialized view in ClickHouse via the OFFICIAL
`mcp-clickhouse` MCP server at runtime. The LLM never writes raw SQL.

Enhancements:
- ADK Agent Architecture with FunctionTool wrapping safe MCP queries
- Rate card benchmark bottom-up estimation (crew, cast, locations, equipment)
- Live external signals: Open-Meteo weather risk & Frankfurter/ECB live FX conversion
- 70% bottom-up + 30% ClickHouse historical evidence calibration
- Persistent MCP client: live ClickHouse queries run in ~100-200ms
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from google.adk import Agent, Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.function_tool import FunctionTool
from google.genai import types

from models import (
    BudgetSentinelResult,
    CaseState,
    CostBreakdown,
    CostLineItem,
    EvidenceRow,
    MCPCall,
    RecoveryOption,
)
from services import clickhouse_client
from services.finance_service import convert_currency, get_exchange_rate
from services.mcp_client import mcp_run_query
from services.safe_query_builder import TEMPLATE_DESCRIPTIONS, build_query
from services.weather_service import get_weather_risk

logger = logging.getLogger("continuity.agents.budget")

# In-memory evidence cache: (disruption_type, severity) -> (timestamp, List[EvidenceRow])
_EVIDENCE_CACHE: Dict[Tuple[str, str], Tuple[float, List[EvidenceRow]]] = {}
_CACHE_TTL_SECONDS = 600.0


def _rows_to_evidence(columns: List[str], rows: List[List[Any]]) -> List[EvidenceRow]:
    out = []
    for row in rows:
        rec = dict(zip(columns, row))
        out.append(EvidenceRow(
            resolution_strategy=str(rec.get("resolution_strategy", "")),
            avg_cost_overrun_usd=float(rec.get("avg_cost_overrun_usd", 0) or 0),
            avg_delay_hours=float(rec.get("avg_delay_hours", 0) or 0),
            avg_continuity_risk=float(rec.get("avg_continuity_risk", 0) or 0),
            avg_compliance_risk=float(rec.get("avg_compliance_risk", 0) or 0),
            avg_success_score=float(rec.get("avg_success_score", 0) or 0),
            past_cases=int(rec.get("past_cases", 0) or 0),
        ))
    return out


# ---------------------------------------------------------------------------
# ADK FunctionTool: Safe Disruption History Query
# ---------------------------------------------------------------------------
async def query_disruption_history(
    template_id: str,
    disruption_type: str,
    severity: Optional[str] = None,
    studio_id: Optional[str] = "global",
    strategy: Optional[str] = None,
    limit: int = 40,
) -> Dict[str, Any]:
    """Query ClickHouse historical disruption metrics via safe SQL templates over MCP.

    Args:
        template_id: Predefined query template ID ('strategy_performance', 'strategy_performance_by_severity', 'studio_strategy_performance', 'raw_history_samples').
        disruption_type: Disruption classification ('lead_actor_unavailable', 'location_unavailable', 'equipment_failure', 'weather_delay', 'permit_issue', 'supporting_actor_unavailable').
        severity: Optional severity level ('low', 'medium', 'high').
        studio_id: Studio identifier for tenant cohort isolation (defaults to 'global').
        strategy: Optional resolution strategy for raw record drilldown.
        limit: Maximum rows to return (1-100, default 40).
    """
    params: Dict[str, Any] = {"disruption_type": disruption_type}
    if severity:
        params["severity"] = severity
    if studio_id:
        params["studio_id"] = studio_id
    if strategy:
        params["strategy"] = strategy
    if limit:
        params["limit"] = limit

    sql = build_query(template_id, params)
    result = await mcp_run_query(sql)
    evidence_rows = _rows_to_evidence(result.get("columns", []), result.get("rows", []))
    return {
        "sql": sql,
        "tool": result.get("tool", "run_query"),
        "latency_ms": result.get("latency_ms", 0),
        "rows_returned": len(result.get("rows", [])),
        "evidence_rows": [e.model_dump() for e in evidence_rows],
    }


query_disruption_history_tool = FunctionTool(query_disruption_history)


def create_budget_sentinel_agent(model_name: Optional[str] = None) -> Agent:
    """Instantiate the ADK Budget Sentinel Agent."""
    model = model_name or os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    return Agent(
        name="budget_sentinel_agent",
        model=model,
        instruction=(
            "You are the Budget Sentinel Agent in the Continuity Council film production recovery system. "
            "Your task is to analyze historical disruption patterns and evaluate economic impacts. "
            "Use the `query_disruption_history` tool to execute safe queries against the ClickHouse "
            "materialized view via MCP to retrieve empirical cost, delay, and risk metrics."
        ),
        tools=[query_disruption_history_tool],
    )


# ---------------------------------------------------------------------------
# ADK Execution: Structured Budget Sentinel Investigation
# ---------------------------------------------------------------------------
async def run_budget_sentinel_adk(
    case: CaseState,
    session_service: Optional[InMemorySessionService] = None,
) -> BudgetSentinelResult:
    """Executes the Budget Sentinel via ADK Runner and returns typed BudgetSentinelResult."""
    if session_service is None:
        session_service = InMemorySessionService()

    app_name = "budget_sentinel_app"
    agent = create_budget_sentinel_agent()
    runner = Runner(
        app_name=app_name,
        agent=agent,
        session_service=session_service,
    )

    user_id = f"user_{case.case_id}"
    session_id = f"session_{case.case_id}"
    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )

    d = case.disruption
    prompt_text = (
        f"Analyze historical disruption data for Case ID '{case.case_id}': "
        f"disruption_type='{d.disruption_type}', severity='{d.severity}', studio_id='{case.studio_id or 'global'}'. "
        f"Call query_disruption_history with template_id='strategy_performance'."
    )
    user_message = types.Content(
        role="user",
        parts=[types.Part(text=prompt_text)],
    )

    collected_evidence_rows: List[EvidenceRow] = []
    collected_narrative: str = ""
    collected_mcp_calls: List[MCPCall] = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_response:
                    fr_dict = part.function_response.response or {}
                    if isinstance(fr_dict, dict) and "evidence_rows" in fr_dict:
                        collected_evidence_rows = [
                            EvidenceRow(**row_dict) for row_dict in fr_dict.get("evidence_rows", [])
                        ]
                        sql = fr_dict.get("sql", "")
                        tool_name = fr_dict.get("tool", "run_query")
                        latency = fr_dict.get("latency_ms", 0)
                        rows_cnt = fr_dict.get("rows_returned", len(collected_evidence_rows))
                        mcp_call = MCPCall(
                            agent="budget_sentinel",
                            tool=tool_name,
                            template_id="strategy_performance",
                            sql=sql,
                            rows_returned=rows_cnt,
                            latency_ms=latency,
                            status="success",
                        )
                        collected_mcp_calls.append(mcp_call)
                if part.text:
                    collected_narrative += part.text

    # If ADK run returned evidence, build structured result
    if collected_evidence_rows:
        best = collected_evidence_rows[0]
        worst = collected_evidence_rows[-1]
        narrative = (
            f"Across {sum(e.past_cases for e in collected_evidence_rows):,} similar past cases, "
            f"'{best.resolution_strategy}' averaged ${best.avg_cost_overrun_usd:,.0f} overrun and "
            f"{best.avg_delay_hours:.1f}h delay, versus ${worst.avg_cost_overrun_usd:,.0f} and "
            f"{worst.avg_delay_hours:.1f}h for '{worst.resolution_strategy}'. "
            f"Historical data favors '{best.resolution_strategy}'."
        )
    else:
        narrative = collected_narrative.strip()

    return BudgetSentinelResult(
        studio_id=case.studio_id or "global",
        evidence_cohort="global",
        evidence_footnote=f"industry baseline (n={sum(e.past_cases for e in collected_evidence_rows):,})" if collected_evidence_rows else "",
        evidence_narrative=narrative,
        evidence_rows=collected_evidence_rows,
        mcp_calls=collected_mcp_calls,
    )


# ---------------------------------------------------------------------------
# Orchestrator Compatibility Entry Point
# ---------------------------------------------------------------------------
async def run(case: CaseState) -> None:
    """Standard entrypoint called by the Orchestrator."""
    d = case.disruption
    primary_evidence: List[EvidenceRow] = []

    async def execute_query(template_id: str, params: Dict[str, Any]) -> List[EvidenceRow]:
        sql = build_query(template_id, params)
        call = MCPCall(agent="budget_sentinel", template_id=template_id, sql=sql)
        try:
            result = await mcp_run_query(sql)
            call.tool = result["tool"]
            call.rows_returned = len(result["rows"])
            call.latency_ms = result["latency_ms"]
            case.mcp_calls.append(call)
            return _rows_to_evidence(result["columns"], result["rows"])
        except Exception as exc:
            call.status = "error"
            call.error = str(exc)[:300]
            case.mcp_calls.append(call)
            logger.warning("MCP query %s failed: %s", template_id, exc)
            return []

    # 1. Resolve studio_id from production bundle
    studio_id = "global"
    try:
        bundle = await clickhouse_client.fetch_production_bundle(case.production_id)
        if bundle and bundle.get("production"):
            studio_id = bundle["production"].get("studio_id", "global") or "global"
    except Exception as exc:
        logger.warning("Failed to fetch studio_id for %s: %s", case.production_id, exc)

    case.studio_id = studio_id
    now = time.time()

    if studio_id != "global":
        # Ingested Studio Tenant: fetch studio cohort and global cohort for blending
        ev_studio = await execute_query(
            "studio_strategy_performance",
            {"disruption_type": d.disruption_type, "studio_id": studio_id},
        )
        ev_global = await execute_query(
            "strategy_performance", {"disruption_type": d.disruption_type}
        )

        n_studio = sum(e.past_cases for e in ev_studio)
        n_global = sum(e.past_cases for e in ev_global)

        if n_studio == 0:
            primary_evidence = ev_global
            case.evidence_footnote = f"industry baseline (n={n_global:,})"
            case.evidence_cohort = "global"
        elif n_studio < 200:
            # Cold-start blending formula: w = n_studio / 200.0
            w = n_studio / 200.0
            global_by_strat = {e.resolution_strategy: e for e in ev_global}
            studio_by_strat = {e.resolution_strategy: e for e in ev_studio}
            all_strats = list(dict.fromkeys(list(studio_by_strat.keys()) + list(global_by_strat.keys())))
            blended = []

            for st in all_strats:
                s_row = studio_by_strat.get(st)
                g_row = global_by_strat.get(st)
                if s_row and g_row:
                    blended.append(
                        EvidenceRow(
                            resolution_strategy=st,
                            avg_cost_overrun_usd=float(
                                round((w * s_row.avg_cost_overrun_usd) + ((1.0 - w) * g_row.avg_cost_overrun_usd))
                            ),
                            avg_delay_hours=float(
                                round((w * s_row.avg_delay_hours) + ((1.0 - w) * g_row.avg_delay_hours), 1)
                            ),
                            avg_continuity_risk=float(
                                round((w * s_row.avg_continuity_risk) + ((1.0 - w) * g_row.avg_continuity_risk), 2)
                            ),
                            avg_compliance_risk=float(
                                round((w * s_row.avg_compliance_risk) + ((1.0 - w) * g_row.avg_compliance_risk), 2)
                            ),
                            avg_success_score=float(
                                round((w * s_row.avg_success_score) + ((1.0 - w) * g_row.avg_success_score), 2)
                            ),
                            past_cases=s_row.past_cases,
                            studio_id=studio_id,
                            is_blended=True,
                            blend_weight=float(round(w, 3)),
                            footnote=f"blended with industry baseline (studio n={n_studio}, industry n={n_global:,})",
                        )
                    )
                elif s_row:
                    blended.append(s_row)
                elif g_row:
                    blended.append(g_row)

            blended.sort(key=lambda x: x.avg_cost_overrun_usd)
            primary_evidence = blended
            case.evidence_footnote = f"blended with industry baseline (studio n={n_studio}, industry n={n_global:,})"
            case.evidence_cohort = f"studio_blended ({studio_id})"
        else:
            # 100% studio cohort
            primary_evidence = ev_studio
            case.evidence_footnote = f"100% studio cohort (n={n_studio:,})"
            case.evidence_cohort = f"studio ({studio_id})"
    else:
        # Standard Global Baseline with caching
        cache_key = (d.disruption_type, d.severity)
        cached_entry = _EVIDENCE_CACHE.get(cache_key)
        if cached_entry and (now - cached_entry[0]) < _CACHE_TTL_SECONDS:
            live_evidence = await execute_query(
                "strategy_performance", {"disruption_type": d.disruption_type}
            )
            primary_evidence = live_evidence or cached_entry[1]
        else:
            ev_all = await execute_query(
                "strategy_performance", {"disruption_type": d.disruption_type}
            )
            ev_sev = await execute_query(
                "strategy_performance_by_severity",
                {"disruption_type": d.disruption_type, "severity": d.severity},
            )
            primary_evidence = ev_all or ev_sev
            if primary_evidence:
                _EVIDENCE_CACHE[cache_key] = (now, primary_evidence)

        case.evidence_footnote = f"industry baseline (n={sum(e.past_cases for e in primary_evidence):,})"
        case.evidence_cohort = "global"

    case.evidence_rows = primary_evidence

    # Build evidence brief narrative
    if primary_evidence:
        best = primary_evidence[0]
        worst = primary_evidence[-1]
        cohort_note = f" [{case.evidence_footnote}]" if case.evidence_footnote else ""
        case.evidence_narrative = (
            f"Across {sum(e.past_cases for e in primary_evidence):,} similar past cases{cohort_note}, "
            f"'{best.resolution_strategy}' averaged ${best.avg_cost_overrun_usd:,.0f} overrun and "
            f"{best.avg_delay_hours:.1f}h delay, versus ${worst.avg_cost_overrun_usd:,.0f} and "
            f"{worst.avg_delay_hours:.1f}h for '{worst.resolution_strategy}'. "
            f"Historical data favors '{best.resolution_strategy}'."
        )


async def calibrate_option_economics(
    case: CaseState, options: List[RecoveryOption], bundle: Dict[str, Any]
) -> None:
    """Bottom-up rate card cost estimation + live external signals + 70/30 calibration."""
    tier = bundle["production"].get("tier", "mid")
    rate_cards = await clickhouse_client.fetch_rate_cards(tier)

    crew_day_rate = rate_cards.get("crew_day", 150000)
    camera_day_rate = rate_cards.get("camera_package_day", 2000)
    stage_day_rate = rate_cards.get("stage_rental_day", 10000)
    permit_day_rate = rate_cards.get("permit_day", 1500)

    loc_dict = {
        l["location_id"]: {
            "name": l["name"],
            "fee": int(l.get("daily_fee_usd", 5000) or 5000),
            "currency": l.get("currency_code", "USD") or "USD",
            "lat": float(l.get("latitude", 0.0) or 0.0),
            "lon": float(l.get("longitude", 0.0) or 0.0),
            "type": l.get("location_type", "interior"),
            "country_code": l.get("country_code", "US") or "US",
            "country_mult": float(l.get("country_mult", 1.0) or 1.0),
            "city_tier": l.get("city_tier", "tier_1") or "tier_1",
            "geo_mult": float(l.get("geo_mult", 1.0) or 1.0),
        }
        for l in bundle["locations"]
    }

    cast_dict = {
        c["cast_id"]: {
            "name": c["name"],
            "rate": int(c.get("day_rate_usd", 1500) or 1500),
            "role": c.get("role_type", "supporting"),
        }
        for c in bundle["cast_members"]
    }

    evidence_by_strat = {e.resolution_strategy: e for e in case.evidence_rows}
    overall_hist_cost = (
        sum(e.avg_cost_overrun_usd for e in case.evidence_rows) / max(1, len(case.evidence_rows))
        if case.evidence_rows else 25000.0
    )

    for opt in options:
        lines: List[CostLineItem] = []
        fx_applied = 1.0
        fx_summary = ""
        weather_risk_score = 0
        weather_summary = ""

        # Identify primary location & affected cast
        target_loc_id = ""
        for ch in opt.scene_changes:
            if ch.to_location:
                target_loc_id = ch.to_location
                break
        if not target_loc_id and bundle["locations"]:
            target_loc_id = bundle["locations"][0]["location_id"]

        loc_info = loc_dict.get(target_loc_id, {})
        loc_curr = loc_info.get("currency", "USD")
        loc_lat = loc_info.get("lat", 0.0)
        loc_lon = loc_info.get("lon", 0.0)
        loc_fee = loc_info.get("fee", 5000)
        is_outdoor = loc_info.get("type", "interior") == "exterior"
        loc_geo_mult = float(loc_info.get("geo_mult", 1.0) or 1.0)
        loc_country = loc_info.get("country_code", "US") or "US"
        loc_tier = loc_info.get("city_tier", "tier_1") or "tier_1"
        tier_label = loc_tier.replace("_", "-")

        # Geo-adjusted operational baseline rates for this location
        adj_crew_rate = int(round(crew_day_rate * loc_geo_mult))
        adj_stage_rate = int(round(stage_day_rate * loc_geo_mult))
        adj_permit_rate = int(round(permit_day_rate * loc_geo_mult))

        # 1. Fetch live signals in parallel (Weather & FX)
        w_task = get_weather_risk(loc_lat, loc_lon)
        fx_task = get_exchange_rate(loc_curr, "USD")
        w_res, fx_res = await asyncio.gather(w_task, fx_task)

        weather_risk_score = w_res["risk_score"]
        weather_summary = f"{w_res['rain_risk_pct']}% historical rain risk — {w_res['source']}"
        opt.weather_risk = weather_risk_score
        opt.weather_summary = weather_summary

        if loc_curr != "USD":
            fx_applied = fx_res["rate"]
            fx_summary = f"Applied {fx_applied:.2f} {loc_curr}/USD — {fx_res['source']}"
            opt.fx_summary = fx_summary

        # Add transparent Geo Adjustment breakdown line
        lines.append(
            CostLineItem(
                line=f"Geo adjustment x{loc_geo_mult:.2f} ({loc_country}, {tier_label})",
                amount_usd=0,
                source="World Bank GDP PPP (CC-BY 4.0) + OSM Population Tier",
            )
        )

        # 2. Compute bottom-up line items based on strategy
        strat = opt.strategy
        if strat == "shoot_cover_scenes":
            crew_cost = int(adj_crew_rate * 0.08)
            stage_hold = int(adj_stage_rate * 0.4)
            lines.append(CostLineItem(line="Set Transition & Crew Staging (0.08 crew day)", amount_usd=crew_cost, source="Rate card: crew_day (geo-scaled)"))
            lines.append(CostLineItem(line="Soundstage Facility Holding & Power", amount_usd=stage_hold, source="Rate card: stage_rental_day (geo-scaled)"))

            # Cast hold for affected principal
            if case.disruption.affected_cast_id:
                c_rate = cast_dict.get(case.disruption.affected_cast_id, {}).get("rate", 1500)
                lines.append(CostLineItem(line=f"Principal Cast Standby Hold ({case.disruption.affected_cast_id})", amount_usd=c_rate, source="Cast day rate"))

        elif strat in ("swap_locations", "swap_shoot_days"):
            crew_cost = int(adj_crew_rate * 0.15)
            lines.append(CostLineItem(line="Company Transit & Rigging Turnaround (0.15 crew day)", amount_usd=crew_cost, source="Rate card: crew_day (geo-scaled)"))

            # Location daily fee with FX conversion and geo multiplier
            converted_fee = int(round(loc_fee * fx_applied * loc_geo_mult))
            loc_label = f"Target Location Daily Fee ({loc_info.get('name', target_loc_id)})"
            if loc_curr != "USD":
                loc_label += f" [{loc_curr} {loc_fee:,} @ {fx_applied:.2f} FX × {loc_geo_mult:.2f} Geo]"
            else:
                loc_label += f" [${loc_fee:,} × {loc_geo_mult:.2f} Geo]"
            lines.append(CostLineItem(line=loc_label, amount_usd=converted_fee, source=f"Location fee & {fx_res['source']}"))

            # Outdoor weather contingency buffer
            if is_outdoor and weather_risk_score > 35:
                weather_buff = int(adj_crew_rate * 0.05)
                lines.append(CostLineItem(line=f"Weather Contingency Buffer ({w_res['rain_risk_pct']}% rain risk)", amount_usd=weather_buff, source="Open-Meteo risk model"))

        elif strat == "move_to_later_day":
            crew_cost = int(adj_crew_rate * 0.22)
            cam_cost = int(camera_day_rate * 1.0)
            lines.append(CostLineItem(line="Schedule Day Push & Extended Crew Hours (0.22 crew day)", amount_usd=crew_cost, source="Rate card: crew_day (geo-scaled)"))
            lines.append(CostLineItem(line="Camera Package & Grip Gear Day Extension", amount_usd=cam_cost, source="Rate card: camera_package_day"))
            lines.append(CostLineItem(line="Municipal Permit Rescheduling Fee", amount_usd=adj_permit_rate, source="Rate card: permit_day (geo-scaled)"))

        elif strat in ("wait_for_actor", "standby"):
            crew_cost = int(adj_crew_rate * 0.35)
            lines.append(CostLineItem(line="Idle Full Unit Standby Burn (0.35 crew day)", amount_usd=crew_cost, source="Rate card: crew_day (geo-scaled)"))
            lines.append(CostLineItem(line="Location Standby Holding Fee", amount_usd=int(loc_fee * fx_applied * loc_geo_mult), source="Location rate (geo-scaled)"))

        else:  # split_scene, recast_scene, etc.
            crew_cost = int(adj_crew_rate * 0.12)
            lines.append(CostLineItem(line="Specialist Unit Setup & Additional Slates (0.12 crew day)", amount_usd=crew_cost, source="Rate card: crew_day (geo-scaled)"))
            lines.append(CostLineItem(line="Production Contingency & Inserts Reserve", amount_usd=int(loc_fee * 0.5 * loc_geo_mult), source="Rate card benchmark"))

        bottom_up_total = sum(l.amount_usd for l in lines)

        # 3. Calibrate with ClickHouse historical evidence (70% bottom-up + 30% historical)
        hist_ev = evidence_by_strat.get(strat)
        hist_cost = hist_ev.avg_cost_overrun_usd if hist_ev else overall_hist_cost
        sample_size = hist_ev.past_cases if hist_ev else sum(e.past_cases for e in case.evidence_rows)

        final_cost = int(round(0.70 * bottom_up_total + 0.30 * hist_cost, -2))
        final_cost = max(500, final_cost)

        opt.estimated_cost_usd = final_cost
        opt.cost_breakdown = CostBreakdown(
            total_usd=final_cost,
            currency="USD",
            breakdown=lines,
            fx_rate_applied=fx_applied,
            weather_risk=weather_risk_score,
            transit_distance_miles=opt.transit_distance_miles,
            historical_sample_size=sample_size,
            calibration_method="70% bottom-up rate card + 30% ClickHouse historical evidence",
        )
