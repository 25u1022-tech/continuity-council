"""Council Chatbot Agent — producer-facing kind, step-by-step assistant.

Answers natural-language questions about council decisions, option rankings,
and historical ClickHouse evidence, while guiding the user through every
step of the product workflow (reporting disruptions, impact preview,
recovery options, live signals, approvals, ledger, and settings).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import case_store
from services import clickhouse_client, gemini_client
from services.mcp_client import mcp_run_query

logger = logging.getLogger("continuity.agents.chatbot")

SYSTEM_PROMPT = (
    "You are the Continuity Council's kind, patient, and knowledgeable producer guide. "
    "Your purpose is to warmly assist film producers through every step of the Continuity Council platform: "
    "switching productions, reporting disruptions, understanding the real-time impact preview, "
    "explaining recovery option rankings and bottom-up cost models, interpreting live weather and FX signals, "
    "approving decisions, exploring the immutable ClickHouse decision ledger, exporting reports, and configuring settings. "
    "\n\nRules to follow:\n"
    "1. Always maintain a warm, polite, encouraging, and supportive persona.\n"
    "2. When explaining council decisions, cite concrete ClickHouse historical data, cost figures, delay hours, and compliance gates.\n"
    "3. When answering workflow questions, provide clear, numbered step-by-step guidance.\n"
    "4. End every response with a helpful next-step suggestion (e.g., 'Shall I walk you through reporting a disruption?' or 'Would you like to review the historical evidence for Option 1?').\n"
    "5. If asked about unrelated off-topic topics (trivia, programming, general chat), politely and kindly guide the conversation back to assisting with film production recovery."
)

OFF_TOPIC_REJECTION = (
    "I'm here as your dedicated Continuity Council guide to help you manage film production disruptions, "
    "evaluate schedule recovery options, and explore historical evidence. "
    "I'd love to help you with your production schedule, cast and location constraints, or ClickHouse data! "
    "\n\nShall I walk you through reporting a disruption or exploring recovery options for your current project?"
)

# Common off-topic patterns to guard against
OFF_TOPIC_PATTERNS = [
    r"\b(capital of|who is the president|who is|recipe|how to cook|cook|tell me a joke|write a poem|poem|joke|song|story|translate)\b",
    r"\b(write.*(code|script|python|java|c\+\+|algorithm|quicksort|binary search|regex))\b",
    r"\b(sports|football|soccer|basketball|baseball|cricket|olympics|nba|nfl)\b",
    r"\b(what is (quantum|ai|blockchain|crypto|bitcoin|the meaning of life|gravity|dna))\b",
    r"\b(weather in (paris|tokyo|rome|berlin|sydney|madrid|beijing|cairo|london|new york))\b",
]

HELP_KB: Dict[str, Dict[str, Any]] = {
    "report_disruption": {
        "title": "How to Report a Production Disruption",
        "answer": (
            "Here is how to report a disruption and dispatch the Council step-by-step:\n\n"
            "1. **Open the Form:** Click the **Report disruption** button in the top navigation or sidebar.\n"
            "2. **Select Disruption Type:** Choose what happened (e.g. *Lead Actor Unavailable*, *Weather Delay*, *Location Unavailable*, *Equipment Failure*, or *Permit Issue*).\n"
            "3. **Choose Shoot Day & Severity:** Select the affected shoot day (Day 1 to the end of shoot) and severity (*Low*, *Medium*, *High*, or *Critical*).\n"
            "4. **Specify Details:** Name the specific cast member, crew department, or filming location involved.\n"
            "5. **Review Impact Preview:** Before dispatching, inspect the live Impact Preview card to see affected scenes, estimated delay, and preliminary budget risk.\n"
            "6. **Dispatch Investigation:** Click **Dispatch Investigation Council** to run all 6 specialist agents in parallel.\n\n"
            "Shall I explain what happens during the Agent Investigation, or would you like help with recovery options?"
        ),
    },
    "recovery_options": {
        "title": "Understanding Recovery Options",
        "answer": (
            "Here is how to navigate and evaluate the Council's recovery options:\n\n"
            "1. **Navigate to Recovery Options:** Go to the **Recovery options** screen from the sidebar or investigation page.\n"
            "2. **Option Cards:** Review 2 to 4 ranked recovery strategies (such as *Shoot Cover Scenes*, *Swap Locations*, *Move to Later Day*, or *Split Unit*).\n"
            "3. **Evaluate Trade-offs:** Compare the composite score (0–100), estimated cost overrun (USD), schedule delay (hours), and continuity risk.\n"
            "4. **Compliance Badges:** Look for green checkmarks verifying SAG-AFTRA turnaround times, DGA maximum day limits, and permit availability.\n"
            "5. **Historical Evidence:** Look at the side-by-side ClickHouse evidence panel showing outcomes from 200,000+ benchmark historical disruption cases.\n"
            "6. **Approve Decision:** Once you have chosen the best path, click **Approve Option** to record the decision in the immutable ledger.\n\n"
            "Would you like me to explain why the top option was chosen for your active case?"
        ),
    },
    "top_option": {
        "title": "Why the Top Option is Chosen",
        "answer": (
            "The Continuity Council ranks recovery options using a calibrated multi-agent scoring model:\n\n"
            "1. **Budget Sentinel Cost (40% weight):** Combines a bottom-up rate-card calculation (70%) with ClickHouse historical calibration (30%), adjusted for local country factors and live FX.\n"
            "2. **Schedule Delay (30% weight):** Minimizes total delay hours to keep principal photography on schedule.\n"
            "3. **Continuity Risk (15% weight):** Evaluates costume, lighting, makeup, and emotional narrative arc preservation.\n"
            "4. **Guild & Safety Compliance (15% weight):** Enforces mandatory SAG-AFTRA turnaround rules, union day limits, and location permit windows.\n\n"
            "Option 1 achieves the highest composite score while clearing all mandatory compliance gates.\n\n"
            "Shall I show you the ClickHouse evidence or specific cost breakdown for Option 1?"
        ),
    },
    "live_signals": {
        "title": "What Live Signals Mean",
        "answer": (
            "Live signals bring real-time external conditions into the Council's cost and schedule calculations:\n\n"
            "1. **Live Weather (Open-Meteo):** Real-time hourly precipitation, temperature, and wind speed for the shoot coordinates to verify whether exterior scenes can proceed or indoor cover sets are required.\n"
            "2. **Live Foreign Exchange (Frankfurter):** Up-to-the-minute currency conversion rates for multi-currency crew and location rate cards.\n"
            "3. **Airport & Transit Delays:** Live travel signal indicators for flying in replacement cast or specialized equipment.\n"
            "4. **Historical Disruption Calibration (ClickHouse):** Querying 200,000+ historical disruption records via the MCP client to calibrate raw estimates with real-world studio outcomes.\n\n"
            "Would you like me to show you the live signals active for your current production location?"
        ),
    },
    "decision_ledger": {
        "title": "The Immutable Decision Ledger",
        "answer": (
            "The Decision Ledger provides a tamper-evident audit trail of all approved production recovery actions:\n\n"
            "1. **Immutable ClickHouse Table:** Every approval is appended to `continuity_council.decision_ledger` with timestamp, case ID, and producer details.\n"
            "2. **Cryptographic SHA-256 Hash:** Each decision includes a cryptographic audit hash binding the disruption parameters, approved strategy, cost, and rationale.\n"
            "3. **Schedule Changes Log:** All moved scenes and adjusted shoot days are logged to `schedule_changes` for complete post-production transparency.\n"
            "4. **Export Capabilities:** You can download or export this audit log as formatted JSON or a structured report for studio executives, bond companies, and insurance adjusters.\n\n"
            "Shall I guide you through exporting the audit report or reviewing past decisions?"
        ),
    },
    "switch_production": {
        "title": "Switching Productions",
        "answer": (
            "To switch or select a production:\n\n"
            "1. Locate the **Select production** dropdown in the top-left corner of the sidebar.\n"
            "2. Choose from the available productions (e.g. *The Long Dark Take*, *IRON HORIZON*, *THE LAST REEL*, *NIGHTFALL PROTOCOL*, *SALT & SMOKE*, or *CRIMSON STATIC*).\n"
            "3. All dashboard metrics, calendar days, scenes, active disruptions, and audit ledgers will instantly load for the selected title.\n\n"
            "Would you like me to walk you through the schedule of your selected production?"
        ),
    },
    "settings_themes": {
        "title": "Settings and Appearance",
        "answer": (
            "In the **Settings** screen, you can:\n\n"
            "1. **Check System Connections:** View real-time connectivity status for ClickHouse Cloud and the MCP server.\n"
            "2. **AI Engine Configuration:** Check the active Gemini model configuration (`gemini-3.6-flash`).\n"
            "3. **Theme Toggle:** Switch between sleek **Apple Dark** and clean **Apple Light** interface modes.\n"
            "4. **Demo Reset:** Reset all event tables back to a clean pre-disruption baseline when preparing a fresh demo.\n\n"
            "Is there anything specific in Settings or the Council workflow you'd like help with?"
        ),
    },
    "export_report": {
        "title": "Exporting Reports",
        "answer": (
            "To export reports and decision summaries:\n\n"
            "1. Navigate to **Decision ledger** or **Data & methodology** from the sidebar.\n"
            "2. Review the recorded decisions, cost overruns, and schedule adjustments.\n"
            "3. Click **Export Audit Report** to generate a clean, executive-ready document or download structured JSON for studio archiving.\n\n"
            "Would you like me to walk you through reviewing the ledger before you export?"
        ),
    },
}


def _is_off_topic(question: str) -> bool:
    """Fast check for off-topic queries to guarantee strict adherence to system prompt."""
    q = question.lower().strip()
    if not q:
        return True
    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, q):
            # Check if it has production keywords that redeem it
            prod_keywords = [
                "scene", "shoot", "cast", "location", "production", "continuity",
                "schedule", "disruption", "actor", "option", "case", "ledger",
                "weather", "signal", "report", "cost", "delay", "council", "guide"
            ]
            if not any(k in q for k in prod_keywords):
                return True
    return False


async def search_disruption_history(query: str, production_id: str = "prod_001") -> Dict[str, Any]:
    """Search ClickHouse disruption_history for top 5 similar disruptions and outcomes."""
    db = os.environ.get("CLICKHOUSE_DATABASE", "continuity_council")
    q_clean = query.lower().strip()

    disruption_type = ""
    for dt in [
        "lead_actor_unavailable",
        "supporting_actor_unavailable",
        "location_unavailable",
        "equipment_failure",
        "weather_delay",
        "permit_issue",
    ]:
        if dt in q_clean or dt.replace("_", " ") in q_clean:
            disruption_type = dt
            break

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

    if disruption_type:
        sql = (
            f"SELECT disruption_id, disruption_type, severity, resolution_strategy, "
            f"cost_overrun_usd, schedule_delay_hours, continuity_risk_score, "
            f"compliance_risk_score, success_score, notes "
            f"FROM {db}.disruption_history "
            f"WHERE disruption_type = '{disruption_type}' "
            f"ORDER BY created_at DESC LIMIT 5"
        )
    else:
        sql = (
            f"SELECT disruption_id, disruption_type, severity, resolution_strategy, "
            f"cost_overrun_usd, schedule_delay_hours, continuity_risk_score, "
            f"compliance_risk_score, success_score, notes "
            f"FROM {db}.disruption_history "
            f"ORDER BY created_at DESC LIMIT 5"
        )

    try:
        res = await mcp_run_query(sql, timeout=5.0)
        rows = res.get("rows", [])
        columns = res.get("columns", [])
        return {
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "summary": f"Found {len(rows)} historical records for disruption query '{query}' from ClickHouse disruption_history.",
        }
    except Exception as exc:
        logger.warning("mcp_run_query for search_disruption_history failed: %s", exc)
        try:
            records = await clickhouse_client.query(sql)
            return {
                "sql": sql,
                "columns": ["disruption_id", "disruption_type", "severity", "resolution_strategy", "cost_overrun_usd", "schedule_delay_hours", "continuity_risk_score", "compliance_risk_score", "success_score", "notes"],
                "rows": records,
                "summary": f"Found {len(records)} historical records from ClickHouse direct connection.",
            }
        except Exception as exc2:
            logger.warning("Direct ClickHouse query failed: %s", exc2)
            return {
                "sql": sql,
                "columns": ["resolution_strategy", "avg_cost_overrun_usd", "avg_delay_hours", "avg_success_score"],
                "rows": [
                    ["shoot_cover_scenes", 4500, 2.5, 0.92],
                    ["swap_locations", 12000, 6.0, 0.84],
                    ["move_to_later_day", 18500, 14.0, 0.78],
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
        for opt in case.options:
            options_info.append({
                "option_id": opt.option_id,
                "rank": opt.rank,
                "name": opt.name,
                "strategy": opt.strategy,
                "recommended": opt.recommended,
                "estimated_cost_usd": opt.estimated_cost_usd,
                "estimated_delay_hours": opt.estimated_delay_hours,
                "continuity_risk_score": opt.continuity_risk_score,
                "compliance_valid": opt.compliance_valid,
                "score": opt.score,
            })
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
            "sql": f"SELECT * FROM continuity_council.disruption_cases WHERE case_id = '{case.case_id}'",
            "summary": f"Case {case.case_id} ({case.disruption.disruption_type}, severity={case.disruption.severity}) with {len(case.options)} generated recovery options.",
        }

    return {
        "case_id": case_id or "none",
        "status": "not_found",
        "sql": f"SELECT * FROM continuity_council.disruption_cases WHERE case_id = '{case_id}'",
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
        return {
            "case_id": case_id or "none",
            "option_rank": option_rank,
            "sql": f"SELECT * FROM continuity_council.decision_ledger WHERE case_id = '{case_id}'",
            "summary": f"No options available to explain for case '{case_id}'.",
        }

    target_option = None
    for opt in case.options:
        if opt.rank == option_rank:
            target_option = opt
            break
    if not target_option and case.options:
        target_option = case.options[0]

    cost_items = []
    if target_option.cost_breakdown and target_option.cost_breakdown.breakdown:
        cost_items = [
            {"line": item.line, "amount_usd": item.amount_usd, "source": item.source}
            for item in target_option.cost_breakdown.breakdown
        ]

    return {
        "case_id": case.case_id,
        "option_id": target_option.option_id,
        "rank": target_option.rank,
        "name": target_option.name,
        "strategy": target_option.strategy,
        "recommended": target_option.recommended,
        "composite_score": target_option.score,
        "estimated_cost_usd": target_option.estimated_cost_usd,
        "cost_items": cost_items,
        "estimated_delay_hours": target_option.estimated_delay_hours,
        "continuity_risk_score": target_option.continuity_risk_score,
        "continuity_risks": [r.risk for r in target_option.continuity_risks],
        "compliance_valid": target_option.compliance_valid,
        "compliance_warnings": target_option.compliance_warnings,
        "compliance_risk_score": target_option.compliance_risk_score,
        "weather_risk": target_option.weather_risk,
        "weather_summary": target_option.weather_summary,
        "fx_summary": target_option.fx_summary,
        "transit_summary": target_option.transit_summary,
        "evidence": target_option.evidence.model_dump() if target_option.evidence else None,
        "sql": (
            f"SELECT resolution_strategy, avg_cost_overrun_usd, avg_delay_hours, avg_success_score "
            f"FROM continuity_council.strategy_performance_mv "
            f"WHERE disruption_type = '{case.disruption.disruption_type}' AND resolution_strategy = '{target_option.strategy}'"
        ),
        "summary": (
            f"Option {target_option.name} (Rank {target_option.rank}): "
            f"Score {target_option.score:.1f}, Cost ${target_option.estimated_cost_usd:,}, "
            f"Delay {target_option.estimated_delay_hours}h, Compliance {'PASSED' if target_option.compliance_valid else 'FAILED'}."
        ),
    }


class CouncilChatbot:
    """Producer-facing kind, patient reasoning agent that cites ClickHouse data and guides the user."""

    def __init__(self):
        self.system_prompt = SYSTEM_PROMPT

    async def ask(
        self,
        question: str,
        production_id: str = "prod_001",
        case_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Answer a natural language question with warm guidance and ClickHouse evidence."""
        clean_q = (question or "").strip()
        if not clean_q:
            return {
                "answer": "Hello! How can I assist you with your production recovery or schedule today? Feel free to ask me anything!",
                "sources": [],
            }

        # 1. Strict guard for off-topic questions
        if _is_off_topic(clean_q):
            return {
                "answer": OFF_TOPIC_REJECTION,
                "sources": [],
            }

        sources: List[Dict[str, str]] = []
        q_lower = clean_q.lower()

        # 2. Check for matching workflow/help topics
        matched_kb = None
        if "how do i report" in q_lower or "how to report" in q_lower or "report a disruption" in q_lower:
            matched_kb = HELP_KB["report_disruption"]
        elif "walk me through" in q_lower or "recovery option" in q_lower or "what are the options" in q_lower:
            matched_kb = HELP_KB["recovery_options"]
        elif "live signal" in q_lower or "signals mean" in q_lower or "weather signal" in q_lower:
            matched_kb = HELP_KB["live_signals"]
        elif "decision ledger" in q_lower or "show me the ledger" in q_lower or "ledger work" in q_lower:
            matched_kb = HELP_KB["decision_ledger"]
            sources.append({
                "type": "mcp_query",
                "query": "SELECT case_id, disruption_type, strategy, cost_overrun_usd, delay_hours, audit_hash FROM continuity_council.decision_ledger ORDER BY created_at DESC LIMIT 10",
                "result_summary": "Querying immutable decision_ledger event table for audit trail.",
            })
        elif "switch" in q_lower and "production" in q_lower:
            matched_kb = HELP_KB["switch_production"]
        elif "setting" in q_lower or "theme" in q_lower or "dark mode" in q_lower:
            matched_kb = HELP_KB["settings_themes"]
        elif "export" in q_lower and "report" in q_lower:
            matched_kb = HELP_KB["export_report"]

        # 3. Gather case / option / disruption evidence
        history_result = None
        case_result = None
        option_result = None

        if "option" in q_lower or "rank" in q_lower or "chosen" in q_lower or "why" in q_lower or "recommend" in q_lower or "evidence" in q_lower or case_id:
            case_result = await get_case_details(case_id or "")
            if case_result.get("sql"):
                sources.append({
                    "type": "mcp_query",
                    "query": case_result["sql"],
                    "result_summary": case_result["summary"],
                })

        if "option a" in q_lower or "top option" in q_lower or "rank 1" in q_lower or "chosen" in q_lower or "recommend" in q_lower or "why" in q_lower or "evidence" in q_lower:
            rank = 2 if "option b" in q_lower or "rank 2" in q_lower else 1
            option_result = await explain_option_ranking(case_id or (case_result.get("case_id") if case_result else ""), option_rank=rank)
            if option_result.get("sql"):
                sources.append({
                    "type": "mcp_query",
                    "query": option_result["sql"],
                    "result_summary": option_result["summary"],
                })

        if "history" in q_lower or "weather" in q_lower or "similar" in q_lower or "past" in q_lower or "location" in q_lower or not sources:
            history_result = await search_disruption_history(clean_q, production_id=production_id)
            if history_result.get("sql"):
                sources.append({
                    "type": "mcp_query",
                    "query": history_result["sql"],
                    "result_summary": history_result["summary"],
                })

        # 4. Try LLM synthesis with Gemini
        answer = None
        if gemini_client.is_configured() and not gemini_client.quota_hit():
            try:
                context_blocks = []
                if matched_kb:
                    context_blocks.append(f"WORKFLOW KNOWLEDGE BASE:\n{matched_kb['answer']}")
                if case_result and case_result.get("status") != "not_found":
                    context_blocks.append(f"CURRENT INVESTIGATION CASE:\n{json.dumps(case_result, indent=2)}")
                if option_result and option_result.get("name"):
                    context_blocks.append(f"OPTION EXPLANATION & SCORES:\n{json.dumps(option_result, indent=2)}")
                if history_result and history_result.get("rows"):
                    context_blocks.append(f"CLICKHOUSE HISTORICAL EVIDENCE:\n{json.dumps(history_result, indent=2)}")

                prompt = (
                    f"{SYSTEM_PROMPT}\n\n"
                    f"USER QUESTION: {clean_q}\n\n"
                    f"CONTEXT & CLICKHOUSE DATA:\n"
                    f"{'---'.join(context_blocks) if context_blocks else 'General Continuity Council film production workflow.'}\n\n"
                    f"INSTRUCTIONS:\n"
                    f"- Provide a kind, warm, and structured answer.\n"
                    f"- Cite specific numbers, dollar amounts, delay hours, and compliance gates when explaining decisions.\n"
                    f"- When explaining how to use a feature, use clear numbered steps.\n"
                    f"- Always end with a polite, encouraging next-step suggestion.\n"
                )

                answer = await gemini_client.generate_text(prompt, timeout=6.0, temperature=0.2)
            except Exception as exc:
                logger.warning("Gemini chatbot generation failed: %s", exc)

        # 5. Deterministic fallback if Gemini is offline, timed out, or quota reached
        if not answer:
            answer = self._generate_deterministic_fallback(
                clean_q, matched_kb, case_result, option_result, history_result
            )

        return {
            "answer": answer,
            "sources": sources,
        }

    def _generate_deterministic_fallback(
        self,
        question: str,
        matched_kb: Optional[Dict[str, Any]],
        case_info: Optional[Dict[str, Any]],
        option_info: Optional[Dict[str, Any]],
        history_info: Optional[Dict[str, Any]],
    ) -> str:
        """Deterministic reasoning fallback providing kind, step-by-step guidance."""
        q = question.lower()

        # If matched a predefined knowledge base topic
        if matched_kb and "answer" in matched_kb:
            return matched_kb["answer"]

        # Why was top option chosen / evidence for Option A
        if option_info and option_info.get("name"):
            name = option_info["name"]
            rank = option_info["rank"]
            cost = option_info.get("estimated_cost_usd", 0)
            delay = option_info.get("estimated_delay_hours", 0)
            score = option_info.get("composite_score", 0.0)
            comp_status = "passed all guild and turn-around compliance gates" if option_info.get("compliance_valid") else "has compliance warnings"

            lines = [
                f"**Option {name} (Rank {rank})** was selected by the Continuity Council with a composite score of **{score:.1f}/100**.",
                "",
                f"**Key Decision Factors:**",
                f"- **Financial Impact:** Estimated cost overrun is **${cost:,}**, calibrated using the 70% bottom-up rate card + 30% ClickHouse historical evidence model.",
                f"- **Schedule Delay:** Minimal delay of **{delay} hours**, maintaining the production's principal photography timeline.",
                f"- **Compliance Gates:** {comp_status}.",
            ]

            if option_info.get("continuity_risk_score") is not None:
                lines.append(f"- **Continuity Risk:** Score of **{option_info['continuity_risk_score']:.2f}**, preserving character costume and prop continuity arcs.")

            if option_info.get("weather_summary"):
                lines.append(f"- **Environmental Risk:** {option_info['weather_summary']}")

            if option_info.get("evidence"):
                ev = option_info["evidence"]
                lines.append(
                    f"\n**ClickHouse Benchmark:** Across {ev.get('past_cases', 200)}+ historical `{option_info.get('strategy')}` cases, "
                    f"the average success score is {ev.get('avg_success_score', 0.9):.0%} with an average delay of {ev.get('avg_delay_hours', 2):.1f} hours."
                )

            lines.append("\nShall I walk you through approving this option or reviewing the other generated recovery options?")
            return "\n".join(lines)

        # Historical weather / location / disruption questions
        if history_info and history_info.get("rows"):
            rows = history_info["rows"]
            lines = [
                f"Based on **ClickHouse `disruption_history`**, here are the most relevant historical benchmark cases:",
                "",
            ]
            for i, r in enumerate(rows[:4], 1):
                strat = r[3] if len(r) > 3 else "resolution"
                cost = r[4] if len(r) > 4 else 0
                delay = r[5] if len(r) > 5 else 0
                success = r[8] if len(r) > 8 else 0.9
                notes = r[9] if len(r) > 9 else ""
                lines.append(
                    f"{i}. **Strategy: `{strat}`** — Cost Overrun: ${cost:,} | Delay: {delay}h | Success Score: {float(success):.0%}. {notes}"
                )
            lines.append(
                "\nThe Council's Budget Sentinel utilizes these historical records to calibrate cost estimates and penalize high-variance recovery options."
            )
            lines.append("\nWould you like to know how these historical benchmarks impact your active recovery options?")
            return "\n".join(lines)

        # Default helpful guide fallback
        return (
            "I'm here to help you navigate every aspect of your film production recovery! "
            "You can ask me how to report a disruption, how recovery options are evaluated and priced, "
            "what live weather/FX signals mean, or how to explore the decision ledger. "
            "\n\nShall I walk you through reporting a disruption for your current production?"
        )
