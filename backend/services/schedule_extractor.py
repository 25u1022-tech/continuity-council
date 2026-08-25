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
    """Normalize and deduplicate raw AI extraction payload."""
    # 1. Cast deduplication
    raw_cast = raw.get("cast") or []
    seen_cast: Set[str] = set()
    cast_list: List[Dict[str, Any]] = []

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

    # 2. Locations deduplication
    raw_locs = raw.get("locations") or []
    seen_locs: Set[str] = set()
    loc_list: List[Dict[str, Any]] = []

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

    # 3. Shoot Days
    raw_days = raw.get("shoot_days") or []
    day_map: Dict[int, str] = {}
    for d in raw_days:
        try:
            d_num = int(d.get("day_number", 1))
            d_date = str(d.get("date", default_start_date))
            day_map[d_num] = d_date
        except (ValueError, TypeError):
            continue

    # 4. Scenes normalization
    raw_scenes = raw.get("scenes") or []
    normalized_scenes: List[Dict[str, Any]] = []
    seq_counters: Dict[int, int] = {}

    for idx, sc in enumerate(raw_scenes):
        sc_num = str(sc.get("scene_number") or sc.get("scene_id") or str(idx + 1)).strip()
        sc_day = int(sc.get("shoot_day", 1))
        if sc_day < 1:
            sc_day = 1

        seq_counters[sc_day] = seq_counters.get(sc_day, 0) + 1
        seq_order = sc.get("sequence_order") or seq_counters[sc_day]

        sc_title = (sc.get("scene_title") or sc.get("description") or f"Scene {sc_num}").strip()
        if len(sc_title) > 80:
            sc_title = sc_title[:77] + "..."

        loc_name = str(sc.get("location_name") or "").strip()
        # Find matching location ID
        matched_loc_id = "stage_a"
        if loc_name:
            for l in loc_list:
                if l["name"].lower() == loc_name.lower() or loc_name.lower() in l["name"].lower():
                    matched_loc_id = l["location_id"]
                    break
            else:
                # Add auto-discovered location
                if loc_name.lower() not in seen_locs:
                    seen_locs.add(loc_name.lower())
                    new_lid = f"loc_{loc_name.lower().replace(' ', '_')[:16]}"
                    loc_list.append({
                        "location_id": new_lid,
                        "name": loc_name,
                        "location_type": "interior" if "INT" in loc_name.upper() else "exterior",
                        "daily_fee_usd": 4000,
                        "country_code": "US",
                        "country_mult": 1.0,
                        "city_tier": "tier_1",
                        "geo_mult": 1.0,
                    })
                    matched_loc_id = new_lid

        # Cast names in scene
        raw_scene_cast = sc.get("cast_names") or sc.get("required_cast") or []
        scene_cast_names = []
        for c in raw_scene_cast:
            c_str = (c if isinstance(c, str) else c.get("name", "")).strip()
            if c_str:
                scene_cast_names.append(c_str)
                # Auto-add to cast list if not seen
                if c_str.lower() not in seen_cast:
                    seen_cast.add(c_str.lower())
                    new_cid = f"cast_{c_str.lower().replace(' ', '_')[:16]}"
                    cast_list.append({
                        "cast_id": new_cid,
                        "name": c_str,
                        "role_type": "supporting",
                        "day_rate_usd": 1200,
                    })

        int_ext = normalize_int_ext(sc.get("int_ext") or loc_name)
        day_night = normalize_day_night(sc.get("day_night") or sc.get("time_of_day"))

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
            "pages": float(sc.get("pages", 1.0)),
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
        "filming locations, cast members/characters, and scene breakdowns.\n\n"
        "Return a JSON object conforming to this exact schema:\n"
        "{\n"
        '  "shoot_days": [\n'
        '    {"day_number": 1, "date": "2026-08-24", "scenes": ["1", "2A"]}\n'
        "  ],\n"
        '  "scenes": [\n'
        "    {\n"
        '      "scene_number": "1",\n'
        '      "scene_title": "Scene summary",\n'
        '      "description": "Scene action details",\n'
        '      "location_name": "Location or stage name",\n'
        '      "cast_names": ["Actor 1", "Actor 2"],\n'
        '      "int_ext": "INT",\n'
        '      "day_night": "DAY",\n'
        '      "pages": 1.2,\n'
        '      "shoot_day": 1\n'
        "    }\n"
        "  ],\n"
        '  "locations": ["Harbor Pier 7", "Downtown Loft", "Stage A"],\n'
        '  "cast": ["Mara Voss", "Dev Okafor", "Lena Petrov"]\n'
        "}\n"
    )

    extracted_raw = None
    try:
        # 1. Attempt Gemini native multimodal document extraction (30s timeout)
        extracted_raw = await gemini_client.generate_json_with_pdf(
            pdf_bytes=pdf_bytes,
            prompt=prompt,
            timeout=30.0,
            max_tokens=4096,
        )
    except Exception as exc:
        logger.warning("Gemini PDF extraction encountered error: %s", exc)

    # 2. Fallback to heuristic parser if Gemini returned empty or was unavailable
    if not extracted_raw or not isinstance(extracted_raw, dict) or not extracted_raw.get("scenes"):
        logger.info("Attempting heuristic text parser fallback for job %s", job_id)
        extracted_raw = heuristic_pdf_text_parser(pdf_bytes)

    # 3. Check if extraction succeeded
    if not extracted_raw or not isinstance(extracted_raw, dict) or not (extracted_raw.get("scenes") or extracted_raw.get("shoot_days")):
        job["status"] = "failed"
        job["error"] = "We couldn't read this schedule. You can still enter it manually or via CSV."
        logger.warning("Schedule extraction failed for job %s", job_id)
        return

    # 4. Normalize extracted data
    normalized = normalize_extracted_data(extracted_raw)
    job["extracted_data"] = normalized

    # 5. Build preview summary
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
