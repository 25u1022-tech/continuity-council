"""Direct ClickHouse Cloud access via clickhouse-connect.

Used for: schedule reads, disruption_case events, decision ledger writes and
schedule change events. The Budget Sentinel agent does NOT use this module —
it queries through the official mcp-clickhouse MCP server (see mcp_client.py).

ClickHouse is treated as append-only: schedule updates are recorded as
`schedule_changes` events and overlaid at read time (no UPDATE statements).
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("continuity.clickhouse")


def _tick(label: str, rows: int | None = None, latency_ms: int | None = None) -> None:
    """Feed the Live MCP Ticker (never allowed to break a query)."""
    try:
        from services import activity_log

        activity_log.record("clickhouse", label, rows, latency_ms)
    except Exception:  # noqa: BLE001
        pass

_client = None
_client_lock = threading.Lock()

# clickhouse-connect sync clients forbid concurrent queries on one instance
# ("Attempt to execute concurrent queries within the same session"). Demo-scale
# load is tiny, so we serialize all direct ClickHouse operations.
_query_lock: asyncio.Lock = asyncio.Lock()


def is_configured() -> bool:
    return bool(os.environ.get("CLICKHOUSE_HOST", "").strip())


def _db() -> str:
    return os.environ.get("CLICKHOUSE_DATABASE", "continuity_council")


def _get_client():
    """Lazy singleton sync client (thread-safe)."""
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        import clickhouse_connect

        _client = clickhouse_connect.get_client(
            host=os.environ["CLICKHOUSE_HOST"],
            port=int(os.environ.get("CLICKHOUSE_PORT", "8443")),
            username=os.environ.get("CLICKHOUSE_USER", "default"),
            password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
            secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() != "false",
            connect_timeout=10,
            send_receive_timeout=30,
            # Allow safe concurrent queries from multiple request threads:
            # without this, clickhouse-connect raises ProgrammingError on
            # simultaneous queries sharing one session id.
            autogenerate_session_id=False,
        )
        logger.info("ClickHouse client connected to %s", os.environ["CLICKHOUSE_HOST"])
        return _client


def reset_client() -> None:
    global _client
    with _client_lock:
        _client = None


async def _run(fn, *args, **kwargs):
    async with _query_lock:
        return await asyncio.to_thread(fn, *args, **kwargs)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
async def ping() -> Dict[str, Any]:
    if not is_configured():
        return {"connected": False, "error": "CLICKHOUSE_HOST not configured"}
    try:
        def _ping():
            c = _get_client()
            version = c.command("SELECT version()")
            rows = c.command(f"SELECT COUNT(*) FROM {_db()}.disruption_history")
            return {"connected": True, "version": str(version), "history_rows": int(rows)}
        return await asyncio.wait_for(_run(_ping), timeout=12)
    except Exception as exc:  # noqa: BLE001
        logger.error("ClickHouse ping failed: %s", exc)
        reset_client()
        return {"connected": False, "error": str(exc)[:300]}


# ---------------------------------------------------------------------------
# Schema evolution (idempotent) — adds columns introduced after initial seed
# ---------------------------------------------------------------------------
async def ensure_schema() -> None:
    """Add columns and tables that post-date the original seed so old + new data coexist.
    Safe to call repeatedly (ClickHouse ADD COLUMN IF NOT EXISTS is metadata-only)."""
    if not is_configured():
        return
    def _ensure():
        c = _get_client()
        db = _db()
        c.command(
            f"ALTER TABLE {db}.productions ADD COLUMN IF NOT EXISTS director String DEFAULT ''"
        )
        c.command(
            f"ALTER TABLE {db}.productions ADD COLUMN IF NOT EXISTS tier String DEFAULT 'mid'"
        )
        c.command(
            f"ALTER TABLE {db}.productions ADD COLUMN IF NOT EXISTS studio_id String DEFAULT 'global'"
        )
        c.command(
            f"ALTER TABLE {db}.disruption_history ADD COLUMN IF NOT EXISTS studio_id String DEFAULT 'global'"
        )
        c.command(
            f"ALTER TABLE {db}.locations ADD COLUMN IF NOT EXISTS daily_fee_usd Int64 DEFAULT 5000"
        )
        c.command(
            f"ALTER TABLE {db}.locations ADD COLUMN IF NOT EXISTS latitude Float64 DEFAULT 0.0"
        )
        c.command(
            f"ALTER TABLE {db}.locations ADD COLUMN IF NOT EXISTS longitude Float64 DEFAULT 0.0"
        )
        c.command(
            f"ALTER TABLE {db}.locations ADD COLUMN IF NOT EXISTS currency_code String DEFAULT 'USD'"
        )
        c.command(
            f"ALTER TABLE {db}.cast_members ADD COLUMN IF NOT EXISTS day_rate_usd Int64 DEFAULT 1100"
        )
        c.command(
            f"ALTER TABLE {db}.decision_ledger ADD COLUMN IF NOT EXISTS affected_location_id String DEFAULT ''"
        )
        c.command(
            f"ALTER TABLE {db}.locations ADD COLUMN IF NOT EXISTS country_code String DEFAULT 'US'"
        )
        c.command(
            f"ALTER TABLE {db}.locations ADD COLUMN IF NOT EXISTS country_mult Float32 DEFAULT 1.0"
        )
        c.command(
            f"ALTER TABLE {db}.locations ADD COLUMN IF NOT EXISTS city_tier String DEFAULT 'tier_1'"
        )
        c.command(
            f"ALTER TABLE {db}.locations ADD COLUMN IF NOT EXISTS geo_mult Float32 DEFAULT 1.0"
        )
        c.command(f"""
            CREATE TABLE IF NOT EXISTS {db}.geo_cost_index
            (
                country_code String,
                country_mult Float32,
                gdp_ppp Float64,
                source_note String,
                updated_at DateTime DEFAULT now()
            )
            ENGINE = MergeTree
            ORDER BY country_code
        """)
        c.command(f"""
            CREATE TABLE IF NOT EXISTS {db}.rate_cards
            (
                tier String,
                item String,
                unit String,
                daily_rate_usd Int64,
                source_note String,
                created_at DateTime DEFAULT now()
            )
            ENGINE = MergeTree
            ORDER BY (tier, item)
        """)
    try:
        await _run(_ensure)
        logger.info("Schema ensured (rate_cards + geo/rates/studio columns + geo_cost_index present)")
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_schema skipped: %s", exc)


# ---------------------------------------------------------------------------
# World Bank Geo Cost Index Cache
# ---------------------------------------------------------------------------
async def get_cached_country_factor(country_code: str) -> Optional[Dict[str, Any]]:
    code = (country_code or "US").upper().strip()
    def _fetch():
        c = _get_client()
        db = _db()
        try:
            res = c.query(
                f"SELECT country_code, country_mult, gdp_ppp, source_note, updated_at "
                f"FROM {db}.geo_cost_index WHERE country_code = %(code)s AND updated_at >= now() - INTERVAL 30 DAY "
                f"ORDER BY updated_at DESC LIMIT 1",
                parameters={"code": code},
            )
            if not res.result_rows:
                return None
            r = res.result_rows[0]
            return {
                "country_code": r[0],
                "country_mult": float(r[1]),
                "gdp_ppp": float(r[2]),
                "source_note": str(r[3]),
                "is_fallback": False,
                "warning": "",
            }
        except Exception:
            return None
    return await _run(_fetch)


async def cache_country_factor(country_code: str, country_mult: float, gdp_ppp: float, note: str = "") -> None:
    code = (country_code or "US").upper().strip()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    def _insert():
        c = _get_client()
        db = _db()
        try:
            c.insert(
                f"{db}.geo_cost_index",
                [[code, float(country_mult), float(gdp_ppp), note or "World Bank open data (CC-BY 4.0)", now]],
                column_names=["country_code", "country_mult", "gdp_ppp", "source_note", "updated_at"],
            )
        except Exception as exc:
            logger.debug("Failed to cache country factor in ClickHouse: %s", exc)
    await _run(_insert)



# ---------------------------------------------------------------------------
# Production onboarding
# ---------------------------------------------------------------------------
DEMO_PRODUCTION_ID = "prod_001"


async def list_productions() -> List[Dict[str, Any]]:
    """All productions with lightweight counts for the switcher / management UI."""
    def _fetch():
        c = _get_client()
        db = _db()
        res = c.query(
            f"SELECT production_id, title, start_date, total_shoot_days, currency, director, created_at "
            f"FROM {db}.productions ORDER BY created_at ASC"
        )
        prods = []
        for r in res.result_rows:
            prods.append({
                "production_id": r[0], "title": r[1], "start_date": str(r[2]),
                "total_shoot_days": int(r[3]), "currency": r[4],
                "director": r[5] if len(r) > 5 else "",
                "created_at": r[6].isoformat() if len(r) > 6 and r[6] else "",
                "is_demo": r[0] == DEMO_PRODUCTION_ID,
            })
        # Counts per production (single grouped query each — demo scale is tiny)
        def _counts(table):
            q = c.query(f"SELECT production_id, COUNT(*) FROM {db}.{table} GROUP BY production_id")
            return {row[0]: int(row[1]) for row in q.result_rows}
        scene_counts = _counts("production_schedule")
        cast_counts = _counts("cast_members")
        loc_counts = _counts("locations")
        for p in prods:
            pid = p["production_id"]
            p["scene_count"] = scene_counts.get(pid, 0)
            p["cast_count"] = cast_counts.get(pid, 0)
            p["location_count"] = loc_counts.get(pid, 0)
        return prods

    return await _run(_fetch)


async def production_exists(production_id: str) -> bool:
    def _check():
        c = _get_client()
        res = c.query(
            f"SELECT count() FROM {_db()}.productions WHERE production_id = %(pid)s",
            parameters={"pid": production_id},
        )
        return int(res.result_rows[0][0]) > 0
    return await _run(_check)


async def title_exists(title: str) -> bool:
    def _check():
        c = _get_client()
        res = c.query(
            f"SELECT count() FROM {_db()}.productions WHERE lower(title) = %(t)s",
            parameters={"t": title.strip().lower()},
        )
        return int(res.result_rows[0][0]) > 0
    return await _run(_check)


async def create_production(
    production: Dict[str, Any],
    locations: List[Dict[str, Any]],
    cast: List[Dict[str, Any]],
    scenes: List[Dict[str, Any]],
    location_availability: List[Dict[str, Any]],
    cast_availability: List[Dict[str, Any]],
) -> None:
    """Persist a full production bundle to ClickHouse (append-only inserts)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    def _create():
        c = _get_client()
        db = _db()

        c.insert(
            f"{db}.productions",
            [[production["production_id"], production["title"], production["start_date"],
              int(production["total_shoot_days"]), production.get("currency", "USD"),
              production.get("director", ""), production.get("tier", "mid"), now]],
            column_names=["production_id", "title", "start_date", "total_shoot_days",
                          "currency", "director", "tier", "created_at"],
        )

        if locations:
            c.insert(
                f"{db}.locations",
                [[l["production_id"], l["location_id"], l["name"], l["location_type"],
                  int(l.get("capacity", 100)), int(l.get("daily_fee_usd", 5000)),
                  float(l.get("latitude", 0.0)), float(l.get("longitude", 0.0)),
                  l.get("currency_code", "USD"), l.get("notes", ""),
                  l.get("country_code", "US"), float(l.get("country_mult", 1.0)),
                  l.get("city_tier", "tier_1"), float(l.get("geo_mult", 1.0)),
                  now] for l in locations],
                column_names=["production_id", "location_id", "name", "location_type",
                              "capacity", "daily_fee_usd", "latitude", "longitude",
                              "currency_code", "notes", "country_code", "country_mult",
                              "city_tier", "geo_mult", "created_at"],
            )

        if cast:
            c.insert(
                f"{db}.cast_members",
                [[m["production_id"], m["cast_id"], m["name"], m["role_type"],
                  int(m.get("day_rate_usd", 1500)), now] for m in cast],
                column_names=["production_id", "cast_id", "name", "role_type", "day_rate_usd", "created_at"],
            )

        if scenes:
            c.insert(
                f"{db}.production_schedule",
                [[s["production_id"], s["scene_id"], s["scene_title"], int(s["shoot_day"]),
                  int(s["sequence_order"]), s["location_id"], list(s["required_cast"]),
                  s["scene_type"], int(s["is_cover_scene"]), int(s["priority"]),
                  list(s["continuity_tags"]), list(s["depends_on"]), s["status"], now]
                 for s in scenes],
                column_names=["production_id", "scene_id", "scene_title", "shoot_day",
                              "sequence_order", "location_id", "required_cast", "scene_type",
                              "is_cover_scene", "priority", "continuity_tags", "depends_on",
                              "status", "updated_at"],
            )

        if location_availability:
            c.insert(
                f"{db}.location_availability",
                [[a["production_id"], a["location_id"], int(a["shoot_day"]),
                  int(a["available"]), a.get("notes", ""), now] for a in location_availability],
                column_names=["production_id", "location_id", "shoot_day", "available",
                              "notes", "updated_at"],
            )

        if cast_availability:
            c.insert(
                f"{db}.cast_availability",
                [[a["production_id"], a["cast_id"], int(a["shoot_day"]),
                  int(a["available"]), a.get("reason", ""), now] for a in cast_availability],
                column_names=["production_id", "cast_id", "shoot_day", "available",
                              "reason", "updated_at"],
            )

    await _run(_create)
    _tick(f"INSERT production · {production['production_id']}", len(scenes))


