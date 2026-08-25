"""Continuity Council — FastAPI backend.

Stack: FastAPI + ClickHouse Cloud (clickhouse-connect + official mcp-clickhouse)
+ Gemini (official google-genai SDK). No other database is used.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path as FilePath

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, File, HTTPException, Path, Query, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = FilePath(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import case_store  # noqa: E402
from agents.council_chatbot import CouncilChatbot  # noqa: E402
from models import (  # noqa: E402
    ApprovalRequest,
    ChatRequest,
    ChatResponse,
    CreateProductionRequest,
    DisruptionReport,
    DisruptionType,
    ParseNLDisruptionRequest,
    ParseNLDisruptionResponse,
    new_case,
    short_id,
)
from services import (  # noqa: E402
    clickhouse_client,
    gemini_client,
    geo_service,
    import_service,
    mcp_client,
    moodboard_service,
    nl_parser,
    scene_generator,
    schedule_extractor,
)
from services.geo_service import geocode_location, resolve_geo_economics  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("continuity.api")

PRODUCTION_ID_PATTERN = r"^[a-zA-Z0-9_\-]{3,64}$"
CASE_ID_PATTERN = r"^[a-zA-Z0-9_\-]{3,64}$"

app = FastAPI(title="Continuity Council API", version="1.0.0")
api = APIRouter(prefix="/api")


@api.get("/")
async def root():
    return {"service": "Continuity Council", "track": "ClickHouse", "status": "ok"}


@api.get("/health")
async def health():
    ch = await clickhouse_client.ping()
    return {
        "status": "ok" if ch.get("connected") else "degraded",
        "clickhouse": ch,
        "gemini": {
            "configured": gemini_client.is_configured(),
            "model": gemini_client.model_name(),
        },
        "mcp": {"server": "mcp-clickhouse", "transport": "stdio", "read_only": True},
    }


@api.get("/productions")
async def list_productions():
    """All productions for the switcher + management UI."""
    if not clickhouse_client.is_configured():
        raise HTTPException(503, "ClickHouse is not configured. Add credentials to backend/.env.")
    try:
        return {"productions": await clickhouse_client.list_productions()}
    except Exception as exc:  # noqa: BLE001
        logger.exception("list productions failed")
        raise HTTPException(502, f"ClickHouse query failed: {str(exc)[:200]}")


def _parse_date(value: str, field: str):
    from datetime import date

    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        raise HTTPException(422, f"{field} must be a valid date (YYYY-MM-DD)")


@api.post("/productions", status_code=201)
async def create_production(req: CreateProductionRequest):
    if not clickhouse_client.is_configured():
        raise HTTPException(503, "ClickHouse is not configured. Add credentials to backend/.env.")

    # --- Validation --------------------------------------------------------
    name = req.name.strip()
    if not name:
        raise HTTPException(422, "Production name is required")
    if not req.cast:
        raise HTTPException(422, "Add at least one cast member")
    if not req.locations:
        raise HTTPException(422, "Add at least one location")

    start = _parse_date(req.shoot_start, "shoot_start")
    end = _parse_date(req.shoot_end, "shoot_end")
    if end < start:
        raise HTTPException(422, "Shoot end date cannot be before the start date")
    total_days = (end - start).days + 1
    if total_days < 1 or total_days > 365:
        raise HTTPException(422, "Shoot span must be between 1 and 365 days")

    # Duplicate names within the submission
    cast_names = [c.name.strip() for c in req.cast]
    if len(set(n.lower() for n in cast_names)) != len(cast_names):
        raise HTTPException(422, "Duplicate cast member names are not allowed")
    loc_names = [l.name.strip() for l in req.locations]
    if len(set(n.lower() for n in loc_names)) != len(loc_names):
        raise HTTPException(422, "Duplicate location names are not allowed")

    try:
        if await clickhouse_client.title_exists(name):
            raise HTTPException(409, f"A production named '{name}' already exists")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("title_exists check failed (continuing): %s", exc)

    days = list(range(1, total_days + 1))

    def _valid_days(raw):
        return sorted({d for d in (raw or []) if isinstance(d, int) and 1 <= d <= total_days})

    # --- Build ids + bundle rows ------------------------------------------
    production_id = short_id("prod")
    while await clickhouse_client.production_exists(production_id):
        production_id = short_id("prod")

    cast_rows, cast_for_gen, cast_avail = [], [], []
    for i, c in enumerate(req.cast, start=1):
        cast_id = f"cast_{i:03d}"
        role = (c.role or "supporting").strip().lower()
        avail = _valid_days(c.available_days)
        day_rate = 3500 if role == "lead" else 1500
        cast_rows.append({
            "production_id": production_id, "cast_id": cast_id,
            "name": c.name.strip(), "role_type": role,
            "day_rate_usd": day_rate,
        })
        cast_for_gen.append({
            "cast_id": cast_id, "name": c.name.strip(),
            "role_type": role, "available_days": avail,
        })
        for d in days:
            available = 1 if (not avail or d in avail) else 0
            cast_avail.append({
                "production_id": production_id, "cast_id": cast_id, "shoot_day": d,
                "available": available, "reason": "" if available else "Unavailable this day",
            })

    loc_rows, loc_for_gen, loc_avail = [], [], []
    for i, l in enumerate(req.locations, start=1):
        location_id = f"loc_{i:03d}"
        avail = _valid_days(l.available_days)
        l_name = l.name.strip()
        l_type = (l.location_type or "interior").strip().lower()

        # Resolve geo economics once at location creation (ZERO live geo calls during investigation)
        fallback_lat = float(l.latitude) if l.latitude is not None else 34.05
        fallback_lon = float(l.longitude) if l.longitude is not None else -118.25
        geo_info = await resolve_geo_economics(l_name, fallback_lat=fallback_lat, fallback_lon=fallback_lon)

        lat = float(l.latitude if l.latitude is not None else geo_info["latitude"])
        lon = float(l.longitude if l.longitude is not None else geo_info["longitude"])
        country_code = (l.country_code or geo_info["country_code"]).upper()
        country_mult = float(geo_info["country_mult"])
        city_tier = l.city_tier or geo_info["city_tier"]
        tier_mult = 1.0 if city_tier == "tier_1" else (0.5 if city_tier == "tier_2" else 0.35)
        geo_mult = float(l.geo_mult if l.geo_mult is not None else round(country_mult * tier_mult, 4))
        currency_code = l.currency_code or geo_info["currency_code"]

        daily_fee = 10000 if l_type == "stage" else (3500 if l_type == "interior" else 5000)

        loc_rows.append({
            "production_id": production_id, "location_id": location_id,
            "name": l_name, "location_type": l_type,
            "capacity": 100, "daily_fee_usd": daily_fee,
            "latitude": lat, "longitude": lon, "currency_code": currency_code,
            "country_code": country_code, "country_mult": country_mult,
            "city_tier": city_tier, "geo_mult": geo_mult,
            "notes": l.permit_notes.strip(),
        })

        loc_for_gen.append({
            "location_id": location_id, "name": l_name,
            "location_type": l_type, "available_days": avail,
        })
        for d in days:
            available = 1 if (not avail or d in avail) else 0
            loc_avail.append({
                "production_id": production_id, "location_id": location_id, "shoot_day": d,
                "available": available,
                "notes": (l.permit_notes.strip() if not available else ""),
            })

    # --- Generate scenes (Gemini + deterministic fallback) ----------------
    scenes, llm_mode = await scene_generator.generate_scenes(
        name, req.director.strip(), days, cast_for_gen, loc_for_gen
    )
    for s in scenes:
        s["production_id"] = production_id

    prod_tier = "tentpole" if total_days > 90 else ("mid" if total_days > 15 else "indie")
    production = {
        "production_id": production_id, "title": name,
        "start_date": start, "total_shoot_days": total_days,
        "currency": "USD", "director": req.director.strip(),
        "tier": prod_tier,
    }

    try:
        await clickhouse_client.create_production(
            production, loc_rows, cast_rows, scenes, loc_avail, cast_avail
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("create production failed")
        raise HTTPException(502, f"Failed to store production: {str(exc)[:200]}")

    logger.info("Created production %s ('%s') — %d scenes via %s",
                production_id, name, len(scenes), llm_mode)
    return {
        "production_id": production_id,
        "title": name,
        "total_shoot_days": total_days,
        "scenes_generated": len(scenes),
        "cast_count": len(cast_rows),
        "location_count": len(loc_rows),
        "llm_mode": llm_mode,
    }


@api.get("/productions/{production_id}")
async def get_production(
    production_id: str = Path(..., pattern=PRODUCTION_ID_PATTERN, description="Production ID"),
):
    if not clickhouse_client.is_configured():
        raise HTTPException(503, "ClickHouse is not configured. Add credentials to backend/.env.")
    try:
        bundle = await clickhouse_client.fetch_production_bundle(production_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("production fetch failed")
        raise HTTPException(502, f"ClickHouse query failed: {str(exc)[:200]}")
    if bundle is None:
        raise HTTPException(404, f"Production {production_id} not found.")
    bundle["active_cases"] = [
        {
            "case_id": c.case_id,
            "disruption_type": c.disruption.disruption_type,
            "severity": c.disruption.severity,
            "affected_day": c.disruption.affected_day,
            "status": c.status,
            "created_at": c.created_at.isoformat(),
        }
        for c in case_store.all_cases()
        if c.production_id == production_id
    ]
    return bundle


@api.get("/templates/disruption-history.csv")
async def download_disruption_history_template():
    """Download a pre-formatted CSV template with valid headers and sample disruption rows."""
    csv_text = import_service.generate_template_csv()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="disruption-history-template.csv"'},
    )


@api.post("/productions/{production_id}/import-history")
async def import_production_history(
    production_id: str = Path(..., pattern=PRODUCTION_ID_PATTERN, description="Production ID"),
    file: UploadFile = File(...),
):
    """Import historical disruption CSV for a specific production tenant."""
    if not clickhouse_client.is_configured():
        raise HTTPException(503, "ClickHouse is not configured. Add credentials to backend/.env.")
    try:
        content_bytes = await file.read()
        csv_text = content_bytes.decode("utf-8-sig", errors="replace")
    except Exception as exc:
        raise HTTPException(400, f"Could not read CSV file: {exc}")

    # Determine studio_id for this production
    bundle = await clickhouse_client.fetch_production_bundle(production_id)
    if bundle is None:
        raise HTTPException(404, f"Production {production_id} not found.")
    studio_id = "global"
    if bundle and bundle.get("production"):
        studio_id = bundle["production"].get("studio_id", "global") or "global"
    if not studio_id or studio_id == "global":
        studio_id = f"studio_{production_id}"
        await clickhouse_client.update_production_studio(production_id, studio_id)

    res = await import_service.import_historical_data(csv_text, studio_id=studio_id)
    return {
        "status": "ok",
        "production_id": production_id,
        "studio_id": studio_id,
        **res,
    }


@api.post("/productions/{production_id}/import-schedule")
async def import_schedule_pdf(
    production_id: str = Path(..., pattern=PRODUCTION_ID_PATTERN, description="Production ID"),
    file: UploadFile = File(...),
):
    """Upload a shooting-schedule or call-sheet PDF for Gemini document understanding."""
    bundle = await clickhouse_client.fetch_production_bundle(production_id)
    if bundle is None:
        raise HTTPException(404, f"Production {production_id} not found.")

    content_bytes = await file.read()
    try:
        schedule_extractor.validate_pdf_bytes(content_bytes, filename=file.filename or "schedule.pdf")
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    job_id = schedule_extractor.create_import_job(
        production_id=production_id,
        filename=file.filename or "schedule.pdf",
        file_size_bytes=len(content_bytes),
    )

    # Launch background async worker (non-blocking)
    asyncio.create_task(schedule_extractor.process_schedule_pdf_async(job_id, content_bytes))

    job = schedule_extractor.get_import_job(job_id)
    return job


@api.get("/imports/{job_id}")
async def get_schedule_import_job(job_id: str):
    """Poll status and preview of an asynchronous PDF schedule import job."""
    job = schedule_extractor.get_import_job(job_id)
    if not job:
        raise HTTPException(404, f"Import job '{job_id}' not found.")
    return job


@api.post("/imports/{job_id}/confirm")
async def confirm_schedule_import(job_id: str):
    """Confirm previewed schedule extraction and upsert rows into ClickHouse."""
    try:
        res = await schedule_extractor.confirm_and_import_schedule(job_id)
        return res
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.error("Failed to confirm schedule import job %s: %s", job_id, exc)
        raise HTTPException(500, f"Failed to persist schedule rows: {exc}")


@api.get("/locations/{location_id}/moodboard")
async def get_location_moodboard(
    location_id: str = Path(..., description="Location ID"),
    scene_id: Optional[str] = Query(None, description="Optional scene ID for lighting/atmosphere context"),
):
    """Get on-demand Imagen 3 cinematic mood-board preview for a location."""
    res = await moodboard_service.generate_moodboard(
        location_id=location_id,
        timeout=8.0,
    )
    if res and res.get("image_base64"):
        return JSONResponse(
            status_code=200,
            content=res,
        )
    # 202 Accepted with unavailable status on failure/quota (never 500)
    return JSONResponse(
        status_code=202,
        content={
            "status": "unavailable",
            "location_id": location_id,
            "detail": "AI moodboard preview currently unavailable or cooling down.",
        },
    )


@api.get("/productions/{production_id}/studio-cohort")
async def get_studio_cohort(
    production_id: str = Path(..., pattern=PRODUCTION_ID_PATTERN, description="Production ID"),
):
    """Get current studio historical cohort sample size and blending weight."""
    bundle = await clickhouse_client.fetch_production_bundle(production_id)
    if bundle is None:
        raise HTTPException(404, f"Production {production_id} not found.")
    studio_id = "global"
    if bundle and bundle.get("production"):
        studio_id = bundle["production"].get("studio_id", "global") or "global"
    count = (
        await clickhouse_client.fetch_studio_history_count(studio_id)
        if studio_id != "global"
        else 0
    )
    return {
        "production_id": production_id,
        "studio_id": studio_id,
        "sample_size": count,
        "is_blended": 0 < count < 200,
        "blend_weight": round(count / 200.0, 3) if count < 200 else 1.0,
    }


def _impact_preview_scenes(bundle, disruption_type: str, affected_day: int,
                           affected_cast_id: str = "", affected_location_id: str = ""):
    """Return scheduled scenes directly blocked by a disruption selection."""
    scenes = [s for s in bundle["scenes"] if s["shoot_day"] == affected_day]
    if disruption_type in ("lead_actor_unavailable", "supporting_actor_unavailable"):
        return [s for s in scenes if affected_cast_id in s["required_cast"]]
    if disruption_type == "location_unavailable":
        return [s for s in scenes if s["location_id"] == affected_location_id]
    return scenes


@api.get("/disruptions/impact-preview")
async def disruption_impact_preview(
    production_id: str = Query(..., pattern=PRODUCTION_ID_PATTERN, description="Production ID"),
    disruption_type: DisruptionType = Query(...),
    affected_day: int = Query(..., ge=1, le=3650, description="Affected shoot day (1..3650)"),
    affected_cast_id: str = Query(""),
    affected_location_id: str = Query(""),
):
    if not 1 <= affected_day <= 3650:
        raise HTTPException(422, "affected_day must be between 1 and 3650")
    if disruption_type == "location_unavailable" and not affected_location_id.strip():
        raise HTTPException(422, "affected_location_id is required for location_unavailable")
    if disruption_type in ("lead_actor_unavailable", "supporting_actor_unavailable") and not affected_cast_id.strip():
        raise HTTPException(422, "affected_cast_id is required for actor-unavailable disruptions")
    if not clickhouse_client.is_configured():
        raise HTTPException(503, "ClickHouse is not configured. Add credentials to backend/.env.")
    bundle = await clickhouse_client.fetch_production_bundle(production_id)
    if bundle is None:
        raise HTTPException(404, f"Production {production_id} not found.")
    scenes = _impact_preview_scenes(
        bundle, disruption_type, affected_day, affected_cast_id, affected_location_id
    )
    return {"production_id": production_id, "affected_day": affected_day, "scenes": scenes}


@api.post("/disruptions/parse-nl", response_model=ParseNLDisruptionResponse)
async def parse_nl_disruption(req: ParseNLDisruptionRequest):
    """Parse natural-language incident description into structured disruption fields."""
    try:
        res = await nl_parser.parse_disruption(req.description, req.production_id)
        return res
    except Exception as exc:
        logger.warning("NL disruption parse failed: %s", exc)
        return {
            "confidence": "low",
            "disruption_type": "lead_actor_unavailable",
            "severity": "medium",
            "affected_day": 1,
            "affected_date": "",
            "affected_cast_id": "",
            "affected_cast_name": "",
            "affected_location_id": "",
            "affected_location_name": "",
            "notes": req.description,
            "scene_ids": [],
            "reasoning": "Could not parse description",
        }


@api.post("/disruptions", status_code=201)
async def report_disruption(report: DisruptionReport):
    if not clickhouse_client.is_configured():
        raise HTTPException(503, "ClickHouse is not configured. Add credentials to backend/.env.")
    if not await clickhouse_client.production_exists(report.production_id):
        raise HTTPException(404, f"Production '{report.production_id}' not found")
    case = new_case(report)
    case_store.put(case)

    # Append the case event to ClickHouse (non-blocking for UX, but attempted immediately)
    try:
        await clickhouse_client.insert_disruption_case(case)
    except Exception as exc:  # noqa: BLE001
        logger.warning("disruption_cases insert failed (continuing): %s", exc)

    from agents import orchestrator
    asyncio.create_task(orchestrator.run_investigation(case.case_id))
    logger.info("Case %s created for %s", case.case_id, report.disruption_type)
    return {"case_id": case.case_id, "status": case.status}


@api.get("/cases/{case_id}")
async def get_case(
    case_id: str = Path(..., pattern=CASE_ID_PATTERN, description="Case ID"),
):
    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(404, f"Case {case_id} not found")
    return case.model_dump(mode="json")


@api.get("/cases")
async def list_cases():
    return [c.model_dump(mode="json") for c in case_store.all_cases()]


@api.post("/cases/{case_id}/approve")
async def approve_option(
    approval: ApprovalRequest,
    case_id: str = Path(..., pattern=CASE_ID_PATTERN, description="Case ID"),
):
    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(404, f"Case {case_id} not found")
    if case.status != "options_ready":
        raise HTTPException(409, f"Case is '{case.status}', not ready for approval")
    option = next((o for o in case.options if o.option_id == approval.option_id), None)
    if option is None:
        raise HTTPException(404, f"Option {approval.option_id} not found on case {case_id}")

    from agents import auditor
    case.touch_stage("OPTION_APPROVED")
    case.agent_start("auditor", "Writing decision ledger to ClickHouse…")
    try:
        decision_id = await auditor.write_decision_ledger(case, option, approval.approved_by)
    except Exception as exc:  # noqa: BLE001
        case.agent_error("auditor", f"Ledger write failed: {str(exc)[:160]}")
        logger.exception("ledger write failed")
        raise HTTPException(502, f"Decision ledger write failed: {str(exc)[:200]}")

    case.decision_id = decision_id
    case.approved_option_id = option.option_id
    case.status = "approved"
    case.touch_stage("SCHEDULE_UPDATED")
    case.touch_stage("DECISION_RECORDED")
    case.agent_complete(
        "auditor",
        f"Decision {decision_id} written · {len(option.scene_changes)} schedule change(s) recorded",
    )
    return {
        "decision_id": decision_id,
        "status": "written",
        "case_id": case.case_id,
        "selected_option": option.option_id,
        "schedule_changes": [ch.model_dump() for ch in option.scene_changes],
    }


@api.get("/activity")
async def recent_activity(limit: int = 10):
    """Recent ClickHouse / MCP activity events for the Live MCP Ticker."""
    from services import activity_log

    return {"events": activity_log.recent(limit)}


@api.get("/evidence/drilldown")
async def evidence_drilldown(
    disruption_type: str,
    strategy: str,
    severity: str | None = None,
    limit: int = 40,
):
    """Raw ClickHouse provenance behind an evidence bar: the actual
    disruption_history rows for one (disruption_type, strategy) pair.
    Uses the Safe Query Builder — no free-form SQL, allowlisted params only."""
    if not clickhouse_client.is_configured():
        raise HTTPException(503, "ClickHouse is not configured. Add credentials to backend/.env.")
    from services import safe_query_builder

    try:
        sql = safe_query_builder.build_query(
            "raw_history_samples",
            {
                "disruption_type": disruption_type,
                "strategy": strategy,
                "severity": severity or "",
                "limit": limit,
            },
        )
    except safe_query_builder.UnsafeQueryError as exc:
        raise HTTPException(400, str(exc))

    try:
        result = await clickhouse_client.run_evidence_select(sql)
    except Exception as exc:  # noqa: BLE001
        logger.exception("evidence drilldown query failed")
        raise HTTPException(502, f"ClickHouse query failed: {str(exc)[:200]}")

    logger.info(
        "Evidence drilldown: %s/%s severity=%s → %d rows in %d ms",
        disruption_type, strategy, severity or "all",
        len(result["rows"]), result["latency_ms"],
    )
    from services import activity_log

    activity_log.record(
        "clickhouse", f"SELECT raw evidence · {strategy}",
        len(result["rows"]), result["latency_ms"],
    )
    return {
        "rows": result["rows"],
        "columns": result["columns"],
        "query_meta": {
            "sql": sql,
            "row_count": len(result["rows"]),
            "latency_ms": result["latency_ms"],
        },
        "provenance": {
            "source": "ClickHouse Cloud (live)",
            "database": os.environ.get("CLICKHOUSE_DATABASE", "continuity_council"),
            "table": "disruption_history",
            "query_builder": "safe_query_builder.raw_history_samples",
        },
    }


@api.get("/audit/{production_id}")
async def get_audit(
    production_id: str = Path(..., pattern=PRODUCTION_ID_PATTERN, description="Production ID"),
):
    if not clickhouse_client.is_configured():
        raise HTTPException(503, "ClickHouse is not configured. Add credentials to backend/.env.")
    if not await clickhouse_client.production_exists(production_id):
        raise HTTPException(404, f"Production {production_id} not found.")
    try:
        return await clickhouse_client.fetch_audit(production_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("audit fetch failed")
        raise HTTPException(502, f"ClickHouse query failed: {str(exc)[:200]}")


@api.post("/demo/reset")
async def reset_demo(
    production_id: str | None = Query(None, pattern=PRODUCTION_ID_PATTERN),
):
    """Restore the clean pre-disruption baseline for a production (or all).

    With `?production_id=...` only that production's event rows and in-memory
    cases are cleared. Without it, every production's events are truncated.
    The baseline schedule itself is never modified (overlay pattern)."""
    if not clickhouse_client.is_configured():
        raise HTTPException(503, "ClickHouse is not configured.")
    if production_id and not await clickhouse_client.production_exists(production_id):
        raise HTTPException(404, f"Production '{production_id}' not found")
    try:
        await clickhouse_client.reset_demo_events(production_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("demo reset failed")
        raise HTTPException(502, f"Demo reset failed: {str(exc)[:200]}")
    cleared = case_store.clear(production_id)
    logger.info("Demo reset (scope=%s): events cleared, %d in-memory cases cleared",
                production_id or "all", cleared)
    return {"status": "ok", "cleared_cases": cleared, "production_id": production_id}

@api.get("/geo/resolve")
async def resolve_geo(
    query: str,
    lat: float | None = None,
    lon: float | None = None,
):
    """Resolve location to coordinates, World Bank GDP PPP country factor, city tier, and currency."""
    info = await resolve_geo_economics(
        query,
        fallback_lat=lat if lat is not None else 34.05,
        fallback_lon=lon if lon is not None else -118.25,
    )
    return info


@api.get("/geo/country-factor")
async def get_country_factor_endpoint(country_code: str):
    """Get World Bank GDP PPP country factor for a country code."""
    return await geo_service.get_country_factor(country_code)


@api.post("/chat", response_model=ChatResponse)
@api.post("/chat/", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """Producer-facing conversational interface to ask questions about council reasoning."""
    chatbot = CouncilChatbot()
    try:
        res = await asyncio.wait_for(
            chatbot.ask(
                question=req.message,
                production_id=req.production_id,
                case_id=req.case_id,
            ),
            timeout=8.0,
        )
        return res
    except asyncio.TimeoutError:
        logger.warning("Chatbot request timed out after 8.0s")
        return {
            "answer": "I'm having a little trouble reaching the council right now — one moment, or try asking me how to report a disruption. I'm always here to help you step-by-step!",
            "sources": [],
        }
    except Exception as exc:
        logger.exception("Chatbot request failed: %s", exc)
        return {
            "answer": "I'm having a little trouble reaching the council right now — one moment, or try asking me how to report a disruption. I'm always here to help you step-by-step!",
            "sources": [],
        }


app.include_router(api)

# Route aliases on app root to ensure POST /chat or direct POST /api/chat never return 404/405
@app.post("/chat", response_model=ChatResponse, include_in_schema=False)
@app.post("/chat/", response_model=ChatResponse, include_in_schema=False)
@app.post("/api/chat", response_model=ChatResponse, include_in_schema=False)
@app.post("/api/chat/", response_model=ChatResponse, include_in_schema=False)
async def app_chat_fallback(req: ChatRequest):
    return await chat_endpoint(req)


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


def _frontend_build_dir() -> FilePath:
    configured = os.environ.get("FRONTEND_BUILD_DIR", "../frontend/build")
    build_dir = FilePath(configured)
    return build_dir if build_dir.is_absolute() else (ROOT_DIR / build_dir).resolve()


FRONTEND_BUILD_DIR = _frontend_build_dir()
if FRONTEND_BUILD_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=FRONTEND_BUILD_DIR / "static"), name="static")

    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        if path.startswith("api/") or path in {"api", "docs", "redoc", "openapi.json"}:
            raise HTTPException(404, "Not found")
        return FileResponse(FRONTEND_BUILD_DIR / "index.html")


@app.on_event("startup")
async def startup():
    logger.info(
        "Continuity Council starting — ClickHouse configured: %s | Gemini configured: %s",
        clickhouse_client.is_configured(), gemini_client.is_configured(),
    )
    # Ensure post-seed schema additions (e.g. productions.director) exist.
    await clickhouse_client.ensure_schema()
    # Warm up persistent MCP client and Gemini in background
    asyncio.create_task(mcp_client.start_mcp_client())
    asyncio.create_task(_warmup_gemini())


@app.on_event("shutdown")
async def shutdown():
    await mcp_client.stop_mcp_client()


async def _warmup_gemini():
    marker = FilePath("/tmp/.gemini_warmup")
    try:
        import time as _time

        if marker.exists() and (_time.time() - marker.stat().st_mtime) < 900:
            return
        if gemini_client.is_configured():
            marker.touch()
            await gemini_client.generate_text("ok", timeout=10, temperature=0)
            logger.info("Gemini warmup complete")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini warmup skipped: %s", exc)
