"""Scene generator for newly-onboarded productions.

Given a production's cast, locations and shoot-day span, produce ~10 scenes for
the shooting schedule. Uses Gemini (official google-genai SDK) for creative,
context-aware titles/structure, with a deterministic fallback that always
returns a valid, availability-respecting schedule (the demo never breaks even
when the Gemini free-tier quota is exhausted).

Each returned scene is a dict shaped for continuity_council.production_schedule:
  scene_id, scene_title, shoot_day, sequence_order, location_id, required_cast,
  scene_type, is_cover_scene, priority, continuity_tags, depends_on, status
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from models import short_id
from services import gemini_client

logger = logging.getLogger("continuity.scene_generator")

TARGET_SCENES = 10
SCENE_TYPES = ["interior", "exterior", "dialogue", "action", "establishing"]


def _available_on(entity: Dict[str, Any], day: int) -> bool:
    days = entity.get("available_days") or []
    return (not days) or (day in days)


def _first_name(full: str) -> str:
    return (full or "").strip().split(" ")[0] or full


# ---------------------------------------------------------------------------
# Deterministic fallback (always valid)
# ---------------------------------------------------------------------------
def _deterministic_scenes(
    days: List[int],
    cast: List[Dict[str, Any]],
    locations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    scenes: List[Dict[str, Any]] = []
    leads = [c for c in cast if str(c.get("role_type", "")).lower() == "lead"]
    non_leads = [c for c in cast if c not in leads]

    title_templates = [
        "{loc}: opening beat",
        "{loc}: the confrontation",
        "{lead} makes a choice",
        "{loc}: quiet aftermath",
        "Chase through {loc}",
        "{lead} and {other}",
        "Night work at {loc}",
        "{loc}: the reveal",
        "Turning point",
        "The reckoning",
    ]

    for i in range(TARGET_SCENES):
        day = days[i % len(days)]

        # Location available that day (fall back to any)
        day_locs = [l for l in locations if _available_on(l, day)] or locations
        loc = day_locs[i % len(day_locs)]

        # Cast available that day; prefer including a lead
        day_cast = [c for c in cast if _available_on(c, day)] or cast
        chosen: List[Dict[str, Any]] = []
        day_leads = [c for c in day_cast if c in leads]
        if day_leads:
            chosen.append(day_leads[i % len(day_leads)])
        for c in day_cast:
            if c not in chosen and len(chosen) < 2:
                chosen.append(c)
        if not chosen and day_cast:
            chosen = [day_cast[0]]

        lead_name = _first_name(chosen[0]["name"]) if chosen else "The lead"
        other_name = _first_name(chosen[1]["name"]) if len(chosen) > 1 else "the crew"
        title = title_templates[i % len(title_templates)].format(
            loc=loc["name"], lead=lead_name, other=other_name
        )

        scenes.append({
            "scene_title": title,
            "shoot_day": day,
            "location_id": loc["location_id"],
            "required_cast": [c["cast_id"] for c in chosen],
            "scene_type": SCENE_TYPES[i % len(SCENE_TYPES)],
            "is_cover_scene": 0,
            "priority": 2 if i % 3 == 0 else 3,
        })

    # Guarantee one cover scene on the last day (recovery flows rely on it)
    last_day = days[-1]
    cover_locs = [l for l in locations if _available_on(l, last_day)] or locations
    cover_cast = [c for c in non_leads if _available_on(c, last_day)] or \
                 [c for c in cast if _available_on(c, last_day)] or cast
    scenes[-1] = {
        "scene_title": f"Cover set: {cover_locs[0]['name']} inserts & B-roll",
        "shoot_day": last_day,
        "location_id": cover_locs[0]["location_id"],
        "required_cast": [cover_cast[0]["cast_id"]] if cover_cast else [],
        "scene_type": "cover",
        "is_cover_scene": 1,
        "priority": 4,
    }
    return scenes


# ---------------------------------------------------------------------------
# Gemini mapping / validation
# ---------------------------------------------------------------------------
def _coerce_llm_scenes(
    raw: Any,
    days: List[int],
    cast: List[Dict[str, Any]],
    locations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Map free-form Gemini scenes onto valid ids/days. Raises on unusable input."""
    if isinstance(raw, dict):
        raw = raw.get("scenes") or raw.get("items") or raw.get("data")
    if not isinstance(raw, list) or not raw:
        raise ValueError("Gemini returned no scene list")

    name_to_loc = {l["name"].strip().lower(): l for l in locations}
    name_to_cast = {c["name"].strip().lower(): c for c in cast}
    default_loc = locations[0]
    max_day = days[-1]

    out: List[Dict[str, Any]] = []
    for item in raw[:TARGET_SCENES + 2]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("scene_title") or "").strip()[:160]
        if not title:
            continue

        try:
            day = int(item.get("day") or item.get("shoot_day") or 1)
        except (TypeError, ValueError):
            day = 1
        day = min(max(day, 1), max_day)

        loc_name = str(item.get("location") or item.get("location_name") or "").strip().lower()
        loc = name_to_loc.get(loc_name)
        if loc is None or not _available_on(loc, day):
            avail = [l for l in locations if _available_on(l, day)]
            loc = (avail or [default_loc])[len(out) % len(avail or [default_loc])]

        cast_field = item.get("cast") or item.get("required_cast") or []
        if isinstance(cast_field, str):
            cast_field = [x.strip() for x in cast_field.split(",")]
        req: List[str] = []
        for nm in cast_field:
            m = name_to_cast.get(str(nm).strip().lower())
            if m and _available_on(m, day) and m["cast_id"] not in req:
                req.append(m["cast_id"])
        if not req:
            avail_cast = [c for c in cast if _available_on(c, day)] or cast
            if avail_cast:
                req = [avail_cast[len(out) % len(avail_cast)]["cast_id"]]

        stype = str(item.get("scene_type") or item.get("type") or "interior").strip().lower()
        is_cover = 1 if (stype == "cover" or bool(item.get("is_cover_scene"))) else 0
        if stype not in SCENE_TYPES and not is_cover:
            stype = "interior"

        out.append({
            "scene_title": title,
            "shoot_day": day,
            "location_id": loc["location_id"],
            "required_cast": req,
            "scene_type": "cover" if is_cover else stype,
            "is_cover_scene": is_cover,
            "priority": int(item.get("priority") or 3) if str(item.get("priority") or "3").isdigit() else 3,
        })

    if len(out) < 4:
        raise ValueError("Gemini produced too few usable scenes")

    # Ensure at least one cover scene exists
    if not any(s["is_cover_scene"] for s in out):
        last_day = days[-1]
        cover_locs = [l for l in locations if _available_on(l, last_day)] or locations
        out[-1]["scene_type"] = "cover"
        out[-1]["is_cover_scene"] = 1
        out[-1]["priority"] = 4
        out[-1]["location_id"] = cover_locs[0]["location_id"]
    return out


