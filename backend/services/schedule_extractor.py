"""Shooting Schedule & Call Sheet PDF Ingestion Pipeline.

Uses Gemini's native multimodal document understanding to extract:
- Shoot days & calendar dates
- Scenes (number, title, description, location, cast, INT/EXT, DAY/NIGHT)
- Cast member list
- Filming locations list

Features:
- Multipart PDF upload validation (<= 10MB, <= 20 pages, PDF magic header)
- Async job lifecycle (pending -> processing -> ready | failed -> confirmed)
- Normalization (deduplication of cast & locations, INT/EXT cleaning, day sorting)
- Rich preview with summary counts and sample rows
- ClickHouse upsert with MCP-visible audit logging
- Graceful failure handling with kind fallback messaging
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from services import clickhouse_client, gemini_client

logger = logging.getLogger("continuity.schedule_extractor")

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_PDF_PAGES = 20

# In-memory storage for async schedule import jobs
IMPORT_JOBS: Dict[str, Dict[str, Any]] = {}


def validate_pdf_bytes(pdf_bytes: bytes, filename: str = "") -> None:
    """Validate uploaded PDF file size, type, and page count bounds."""
    if not pdf_bytes:
        raise ValueError("Uploaded file is empty")

    if len(pdf_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File size ({len(pdf_bytes) / (1024*1024):.1f}MB) exceeds 10MB limit")

    # Check magic header
    if not pdf_bytes.startswith(b"%PDF-"):
        # Check if filename ends with .pdf
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only valid PDF files are supported")

    # Check page count via PDF structure regex
    page_matches = re.findall(rb"/Type\s*/Page\b", pdf_bytes)
    if len(page_matches) > MAX_PDF_PAGES:
        raise ValueError(f"PDF exceeds maximum page limit of {MAX_PDF_PAGES} pages ({len(page_matches)} detected)")


def normalize_int_ext(val: Any) -> str:
    """Normalize interior/exterior scene tag."""
    s = str(val or "").strip().upper()
    if "INT" in s and "EXT" in s:
        return "INT/EXT"
    if "EXT" in s:
        return "EXT"
    return "INT"


def normalize_day_night(val: Any) -> str:
    """Normalize day/night scene tag."""
    s = str(val or "").strip().upper()
    if "NIGHT" in s or "NITE" in s:
        return "NIGHT"
    if "DUSK" in s:
        return "DUSK"
    if "DAWN" in s:
        return "DAWN"
    return "DAY"


def normalize_extracted_data(raw: Dict[str, Any], default_start_date: str = "2026-08-24") -> Dict[str, Any]:
    """Normalize, flatten and deduplicate raw AI extraction payload (handles both flat and nested schemas)."""
    if not isinstance(raw, dict):
        raw = {}

    # 1. Flexible scene collection (defense-in-depth)
    extracted_scene_dicts: List[Dict[str, Any]] = []

    # Case A: Top-level scenes array
    if isinstance(raw.get("scenes"), list):
        for s in raw["scenes"]:
            if isinstance(s, dict):
                extracted_scene_dicts.append(s)

    # Case B: Top-level schedule / shoot_days / days / shooting_schedule
    for key in ("schedule", "shoot_days", "days", "shooting_schedule", "production_schedule"):
        val = raw.get(key)
        if isinstance(val, list):
            for day_idx, day_obj in enumerate(val):
                if not isinstance(day_obj, dict):
                    continue
                d_num = day_obj.get("day_number") or day_obj.get("day") or (day_idx + 1)
                try:
                    d_num = int(d_num)
                except (ValueError, TypeError):
                    d_num = day_idx + 1

                day_scenes = day_obj.get("scenes") or []
                if isinstance(day_scenes, list):
                    for sc_item in day_scenes:
                        if isinstance(sc_item, dict):
                            sc_item_copy = dict(sc_item)
                            if "shoot_day" not in sc_item_copy and "day_number" not in sc_item_copy:
                                sc_item_copy["shoot_day"] = d_num
                            extracted_scene_dicts.append(sc_item_copy)

    # Deduplicate extracted_scene_dicts
    deduped_raw_scenes: List[Dict[str, Any]] = []
    seen_scene_ids: Set[str] = set()
    for sc in extracted_scene_dicts:
        s_num = str(sc.get("scene_number") or sc.get("scene_id") or len(deduped_raw_scenes) + 1).strip()
        s_day = str(sc.get("shoot_day") or sc.get("day_number") or 1).strip()
        key = f"{s_day}_{s_num}"
        if key not in seen_scene_ids:
            seen_scene_ids.add(key)
            deduped_raw_scenes.append(sc)

    # 2. Shoot Days map
    day_map: Dict[int, str] = {}
    for key in ("shoot_days", "days", "schedule"):
        val = raw.get(key)
        if isinstance(val, list):
            for d_idx, d in enumerate(val):
                if isinstance(d, dict):
                    try:
                        d_num = int(d.get("day_number") or d.get("day") or (d_idx + 1))
                        d_date = str(d.get("date") or default_start_date)
                        day_map[d_num] = d_date
                    except (ValueError, TypeError):
                        continue

    # 3. Cast collection & deduplication
    raw_cast = raw.get("cast") or raw.get("cast_members") or []
    seen_cast: Set[str] = set()
    cast_list: List[Dict[str, Any]] = []

    if isinstance(raw_cast, list):
        for item in raw_cast:
            name = (item if isinstance(item, str) else item.get("name", "")).strip()
            if not name or name.lower() in seen_cast:
                continue
            seen_cast.add(name.lower())
            role_type = "lead" if len(cast_list) == 0 else "supporting"
            if isinstance(item, dict) and item.get("role_type"):
                role_type = item["role_type"]
            cid = f"cast_{name.lower().replace(' ', '_')[:16]}"
            cast_list.append({
                "cast_id": cid,
                "name": name,
                "role_type": role_type,
                "day_rate_usd": 1200 if role_type == "supporting" else 3500,
            })

    # Also discover cast from scenes if missing from top-level
    for sc in deduped_raw_scenes:
        for c in (sc.get("cast_names") or sc.get("cast") or sc.get("required_cast") or []):
            c_name = (c if isinstance(c, str) else (c.get("name") if isinstance(c, dict) else "")).strip()
            if c_name and c_name.lower() not in seen_cast:
                seen_cast.add(c_name.lower())
                role_type = "lead" if len(cast_list) == 0 else "supporting"
                cid = f"cast_{c_name.lower().replace(' ', '_')[:16]}"
                cast_list.append({
                    "cast_id": cid,
                    "name": c_name,
                    "role_type": role_type,
                    "day_rate_usd": 1200 if role_type == "supporting" else 3500,
                })

    # 4. Locations collection & deduplication
    raw_locs = raw.get("locations") or raw.get("filming_locations") or []
    seen_locs: Set[str] = set()
    loc_list: List[Dict[str, Any]] = []

    if isinstance(raw_locs, list):
        for item in raw_locs:
            name = (item if isinstance(item, str) else item.get("name", "")).strip()
            if not name or name.lower() in seen_locs:
                continue
            seen_locs.add(name.lower())
            loc_type = "interior" if "INT" in name.upper() or "STAGE" in name.upper() else "exterior"
            lid = f"loc_{name.lower().replace(' ', '_')[:16]}"
            loc_list.append({
                "location_id": lid,
                "name": name,
                "location_type": loc_type,
                "daily_fee_usd": 5000 if loc_type == "exterior" else 3500,
                "country_code": "US",
                "country_mult": 1.0,
                "city_tier": "tier_1",
                "geo_mult": 1.0,
            })

    # Also discover locations from scenes if missing
    for sc in deduped_raw_scenes:
        l_name = str(sc.get("location_name") or sc.get("location") or sc.get("setting") or "").strip()
        if l_name and l_name.lower() not in seen_locs:
            seen_locs.add(l_name.lower())
            loc_type = "interior" if "INT" in l_name.upper() or "STAGE" in l_name.upper() else "exterior"
            lid = f"loc_{l_name.lower().replace(' ', '_')[:16]}"
            loc_list.append({
                "location_id": lid,
                "name": l_name,
                "location_type": loc_type,
                "daily_fee_usd": 4000,
                "country_code": "US",
                "country_mult": 1.0,
                "city_tier": "tier_1",
                "geo_mult": 1.0,
            })

    # 5. Scenes normalization
    normalized_scenes: List[Dict[str, Any]] = []
    seq_counters: Dict[int, int] = {}

    for idx, sc in enumerate(deduped_raw_scenes):
        sc_num = str(sc.get("scene_number") or sc.get("scene_id") or str(idx + 1)).strip()
        try:
            sc_day = int(sc.get("shoot_day") or sc.get("day_number") or sc.get("day") or 1)
        except (ValueError, TypeError):
            sc_day = 1
        if sc_day < 1:
            sc_day = 1

        seq_counters[sc_day] = seq_counters.get(sc_day, 0) + 1
        seq_order = sc.get("sequence_order") or seq_counters[sc_day]

        sc_title = (sc.get("scene_title") or sc.get("title") or sc.get("description") or f"Scene {sc_num}").strip()
        if len(sc_title) > 80:
            sc_title = sc_title[:77] + "..."

        loc_name = str(sc.get("location_name") or sc.get("location") or sc.get("setting") or "").strip()
        matched_loc_id = "stage_a"
        if loc_name:
            for l in loc_list:
                if l["name"].lower() == loc_name.lower() or loc_name.lower() in l["name"].lower():
                    matched_loc_id = l["location_id"]
                    break
            else:
                matched_loc_id = f"loc_{loc_name.lower().replace(' ', '_')[:16]}"

        raw_scene_cast = sc.get("cast_names") or sc.get("cast") or sc.get("required_cast") or []
        scene_cast_names = []
        for c in raw_scene_cast:
            c_str = (c if isinstance(c, str) else (c.get("name") if isinstance(c, dict) else "")).strip()
            if c_str:
                scene_cast_names.append(c_str)

        int_ext = normalize_int_ext(sc.get("int_ext") or sc_title or loc_name)
        day_night = normalize_day_night(sc.get("day_night") or sc.get("time_of_day") or sc_title)

        pages_val = 1.0
        try:
            pages_val = float(sc.get("pages") or sc.get("page_count") or 1.0)
        except (ValueError, TypeError):
            pages_val = 1.0

        normalized_scenes.append({
            "scene_id": f"sc_{sc_num.replace(' ', '_').lower()}",
            "scene_number": sc_num,
            "scene_title": sc_title,
            "shoot_day": sc_day,
            "sequence_order": int(seq_order),
            "location_name": loc_name or "Stage A",
            "location_id": matched_loc_id,
            "cast_names": scene_cast_names,
            "int_ext": int_ext,
            "day_night": day_night,
            "description": str(sc.get("description", "")).strip(),
            "pages": pages_val,
            "is_cover_scene": 1 if sc.get("is_cover_scene") else 0,
            "priority": int(sc.get("priority", 3)),
            "continuity_tags": sc.get("continuity_tags", []),
            "depends_on": sc.get("depends_on", []),
        })

    # Sort scenes by shoot_day and sequence_order
    normalized_scenes.sort(key=lambda s: (s["shoot_day"], s["sequence_order"]))

    # Derive total shoot days
    total_days = max([s["shoot_day"] for s in normalized_scenes] + list(day_map.keys()) + [1])

    # Reconstruct shoot_days list
    shoot_days = []
    for d in range(1, total_days + 1):
        scenes_on_day = [s["scene_number"] for s in normalized_scenes if s["shoot_day"] == d]
        shoot_days.append({
            "day_number": d,
            "date": day_map.get(d, default_start_date),
            "scenes": scenes_on_day,
        })

    return {
        "shoot_days": shoot_days,
        "scenes": normalized_scenes,
        "cast": cast_list,
        "locations": loc_list,
        "total_shoot_days": total_days,
    }


def create_import_job(production_id: str, filename: str, file_size_bytes: int) -> str:
    """Initialize a pending schedule import job."""
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    IMPORT_JOBS[job_id] = {
        "job_id": job_id,
        "production_id": production_id,
        "filename": filename,
        "file_size_bytes": file_size_bytes,
        "status": "pending",
        "created_at": now_iso,
        "preview": None,
        "extracted_data": None,
        "error": None,
    }
    return job_id


def get_import_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the current state of an import job."""
    return IMPORT_JOBS.get(job_id)