# ---------------------------------------------------------------------------
# Production bundle (schedule + availability, with schedule_changes overlay)
# ---------------------------------------------------------------------------
async def fetch_production_bundle(production_id: str) -> Optional[Dict[str, Any]]:
    def _fetch():
        c = _get_client()
        db = _db()
        prod = c.query(
            f"SELECT production_id, title, start_date, total_shoot_days, currency, director, tier, studio_id "
            f"FROM {db}.productions WHERE production_id = %(pid)s LIMIT 1",
            parameters={"pid": production_id},
        )
        if not prod.result_rows:
            return None
        p = prod.result_rows[0]
        production = {
            "production_id": p[0], "title": p[1], "start_date": str(p[2]),
            "total_shoot_days": int(p[3]), "currency": p[4],
            "director": p[5] if len(p) > 5 else "",
            "tier": p[6] if len(p) > 6 and p[6] else "mid",
            "studio_id": p[7] if len(p) > 7 and p[7] else "global",
        }

        locs = c.query(
            f"SELECT location_id, name, location_type, capacity, daily_fee_usd, latitude, longitude, currency_code, notes, country_code, country_mult, city_tier, geo_mult "
            f"FROM {db}.locations WHERE production_id = %(pid)s ORDER BY location_id",
            parameters={"pid": production_id},
        )
        locations = [
            {
                "location_id": r[0], "name": r[1], "location_type": r[2],
                "capacity": int(r[3]), "daily_fee_usd": int(r[4]) if len(r) > 4 and r[4] is not None else 5000,
                "latitude": float(r[5]) if len(r) > 5 and r[5] is not None else 0.0,
                "longitude": float(r[6]) if len(r) > 6 and r[6] is not None else 0.0,
                "currency_code": r[7] if len(r) > 7 and r[7] else "USD",
                "notes": r[8] if len(r) > 8 else "",
                "country_code": r[9] if len(r) > 9 and r[9] else "US",
                "country_mult": float(r[10]) if len(r) > 10 and r[10] is not None else 1.0,
                "city_tier": r[11] if len(r) > 11 and r[11] else "tier_1",
                "geo_mult": float(r[12]) if len(r) > 12 and r[12] is not None else 1.0,
            }
            for r in locs.result_rows
        ]

        cast = c.query(
            f"SELECT cast_id, name, role_type, day_rate_usd FROM {db}.cast_members "
            f"WHERE production_id = %(pid)s ORDER BY cast_id",
            parameters={"pid": production_id},
        )
        cast_members = [
            {
                "cast_id": r[0], "name": r[1], "role_type": r[2],
                "day_rate_usd": int(r[3]) if len(r) > 3 and r[3] is not None else 1100,
            }
            for r in cast.result_rows
        ]

        sched = c.query(
            f"SELECT scene_id, scene_title, shoot_day, sequence_order, location_id, required_cast, "
            f"scene_type, is_cover_scene, priority, continuity_tags, depends_on, status "
            f"FROM {db}.production_schedule WHERE production_id = %(pid)s "
            f"ORDER BY shoot_day, sequence_order",
            parameters={"pid": production_id},
        )
        scenes = [
            {
                "scene_id": r[0], "scene_title": r[1], "shoot_day": int(r[2]),
                "sequence_order": int(r[3]), "location_id": r[4],
                "required_cast": list(r[5]), "scene_type": r[6],
                "is_cover_scene": bool(r[7]), "priority": int(r[8]),
                "continuity_tags": list(r[9]), "depends_on": list(r[10]),
                "status": r[11],
            }
            for r in sched.result_rows
        ]

        # Overlay append-only schedule change events (ClickHouse-idiomatic)
        changes = c.query(
            f"SELECT scene_id, new_shoot_day, new_location_id, change_type, created_at "
            f"FROM {db}.schedule_changes WHERE production_id = %(pid)s ORDER BY created_at ASC",
            parameters={"pid": production_id},
        )
        by_scene = {s["scene_id"]: s for s in scenes}
        for r in changes.result_rows:
            sc = by_scene.get(r[0])
            if sc:
                sc["shoot_day"] = int(r[1])
                if r[2]:
                    sc["location_id"] = r[2]
                sc["status"] = "moved"
        scenes.sort(key=lambda s: (s["shoot_day"], s["sequence_order"]))

        la = c.query(
            f"SELECT location_id, shoot_day, available, notes FROM {db}.location_availability "
            f"WHERE production_id = %(pid)s",
            parameters={"pid": production_id},
        )
        location_availability = [
            {"location_id": r[0], "shoot_day": int(r[1]), "available": bool(r[2]), "notes": r[3]}
            for r in la.result_rows
        ]

        ca = c.query(
            f"SELECT cast_id, shoot_day, available, reason FROM {db}.cast_availability "
            f"WHERE production_id = %(pid)s",
            parameters={"pid": production_id},
        )
        cast_availability = [
            {"cast_id": r[0], "shoot_day": int(r[1]), "available": bool(r[2]), "reason": r[3]}
            for r in ca.result_rows
        ]

        return {
            "production": production,
            "locations": locations,
            "cast_members": cast_members,
            "scenes": scenes,
            "location_availability": location_availability,
            "cast_availability": cast_availability,
        }

    return await _run(_fetch)


