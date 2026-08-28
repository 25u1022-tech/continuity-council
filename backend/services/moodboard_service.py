"""Dual-Backend Mood-Board Service (Gemini Native Image & Imagen 3).

Provides on-demand cinematic visual previews for alternate locations:
- Generates rich film-still prompts from location & scene attributes
- Default: Gemini native multimodal image generation (`gemini-2.5-flash-image`, `gemini-2.0-flash-preview-image-generation`)
- Optional: Native Google GenAI SDK Imagen 3 generation (`imagen-3.0-generate-002`) via `MOODBOARD_BACKEND=imagen`
- 24-hour dual-tier cache (in-memory LRU + disk cache)
- Serves both metadata JSON and direct binary image bytes (`/api/locations/{id}/moodboard/image`)
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
from typing import Any, Dict, List, Optional, Tuple

from services import clickhouse_client, gemini_client

logger = logging.getLogger("continuity.moodboard")

MOODBOARD_BACKEND = os.getenv("MOODBOARD_BACKEND", "gemini").lower().strip()
DEFAULT_IMAGEN_MODEL = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
DEFAULT_GEMINI_IMAGE_MODELS = ["gemini-2.5-flash-image", "gemini-2.0-flash-preview-image-generation"]
CACHE_TTL_SECONDS = 24 * 3600  # 24 hours
CACHE_DIR = Path(__file__).parent.parent / ".cache" / "moodboards"

# In-memory LRU cache: location_id -> {image_base64, mime, prompt, location_name, created_at, expires_at}
_MEMORY_CACHE: Dict[str, Dict[str, Any]] = {}


def _get_gemini_image_models() -> List[str]:
    custom_model = os.getenv("GEMINI_IMAGE_MODEL", "").strip()
    models: List[str] = []
    if custom_model:
        models.append(custom_model)
    for m in DEFAULT_GEMINI_IMAGE_MODELS:
        if m not in models:
            models.append(m)
    return models


def _ensure_cache_dir() -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.debug("Could not create disk cache dir: %s", exc)


def purge_cache(location_id: Optional[str] = None) -> None:
    """Purge memory and disk cache entries (all or specific location)."""
    global _MEMORY_CACHE
    _ensure_cache_dir()
    if location_id:
        _MEMORY_CACHE.pop(location_id, None)
        (CACHE_DIR / f"{location_id}.json").unlink(missing_ok=True)
    else:
        _MEMORY_CACHE.clear()
        for f in CACHE_DIR.glob("*.json"):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass


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
    """Generate or retrieve a cached moodboard image for a location.

    Supports dual backends via MOODBOARD_BACKEND:
      - "gemini" (default): Gemini native image generation models
      - "imagen": Imagen 3 image generation models

    Returns:
        Dict with keys: {status, location_id, location_name, image_url, image_base64, mime, prompt, cached: bool} or None on failure.
    """
    # 1. Check cache first
    cached_entry = _get_from_cache(location_id)
    if cached_entry:
        logger.info("Moodboard cache HIT for location %s", location_id)
        return {
            "status": "ready",
            "location_id": location_id,
            "location_name": cached_entry.get("location_name", "Location"),
            "image_url": f"/api/locations/{location_id}/moodboard/image",
            "image_base64": cached_entry.get("image_base64", ""),
            "mime": cached_entry.get("mime", "image/jpeg"),
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

    backend = os.getenv("MOODBOARD_BACKEND", MOODBOARD_BACKEND).lower().strip()

    # 4. Imagen backend path (UNTOUCHED Imagen 3 code when MOODBOARD_BACKEND=imagen)
    if backend == "imagen":
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
            mime_type = "image/jpeg"

            # 5. Cache the generated image
            now = time.time()
            entry = {
                "location_id": location_id,
                "location_name": location_name,
                "image_base64": b64_str,
                "mime": mime_type,
                "prompt": prompt,
                "created_at": now,
                "expires_at": now + CACHE_TTL_SECONDS,
            }
            _save_to_cache(location_id, entry)

            return {
                "status": "ready",
                "location_id": location_id,
                "location_name": location_name,
                "image_url": f"/api/locations/{location_id}/moodboard/image",
                "image_base64": b64_str,
                "mime": mime_type,
                "prompt": prompt,
                "cached": False,
            }

        except asyncio.TimeoutError:
            logger.warning("Imagen 3 generation timed out after %.1fs for location %s", timeout, location_id)
            return None
        except Exception as exc:
            logger.warning("Imagen 3 generation failed for location %s: %s", location_id, exc)
            return None

    # 5. Gemini native image backend path (default)
    elif backend == "gemini":
        logger.info("Generating Gemini native moodboard for location %s", location_id)
        start_time = time.time()
        try:
            from google.genai import types

            client = gemini_client._get_client()
            candidate_models = _get_gemini_image_models()

            for model_name in candidate_models:
                elapsed_so_far = time.time() - start_time
                remaining_timeout = timeout - elapsed_so_far
                if remaining_timeout <= 0.5:
                    logger.warning("Remaining timeout (%.2fs) exhausted before trying model %s", remaining_timeout, model_name)
                    break

                try:
                    logger.info("Attempting Gemini native image generation with model %s for %s", model_name, location_id)
                    response = await asyncio.wait_for(
                        client.aio.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                response_modalities=["TEXT", "IMAGE"],
                            ),
                        ),
                        timeout=remaining_timeout,
                    )

                    b64_str = None
                    mime_type = "image/jpeg"
                    if response and getattr(response, "candidates", None):
                        for cand in response.candidates:
                            content = getattr(cand, "content", None)
                            parts = getattr(content, "parts", None) if content else []
                            for part in (parts or []):
                                inline_data = getattr(part, "inline_data", None)
                                if inline_data and getattr(inline_data, "data", None):
                                    raw_data = inline_data.data
                                    if isinstance(raw_data, bytes):
                                        b64_str = base64.b64encode(raw_data).decode("utf-8")
                                    elif isinstance(raw_data, str):
                                        b64_str = raw_data
                                    if getattr(inline_data, "mime_type", None):
                                        mime_type = inline_data.mime_type
                                    if b64_str:
                                        break
                            if b64_str:
                                break

                    if b64_str:
                        logger.info("Gemini native image successfully generated with model %s for %s (mime: %s)", model_name, location_id, mime_type)
                        now = time.time()
                        entry = {
                            "location_id": location_id,
                            "location_name": location_name,
                            "image_base64": b64_str,
                            "mime": mime_type,
                            "prompt": prompt,
                            "model": model_name,
                            "created_at": now,
                            "expires_at": now + CACHE_TTL_SECONDS,
                        }
                        _save_to_cache(location_id, entry)

                        return {
                            "status": "ready",
                            "location_id": location_id,
                            "location_name": location_name,
                            "image_url": f"/api/locations/{location_id}/moodboard/image",
                            "image_base64": b64_str,
                            "mime": mime_type,
                            "prompt": prompt,
                            "cached": False,
                        }

                    logger.warning("Gemini model %s returned no inline_data image for %s", model_name, location_id)

                except asyncio.TimeoutError:
                    logger.warning("Gemini model %s timed out for location %s", model_name, location_id)
                    return None
                except Exception as exc:
                    logger.warning("Gemini model %s generation failed for %s: %s", model_name, location_id, exc)
                    continue

            logger.warning("All Gemini native image models exhausted for location %s", location_id)
            return None

        except Exception as exc:
            logger.warning("Gemini native image generation failed for location %s: %s", location_id, exc)
            return None
    else:
        logger.warning("Unknown moodboard backend '%s'; returning None", backend)
        return None


async def get_or_generate_moodboard_image(
    location_id: str,
    timeout: float = 8.0,
) -> Optional[Tuple[bytes, str]]:
    """Retrieve raw image bytes and mime type for a location from cache, or generate on-demand.

    Returns:
        Tuple of (image_bytes, mime_type) or None if unavailable.
    """
    cached = _get_from_cache(location_id)
    if cached and cached.get("image_base64"):
        try:
            raw_bytes = base64.b64decode(cached["image_base64"])
            mime = cached.get("mime") or "image/jpeg"
            return raw_bytes, mime
        except Exception as exc:
            logger.warning("Failed to decode cached image for %s: %s", location_id, exc)

    # If not cached, attempt on-demand generation
    res = await generate_moodboard(location_id=location_id, timeout=timeout)
    if res and res.get("image_base64"):
        try:
            raw_bytes = base64.b64decode(res["image_base64"])
            mime = res.get("mime") or "image/jpeg"
            return raw_bytes, mime
        except Exception as exc:
            logger.warning("Failed to decode generated image for %s: %s", location_id, exc)

    return None
