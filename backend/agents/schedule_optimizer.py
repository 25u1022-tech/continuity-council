"""Schedule Optimizer Agent (ADK Agent).

Deterministically generates 2-4 recovery options from the current schedule
(scene moves, location swaps, holds), then asks Gemini to polish the option
descriptions (deterministic fallback text if the LLM is unavailable).
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from google.adk import Agent, Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.function_tool import FunctionTool
from google.genai import types

from models import CaseState, RecoveryOption, SceneChange
from services import gemini_client

logger = logging.getLogger("continuity.agents.schedule")


def _affected_scenes(case: CaseState, scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    d = case.disruption
    day_scenes = [s for s in scenes if s["shoot_day"] == d.affected_day and s["status"] != "cancelled"]
    if d.disruption_type in ("lead_actor_unavailable", "supporting_actor_unavailable"):
        return [s for s in day_scenes if d.affected_cast_id in s["required_cast"]]
    if d.disruption_type in ("location_unavailable", "permit_issue"):
        return [s for s in day_scenes if s["location_id"] == d.affected_location_id]
    # weather / equipment: whole day is at risk
    return day_scenes


def _alternate_day(case: CaseState, total_days: int) -> Optional[int]:
    """Return a viable alternate shoot day: next day if within shoot window, else previous day."""
    d = case.disruption.affected_day
    if d < total_days:
        return d + 1
    if d > 1:
        return d - 1
    return None


def generate_schedule_options(case: CaseState, bundle: Dict[str, Any]) -> List[RecoveryOption]:
    """TRD Tool 2: `generate_schedule_options` — 2-4 recovery options with scene changes."""
    scenes = bundle["scenes"]
    total_days = bundle["production"]["total_shoot_days"]
    d = case.disruption
    affected = _affected_scenes(case, scenes)
    case.affected_scene_ids = [s["scene_id"] for s in affected]
    target_day = _alternate_day(case, total_days)

    def mk_change(s: Dict[str, Any], new_day: int, new_loc: str = "") -> SceneChange:
        return SceneChange(
            scene_id=s["scene_id"], scene_title=s["scene_title"],
            from_day=s["shoot_day"], to_day=new_day,
            from_location=s["location_id"], to_location=new_loc or s["location_id"],
            change_type="move_scene_day" if not new_loc or new_loc == s["location_id"] else "move_scene_location",
        )

    options: List[RecoveryOption] = []

    # --- Option A: shoot cover scenes / unaffected work on the disrupted day ---
    cover_pool = [
        s for s in scenes
        if s["shoot_day"] != d.affected_day
        and s["scene_id"] not in case.affected_scene_ids
        and (s["is_cover_scene"] or (
            d.affected_cast_id and d.affected_cast_id not in s["required_cast"]
        ))
    ]
    if affected and target_day is not None and target_day != d.affected_day:
        changes = [mk_change(s, target_day) for s in affected]
        pulled = []
        for s in cover_pool[: max(1, len(affected))]:
            if s["shoot_day"] != d.affected_day:
                pulled.append(mk_change(s, d.affected_day))
        day_dir = "later" if target_day > d.affected_day else "earlier"
        options.append(RecoveryOption(
            option_id="option_a",
            name="Shoot cover scenes",
            strategy="shoot_cover_scenes",
            description=(
                f"Keep Day {d.affected_day} shooting: pull cover/insert scenes to Day {d.affected_day} and move the "
                f"{len(affected)} affected scene(s) to Day {target_day} ({day_dir} slate)."
            ),
            scene_changes=changes + pulled,
        ))

    # --- Location disruption: move the blocked slate to an available location
    if affected and d.disruption_type == "location_unavailable":
        alternate = next(
            (loc for loc in bundle["locations"]
             if loc["location_id"] != d.affected_location_id
             and any(a["location_id"] == loc["location_id"]
                     and a["shoot_day"] == d.affected_day and a["available"]
                     for a in bundle["location_availability"])),
            None,
        )
        if alternate:
            options.append(RecoveryOption(
                option_id="option_location",
                name="Move to alternate location",
                strategy="swap_locations",
                description=(
                    f"Move the {len(affected)} blocked scene(s) to {alternate['name']} "
                    f"on Day {d.affected_day} while keeping the unit shooting."
                ),
                scene_changes=[mk_change(s, d.affected_day, alternate["location_id"]) for s in affected],
            ))

    # --- Option B: full day swap (company move) ---
    if target_day is not None and target_day != d.affected_day:
        day_a_scenes = [s for s in scenes if s["shoot_day"] == d.affected_day]
        day_b_scenes = [s for s in scenes if s["shoot_day"] == target_day]
        if day_a_scenes and day_b_scenes:
            changes = [mk_change(s, target_day) for s in day_a_scenes]
            changes += [mk_change(s, d.affected_day) for s in day_b_scenes]
            options.append(RecoveryOption(
                option_id="option_b",
                name="Swap shoot days",
                strategy="swap_locations",
                description=(
                    f"Full company move: swap the entire Day {d.affected_day} slate with "
                    f"Day {target_day}, shooting Day {target_day} material on Day {d.affected_day}."
                ),
                scene_changes=changes,
            ))

    # --- Option C: wait / hold for the resource ---
    if affected and target_day is not None and target_day != d.affected_day:
        wait_strategy = "wait_for_actor" if d.disruption_type in (
            "lead_actor_unavailable", "supporting_actor_unavailable"
        ) else "move_to_later_day"
        wait_name = "Wait for actor" if wait_strategy == "wait_for_actor" else "Move to later day"
        options.append(RecoveryOption(
            option_id="option_c",
            name=wait_name,
            strategy=wait_strategy,
            description=(
                f"Hold the unit and absorb the delay: affected scenes stay grouped and shift to "
                f"Day {target_day}, accepting idle-crew cost on Day {d.affected_day}."
            ),
            scene_changes=[mk_change(s, target_day) for s in affected],
        ))

    # Keep 2-4 options
    return options[:4]


async def polish_descriptions(case: CaseState, options: List[RecoveryOption], bundle: Dict[str, Any]) -> None:
    """One short structured Gemini call to make option descriptions producer-grade."""
    try:
        prompt = (
            "You are the Schedule Optimizer agent for a film production recovery system. "
            f"Production: {bundle['production']['title']}. "
            f"Disruption: {case.disruption.disruption_type} on Day {case.disruption.affected_day}. "
            "Rewrite each option description in ONE crisp sentence. "
            "Return JSON array [{\"option_id\": str, \"description\": str}] for: "
            + "; ".join(f"{o.option_id}: {o.name} — {o.description}" for o in options)
        )
        data = await gemini_client.generate_json(prompt, timeout=5.0, max_tokens=256)
        if isinstance(data, list):
            by_id = {o.option_id: o for o in options}
            for item in data:
                oid = item.get("option_id")
                desc = (item.get("description") or "").strip()
                if oid in by_id and 20 < len(desc) < 400:
                    by_id[oid].description = desc
    except Exception as exc:  # noqa: BLE001
        logger.warning("description polish skipped: %s", exc)


# ---------------------------------------------------------------------------
# ADK Tool & Agent Wrappers
# ---------------------------------------------------------------------------
async def generate_recovery_options_tool(
    production_id: str,
    disruption_type: str,
    affected_day: int,
    affected_cast_id: Optional[str] = None,
    affected_location_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Generates candidate schedule recovery options based on the active production schedule and disruption.

    Args:
        production_id: Production identifier.
        disruption_type: Disruption classification.
        affected_day: Disrupted shoot day index (1-based).
        affected_cast_id: ID of disrupted cast member if applicable.
        affected_location_id: ID of disrupted location if applicable.
    """
    bundle = await clickhouse_client.get_current_schedule(production_id)
    if bundle is None:
        return []
    from models import DisruptionReport, new_case
    report = DisruptionReport(
        production_id=production_id,
        disruption_type=disruption_type,
        affected_day=affected_day,
        affected_cast_id=affected_cast_id,
        affected_location_id=affected_location_id,
        reported_by="ADK Tool",
    )
    case = new_case(report)
    opts = generate_schedule_options(case, bundle)
    await polish_descriptions(case, opts, bundle)
    return [o.model_dump() for o in opts]


schedule_optimizer_tool = FunctionTool(generate_recovery_options_tool)


def create_schedule_optimizer_agent(model_name: Optional[str] = None) -> Agent:
    """Instantiate the ADK Schedule Optimizer Agent."""
    model = model_name or os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    return Agent(
        name="schedule_optimizer_agent",
        model=model,
        instruction=(
            "You are the Schedule Optimizer Agent for the Continuity Council. "
            "Execute the `generate_recovery_options_tool` to formulate viable candidate recovery options "
            "(cover scene pull, company moves, holds) for production disruptions."
        ),
        tools=[schedule_optimizer_tool],
    )
