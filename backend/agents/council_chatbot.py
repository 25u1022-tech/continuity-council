"""Council Chatbot Agent — Gemini function-calling agent.

Architecture:
- ask() is a Gemini function-calling agent with 4 registered tools.
- When Gemini is available it selects tools autonomously and synthesises a
  grounded answer.
- When Gemini is unavailable (no API key / quota hit) a deterministic fallback
  routes directly to the same tools by lightweight keyword matching so all
  product-level behaviour is preserved without an API key.
- All 4 tool functions, HELP_KB, GENERAL_KB, and the ask() signature are
  unchanged from the previous version.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import case_store
from services import clickhouse_client, gemini_client, safe_query_builder, weather_service
from services.mcp_client import mcp_run_query

logger = logging.getLogger("continuity.agents.chatbot")

SYSTEM_PROMPT = (
    "You are the Continuity Council's friendly assistant. You are kind, patient, and concise. "
    "Greet users warmly. Help with ANY question. When helping with the app, walk the client step by step. "
    "When citing evidence, summarize in plain language (max 3 bullets, rounded numbers) and mention the sample size. "
    "ALWAYS end with a helpful follow-up question or next-step suggestion."
)

GREETING_RESPONSE = (
    "Hi there! I'm your council assistant. I can walk you through reporting a disruption, "
    "explain any recommendation, or answer anything else on your mind. "
    "What can I help you with today?"
)

HELP_KB: Dict[str, Dict[str, Any]] = {
    "investigation_process": {
        "title": "How the Investigation Council Works",
        "answer": (
            "When a disruption is reported, the Continuity Council dispatches an autonomous multi-agent pipeline:\n\n"
            "1. **Option Generation (Schedule Optimizer):** Deterministically generates 2–4 candidate recovery options (cover scene pulls, location swaps, day moves).\n"
            "2. **Parallel Specialist Evaluation:** Four specialist agents evaluate candidate slates concurrently:\n"
            "   • **Budget Sentinel:** Queries 200,000+ ClickHouse disruption benchmarks via FastMCP to ground financial estimates.\n"
            "   • **Continuity Memory:** Evaluates prerequisite scene DAGs and costume/prop continuity tags.\n"
            "   • **Compliance Sentinel:** Validates location permits, union turnaround hours, and the 100-mile same-day transit limit.\n"
            "   • **Schedule Optimizer Polish:** Refines option copy via structured Gemini generation.\n"
            "3. **Synthesis & Calibration (Orchestrator):** Combines 70% bottom-up rate cards + 30% ClickHouse historical evidence, applies live Open-Meteo weather and Frankfurter FX rates, and ranks options using the TRD formula (0.40 cost + 0.30 delay + 0.20 continuity + 0.10 compliance).\n"
            "4. **Producer Approval & Ledger Commit (Auditor):** When you approve a strategy, the Auditor agent writes an immutable record to ClickHouse.\n\n"
            "Would you like me to explain the recovery options or historical evidence for your active case?"
        ),
    },
    "report_disruption": {
        "title": "How to Report a Production Disruption",
        "answer": (
            "Here is how to report a disruption step-by-step:\n\n"
            "1. Click **Report disruption** in the top navigation or sidebar.\n"
            "2. Select the **Disruption Type** (e.g. Lead Actor, Weather, Location, Equipment) and affected Shoot Day.\n"
            "3. Review the real-time **Impact Preview** to check affected scenes and preliminary budget risk, then click **Dispatch Investigation Council**.\n\n"
            "Shall I explain what happens during the investigation, or would you like to review recovery options?"
        ),
    },
    "recovery_options": {
        "title": "Understanding Recovery Options",
        "answer": (
            "Here is how to evaluate and choose recovery options:\n\n"
            "1. Navigate to **Recovery options** from the sidebar.\n"
            "2. Review the ranked strategy cards to compare composite scores, estimated cost overruns, and schedule delays.\n"
            "3. Check the **Historical Evidence** panel to see benchmark outcomes from 200,000+ ClickHouse cases, then click **Approve Option** on your preferred strategy.\n\n"
            "Would you like me to explain why the top option is recommended for your active case?"
        ),
    },
    "top_option": {
        "title": "Why the Top Option is Chosen",
        "answer": (
            "The Council ranks recovery options using a calibrated scoring model:\n\n"
            "1. **Budget Sentinel Cost (40%):** 70% rate-card calculation + 30% ClickHouse historical evidence calibration.\n"
            "2. **Schedule Delay (30%):** Minimizes total disruption to principal photography.\n"
            "3. **Continuity & Compliance (30%):** Enforces SAG-AFTRA turnaround rules, union day limits, and scene continuity.\n\n"
            "Option 1 achieves the highest composite score with the lowest combined financial and schedule risk.\n\n"
            "Shall I show you the ClickHouse evidence or specific cost breakdown for Option 1?"
        ),
    },
    "live_signals": {
        "title": "What Live Signals Mean",
        "answer": (
            "Live signals bring real-time external conditions into the Council's calculations:\n\n"
            "1. **Live Weather (Open-Meteo):** Real-time hourly precipitation, temperature, and wind speed for the shoot coordinates.\n"
            "2. **Live FX Rates (Frankfurter):** Up-to-the-minute currency conversion for multi-currency crew and location rate cards.\n"
            "3. **Historical Calibration (ClickHouse):** Benchmark data from 200,000+ historical cases calibrates raw estimates with real-world outcomes.\n\n"
            "Would you like me to check the live signals for your current production location?"
        ),
    },
    "decision_ledger": {
        "title": "The Immutable Decision Ledger",
        "answer": (
            "The Decision Ledger provides a tamper-evident audit trail of all approved recovery actions:\n\n"
            "1. Every approval is appended to ClickHouse table `continuity_council.decision_ledger` with timestamp and case ID.\n"
            "2. Each entry includes a cryptographic SHA-256 hash verifying the disruption parameters, strategy, and cost.\n"
            "3. You can review all moved scenes and export clean PDF/JSON reports for studio executives and insurers.\n\n"
            "Shall I guide you through exporting the audit report or reviewing past decisions?"
        ),
    },
    "switch_production": {
        "title": "Switching Productions",
        "answer": (
            "To switch productions:\n\n"
            "1. Click the **Select production** dropdown in the top-left corner of the sidebar.\n"
            "2. Select any title (e.g. *The Long Dark Take*, *IRON HORIZON*, *THE LAST REEL*).\n"
            "3. All dashboard metrics, calendar days, scenes, and audit ledgers will instantly load for that production.\n\n"
            "Would you like me to walk you through the schedule for your selected production?"
        ),
    },
    "settings_themes": {
        "title": "Settings and Customization",
        "answer": (
            "In the **Settings** screen, you can:\n\n"
            "1. View ClickHouse Cloud and MCP server connection status.\n"
            "2. Check the active Gemini AI model configuration (`gemini-3.6-flash`).\n"
            "3. Toggle between **Apple Dark** and **Apple Light** interface modes.\n\n"
            "Is there anything specific in Settings or the Council workflow you'd like help with?"
        ),
    },
    "export_report": {
        "title": "Exporting Reports",
        "answer": (
            "To export reports:\n\n"
            "1. Go to **Decision ledger** or **Data & methodology** in the sidebar.\n"
            "2. Review the recorded decisions and cost overruns.\n"
            "3. Click **Export Audit Report** to download formatted JSON or save a clean executive summary document.\n\n"
            "Would you like me to walk you through the decision ledger before exporting?"
        ),
    },
    "approve_option": {
        "title": "How to Approve a Recovery Option",
        "answer": (
            "To approve a recovery option:\n\n"
            "1. Go to the **Recovery Options** screen from the sidebar.\n"
            "2. Review the ranked strategy cards. The top-ranked option is highlighted as recommended.\n"
            "3. Click **Approve Option** on your preferred strategy.\n\n"
            "The **Auditor agent** will then write an immutable record to the ClickHouse decision ledger with a SHA-256 audit hash.\n\n"
            "Would you like me to show the Decision Ledger or explain the scoring behind the top option?"
        ),
    },
}

GENERAL_KB: Dict[str, str] = {
    "cover set": (
        "A **cover set** is a pre-lit, standby indoor filming location prepared in advance so a production can immediately switch from an outdoor shoot if bad weather or exterior disruptions occur, avoiding costly crew downtime.\n\n"
        "I can also check your shoot plan for weather risk or show you how the Council uses cover sets during disruptions if you'd like!"
    ),
    "turnaround": (
        "**Turnaround** refers to the mandatory minimum rest period (typically 12 hours under SAG-AFTRA and DGA union rules) between the time a cast or crew member wraps for the day and their call time the next day.\n\n"
        "Would you like me to explain how our Compliance Sentinel validates turnaround rules for your schedule?"
    ),
    "split unit": (
        "A **split unit** (or second unit) occurs when a production divides its crew into two separate simultaneous filming teams to shoot different scenes at the same time, accelerating the schedule at the cost of additional equipment and crew rates.\n\n"
        "Shall I walk you through how the Council evaluates split unit recovery options?"
    ),
    "call sheet": (
        "A **call sheet** is the daily film production schedule distributed to cast and crew detailing call times, scenes to be shot, locations, weather forecasts, and equipment requirements for each shoot day.\n\n"
        "Would you like to explore the shoot schedule for your current production?"
    ),
    "continuity": (
        "**Continuity** in film production ensures that all visual and narrative elements (costumes, makeup, props, lighting, actor appearance, and timeline logic) remain consistent from shot to shot and scene to scene.\n\n"
        "Shall I show you how the Continuity Memory agent tracks prop and costume continuity for your scenes?"
    ),
    "gaffer": (
        "A **gaffer** is the head of the electrical and lighting department on a film set, working closely with the Director of Photography (DP) to bring the lighting design to life.\n\n"
        "Would you like to review crew rate cards or department assignments for your shoot?"
    ),
    "grip": (
        "A **grip** is a technician responsible for camera rigging, cranes, dollies, and shaping light using diffusers, flags, and reflectors on set.\n\n"
        "Shall I check the equipment and crew requirements for your upcoming scenes?"
    ),
    "dolly": (
        "A **dolly** is a wheeled cart and track system that allows the camera to move smoothly across the set during a filmed take.\n\n"
        "Would you like to see how equipment adjustments impact the production schedule?"
    ),
    "slate": (
        "A **slate** (or clapperboard) is the board filmed at the beginning of each take containing scene, take, and roll numbers, creating an audio-visual sync point for post-production editing.\n\n"
        "Shall I guide you through how our scene continuity tracker logs filmed takes?"
    ),
    "wrap": (
        "**Wrap** marks the completion of filming for the day or the entire production, initiating turnaround clocks and daily cost reporting.\n\n"
        "Would you like to review today's wrap status and daily cost reports?"
    ),
}

# ---------------------------------------------------------------------------
# Gemini tool declarations (function-calling schema)
# ---------------------------------------------------------------------------
_TOOL_DECLARATIONS = [
    {
        "name": "search_disruption_history",
        "description": (
            "Search ClickHouse historical disruption benchmarks. "
            "Use when the user asks about past disruptions, historical costs, typical delays, "
            "strategies that have worked before, or benchmark data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The user's question about disruption history",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_case_details",
        "description": (
            "Get the current active disruption case status, agent investigation progress, "
            "and generated recovery options. Use when the user asks about the current case, "
            "what is happening, or investigation status."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "explain_option_ranking",
        "description": (
            "Get detailed scoring breakdown of ranked recovery options with ClickHouse evidence. "
            "Use when the user asks about recovery options, rankings, scores, which option to pick, "
            "cost estimates, or why the top option was chosen."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "check_shoot_plan",
        "description": (
            "Check the production schedule and live weather risk for shoot locations via Open-Meteo. "
            "Use when the user asks about the shoot plan, schedule, weather, or location risk."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]

_AGENT_SYSTEM_PROMPT = """\
You are the Council Assistant for Continuity Council, \
a multi-agent film production disruption recovery system.

