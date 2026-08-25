"""Natural-Language Disruption Parser.

Converts free-text incident descriptions like:
  "Sarah broke her wrist, can't shoot Tuesday"
into strictly-typed, pre-filled disruption form payloads:
  {
    "disruption_type": "lead_actor_unavailable",
    "severity": "high",
    "affected_day": 2,
    "affected_date": "2026-08-25",
    "affected_cast_id": "lead_001",
    "affected_cast_name": "Mara Voss",
    "confidence": "high",
    "reasoning": "..."
  }

Features:
- Calendar-aware relative day resolution (weekdays, Day N, relative phrases).
- Fuzzy cast and location entity matching against ClickHouse production bundles.
- Gemini 3.6-flash structured JSON reasoning with 7.5s hard timeout.
- Instant heuristic fallback engine if Gemini times out, throws, or quota is hit.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from services import clickhouse_client, gemini_client

logger = logging.getLogger("continuity.nl_parser")

WEEKDAY_MAP = [
    ("monday", 0),
    ("tuesday", 1),
    ("wednesday", 2),
    ("thursday", 3),
    ("friday", 4),
    ("saturday", 5),
    ("sunday", 6),
    ("mon", 0),
    ("tue", 1),
    ("tues", 1),
    ("wed", 2),
    ("thu", 3),
    ("thur", 3),
    ("thurs", 3),
    ("fri", 4),
    ("sat", 5),
    ("sun", 6),
]


def parse_iso_date(date_str: str) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def resolve_day_and_date(
    text: str,
    start_date_str: str = "2026-08-24",
    total_shoot_days: int = 30,
) -> Tuple[int, str]:
    """Resolve day number (1-based) and ISO date string from free text and shoot calendar."""
    base_date = parse_iso_date(start_date_str) or date(2026, 8, 24)
    lower = text.lower()

    # 1. Explicit "Day N" or "day-N"
    day_match = re.search(r"\bday\s*[-_#]?\s*(\d+)\b", lower)
    if day_match:
        day_num = int(day_match.group(1))
        day_num = max(1, min(day_num, total_shoot_days))
        target_date = base_date + timedelta(days=day_num - 1)
        return day_num, target_date.isoformat()

    # 2. Relative phrases
    if "today" in lower or "this morning" in lower or "tonight" in lower:
        return 1, base_date.isoformat()
    if "tomorrow" in lower:
        target_date = base_date + timedelta(days=1)
        return 2, target_date.isoformat()
    if "next week" in lower:
        target_date = base_date + timedelta(days=7)
        return 8, target_date.isoformat()

    # 3. Weekdays ("Tuesday", "next Tuesday", etc.)
    for name, target_wd in WEEKDAY_MAP:
        pattern = r"\b" + name + r"\b"
        if re.search(pattern, lower):
            is_next = "next " + name in lower
            base_wd = base_date.weekday()
            diff = (target_wd - base_wd) % 7
            if diff == 0 and is_next:
                diff = 7
            elif is_next and diff < 7:
                diff += 7
            target_date = base_date + timedelta(days=diff)
            day_num = diff + 1
            day_num = max(1, min(day_num, total_shoot_days))
            return day_num, target_date.isoformat()

    # 4. Explicit ISO date "YYYY-MM-DD"
    iso_match = re.search(r"\b(202\d-\d{2}-\d{2})\b", lower)
    if iso_match:
        d = parse_iso_date(iso_match.group(1))
        if d:
            day_num = (d - base_date).days + 1
            day_num = max(1, min(day_num, total_shoot_days))
            return day_num, d.isoformat()

    # Default to Day 1
    return 1, base_date.isoformat()


def resolve_entity(
    text: str,
    cast_members: List[Dict[str, Any]],
    locations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Fuzzy match cast member or location from text against production metadata."""
    lower = text.lower()

    # 1. Cast matching
    for cast in cast_members:
        name = str(cast.get("name", "")).lower()
        cast_id = str(cast.get("cast_id", "")).lower()
        if not name:
            continue

        parts = name.split()
        first_name = parts[0] if parts else name
        last_name = parts[-1] if len(parts) > 1 else ""

        if (
            name in lower
            or cast_id in lower
            or (len(first_name) >= 3 and first_name in lower)
            or (len(last_name) >= 3 and last_name in lower)
        ):
            return {
                "entity_type": "cast",
                "cast_id": cast.get("cast_id", ""),
                "cast_name": cast.get("name", ""),
                "role_type": cast.get("role_type", "supporting"),
            }

    # 2. Location matching
    for loc in locations:
        name = str(loc.get("name", "")).lower()
        loc_id = str(loc.get("location_id", "")).lower()
        loc_type = str(loc.get("location_type", "")).lower()
        if not name:
            continue

        keywords = [w for w in name.split() if len(w) >= 3]
        if name in lower or loc_id in lower or any(k in lower for k in keywords):
            return {
                "entity_type": "location",
                "location_id": loc.get("location_id", ""),
                "location_name": loc.get("name", ""),
                "location_type": loc_type,
            }

    # Fallback to general
    return {"entity_type": "unknown"}


