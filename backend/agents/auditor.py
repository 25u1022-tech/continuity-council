"""Auditor Agent — writes the immutable decision trail to ClickHouse.

After producer approval it appends:
  - one `decision_ledger` row (with the ClickHouse evidence snapshot as JSON)
  - one `schedule_changes` row per scene move
"""
from __future__ import annotations

import json
import logging
from typing import Dict, List

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
        "option_summary": f"{option.name} — {option.description}",
        "estimated_cost_usd": int(option.estimated_cost_usd),
        "estimated_delay_hours": float(option.estimated_delay_hours),
        "continuity_risk_score": float(option.continuity_risk_score),
        "compliance_risk_score": float(option.compliance_risk_score),
        "evidence_json": json.dumps(evidence_payload)[:60000],
        "approved_by": approved_by,
    })

    change_rows: List[Dict] = [
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