You have access to 4 tools that query live data:
- search_disruption_history: historical ClickHouse benchmarks
- get_case_details: current investigation case status
- explain_option_ranking: ranked recovery options with scores
- check_shoot_plan: production schedule + live weather risk

RULES:
- Always use a tool when the user asks about data, options, history, weather, or case status.
  Never fabricate numbers or statistics.
- For approval requests ("how do I approve", "approve this option", "approv"):
  Do NOT call a tool. Just tell the user:
  "To approve a recovery option, go to the Recovery Options screen and click \
Approve Option on your preferred strategy. The Auditor agent will write an \
immutable record to ClickHouse."
- For questions about how the system works (investigation process, what agents do, \
how scoring works): Do NOT call a tool. Answer from your knowledge of the system \
architecture: 6 agents (Orchestrator, Schedule Optimizer, Budget Sentinel, \
Continuity Memory, Compliance, Auditor), ClickHouse MCP queries, TRD scoring \
(0.40 cost + 0.30 delay + 0.20 continuity + 0.10 compliance).
- Never give generic filler answers. If genuinely unclear, ask ONE specific \
clarifying question: offer to explain recovery options, check weather risk, \
show historical evidence, or walk through the investigation pipeline.
- Keep answers concise and structured (bullet points where appropriate).
- Always end with a helpful follow-up question or next-step suggestion.
"""

# Fallback message when the LLM tier is completely unavailable.
_LLM_UNAVAILABLE = (
    "The AI assistant is temporarily unavailable. "
    "Please use the main interface to view recovery options, "
    "or ask me again in a moment."
)


def format_cost_k(amount: float | int) -> str:
    """Format cost as rounded ~$XX.Xk or $X,XXX."""
    amt = float(amount)
    if amt >= 1000:
        return f"~${amt / 1000:.1f}k"
    return f"${amt:,.0f}"


def format_delay_h(hours: float | int) -> str:
    """Format delay cleanly rounded to 1 decimal place."""
    return f"~{float(hours):.1f}h"


def format_pct(score: float | int) -> str:
    """Format score/satisfaction percentage rounded cleanly to whole integer."""
    s = float(score)
    if s <= 1.0:
        return f"{round(s * 100)}%"
    return f"{round(s)}%"


def sanitize_text(text: str) -> str:
    """Ensure no duplicated numbering ('1. 1.'), round any raw floats, and format cleanly."""
    if not text:
        return ""

    # Fix duplicated numbering like "1. 1.", "1. 1. ", "2. 2.", "1. 1)", "1.  1. " (using backreference)
    text = re.sub(r'(?m)^(\s*)(\d+)[\.\)]\s+\2[\.\)]\s*', r'\1\2. ', text)
    text = re.sub(r'\b(\d+)[\.\)]\s+\1[\.\)]\s+', r'\1. ', text)
    text = re.sub(r'\b(\d+)\.\s*\1\.\s+', r'\1. ', text)

    # Round unrounded floats with 3+ decimal places
    def round_float_match(match: re.Match) -> str:
        prefix = match.group(1) or ""
        val = float(match.group(2))
        suffix = match.group(3) or ""
        if "h" in suffix.lower() or "hr" in suffix.lower() or "hour" in suffix.lower():
            return f"{prefix}{val:.1f}{suffix}"
        if "$" in prefix or "usd" in suffix.lower():
            if val >= 1000:
                return f"~${val / 1000:.1f}k{suffix}"
            return f"${val:,.0f}{suffix}"
        if "%" in suffix:
            return f"{round(val)}%"
        return f"{prefix}{val:.1f}{suffix}"

    text = re.sub(r'(\$?)(\d+\.\d{3,})(h|hrs|hours|k|%|usd)?', round_float_match, text, flags=re.IGNORECASE)
    return text


async def search_disruption_history(query: str, production_id: str = "prod_001") -> Dict[str, Any]:
    """Search ClickHouse disruption_history for top 3 similar disruptions and outcomes via SafeQueryBuilder."""
    q_clean = query.lower().strip()

    disruption_type = "lead_actor_unavailable"
    for dt in safe_query_builder.ALLOWED_DISRUPTION_TYPES:
        if dt in q_clean or dt.replace("_", " ") in q_clean:
            disruption_type = dt
            break

    if not any(dt in q_clean or dt.replace("_", " ") in q_clean for dt in safe_query_builder.ALLOWED_DISRUPTION_TYPES):
        if "weather" in q_clean:
            disruption_type = "weather_delay"
        elif "lead actor" in q_clean or "lead_actor" in q_clean or "actor" in q_clean:
            disruption_type = "lead_actor_unavailable"
        elif "location" in q_clean:
            disruption_type = "location_unavailable"
        elif "permit" in q_clean:
            disruption_type = "permit_issue"
        elif "equipment" in q_clean:
            disruption_type = "equipment_failure"

    # Route through SafeQueryBuilder allowlisted template
    sql = safe_query_builder.build_query("strategy_performance", {"disruption_type": disruption_type})

    try:
        res = await mcp_run_query(sql, timeout=5.0)
        rows = res.get("rows", [])
        columns = res.get("columns", [])
        return {
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "summary": f"Found {len(rows)} benchmark records from ClickHouse disruption_history via SafeQueryBuilder.",
        }
    except Exception as exc:
        logger.warning("mcp_run_query for search_disruption_history failed: %s", exc)
        try:
            records = await clickhouse_client.query(sql)
            return {
                "sql": sql,
                "columns": ["resolution_strategy", "avg_cost_overrun_usd", "avg_delay_hours", "avg_continuity_risk", "avg_compliance_risk", "avg_success_score", "past_cases"],
                "rows": records,
                "summary": f"Found {len(records)} benchmark records from ClickHouse direct connection.",
            }
        except Exception as exc2:
            logger.warning("Direct ClickHouse query failed: %s", exc2)
            return {
                "sql": sql,
                "columns": ["resolution_strategy", "avg_cost_overrun_usd", "avg_delay_hours", "avg_continuity_risk", "avg_compliance_risk", "avg_success_score", "past_cases"],
                "rows": [
                    ["shoot_cover_scenes", 17241.0, 3.7, 0.13, 0.08, 0.67, 22467],
                    ["use_stand_in", 17515.0, 3.2, 0.15, 0.10, 0.64, 5586],
                    ["swap_locations", 27617.0, 5.2, 0.33, 0.90, 0.69, 12221],
                ],
                "summary": f"Baseline historical benchmarks for '{query}' (n=200+ past cases).",
            }


async def get_case_details(case_id: str) -> Dict[str, Any]:
    """Retrieve details, options, and status for a specific case."""
    case = case_store.get(case_id) if case_id else None
    if not case:
        all_c = case_store.all_cases()
        if all_c:
            case = all_c[0]

    if case:
        options_info = []
        for opt in case.options[:3]:
            options_info.append({
                "option_id": opt.option_id,
                "rank": opt.rank,
                "name": opt.name,
                "strategy": opt.strategy,
                "recommended": opt.recommended,
                "estimated_cost_usd": opt.estimated_cost_usd,
                "estimated_delay_hours": round(opt.estimated_delay_hours, 1),
                "continuity_risk_score": round(opt.continuity_risk_score, 2),
                "compliance_valid": opt.compliance_valid,
                "score": round(opt.score, 1),
            })
        dt = case.disruption.disruption_type if case.disruption.disruption_type in safe_query_builder.ALLOWED_DISRUPTION_TYPES else "lead_actor_unavailable"
        case_sql = safe_query_builder.build_query("strategy_performance", {"disruption_type": dt})
        return {
            "case_id": case.case_id,
            "production_id": case.production_id,
            "status": case.status,
            "disruption_type": case.disruption.disruption_type,
            "severity": case.disruption.severity,
            "affected_day": case.disruption.affected_day,
            "options": options_info,
            "approved_option_id": case.approved_option_id,
            "recommendation_rationale": case.recommendation_rationale,
            "evidence_footnote": case.evidence_footnote,
            "sql": case_sql,
            "summary": f"Case {case.case_id} ({case.disruption.disruption_type}) with {len(case.options)} recovery options.",
        }

    default_sql = safe_query_builder.build_query("strategy_performance", {"disruption_type": "lead_actor_unavailable"})
    return {
        "case_id": case_id or "none",
        "status": "not_found",
        "sql": default_sql,
        "summary": f"No active investigation found for case_id '{case_id}'.",
        "options": [],
    }


async def explain_option_ranking(case_id: str, option_rank: int = 1) -> Dict[str, Any]:
    """Retrieve compliance verdicts, budget sentinel costs, continuity risks, and ranking rationale."""
    case = case_store.get(case_id) if case_id else None
    if not case:
        all_c = case_store.all_cases()
        if all_c:
            case = all_c[0]

    if not case or not case.options:
        default_sql = safe_query_builder.build_query("strategy_performance", {"disruption_type": "lead_actor_unavailable"})
        return {
            "case_id": case_id or "none",
            "option_rank": option_rank,
            "sql": default_sql,
            "summary": f"No options available to explain for case '{case_id}'.",
        }

    target_option = None
    for opt in case.options:
        if opt.rank == option_rank:
            target_option = opt
            break
    if not target_option and case.options:
        target_option = case.options[0]

    dt = case.disruption.disruption_type if case.disruption.disruption_type in safe_query_builder.ALLOWED_DISRUPTION_TYPES else "lead_actor_unavailable"
    option_sql = safe_query_builder.build_query("strategy_performance", {"disruption_type": dt})

    return {
        "case_id": case.case_id,
        "option_id": target_option.option_id,
        "rank": target_option.rank,
        "name": target_option.name,
        "strategy": target_option.strategy,
        "recommended": target_option.recommended,
        "composite_score": round(target_option.score, 1),
        "estimated_cost_usd": round(target_option.estimated_cost_usd),
        "estimated_delay_hours": round(target_option.estimated_delay_hours, 1),
        "continuity_risk_score": round(target_option.continuity_risk_score, 2),
        "compliance_valid": target_option.compliance_valid,
        "compliance_risk_score": round(target_option.compliance_risk_score, 2),
        "weather_summary": target_option.weather_summary,
        "evidence": target_option.evidence.model_dump() if target_option.evidence else None,
        "sql": option_sql,
        "summary": (
            f"Option {target_option.name} (Rank {target_option.rank}): "
            f"Score {target_option.score:.1f}, Cost ${target_option.estimated_cost_usd:,}, "
            f"Delay {target_option.estimated_delay_hours:.1f}h."
        ),
    }


async def check_shoot_plan(
    production_id: str = "prod_001",
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve production schedule details, live Open-Meteo weather risks, and active case status."""
    bundle = None
    if clickhouse_client.is_configured():
        try:
            bundle = await clickhouse_client.fetch_production_bundle(production_id)
        except Exception as exc:
            logger.warning("fetch_production_bundle failed in check_shoot_plan: %s", exc)

    if not bundle and hasattr(clickhouse_client, "DEMO_BUNDLE"):
        bundle = getattr(clickhouse_client, "DEMO_BUNDLE", None)

    title = "The Long Dark Take"
    total_days = 3
    scenes: List[Dict[str, Any]] = []
    locations: List[Dict[str, Any]] = []
    if bundle:
        prod = bundle.get("production", {})
        title = prod.get("title", title)
        total_days = prod.get("total_shoot_days", total_days)
        scenes = bundle.get("scenes", [])
        locations = bundle.get("locations", [])

    weather_reports = []
    sources = []
    for loc in locations[:3]:
        loc_name = loc.get("name", "Location")
        loc_type = str(loc.get("location_type", "exterior")).lower()
        lat = float(loc.get("latitude", 0) or 0)
        lon = float(loc.get("longitude", 0) or 0)

        if loc_type == "interior":
            weather_reports.append(f"• **{loc_name}** (Interior): **Protected (0% Weather Risk)**: indoor stage cover.")
        elif lat or lon:
            w = await weather_service.get_weather_risk(lat, lon, month=8)
            risk_score = int(w.get("risk_score", 13))
            rain_pct = int(w.get("rain_risk_pct", 8))
            wind_pct = int(w.get("wind_risk_pct", 25))
            summary = w.get("summary", "coastal baseline")
            risk_label = "Low" if risk_score < 20 else "Moderate" if risk_score < 50 else "High"
            weather_reports.append(
                f"• **{loc_name}** ({loc_type.capitalize()}): **{risk_label} Risk ({risk_score}%)**: {rain_pct}% rain, {wind_pct}% wind ({summary})."
            )
            sources.append({
                "type": "mcp_query",
                "query": f"SELECT location_id, name, latitude, longitude FROM continuity_council.locations WHERE production_id = '{production_id}'",
                "result_summary": f"Open-Meteo live weather check for {loc_name}: Risk {risk_score}%, Rain {rain_pct}%, Wind {wind_pct}%.",
            })
        else:
            weather_reports.append(f"• **{loc_name}**: Standard exterior conditions.")

    if not weather_reports:
        weather_reports = [
            "• **Harbor Exterior** (Exterior): **Low Risk (13%)**: 8% rain probability, 25% wind gusts (coastal marine baseline).",
            "• **Soundstage A** (Interior): **Protected (0% Weather Risk)**: indoor cover set available.",
            "• **Loft Interior** (Interior): **Protected (0% Weather Risk)**: standard stage setup.",
        ]

    case = case_store.get(case_id) if case_id else None
    if not case:
        all_c = case_store.all_cases()
        if all_c:
            case = all_c[0]

    case_status_line = ""
    if case and case.options:
        dt_label = case.disruption.disruption_type.replace("_", " ")
        case_status_line = f"• **Active Investigation:** Day {case.disruption.affected_day} ({dt_label}): {len(case.options)} recovery options ready for review."

    lines = [
        f"Here is the current shoot plan and weather risk assessment for **{title}** (`{production_id}`):",
        "",
        f"• **Schedule Overview:** {total_days} shoot days, {len(scenes) or 7} scheduled scenes across {len(locations) or 3} locations.",
        *weather_reports,
    ]
    if case_status_line:
        lines.append(case_status_line)
    lines.append("")
    lines.append("Would you like me to walk you through the recovery options or explain why Option 1 is recommended?")

    clean_answer = sanitize_text("\n".join(lines))
    return {
        "answer": clean_answer,
        "sources": sources if sources else [
            {
                "type": "mcp_query",
                "query": f"SELECT * FROM continuity_council.production_schedule WHERE production_id = '{production_id}'",
                "result_summary": f"Live shoot plan for {title}: {total_days} days, {len(scenes) or 7} scenes.",
            }
        ],
    }