def classify_disruption_heuristic(
    text: str,
    entity: Dict[str, Any],
) -> Tuple[str, str]:
    """Classify disruption type and severity using deterministic heuristics."""
    lower = text.lower()

    # Severity detection
    severity = "medium"
    if any(w in lower for w in ["broke", "hospital", "fracture", "revoked", "emergency", "destroyed", "storm", "hurricane", "flood", "critical", "urgent"]):
        severity = "high"
    elif any(w in lower for w in ["slight", "minor", "brief", "running late", "mild", "drizzle"]):
        severity = "low"

    # Type detection
    if any(w in lower for w in ["storm", "rain", "snow", "weather", "flood", "lightning", "hurricane", "blizzard", "wind"]):
        return "weather_delay", severity

    if any(w in lower for w in ["permit", "license", "revoked", "city council", "zoning", "authorities"]):
        return "permit_issue", severity

    if any(w in lower for w in ["camera", "audio", "mic", "generator", "lens", "drone", "crane", "sensor", "equipment", "hardware"]):
        return "equipment_failure", severity

    if entity.get("entity_type") == "cast":
        role = entity.get("role_type", "supporting").lower()
        if role == "lead":
            return "lead_actor_unavailable", severity
        return "supporting_actor_unavailable", severity

    if entity.get("entity_type") == "location":
        return "location_unavailable", severity

    # Keyword fallbacks
    if any(w in lower for w in ["actor", "actress", "cast", "star", "lead", "wrist", "sick", "covid", "fever", "ill", "injury", "injured"]):
        return "lead_actor_unavailable", severity

    if any(w in lower for w in ["location", "stage", "set", "harbor", "studio", "loft", "warehouse", "closed", "locked"]):
        return "location_unavailable", severity

    return "lead_actor_unavailable", severity


