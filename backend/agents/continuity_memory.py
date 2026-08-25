"""Continuity Memory Agent (ADK Agent).

Deterministic continuity-risk detection over scene dependencies, continuity
tags (costume/emotional state) and narrative order, plus an optional Gemini
polish pass for producer-readable risk language.
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

from models import CaseState, ContinuityRisk, RecoveryOption
from services import gemini_client

logger = logging.getLogger("continuity.agents.continuity")


def _apply_changes(scenes: List[Dict[str, Any]], option: RecoveryOption) -> Dict[str, Dict[str, Any]]:
    projected = {s["scene_id"]: dict(s) for s in scenes}
    for ch in option.scene_changes:
        if ch.scene_id in projected:
            projected[ch.scene_id]["shoot_day"] = ch.to_day
            if ch.to_location:
                projected[ch.scene_id]["location_id"] = ch.to_location
    return projected


def validate_continuity(option: RecoveryOption, scenes: List[Dict[str, Any]]) -> None:
    """TRD Tool 4: `validate_continuity` — continuity risks + continuity_risk_score."""
    projected = _apply_changes(scenes, option)
    risks: List[ContinuityRisk] = []
    score = 0.08  # base risk of any schedule surgery

    moved_ids = {c.scene_id for c in option.scene_changes}

    # 1) Dependency order violations (scene shot before its prerequisite)
    for s in projected.values():
        for dep in s["depends_on"]:
            dep_scene = projected.get(dep)
            if dep_scene and dep_scene["shoot_day"] > s["shoot_day"]:
                risks.append(ContinuityRisk(
                    scene_ids=[dep, s["scene_id"]],
                    risk=(
                        f"{s['scene_id']} now shoots before its prerequisite {dep}: "
                        "narrative order breaks."
                    ),
                    level="high",
                ))
                score += 0.25

    # 2) Shared continuity tags split across days (costume/emotional state)
    tag_map: Dict[str, List[str]] = {}
    for s in projected.values():
        for tag in s["continuity_tags"]:
            tag_map.setdefault(tag, []).append(s["scene_id"])
    for tag, ids in tag_map.items():
        if len(ids) < 2:
            continue
        days = {projected[i]["shoot_day"] for i in ids}
        originally = {next(x["shoot_day"] for x in scenes if x["scene_id"] == i) for i in ids}
        if len(days) > len(originally) and any(i in moved_ids for i in ids):
            risks.append(ContinuityRisk(
                scene_ids=sorted(ids),
                risk=(
                    f"Scenes sharing '{tag.replace('_', ' ')}' continuity are now split across "
                    f"days {sorted(days)}: wardrobe/state matching required."
                ),
                level="medium",
            ))
            score += 0.12

    # 3) Any moved scene with continuity tags carries residual risk
    tagged_moves = [c.scene_id for c in option.scene_changes
                    if projected.get(c.scene_id, {}).get("continuity_tags")]
    if tagged_moves and not risks:
        risks.append(ContinuityRisk(
            scene_ids=tagged_moves,
            risk="Moved scenes carry continuity tags; script supervisor re-check advised.",
            level="low",
        ))
        score += 0.05

    if not option.scene_changes:
        score = 0.05

    option.continuity_risks = risks[:4]
    option.continuity_risk_score = round(min(0.9, score), 2)


# ---------------------------------------------------------------------------
# ADK Tool & Agent Wrappers
# ---------------------------------------------------------------------------
async def evaluate_continuity_risks_tool(
    options: List[Dict[str, Any]],
    scenes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Validates narrative dependency order and wardrobe/costume continuity for recovery options.

    Args:
        options: List of serialized RecoveryOption dicts to validate.
        scenes: List of serialized production scene dicts containing dependencies and continuity tags.
    """
    option_models = [RecoveryOption(**o) for o in options]
    for opt in option_models:
        validate_continuity(opt, scenes)
    flagged = sum(len(o.continuity_risks) for o in option_models)
    return {
        "flagged_count": flagged,
        "summary": f"Flagged {flagged} continuity risk(s) across {len(option_models)} options",
        "evaluated_options": [o.model_dump() for o in option_models],
    }


continuity_memory_tool = FunctionTool(evaluate_continuity_risks_tool)


def create_continuity_memory_agent(model_name: Optional[str] = None) -> Agent:
    """Instantiate the ADK Continuity Memory Agent."""
    model = model_name or os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    return Agent(
        name="continuity_memory_agent",
        model=model,
        instruction=(
            "You are the Continuity Memory Agent for the Continuity Council film recovery system. "
            "Execute the `evaluate_continuity_risks_tool` to check for narrative sequence violations, "
            "costume/makeup continuity breaks, and emotional continuity integrity."
        ),
        tools=[continuity_memory_tool],
    )


# ---------------------------------------------------------------------------
# Orchestrator Compatibility Entry Point
# ---------------------------------------------------------------------------
async def run(case: CaseState, options: List[RecoveryOption], bundle: Dict[str, Any]) -> str:
    scenes = bundle["scenes"]
    for option in options:
        validate_continuity(option, scenes)

    flagged = sum(len(o.continuity_risks) for o in options)
    return f"Flagged {flagged} continuity risk(s) across {len(options)} options"