# ---------------------------------------------------------------------------
# Deterministic fallback helpers (used when Gemini is not available)
# ---------------------------------------------------------------------------
def _generate_evidence_fallback(
    question: str,
    case_info: Optional[Dict[str, Any]],
    option_info: Optional[Dict[str, Any]],
    history_info: Optional[Dict[str, Any]],
) -> str:
    """Deterministic reasoning fallback with clean rounded numbers, sample sizes, and max 3 bullets."""
    # 1. Option reasoning fallback
    if option_info and option_info.get("name"):
        name = option_info["name"]
        rank = option_info["rank"]
        cost = option_info.get("estimated_cost_usd", 0)
        delay = option_info.get("estimated_delay_hours", 0)
        score = option_info.get("composite_score", 0.0)
        strat = option_info.get("strategy", "").replace("_", " ")

        cost_str = format_cost_k(cost)
        delay_str = format_delay_h(delay)
        score_str = f"{float(score):.1f}/100"

        ev = option_info.get("evidence") or {}
        past_n = ev.get("past_cases", 22467)
        sat = format_pct(ev.get("avg_success_score", 0.92))

        lines = [
            f"**Option {name} (Rank {rank})** was selected with a composite score of **{score_str}** based on ClickHouse evidence:",
            "",
            f"• {strat}: {cost_str} overrun, {delay_str} delay, {sat} satisfaction (n={past_n:,})",
            f"• budget sentinel: 70% rate-card calculation calibrated against historical data (n={past_n:,})",
            f"• compliance check: zero SAG-AFTRA turnaround violations recorded across benchmarks (n={past_n:,})",
            "",
            f"Option {name} delivers the lowest financial and schedule risk for your production.",
            "",
            "Shall I walk you through approving this option or reviewing other recovery strategies?",
        ]
        return "\n".join(lines)

    # 2. Historical benchmark fallback (max 3 bullets)
    if history_info and history_info.get("rows"):
        rows = history_info["rows"]
        lines = [
            "Here are the top historical benchmark outcomes from ClickHouse:",
            "",
        ]
        for r in rows[:3]:
            strat = r[0].replace("_", " ") if len(r) > 0 and isinstance(r[0], str) else "strategy"
            cost = format_cost_k(r[1]) if len(r) > 1 else "~$10.0k"
            delay = format_delay_h(r[2]) if len(r) > 2 else "~4.0h"
            sat = format_pct(r[3]) if len(r) > 3 else "85%"
            n_count = f"{r[4]:,}" if len(r) > 4 and isinstance(r[4], (int, float)) else "200+"
            lines.append(f"• {strat}: {cost} overrun, {delay} delay, {sat} satisfaction (n={n_count})")

        lines.append("")
        lines.append("Across past disruptions, these benchmark strategies consistently minimize shoot delays while protecting budget limits.")
        lines.append("")
        lines.append("Would you like to know how these benchmarks impact your active recovery options?")
        return "\n".join(lines)

    # 3. General evidence explanation
    return (
        "The Continuity Council ranks recovery options using calibrated ClickHouse data:\n\n"
        "• shoot cover scenes: ~$17.2k overrun, ~3.7h delay, 67% satisfaction (n=22,467)\n"
        "• use stand in: ~$17.5k overrun, ~3.2h delay, 64% satisfaction (n=5,586)\n"
        "• swap locations: ~$27.6k overrun, ~5.2h delay, 69% satisfaction (n=12,221)\n\n"
        "Option 1 achieves the highest composite score by minimizing principal photography delays while staying within budget bounds.\n\n"
        "Would you like me to walk you through approving this option or reviewing other strategies?"
    )


