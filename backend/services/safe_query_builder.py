"""Safe Query Builder — the LLM NEVER writes raw SQL.

The Budget Sentinel agent may only select from these predefined templates and
inject validated, allowlisted parameters. This prevents SQL injection and
hallucinated table/column names (hard requirement of the TRD).
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict

ALLOWED_DISRUPTION_TYPES = {
    "lead_actor_unavailable",
    "supporting_actor_unavailable",
    "location_unavailable",
    "equipment_failure",
    "weather_delay",
    "permit_issue",
}

ALLOWED_SEVERITIES = {"low", "medium", "high"}

ALLOWED_STRATEGIES = {
    "shoot_cover_scenes",
    "swap_locations",
    "move_to_later_day",
    "wait_for_actor",
    "recast_scene",
    "split_scene",
    "use_stand_in",
}


def _db() -> str:
    return os.environ.get("CLICKHOUSE_DATABASE", "continuity_council")


TEMPLATE_DESCRIPTIONS = {
    "strategy_performance": (
        "Average cost overrun, delay, risk and success score per resolution strategy "
        "for a given disruption_type across all history, from strategy_performance_mv."
    ),
    "strategy_performance_by_severity": (
        "Same as strategy_performance but filtered to a specific severity level."
    ),
    "studio_strategy_performance": (
        "Strategy performance filtered to a specific studio cohort for tenant evidence isolation."
    ),
    "recent_strategy_performance": (
        "Strategy performance restricted to the last N days (30-1095)."
    ),
    "raw_history_samples": (
        "Raw disruption_history rows behind one resolution strategy for a given "
        "disruption_type (optional severity or studio filter). Used by the evidence drilldown."
    ),
}


class UnsafeQueryError(ValueError):
    pass


def _clean_identifier(val: str) -> str:
    cleaned = str(val).strip()
    if not cleaned or not re.match(r"^[a-zA-Z0-9_\-]+$", cleaned) or len(cleaned) > 64:
        raise UnsafeQueryError(f"Invalid identifier format: '{val}'")
    return cleaned


def build_query(template_id: str, params: Dict[str, Any]) -> str:
    """Return a validated, SELECT-only SQL string for an allowlisted template."""
    db = _db()

    disruption_type = str(params.get("disruption_type", "")).strip()
    if disruption_type not in ALLOWED_DISRUPTION_TYPES:
        raise UnsafeQueryError(
            f"disruption_type '{disruption_type}' is not in the allowlist {sorted(ALLOWED_DISRUPTION_TYPES)}"
        )

    # --- Raw-rows drilldown template (no aggregation) -----------------------
    if template_id == "raw_history_samples":
        strategy = str(params.get("strategy", "")).strip()
        if strategy not in ALLOWED_STRATEGIES:
            raise UnsafeQueryError(
                f"strategy '{strategy}' is not in the allowlist {sorted(ALLOWED_STRATEGIES)}"
            )
        try:
            limit = int(params.get("limit", 40))
        except (TypeError, ValueError):
            raise UnsafeQueryError("limit must be an integer")
        limit = max(1, min(100, limit))
        sql = (
            "SELECT disruption_id, severity, affected_role, affected_scene_count, "
            "cost_overrun_usd, schedule_delay_hours, continuity_risk_score, "
            "compliance_risk_score, success_score, notes, created_at "
            f"FROM {db}.disruption_history "
            f"WHERE disruption_type = '{disruption_type}' "
            f"AND resolution_strategy = '{strategy}'"
        )
        severity = str(params.get("severity", "") or "").strip()
        if severity:
            if severity not in ALLOWED_SEVERITIES:
                raise UnsafeQueryError(f"severity '{severity}' is not in {sorted(ALLOWED_SEVERITIES)}")
            sql += f" AND severity = '{severity}'"
        raw_studio = params.get("studio_id")
        if raw_studio:
            clean_studio = _clean_identifier(str(raw_studio))
            sql += f" AND studio_id = '{clean_studio}'"
        sql += f" ORDER BY created_at DESC LIMIT {limit}"
        return _validate_final(sql)

    mv_select = (
        "SELECT strategy AS resolution_strategy, "
        "round(avgMerge(avg_cost)) AS avg_cost_overrun_usd, "
        "round(avgMerge(avg_delay), 1) AS avg_delay_hours, "
        "round(avgMerge(avg_continuity_risk), 2) AS avg_continuity_risk, "
        "round(avgMerge(avg_compliance_risk), 2) AS avg_compliance_risk, "
        "round(avgMerge(avg_success_score), 2) AS avg_success_score, "
        "countMerge(sample_size) AS past_cases "
        f"FROM {db}.strategy_performance_mv "
        f"WHERE disruption_type = '{disruption_type}'"
    )

    studio_select = (
        "SELECT resolution_strategy, "
        "round(AVG(cost_overrun_usd)) AS avg_cost_overrun_usd, "
        "round(AVG(schedule_delay_hours), 1) AS avg_delay_hours, "
        "round(AVG(continuity_risk_score), 2) AS avg_continuity_risk, "
        "round(AVG(compliance_risk_score), 2) AS avg_compliance_risk, "
        "round(AVG(success_score), 2) AS avg_success_score, "
        "COUNT(*) AS past_cases "
        f"FROM {db}.disruption_history "
        f"WHERE disruption_type = '{disruption_type}'"
    )

    recent_select = (
        "SELECT resolution_strategy, "
        "round(AVG(cost_overrun_usd)) AS avg_cost_overrun_usd, "
        "round(AVG(schedule_delay_hours), 1) AS avg_delay_hours, "
        "round(AVG(continuity_risk_score), 2) AS avg_continuity_risk, "
        "round(AVG(compliance_risk_score), 2) AS avg_compliance_risk, "
        "round(AVG(success_score), 2) AS avg_success_score, "
        "COUNT(*) AS past_cases "
        f"FROM {db}.disruption_history "
        f"WHERE disruption_type = '{disruption_type}'"
    )

    if template_id == "strategy_performance":
        sql = mv_select
    elif template_id == "strategy_performance_by_severity":
        severity = str(params.get("severity", "")).strip()
        if severity not in ALLOWED_SEVERITIES:
            raise UnsafeQueryError(f"severity '{severity}' is not in {sorted(ALLOWED_SEVERITIES)}")
        sql = mv_select + f" AND severity = '{severity}'"
    elif template_id == "studio_strategy_performance":
        studio_id = _clean_identifier(str(params.get("studio_id", "global")))
        sql = studio_select + f" AND studio_id = '{studio_id}'"
        severity = str(params.get("severity", "") or "").strip()
        if severity:
            if severity not in ALLOWED_SEVERITIES:
                raise UnsafeQueryError(f"severity '{severity}' is not in {sorted(ALLOWED_SEVERITIES)}")
            sql += f" AND severity = '{severity}'"
    elif template_id == "recent_strategy_performance":
        try:
            days = int(params.get("days", 365))
        except (TypeError, ValueError):
            raise UnsafeQueryError("days must be an integer")
        days = max(30, min(1095, days))
        sql = recent_select + f" AND created_at >= now() - INTERVAL {days} DAY"
    else:
        raise UnsafeQueryError(
            f"Unknown template '{template_id}'. Allowed: {sorted(TEMPLATE_DESCRIPTIONS)}"
        )

    group_by = (
        "strategy"
        if template_id in {"strategy_performance", "strategy_performance_by_severity"}
        else "resolution_strategy"
    )
    sql += f" GROUP BY {group_by} ORDER BY avg_cost_overrun_usd ASC LIMIT 20"
    return _validate_final(sql)


def _validate_final(sql: str) -> str:
    """Defense in depth: final shape validation for every generated query."""
    lowered = sql.lower()
    if not lowered.startswith("select") or ";" in sql:
        raise UnsafeQueryError("Only single SELECT statements are permitted")
    for banned in ("insert", "update", "delete", "drop", "alter", "truncate", "create"):
        if f" {banned} " in f" {lowered} ":
            raise UnsafeQueryError(f"Banned keyword in query: {banned}")
    return sql