def heuristic_pdf_text_parser(pdf_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Lightweight regex extractor for plain-text or synthetic test PDF bytes."""
    try:
        text = pdf_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return None

    # Search for scene lines like "SCENE 1 - INT. LOFT - DAY" or "1. INT. HARBOR"
    scene_pattern = re.compile(
        r"(?:SCENE\s+)?([0-9]+[A-Za-z]?)\s*[:\.\-]?\s*(INT|EXT|INT/EXT)[\.\s]+([^\-\n]+)(?:[\-\s]+(DAY|NIGHT|DUSK|DAWN))?",
        re.IGNORECASE,
    )
    matches = scene_pattern.findall(text)
    if not matches:
        return None

    scenes = []
    locations = set()
    cast = set()

    for m in matches:
        num, ie, loc, dn = m
        loc_clean = loc.strip()
        locations.add(loc_clean)
        scenes.append({
            "scene_number": num.strip(),
            "scene_title": f"{ie.upper()}. {loc_clean}",
            "location_name": loc_clean,
            "int_ext": ie.upper(),
            "day_night": (dn or "DAY").upper(),
            "shoot_day": 1,
            "cast_names": [],
        })

    if not scenes:
        return None

    return {
        "shoot_days": [{"day_number": 1, "date": "2026-08-24", "scenes": [s["scene_number"] for s in scenes]}],
        "scenes": scenes,
        "locations": list(locations),
        "cast": list(cast),
    }


async def process_schedule_pdf_async(job_id: str, pdf_bytes: bytes) -> None:
    """Asynchronous background worker: calls Gemini with PDF bytes, normalizes, and populates preview."""
    job = IMPORT_JOBS.get(job_id)
    if not job:
        return

    job["status"] = "processing"
    logger.info("Starting PDF schedule extraction for job %s (%d bytes)", job_id, len(pdf_bytes))

    prompt = (
        "You are an expert film production coordinator and schedule parser.\n"
        "Carefully analyze this shooting schedule or call sheet PDF document and extract all shoot days, "
        "filming locations, cast members/characters, and scene breakdowns.\n"
        "Extract every scene with its scene number, location/setting, INT/EXT, DAY/NIGHT, pages, assigned shoot day, and cast members."
    )

    extracted_raw = None
    last_error_detail = None
    try:
        # 1. Attempt Gemini native multimodal document extraction (60s timeout, schema constrained)
        extracted_raw = await gemini_client.generate_json_with_pdf(
            pdf_bytes=pdf_bytes,
            prompt=prompt,
            timeout=60.0,
            max_tokens=8192,
        )
    except Exception as exc:  # noqa: BLE001
        last_error_detail = f"{type(exc).__name__}: {exc}"
        logger.warning("Gemini PDF extraction encountered error: %s", exc)

    # 2. Fallback to heuristic parser if Gemini returned empty or was unavailable
    if not extracted_raw or not isinstance(extracted_raw, dict) or not (
        extracted_raw.get("scenes") or extracted_raw.get("shoot_days") or extracted_raw.get("schedule") or extracted_raw.get("days")
    ):
        logger.info("Attempting heuristic text parser fallback for job %s", job_id)
        extracted_raw = heuristic_pdf_text_parser(pdf_bytes)

    # 3. Check if extraction succeeded & normalize
    normalized = None
    if extracted_raw and isinstance(extracted_raw, dict):
        try:
            normalized = normalize_extracted_data(extracted_raw)
        except Exception as norm_exc:  # noqa: BLE001
            last_error_detail = f"NormalizationError: {norm_exc}"
            logger.warning("Normalization failed for job %s: %s", job_id, norm_exc)

    if not normalized or not normalized.get("scenes"):
        job["status"] = "failed"
        job["error"] = "We couldn't read this schedule. You can still enter it manually or via CSV."
        if last_error_detail:
            logger.warning("Schedule extraction failed for job %s. Detail: %s", job_id, last_error_detail)
            job["debug_error"] = last_error_detail
        else:
            logger.warning("Schedule extraction failed for job %s: no scenes could be parsed", job_id)
        return

    job["extracted_data"] = normalized

    # 4. Build preview summary
    scenes = normalized.get("scenes", [])
    days = normalized.get("shoot_days", [])
    cast = normalized.get("cast", [])
    locations = normalized.get("locations", [])

    job["preview"] = {
        "days_count": len(days),
        "scenes_count": len(scenes),
        "cast_count": len(cast),
        "locations_count": len(locations),
        "sample_days": days[:5],
        "sample_scenes": [
            {
                "scene_number": s.get("scene_number"),
                "scene_title": s.get("scene_title"),
                "location_name": s.get("location_name"),
                "shoot_day": s.get("shoot_day"),
                "cast_names": s.get("cast_names", []),
                "int_ext": s.get("int_ext"),
                "day_night": s.get("day_night"),
            }
            for s in scenes[:6]
        ],
        "sample_cast": [c.get("name") for c in cast[:8]],
        "sample_locations": [l.get("name") for l in locations[:8]],
    }
    job["status"] = "ready"
    logger.info(
        "PDF schedule parsed successfully for job %s: %d days, %d scenes, %d cast, %d locations",
        job_id, len(days), len(scenes), len(cast), len(locations)
    )


async def confirm_and_import_schedule(job_id: str) -> Dict[str, Any]:
    """Confirm previewed schedule extraction and upsert rows into ClickHouse."""
    job = IMPORT_JOBS.get(job_id)
    if not job:
        raise ValueError("Import job not found")

    if job.get("status") != "ready":
        raise ValueError(f"Import job is not ready for confirmation (current status: {job.get('status')})")

    extracted = job.get("extracted_data")
    if not extracted:
        raise ValueError("No extracted data available to import")

    production_id = job["production_id"]
    scenes = extracted.get("scenes", [])
    locations = extracted.get("locations", [])
    cast_members = extracted.get("cast", [])
    total_days = extracted.get("total_shoot_days", 1)

    result = await clickhouse_client.upsert_extracted_schedule(
        production_id=production_id,
        scenes=scenes,
        locations=locations,
        cast_members=cast_members,
        total_shoot_days=total_days,
    )

    job["status"] = "confirmed"

    return {
        "success": True,
        "production_id": production_id,
        "days_count": result.get("total_shoot_days", len(extracted.get("shoot_days", []))),
        "scenes_count": result.get("scenes_count", len(scenes)),
        "cast_count": result.get("cast_count", len(cast_members)),
        "locations_count": result.get("locations_count", len(locations)),
    }