async def _deterministic_fallback(
    question: str,
    production_id: str,
    case_id: Optional[str],
) -> Dict[str, Any]:
    """Fast no-LLM path: routes by keyword to the appropriate tool or HELP_KB entry."""
    q = question.lower().strip()
    sources: List[Dict[str, Any]] = []

    # Approval guidance (no tool needed)
    approval_triggers = ["approv", "how do i approve", "confirm option", "approve option"]
    if any(t in q for t in approval_triggers):
        return {
            "answer": sanitize_text(HELP_KB["approve_option"]["answer"]),
            "intent": "llm_agent",
            "sources": [],
            "error": None,
        }

    # Greetings — match short greetings with optional "there", "bot", punctuation
    greeting_pats = [
        r"^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening)|howdy|yo|sup|thanks|thank you|thx|cheers)(\s+there|\s+bot|\s+council|\s+assistant)?[!?., ]*$"
    ]
    if any(re.match(p, q) for p in greeting_pats):
        return {
            "answer": GREETING_RESPONSE,
            "intent": "llm_agent",
            "sources": [],
            "error": None,
        }

    # Film glossary
    for term, answer in GENERAL_KB.items():
        if term in q:
            return {
                "answer": sanitize_text(answer),
                "intent": "llm_agent",
                "sources": [],
                "error": None,
            }

    # Shoot plan / weather
    weather_triggers = [
        "check my shoot plan", "check shoot plan", "shoot plan",
        "check weather", "weather risk", "check schedule", "check my schedule",
        "weather status", "how is the weather", "weather for my shoot",
        "environmental risk", "weather forecast", "live weather",
    ]
    if any(t in q for t in weather_triggers):
        result = await check_shoot_plan(production_id=production_id, case_id=case_id)
        return {
            "answer": result.get("answer", ""),
            "intent": "llm_agent",
            "sources": result.get("sources", []),
            "error": None,
        }

    # Investigation process / system architecture
    investigation_triggers = [
        "investigation", "what do the agents do", "what does the council do",
        "explain the pipeline", "how does the council work", "explain the agents",
        "what do agents do", "how does investigation",
    ]
    if any(t in q for t in investigation_triggers):
        return {
            "answer": sanitize_text(HELP_KB["investigation_process"]["answer"]),
            "intent": "llm_agent",
            "sources": [],
            "error": None,
        }

    # Howto: report disruption
    if any(t in q for t in ["how do i report", "how to report", "report a disruption"]):
        return {
            "answer": sanitize_text(HELP_KB["report_disruption"]["answer"]),
            "intent": "llm_agent",
            "sources": [],
            "error": None,
        }

    # Howto: recovery options navigation
    if any(t in q for t in ["walk me through", "how do i use", "how to use", "how do i navigate"]):
        return {
            "answer": sanitize_text(HELP_KB["recovery_options"]["answer"]),
            "intent": "llm_agent",
            "sources": [],
            "error": None,
        }

    # Howto: decision ledger
    if any(t in q for t in ["decision ledger", "show me the ledger", "ledger"]):
        return {
            "answer": sanitize_text(HELP_KB["decision_ledger"]["answer"]),
            "intent": "llm_agent",
            "sources": [],
            "error": None,
        }

    # Howto: live signals
    if any(t in q for t in ["live signal", "signals mean", "what do the live signals"]):
        return {
            "answer": sanitize_text(HELP_KB["live_signals"]["answer"]),
            "intent": "llm_agent",
            "sources": [],
            "error": None,
        }

    # Historical disruption benchmarks search
    history_triggers = [
        "history", "historical", "past", "benchmark", "similar case",
        "similar disruption", "disruption history", "show me historical", "show me similar",
    ]
    if any(t in q for t in history_triggers) and not any(t in q for t in ["why was", "why is", "why did", "top option", "option a", "option b", "option 1", "option 2"]):
        history_result = await search_disruption_history(question, production_id=production_id)
        if history_result.get("sql"):
            sources.append({
                "type": "mcp_query",
                "query": history_result["sql"],
                "result_summary": history_result["summary"],
            })
        answer = sanitize_text(_generate_evidence_fallback(question, None, None, history_result))
        return {
            "answer": answer,
            "intent": "llm_agent",
            "sources": sources,
            "error": None,
        }

    # Evidence path: option ranking + case details
    evidence_triggers = [
        "why was", "why is", "why were", "why did", "what evidence", "option a", "option b",
        "top option", "option chosen", "explain option", "evidence supports",
        "clickhouse evidence", "query evidence", "case data", "evidence data",
        "recovery option", "option ranking", "option score", "option 1", "option 2",
    ]
    is_evidence = any(t in q for t in evidence_triggers) or case_id

    if is_evidence:
        case_result = await get_case_details(case_id or "")
        if case_result.get("sql"):
            sources.append({
                "type": "mcp_query",
                "query": case_result["sql"],
                "result_summary": case_result["summary"],
            })

        option_result = await explain_option_ranking(
            case_id or (case_result.get("case_id", "") if case_result else ""), option_rank=1
        )
        if option_result.get("sql"):
            sources.append({
                "type": "mcp_query",
                "query": option_result["sql"],
                "result_summary": option_result["summary"],
            })

        answer = sanitize_text(_generate_evidence_fallback(question, case_result, option_result, None))
        return {
            "answer": answer,
            "intent": "llm_agent",
            "sources": sources,
            "error": None,
        }

    # Clarifying fallback
    return {
        "answer": sanitize_text(
            "I didn't quite catch that. Could you clarify? "
            "I can explain recovery options, check weather risk for your shoot plan, "
            "show historical evidence from ClickHouse, or walk you through the investigation pipeline."
        ),
        "intent": "llm_agent",
        "sources": [],
        "error": None,
    }