async def get_current_schedule(production_id: str) -> Optional[Dict[str, Any]]:
    """TRD Tool 1: `get_current_schedule` — production summary + current schedule."""
    return await fetch_production_bundle(production_id)


# ---------------------------------------------------------------------------
# Event writes (append-only)
# ---------------------------------------------------------------------------
async def insert_disruption_case(case) -> None:
    def _ins():
        c = _get_client()
        c.insert(
            f"{_db()}.disruption_cases",
            [[
                case.case_id, case.production_id, case.disruption.disruption_type,
                case.disruption.severity, case.disruption.affected_day,
                case.disruption.affected_cast_id, case.disruption.affected_location_id,
                case.disruption.notes, case.status, datetime.now(timezone.utc).replace(tzinfo=None),
            ]],
            column_names=[
                "case_id", "production_id", "disruption_type", "severity", "affected_day",
                "affected_cast_id", "affected_location_id", "details", "status", "created_at",
            ],
        )
    await _run(_ins)
    _tick("INSERT disruption_cases", 1)


async def insert_decision(decision_row: Dict[str, Any]) -> None:
    def _ins():
        c = _get_client()
        c.insert(
            f"{_db()}.decision_ledger",
            [[
                decision_row["decision_id"], decision_row["case_id"], decision_row["production_id"],
                decision_row["disruption_type"], decision_row["selected_option"],
                decision_row.get("affected_location_id", ""),
                decision_row["option_summary"], decision_row["estimated_cost_usd"],
                decision_row["estimated_delay_hours"], decision_row["continuity_risk_score"],
                decision_row["compliance_risk_score"], decision_row["evidence_json"],
                decision_row["approved_by"], datetime.now(timezone.utc).replace(tzinfo=None),
            ]],
            column_names=[
                "decision_id", "case_id", "production_id", "disruption_type", "selected_option",
                "affected_location_id",
                "option_summary", "estimated_cost_usd", "estimated_delay_hours",
                "continuity_risk_score", "compliance_risk_score", "evidence_json",
                "approved_by", "approved_at",
            ],
        )
    await _run(_ins)
    _tick("INSERT decision_ledger", 1)


