"""Auditor Agent — writes the immutable decision trail to ClickHouse (ADK Agent).

After producer approval it appends:
  - one `decision_ledger` row (with the ClickHouse evidence snapshot as JSON)
  - one `schedule_changes` row per scene move
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from google.adk import Agent, Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.function_tool import FunctionTool
from google.genai import types

from models import CaseState, RecoveryOption, short_id
from services import clickhouse_client

logger = logging.getLogger("continuity.agents.auditor")


async def write_decision_ledger(case: CaseState, option: RecoveryOption, approved_by: str) -> str:
    """TRD Tool 6: `write_decision_ledger` — returns the new decision_id."""
    decision_id = short_id("dec")

    evidence_payload = {
        "narrative": case.evidence_narrative,
        "rows": [e.model_dump() for e in case.evidence_rows],
        "mcp_calls": [
            {"sql": c.sql, "rows": c.rows_returned, "latency_ms": c.latency_ms, "tool": c.tool}
            for c in case.mcp_calls
        ],
    }

    await clickhouse_client.insert_decision({
        "decision_id": decision_id,
        "case_id": case.case_id,
        "production_id": case.production_id,
        "disruption_type": case.disruption.disruption_type,
        "affected_location_id": case.disruption.affected_location_id,
        "selected_option": f"{option.option_id}:{option.strategy}",
        "option_summary": f"{option.name}: {option.description}",
        "estimated_cost_usd": int(option.estimated_cost_usd),
        "estimated_delay_hours": float(option.estimated_delay_hours),
        "continuity_risk_score": float(option.continuity_risk_score),
        "compliance_risk_score": float(option.compliance_risk_score),
        "evidence_json": json.dumps(evidence_payload)[:60000],
        "approved_by": approved_by,
    })

    change_rows: List[Dict[str, Any]] = [
        {
            "change_id": short_id("chg"),
            "decision_id": decision_id,
            "production_id": case.production_id,
            "scene_id": ch.scene_id,
            "old_shoot_day": ch.from_day,
            "new_shoot_day": ch.to_day,
            "old_location_id": ch.from_location,
            "new_location_id": ch.to_location,
            "change_type": ch.change_type,
        }
        for ch in option.scene_changes
    ]
    await clickhouse_client.insert_schedule_changes(change_rows)
    logger.info("Auditor wrote decision %s with %d schedule changes", decision_id, len(change_rows))
    return decision_id


# ---------------------------------------------------------------------------
# ADK Tool & Agent Wrappers
# ---------------------------------------------------------------------------
async def write_decision_ledger_tool(
    case_data: Dict[str, Any],
    option_data: Dict[str, Any],
    approved_by: str,
) -> Dict[str, Any]:
    """Records approved recovery option and scene moves into immutable ClickHouse decision tables.

    Args:
        case_data: Serialized CaseState dictionary.
        option_data: Serialized selected RecoveryOption dictionary.
        approved_by: Name or role of approving producer.
    """
    case = CaseState(**case_data)
    option = RecoveryOption(**option_data)
    decision_id = await write_decision_ledger(case, option, approved_by)
    return {
        "decision_id": decision_id,
        "status": "recorded",
        "case_id": case.case_id,
        "selected_option": option.option_id,
        "schedule_changes_count": len(option.scene_changes),
    }


auditor_tool = FunctionTool(write_decision_ledger_tool)


def create_auditor_agent(model_name: Optional[str] = None) -> Agent:
    """Instantiate the ADK Auditor Agent."""
    model = model_name or os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    return Agent(
        name="auditor_agent",
        model=model,
        instruction=(
            "You are the Auditor Agent for the Continuity Council. "
            "Execute the `write_decision_ledger_tool` to commit producer-approved recovery decisions "
            "and schedule adjustments into the permanent ClickHouse decision ledger."
        ),
        tools=[auditor_tool],
    )