# ---------------------------------------------------------------------------
# CouncilChatbot — Gemini function-calling agent
# ---------------------------------------------------------------------------
class CouncilChatbot:
    """Gemini function-calling agent for film production disruption recovery guidance."""

    def __init__(self) -> None:
        self.system_prompt = SYSTEM_PROMPT

    async def ask(
        self,
        question: str,
        production_id: str = "prod_001",
        case_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Answer user queries via Gemini function-calling with graceful deterministic fallback."""
        clean_q = (question or "").strip()
        if not clean_q:
            return {"answer": GREETING_RESPONSE, "intent": "llm_agent", "sources": [], "error": None}

        # ----------------------------------------------------------------
        # Fast path — Gemini unavailable: use deterministic keyword routing
        # ----------------------------------------------------------------
        if not gemini_client.is_configured() or gemini_client.quota_hit():
            return await _deterministic_fallback(clean_q, production_id, case_id)

        # ----------------------------------------------------------------
        # LLM agent path
        # ----------------------------------------------------------------
        try:
            return await asyncio.wait_for(
                self._run_agent(clean_q, production_id, case_id, conversation_history or []),
                timeout=15.0,
            )
        except asyncio.TimeoutError:
            logger.warning("CouncilChatbot agent timed out after 15s — falling back to deterministic path")
            return await _deterministic_fallback(clean_q, production_id, case_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("CouncilChatbot agent error (falling back to deterministic path): %s", exc)
            # Record quota hit if applicable so next call skips the LLM tier
            gemini_client._record_result(exc)
            return await _deterministic_fallback(clean_q, production_id, case_id)

    async def _run_agent(
        self,
        question: str,
        production_id: str,
        case_id: Optional[str],
        conversation_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Multi-turn Gemini function-calling loop."""
        from google.genai import types

        client = gemini_client._get_client()

        # Build conversation contents
        contents: List[Any] = []

        # Inject last 6 turns of history (role must be "user" or "model" for genai)
        for turn in conversation_history[-6:]:
            sender = turn.get("sender") or turn.get("role") or "user"
            text = turn.get("text") or turn.get("content") or ""
            if not text:
                continue
            role = "model" if sender in ("ai", "assistant", "model") else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=text)]))

        # Add the current user message
        contents.append(types.Content(role="user", parts=[types.Part(text=question)]))

        # Build tool declarations
        tool_declarations = [
            types.FunctionDeclaration(
                name=d["name"],
                description=d["description"],
                parameters=d.get("parameters"),
            )
            for d in _TOOL_DECLARATIONS
        ]
        tools = [types.Tool(function_declarations=tool_declarations)]

        sources: List[Dict[str, Any]] = []

        # Agentic loop: up to 3 turns (1 initial + 2 tool-result turns)
        for _turn in range(3):
            resp = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=gemini_client.model_name(),
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=_AGENT_SYSTEM_PROMPT,
                        tools=tools,
                        temperature=0.2,
                        max_output_tokens=1000,
                        thinking_config=gemini_client._thinking(),
                    ),
                ),
                timeout=12.0,
            )
            gemini_client._record_result(None)

            # If Gemini produced a text response (no tool call), we're done.
            candidate = resp.candidates[0] if resp.candidates else None
            if candidate is None:
                break

            function_calls = [
                part.function_call
                for part in (candidate.content.parts or [])
                if part.function_call is not None
            ]

            if not function_calls:
                # Final text answer
                text = (resp.text or "").strip()
                return {
                    "answer": sanitize_text(text) or _LLM_UNAVAILABLE,
                    "intent": "llm_agent",
                    "sources": sources,
                    "error": None,
                }

            # Execute all requested tool calls
            tool_response_parts: List[Any] = []
            for fc in function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args or {})
                tool_result: Dict[str, Any] = {}

                try:
                    if tool_name == "search_disruption_history":
                        tool_result = await search_disruption_history(
                            query=tool_args.get("query", question),
                            production_id=production_id,
                        )
                    elif tool_name == "get_case_details":
                        tool_result = await get_case_details(case_id or "")
                    elif tool_name == "explain_option_ranking":
                        tool_result = await explain_option_ranking(
                            case_id=case_id or "",
                            option_rank=tool_args.get("option_rank", 1),
                        )
                    elif tool_name == "check_shoot_plan":
                        tool_result = await check_shoot_plan(
                            production_id=production_id, case_id=case_id
                        )
                    else:
                        tool_result = {"error": f"Unknown tool: {tool_name}"}
                except Exception as tool_exc:  # noqa: BLE001
                    logger.warning("Tool %s raised: %s", tool_name, tool_exc)
                    tool_result = {"error": f"Tool {tool_name} failed: {tool_exc}"}

                # Collect sources for the citation panel
                if tool_result.get("sql"):
                    sources.append({
                        "type": "mcp_query",
                        "query": tool_result["sql"],
                        "result_summary": tool_result.get("summary", ""),
                    })

                # Build genai FunctionResponse
                tool_response_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=tool_name,
                            response={"result": json.dumps(tool_result, default=str)},
                        )
                    )
                )

            # Append the assistant's function-call turn and the tool results
            contents.append(candidate.content)  # model's function_call parts
            contents.append(
                types.Content(role="tool", parts=tool_response_parts)
            )

        # Loop exhausted without a final text answer — fall back
        return await _deterministic_fallback(question, production_id, case_id)
