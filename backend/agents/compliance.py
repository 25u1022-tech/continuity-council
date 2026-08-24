"""Compliance Agent — deterministic constraint solver (ADK Agent).

Validates every recovery option BEFORE the Orchestrator ranks it:
  1. Location availability on the proposed day
  2. Cast availability (including the reported disruption itself)
  3. Shoot-day bounds (1..total_shoot_days)
  4. Dependency ordering feasibility
  5. Working-hour proxy: max scenes per day
  6. Geographic transit distance (>100 miles same-day limit)
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from google.adk import Agent, Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.function_tool import FunctionTool
from google.genai import types

from models import CaseState, RecoveryOption
from services.geo_service import haversine_miles

logger = logging.getLogger("continuity.agents.compliance")

MAX_SCENES_PER_DAY = 5  # simple working-hour constraint for a 3-day MVP shoot


def _projected_schedule(scenes: List[Dict[str, Any]], option: RecoveryOption) -> Dict[str, Dict[str, Any]]:
    projected = {s["scene_id"]: dict(s) for s in scenes}
    for ch in option.scene_changes:
        if ch.scene_id in projected:
            projected[ch.scene_id]["shoot_day"] = ch.to_day
            if ch.to_location:
                projected[ch.scene_id]["location_id"] = ch.to_location
    return projected


def validate_compliance(
    case: CaseState,
    option: RecoveryOption,
    bundle: Dict[str, Any],
) -> Tuple[bool, List[str], float]:
    """TRD Tool 5: `validate_compliance` — (valid, warnings, compliance_risk_score)."""
    scenes = bundle["scenes"]
    total_days = bundle["production"]["total_shoot_days"]
    d = case.disruption

    loc_avail = {
        (a["location_id"], a["shoot_day"]): (a["available"], a["notes"])
        for a in bundle["location_availability"]
    }
    cast_avail = {
        (a["cast_id"], a["shoot_day"]): a["available"]
        for a in bundle["cast_availability"]
    }
    loc_names = {l["location_id"]: l["name"] for l in bundle["locations"]}
    loc_coords = {
        l["location_id"]: (float(l.get("latitude", 0.0) or 0.0), float(l.get("longitude", 0.0) or 0.0))
        for l in bundle["locations"]
    }
    cast_names = {c["cast_id"]: c["name"] for c in bundle["cast_members"]}

    projected = _projected_schedule(scenes, option)
    warnings: List[str] = []
    hard_fail = False

    # 1) Day bounds & Geographic transit distance rule (>100mi in same day = hard fail)
    for ch in option.scene_changes:
        if ch.to_day < 1 or ch.to_day > total_days:
            warnings.append(f"{ch.scene_id} moved outside the {total_days}-day shoot window.")
            hard_fail = True

        from_loc = ch.from_location
        to_loc = ch.to_location
        if from_loc and to_loc and from_loc != to_loc and ch.from_day == ch.to_day:
            lat1, lon1 = loc_coords.get(from_loc, (None, None))
            lat2, lon2 = loc_coords.get(to_loc, (None, None))
            if lat1 is not None and lon1 is not None and lat2 is not None and lon2 is not None:
                dist = haversine_miles(lat1, lon1, lat2, lon2)
                option.transit_distance_miles = max(option.transit_distance_miles, dist)
                if dist > 100.0:
                    warnings.append(
                        f"Transit distance of {dist:.0f} miles exceeds 100-mile same-day limit between "
                        f"{loc_names.get(from_loc, from_loc)} and {loc_names.get(to_loc, to_loc)} "
                        f"(physically impossible in shoot window)."
                    )
                    hard_fail = True
                    option.transit_summary = f"{dist:.0f}-mile crew transit (violates 100mi max) — OpenStreetMap"
                elif dist > 0.0 and not option.transit_summary:
                    option.transit_summary = f"{dist:.0f}-mile crew transit — OpenStreetMap"

    # 2) Location availability on new days
    for s in projected.values():
        if (
            d.disruption_type == "location_unavailable"
            and d.affected_location_id
            and s["location_id"] == d.affected_location_id
            and s["shoot_day"] == d.affected_day
        ):
            loc_label = loc_names.get(s["location_id"], s["location_id"])
            warnings.append(
                f"{loc_label} is unavailable on Day {d.affected_day} — blocks {s['scene_id']}."
            )
            hard_fail = True
        avail, note = loc_avail.get((s["location_id"], s["shoot_day"]), (True, ""))
        if not avail:
            loc_label = loc_names.get(s["location_id"], s["location_id"])
            suffix = f" ({note})" if note else ""
            warnings.append(
                f"{loc_label} is not available on Day {s['shoot_day']} — blocks {s['scene_id']}{suffix}."
            )
            hard_fail = True

    # 3) Cast availability, including the live disruption
    unavailable_cast = set()
    if d.disruption_type in ("lead_actor_unavailable", "supporting_actor_unavailable") and d.affected_cast_id:
        unavailable_cast.add((d.affected_cast_id, d.affected_day))
    for s in projected.values():
        for cid in s["required_cast"]:
            base_available = cast_avail.get((cid, s["shoot_day"]), True)
            live_blocked = (cid, s["shoot_day"]) in unavailable_cast
            if not base_available or live_blocked:
                warnings.append(
                    f"{cast_names.get(cid, cid)} unavailable on Day {s['shoot_day']} — blocks {s['scene_id']}."
                )
                hard_fail = True

    # 4) Dependency ordering must remain satisfiable
    for s in projected.values():
        for dep in s["depends_on"]:
            dep_scene = projected.get(dep)
            if dep_scene and dep_scene["shoot_day"] > s["shoot_day"]:
                warnings.append(
                    f"Dependency conflict: {s['scene_id']} would shoot before {dep}."
                )

    # 5) Working-hour proxy — scenes per day
    per_day: Dict[int, int] = {}
    for s in projected.values():
        if s["status"] != "cancelled":
            per_day[s["shoot_day"]] = per_day.get(s["shoot_day"], 0) + 1
    for day, count in sorted(per_day.items()):
        if count > MAX_SCENES_PER_DAY:
            warnings.append(
                f"Day {day} would carry {count} scenes (>{MAX_SCENES_PER_DAY}) — likely crew overtime."
            )

    # Risk score: hard fails dominate; soft warnings accumulate
    if hard_fail:
        risk = 0.9
    else:
        risk = min(0.75, 0.08 + 0.15 * len(warnings))
    return (not hard_fail), warnings, round(risk, 2)


# ---------------------------------------------------------------------------
# ADK Tool & Agent Wrappers
# ---------------------------------------------------------------------------
async def validate_compliance_rules_tool(
    case_data: Dict[str, Any],
    options: List[Dict[str, Any]],
    bundle: Dict[str, Any],
) -> Dict[str, Any]:
    """Validates operational feasibility, cast/location availability, and geographic transit rules.

    Args:
        case_data: Serialized CaseState dictionary.
        options: List of serialized RecoveryOption dicts.
        bundle: Serialized schedule bundle with scenes, locations, and availability schedules.
    """
    case = CaseState(**case_data)
    option_models = [RecoveryOption(**o) for o in options]
    invalid_count = 0
    for opt in option_models:
        valid, warnings, risk = validate_compliance(case, opt, bundle)
        opt.compliance_valid = valid
        opt.compliance_warnings = warnings[:5]
        opt.compliance_risk_score = risk
        if not valid:
            invalid_count += 1

    return {
        "invalid_count": invalid_count,
        "valid_count": len(option_models) - invalid_count,
        "summary": f"Validated {len(option_models)} options — {invalid_count} blocked by hard constraints",
        "evaluated_options": [o.model_dump() for o in option_models],
    }


compliance_tool = FunctionTool(validate_compliance_rules_tool)


def create_compliance_agent(model_name: Optional[str] = None) -> Agent:
    """Instantiate the ADK Compliance Agent."""
    model = model_name or os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    return Agent(
        name="compliance_agent",
        model=model,
        instruction=(
            "You are the Compliance Agent for the Continuity Council film production system. "
            "Execute the `validate_compliance_rules_tool` to ensure candidate recovery options satisfy "
            "location permits, cast union availability, working-hour limits, and geographic transit constraints."
        ),
        tools=[compliance_tool],
    )


# ---------------------------------------------------------------------------
# Orchestrator Compatibility Entry Point
# ---------------------------------------------------------------------------
async def run(case: CaseState, options: List[RecoveryOption], bundle: Dict[str, Any]) -> str:
    invalid = 0
    for option in options:
        valid, warnings, risk = validate_compliance(case, option, bundle)
        option.compliance_valid = valid
        option.compliance_warnings = warnings[:5]
        option.compliance_risk_score = risk
        if not valid:
            invalid += 1
    return f"Validated {len(options)} options — {invalid} blocked by hard constraints"