async def insert_schedule_changes(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    def _ins():
        c = _get_client()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        c.insert(
            f"{_db()}.schedule_changes",
            [[
                r["change_id"], r["decision_id"], r["production_id"], r["scene_id"],
                r["old_shoot_day"], r["new_shoot_day"], r["old_location_id"],
                r["new_location_id"], r["change_type"], now,
            ] for r in rows],
            column_names=[
                "change_id", "decision_id", "production_id", "scene_id", "old_shoot_day",
                "new_shoot_day", "old_location_id", "new_location_id", "change_type", "created_at",
            ],
        )
    await _run(_ins)
    _tick("INSERT schedule_changes", len(rows))


async def insert_disruption_history_rows(rows: List[Dict[str, Any]]) -> None:
    """Batch-insert disruption_history rows tagged with studio_id."""
    if not rows:
        return

    def _ins():
        c = _get_client()
        column_names = [
            "disruption_id", "production_type", "disruption_type", "severity",
            "affected_role", "affected_scene_count", "resolution_strategy",
            "cost_overrun_usd", "schedule_delay_hours", "continuity_risk_score",
            "compliance_risk_score", "success_score", "notes", "created_at", "studio_id",
        ]
        data = [
            [
                r["disruption_id"], r["production_type"], r["disruption_type"],
                r["severity"], r["affected_role"], r["affected_scene_count"],
                r["resolution_strategy"], r["cost_overrun_usd"], r["schedule_delay_hours"],
                r["continuity_risk_score"], r["compliance_risk_score"], r["success_score"],
                r["notes"], r["created_at"], r.get("studio_id", "global"),
            ]
            for r in rows
        ]
        c.insert(f"{_db()}.disruption_history", data, column_names=column_names)

    await _run(_ins)
    _tick(f"INSERT disruption_history · {rows[0].get('studio_id', 'global')}", len(rows))


async def fetch_studio_history_count(studio_id: str) -> int:
    """Count of disruption_history rows for a given studio."""
    def _count():
        c = _get_client()
        db = _db()
        cnt = c.command(
            f"SELECT count(*) FROM {db}.disruption_history WHERE studio_id = %(sid)s",
            parameters={"sid": studio_id},
        )
        return int(cnt or 0)
    return await _run(_count)


async def update_production_studio(production_id: str, studio_id: str) -> None:
    """Associate a production with a studio_id."""
    def _update():
        c = _get_client()
        db = _db()
        c.command(
            f"ALTER TABLE {db}.productions UPDATE studio_id = %(sid)s WHERE production_id = %(pid)s",
            parameters={"sid": studio_id, "pid": production_id},
        )
    try:
        await _run(_update)
    except Exception as exc:  # noqa: BLE001
        logger.warning("update_production_studio skipped: %s", exc)


async def reset_demo_events(production_id: Optional[str] = None) -> None:
    """Reset event tables so the schedule overlay returns to baseline.

    - With `production_id`: lightweight DELETE of just that production's events
      (other productions untouched).
    - Without: TRUNCATE all event tables (global demo reset).
    Reference tables (schedule, cast, history) are never touched.
    """
    tables = ("disruption_cases", "decision_ledger", "schedule_changes")

    def _reset():
        c = _get_client()
        db = _db()
        if production_id:
            for tbl in tables:
                c.command(
                    f"DELETE FROM {db}.{tbl} WHERE production_id = %(pid)s",
                    parameters={"pid": production_id},
                )
        else:
            for tbl in tables:
                c.command(f"TRUNCATE TABLE {db}.{tbl}")

    await _run(_reset)
    scope = production_id or "all"
    _tick(f"Reset event tables · {scope}", 3)


async def run_evidence_select(sql: str) -> Dict[str, Any]:
    """Execute a Safe-Query-Builder-validated SELECT live against ClickHouse
    and return column names + row dicts with timing metadata. Used by the
    evidence drilldown endpoint (raw provenance rows behind an evidence bar)."""
    import time as _time

    def _fetch():
        c = _get_client()
        t0 = _time.perf_counter()
        res = c.query(sql)
        latency_ms = int((_time.perf_counter() - t0) * 1000)
        cols = list(res.column_names)
        rows = []
        for r in res.result_rows:
            row = {}
            for k, v in zip(cols, r):
                if isinstance(v, datetime):
                    row[k] = v.isoformat()
                else:
                    row[k] = v
            rows.append(row)
        return {"columns": cols, "rows": rows, "latency_ms": latency_ms}

    return await _run(_fetch)


async def fetch_audit(production_id: str) -> Dict[str, Any]:
    def _fetch():
        c = _get_client()
        db = _db()
        led = c.query(
            f"SELECT decision_id, case_id, disruption_type, selected_option, option_summary, "
            f"affected_location_id, "
            f"estimated_cost_usd, estimated_delay_hours, continuity_risk_score, "
            f"compliance_risk_score, evidence_json, approved_by, approved_at "
            f"FROM {db}.decision_ledger WHERE production_id = %(pid)s ORDER BY approved_at DESC",
            parameters={"pid": production_id},
        )
        decisions = [
            {
                "decision_id": r[0], "case_id": r[1], "disruption_type": r[2],
                "selected_option": r[3], "option_summary": r[4], "affected_location_id": r[5],
                "estimated_cost_usd": int(r[6]), "estimated_delay_hours": float(r[7]),
                "continuity_risk_score": float(r[8]), "compliance_risk_score": float(r[9]),
                "evidence_json": r[10], "approved_by": r[11], "approved_at": r[12].isoformat(),
            }
            for r in led.result_rows
        ]
        ch = c.query(
            f"SELECT change_id, decision_id, scene_id, old_shoot_day, new_shoot_day, "
            f"old_location_id, new_location_id, change_type, created_at "
            f"FROM {db}.schedule_changes WHERE production_id = %(pid)s ORDER BY created_at DESC",
            parameters={"pid": production_id},
        )
        changes = [
            {
                "change_id": r[0], "decision_id": r[1], "scene_id": r[2],
                "old_shoot_day": int(r[3]), "new_shoot_day": int(r[4]),
                "old_location_id": r[5], "new_location_id": r[6],
                "change_type": r[7], "created_at": r[8].isoformat(),
            }
            for r in ch.result_rows
        ]
        return {"decisions": decisions, "schedule_changes": changes}

    return await _run(_fetch)


async def fetch_rate_cards(tier: str = "mid") -> Dict[str, int]:
    """Retrieve industry rate card benchmarks for a production tier."""
    def _fetch():
        c = _get_client()
        db = _db()
        try:
            res = c.query(
                f"SELECT item, daily_rate_usd FROM {db}.rate_cards WHERE tier = %(t)s",
                parameters={"t": tier.strip().lower()},
            )
            return {r[0]: int(r[1]) for r in res.result_rows}
        except Exception as exc:
            logger.warning("fetch_rate_cards failed (%s), using default fallbacks", exc)
            return {}

    rates = await _run(_fetch)
    # Default fallbacks if table not yet seeded or item missing
    tier_defaults = {
        "indie": {"crew_day": 40000, "sag_scale_day": 1100, "soundstage_day": 5000, "permit_day": 500, "camera_package_day": 1200},
        "mid": {"crew_day": 150000, "sag_scale_day": 3500, "soundstage_day": 10000, "permit_day": 1500, "camera_package_day": 2000},
        "tentpole": {"crew_day": 500000, "sag_scale_day": 15000, "soundstage_day": 25000, "permit_day": 5000, "camera_package_day": 3500},
    }
    base = dict(tier_defaults.get(tier.lower(), tier_defaults["mid"]))
    base.update(rates)
    return base