async def parse_disruption(
    description: str,
    production_id: str = "prod_001",
) -> Dict[str, Any]:
    """Parse a free-form natural language disruption description into structured case fields."""
    desc = (description or "").strip()
    if not desc:
        return {
            "confidence": "low",
            "error": "Empty disruption description provided",
            "parsed": None,
        }

    # Fetch production bundle
    bundle = None
    try:
        bundle = await clickhouse_client.fetch_production_bundle(production_id)
    except Exception as exc:
        logger.warning("Failed to fetch bundle for NL parse: %s", exc)

    prod_info = (bundle or {}).get("production", {})
    start_date_str = str(prod_info.get("start_date", "2026-08-24"))
    total_days = int(prod_info.get("total_shoot_days", 30))
    cast_list = (bundle or {}).get("cast_members", [])
    loc_list = (bundle or {}).get("locations", [])
    scenes = (bundle or {}).get("scenes", [])

    # Step 1: Base heuristic resolution
    day_num, iso_date = resolve_day_and_date(desc, start_date_str, total_days)
    entity = resolve_entity(desc, cast_list, loc_list)
    heuristic_type, heuristic_sev = classify_disruption_heuristic(desc, entity)

    ai_parsed = None
    reasoning = f"Parsed '{desc}'"

    # Step 2: Gemini JSON Enhancement (if available and within SLA)
    if gemini_client.is_configured() and not gemini_client.quota_hit():
        cast_names = ", ".join(f"{c.get('name')} ({c.get('role_type')}, ID: {c.get('cast_id')})" for c in cast_list[:8])
        loc_names = ", ".join(f"{l.get('name')} (ID: {l.get('location_id')})" for l in loc_list[:8])

        prompt = (
            "You are an assistant for a film production continuity council. "
            "Analyze this natural-language incident description and extract structured case details.\n\n"
            f"Description: \"{desc}\"\n"
            f"Production Shoot Start Date: {start_date_str}, Total Days: {total_days}\n"
            f"Cast: {cast_names}\n"
            f"Locations: {loc_names}\n"
            "Valid disruption types: [lead_actor_unavailable, supporting_actor_unavailable, location_unavailable, equipment_failure, weather_delay, permit_issue]\n"
            "Valid severity: [low, medium, high]\n\n"
            "Return JSON matching this exact schema:\n"
            "{\n"
            "  \"disruption_type\": \"lead_actor_unavailable\",\n"
            "  \"severity\": \"high\",\n"
            "  \"entity_mention\": \"entity or person name mentioned\",\n"
            "  \"day_mention\": \"e.g. Tuesday or Day 2\",\n"
            "  \"reasoning\": \"1 sentence explaining the disruption\"\n"
            "}"
        )

        try:
            data = await asyncio.wait_for(
                gemini_client.generate_json(prompt, timeout=7.5, max_tokens=256),
                timeout=8.0,
            )
            if isinstance(data, dict):
                ai_parsed = data
        except Exception as exc:
            logger.info("Gemini NL parse fallback to heuristics: %s", exc)

    # Reconcile AI output with grounded calendar and entities
    final_type = heuristic_type
    final_sev = heuristic_sev

    if ai_parsed:
        cand_type = str(ai_parsed.get("disruption_type", "")).strip()
        if cand_type in [
            "lead_actor_unavailable", "supporting_actor_unavailable",
            "location_unavailable", "equipment_failure",
            "weather_delay", "permit_issue",
        ]:
            final_type = cand_type

        cand_sev = str(ai_parsed.get("severity", "")).strip().lower()
        if cand_sev in ["low", "medium", "high"]:
            final_sev = cand_sev

        day_mention = str(ai_parsed.get("day_mention", "")).strip()
        if day_mention:
            day_num, iso_date = resolve_day_and_date(day_mention, start_date_str, total_days)

        entity_mention = str(ai_parsed.get("entity_mention", "")).strip()
        if entity_mention:
            resolved_ai_entity = resolve_entity(entity_mention, cast_list, loc_list)
            if resolved_ai_entity.get("entity_type") != "unknown":
                entity = resolved_ai_entity

        if ai_parsed.get("reasoning"):
            reasoning = str(ai_parsed["reasoning"]).strip()

    # Determine affected cast or location ID
    affected_cast_id = ""
    affected_cast_name = ""
    affected_loc_id = ""
    affected_loc_name = ""

    if entity.get("entity_type") == "cast":
        affected_cast_id = entity.get("cast_id", "")
        affected_cast_name = entity.get("cast_name", "")
        if not final_type.startswith("lead") and not final_type.startswith("supp"):
            final_type = "lead_actor_unavailable" if entity.get("role_type") == "lead" else "supporting_actor_unavailable"
    elif entity.get("entity_type") == "location":
        affected_loc_id = entity.get("location_id", "")
        affected_loc_name = entity.get("location_name", "")
        if final_type not in ("location_unavailable", "permit_issue"):
            final_type = "location_unavailable"
    else:
        # Default prefill for form readiness
        if final_type in ("lead_actor_unavailable", "supporting_actor_unavailable") and cast_list:
            lead = next((c for c in cast_list if c.get("role_type") == "lead"), cast_list[0])
            affected_cast_id = lead.get("cast_id", "")
            affected_cast_name = lead.get("name", "")
        elif final_type in ("location_unavailable", "permit_issue") and loc_list:
            affected_loc_id = loc_list[0].get("location_id", "")
            affected_loc_name = loc_list[0].get("name", "")

    # Match affected scene IDs on that shoot day
    affected_scenes = [
        s.get("scene_id", "")
        for s in scenes
        if int(s.get("shoot_day", 0)) == day_num
        and (
            (affected_cast_id and affected_cast_id in s.get("required_cast", []))
            or (affected_loc_id and affected_loc_id == s.get("location_id", ""))
            or (not affected_cast_id and not affected_loc_id)
        )
    ]

    # Calculate confidence
    confidence = "high"
    if (final_type.startswith("lead") or final_type.startswith("supp")) and not affected_cast_id:
        confidence = "medium"
    elif final_type == "location_unavailable" and not affected_loc_id:
        confidence = "medium"

    return {
        "confidence": confidence,
        "disruption_type": final_type,
        "severity": final_sev,
        "affected_day": day_num,
        "affected_date": iso_date,
        "affected_cast_id": affected_cast_id,
        "affected_cast_name": affected_cast_name,
        "affected_location_id": affected_loc_id,
        "affected_location_name": affected_loc_name,
        "notes": desc,
        "scene_ids": affected_scenes,
        "reasoning": reasoning,
    }
