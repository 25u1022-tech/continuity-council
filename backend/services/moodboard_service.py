"""Imagen 3 Mood-Board Service.

Provides on-demand cinematic visual previews for alternate locations:
- Generates rich film-still prompts from location & scene attributes
- Native Google GenAI SDK Imagen 3 generation (`imagen-3.0-generate-002`)
- 24-hour dual-tier cache (in-memory LRU + disk cache)
- Strict 8-second hard timeout; zero overhead on recovery investigation SLA
- Graceful 202 "unavailable" fallback on quota exhaustion or error
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from services import clickhouse_client, gemini_client

logger = logging.getLogger("continuity.moodboard")

DEFAULT_IMAGEN_MODEL = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
CACHE_TTL_SECONDS = 24 * 3600  # 24 hours
CACHE_DIR = Path(__file__).parent.parent / ".cache" / "moodboards"

# In-memory LRU cache: location_id -> {image_base64, prompt, location_name, created_at, expires_at}
_MEMORY_CACHE: Dict[str, Dict[str, Any]] = {}


def _ensure_cache_dir() -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.debug("Could not create disk cache dir: %s", exc)


def build_prompt(
    location: Dict[str, Any],
    scene: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a cinematic film-still prompt from location and scene metadata."""
    name = str(location.get("name") or "Filming Location").strip()
    loc_type = str(location.get("location_type") or "exterior").lower()
    notes = str(location.get("notes") or "").strip()

    # Determine lighting/time of day from scene if available
    time_of_day = "golden hour"
    scene_env = ""
    if scene:
        dn = str(scene.get("day_night") or "").upper()
        if "NIGHT" in dn:
            time_of_day = "atmospheric cinematic night with practical lighting and neon reflections"
        elif "DUSK" in dn or "DAWN" in dn:
            time_of_day = "blue hour with dramatic horizon gradients"
        else:
            time_of_day = "cinematic golden hour with diffused natural daylight"

        desc = str(scene.get("description") or scene.get("scene_title") or "").strip()
        if desc:
            scene_env = f", context: {desc}"

    setting_desc = f"{name} ({loc_type})"
    if notes:
        setting_desc += f", {notes}"

    prompt = (
        f"Cinematic film still, 35mm motion picture photography, Panavision anamorphic lens. "
        f"Wide establishing shot of {setting_desc}{scene_env}. "
        f"Atmosphere: {time_of_day}. "
        f"Masterful production design, authentic textures, volumetric haze, photorealistic depth of field, 8k resolution. "
        f"No text, no watermarks, no subtitles, no close-up people, no logos."
    )
    return prompt


def _get_from_cache(location_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve moodboard from memory or disk cache if not expired."""
    now = time.time()

    # 1. Check in-memory cache
    if location_id in _MEMORY_CACHE:
        entry = _MEMORY_CACHE[location_id]
        if now < entry.get("expires_at", 0):
            return entry
        # Expired
        _MEMORY_CACHE.pop(location_id, None)

    # 2. Check disk cache
    _ensure_cache_dir()
    disk_file = CACHE_DIR / f"{location_id}.json"
    if disk_file.exists():
        try:
            with open(disk_file, "r", encoding="utf-8") as f:
                entry = json.load(f)
            if now < entry.get("expires_at", 0):
                # Repopulate memory cache
                _MEMORY_CACHE[location_id] = entry
                return entry
            # Expired on disk
            disk_file.unlink(missing_ok=True)
        except Exception as exc:
            logger.debug("Disk cache read error for %s: %s", location_id, exc)

    return None


def _save_to_cache(location_id: str, entry: Dict[str, Any]) -> None:
    """Save moodboard entry to memory and disk cache."""
    _MEMORY_CACHE[location_id] = entry

    _ensure_cache_dir()
    disk_file = CACHE_DIR / f"{location_id}.json"
    try:
        with open(disk_file, "w", encoding="utf-8") as f:
            json.dump(entry, f)
    except Exception as exc:
        logger.debug("Disk cache write error for %s: %s", location_id, exc)


async def generate_moodboard(
    location_id: str,
    location: Optional[Dict[str, Any]] = None,
    scene: Optional[Dict[str, Any]] = None,
    timeout: float = 8.0,
) -> Optional[Dict[str, Any]]:
    """Generate or retrieve a cached Imagen 3 moodboard image for a location.

    Returns:
        Dict with keys: {image_base64, prompt, location_name, cached: bool} or None on failure.
    """
    # 1. Check cache first
    cached_entry = _get_from_cache(location_id)
    if cached_entry:
        logger.info("Moodboard cache HIT for location %s", location_id)
        return {
            "status": "ready",
            "location_id": location_id,
            "location_name": cached_entry.get("location_name", "Location"),
            "image_base64": cached_entry.get("image_base64", ""),
            "prompt": cached_entry.get("prompt", ""),
            "cached": True,
        }

    # 2. If location details not passed, query ClickHouse
    loc_meta = location or {}
    if not loc_meta and clickhouse_client.is_configured():
        try:
            bundle = await clickhouse_client.fetch_production_bundle("prod_001")
            for l in (bundle or {}).get("locations", []):
                if l.get("location_id") == location_id or l.get("name", "").lower() == location_id.lower():
                    loc_meta = l
                    break
        except Exception as exc:
            logger.warning("Failed to fetch location bundle for %s: %s", location_id, exc)

    location_name = loc_meta.get("name") or location_id.replace("_", " ").title()
    prompt = build_prompt(loc_meta or {"name": location_name}, scene)

    # 3. Check if Gemini client is configured
    if not gemini_client.is_configured() or gemini_client.quota_hit():
        logger.warning("Gemini / Imagen API unavailable or quota active for moodboard generation")
        return None

    # 4. Generate with Imagen 3 via Google GenAI SDK (8s hard timeout)
    logger.info("Generating Imagen 3 moodboard for location %s (model: %s)", location_id, DEFAULT_IMAGEN_MODEL)
    try:
        from google.genai import types

        client = gemini_client._get_client()

        # Call Imagen generation asynchronously
        response = await asyncio.wait_for(
            client.aio.models.generate_images(
                model=DEFAULT_IMAGEN_MODEL,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    output_mime_type="image/jpeg",
                    aspect_ratio="16:9",
                ),
            ),
            timeout=timeout,
        )

        if not response or not getattr(response, "generated_images", None):
            logger.warning("Imagen returned empty generated_images list for %s", location_id)
            return None

        first_img = response.generated_images[0]
        raw_bytes = first_img.image.image_bytes
        if not raw_bytes:
            logger.warning("Imagen generated image contained no bytes for %s", location_id)
            return None

        b64_str = base64.b64encode(raw_bytes).decode("utf-8")

        # 5. Cache the generated image
        now = time.time()
        entry = {
            "location_id": location_id,
            "location_name": location_name,
            "image_base64": b64_str,
            "prompt": prompt,
            "created_at": now,
            "expires_at": now + CACHE_TTL_SECONDS,
        }
        _save_to_cache(location_id, entry)

        return {
            "status": "ready",
            "location_id": location_id,
            "location_name": location_name,
            "image_base64": b64_str,
            "prompt": prompt,
            "cached": False,
        }

    except asyncio.TimeoutError:
        logger.warning("Imagen 3 generation timed out after %.1fs for location %s", timeout, location_id)
        return None
    except Exception as exc:
        logger.warning("Imagen 3 generation failed for location %s: %s", location_id, exc)
        return None