async def generate_scenes(
    name: str,
    director: str,
    days: List[int],
    cast: List[Dict[str, Any]],
    locations: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], str]:
    """Return (scenes, llm_mode) where llm_mode is 'gemini' or 'deterministic'.

    `cast` items: {cast_id, name, role_type, available_days}
    `locations` items: {location_id, name, location_type, available_days}
    """
    llm_mode = "deterministic"
    scenes: List[Dict[str, Any]] = []

    if gemini_client.is_configured() and cast and locations:
        cast_desc = "; ".join(
            f"{c['name']} ({c.get('role_type', 'supporting')}, days "
            f"{c.get('available_days') or 'all'})" for c in cast
        )
        loc_desc = "; ".join(
            f"{l['name']} ({l.get('location_type', 'interior')}, days "
            f"{l.get('available_days') or 'all'})" for l in locations
        )
        prompt = (
            "You are a film first assistant director building a shooting schedule. "
            f"Production: '{name}'"
            + (f", directed by {director}." if director else ".")
            + f" Shoot spans {len(days)} day(s): {days}. "
            f"Cast: {cast_desc}. Locations: {loc_desc}. "
            f"Create exactly {TARGET_SCENES} scenes that tell a coherent story. "
            "Return JSON: {\"scenes\": [{\"title\": string, \"scene_type\": one of "
            "[interior, exterior, dialogue, action, establishing, cover], "
            "\"location\": must be one of the location names above, "
            "\"cast\": array of cast names from above (only those available on that day), "
            "\"day\": integer within the shoot span}]}. "
            "Only assign a cast member or location to a day they are available. "
            "Include exactly one 'cover' scene (no lead required) so the unit always has fallback work."
        )
        try:
            data = await gemini_client.generate_json(prompt, timeout=40)
            if data is not None:
                scenes = _coerce_llm_scenes(data, days, cast, locations)
                llm_mode = "gemini"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini scene generation unusable, falling back: %s", exc)

    if not scenes:
        scenes = _deterministic_scenes(days, cast, locations)
        llm_mode = "deterministic"

    # Finalize: stable ids + sequence order (sorted by day)
    scenes.sort(key=lambda s: s["shoot_day"])
    finalized: List[Dict[str, Any]] = []
    for i, s in enumerate(scenes, start=1):
        finalized.append({
            "scene_id": f"sc_{i:03d}",
            "scene_title": s["scene_title"],
            "shoot_day": int(s["shoot_day"]),
            "sequence_order": i,
            "location_id": s["location_id"],
            "required_cast": list(s.get("required_cast") or []),
            "scene_type": s["scene_type"],
            "is_cover_scene": int(s.get("is_cover_scene") or 0),
            "priority": int(s.get("priority") or 3),
            "continuity_tags": [],
            "depends_on": [],
            "status": "scheduled",
        })
    logger.info("Generated %d scenes via %s for '%s'", len(finalized), llm_mode, name)
    return finalized, llm_mode
