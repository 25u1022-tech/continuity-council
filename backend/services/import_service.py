"""Historical Disruption CSV Import Pipeline.

Handles studio-specific historical data ingestion:
- CSV header inspection and alias mapping
- Strict type, range, and date sanity validation
- In-memory row deduplication
- Multi-currency normalization via ECB/Frankfurter FX rates
- 10,000-row batch insertion into ClickHouse tagged with studio_id
- Detailed error reporting (accepted vs. rejected rows with explicit reasons)
"""
from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from services import clickhouse_client
from services.finance_service import convert_currency, get_exchange_rate
from services.safe_query_builder import (
    ALLOWED_DISRUPTION_TYPES,
    ALLOWED_SEVERITIES,
    ALLOWED_STRATEGIES,
)

logger = logging.getLogger("continuity.import")

HEADER_ALIASES = {
    "date": "date",
    "timestamp": "date",
    "created_at": "date",
    "shoot_date": "date",
    "disruption_type": "disruption_type",
    "type": "disruption_type",
    "disruption": "disruption_type",
    "severity": "severity",
    "sev": "severity",
    "strategy": "strategy",
    "resolution_strategy": "strategy",
    "resolution": "strategy",
    "cost_overrun": "cost_overrun",
    "cost_overrun_usd": "cost_overrun",
    "cost": "cost_overrun",
    "overrun": "cost_overrun",
    "delay_hours": "delay_hours",
    "schedule_delay_hours": "delay_hours",
    "delay": "delay_hours",
    "hours_delayed": "delay_hours",
    "satisfaction": "satisfaction",
    "success_score": "satisfaction",
    "score": "satisfaction",
    "currency": "currency",
    "curr": "currency",
    "notes": "notes",
}

REQUIRED_CANONICAL_HEADERS = {
    "date",
    "disruption_type",
    "severity",
    "strategy",
    "cost_overrun",
    "delay_hours",
}


def normalize_string_key(val: str) -> str:
    """Normalize disruption type or strategy name into canonical snake_case."""
    return val.strip().lower().replace(" ", "_").replace("-", "_")


def parse_date(val: str) -> Optional[datetime]:
    """Parse various date formats between years 2000 and 2030."""
    val = val.strip()
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ):
        try:
            dt = datetime.strptime(val, fmt)
            if 2000 <= dt.year <= 2030:
                return dt
        except ValueError:
            continue
    return None


async def parse_and_validate_csv(
    csv_content: str, studio_id: str = "global"
) -> Dict[str, Any]:
    """Validate and normalize a CSV string, returning accepted rows and rejected reasons."""
    lines = [line for line in csv_content.splitlines() if line.strip()]
    if not lines:
        return {
            "accepted": 0,
            "rejected": [{"row": 0, "reason": "Empty CSV file"}],
            "total_rows": 0,
            "rows_to_insert": [],
            "studio_id": studio_id,
        }

    reader = csv.reader(io.StringIO("\n".join(lines)))
    try:
        raw_headers = next(reader)
    except StopIteration:
        return {
            "accepted": 0,
            "rejected": [{"row": 0, "reason": "Missing header row"}],
            "total_rows": 0,
            "rows_to_insert": [],
            "studio_id": studio_id,
        }

    # Map headers to canonical names
    header_map: Dict[int, str] = {}
    for idx, h in enumerate(raw_headers):
        clean_h = h.strip().lower().replace(" ", "_").replace("-", "_")
        canonical = HEADER_ALIASES.get(clean_h)
        if canonical:
            header_map[idx] = canonical

    missing_headers = REQUIRED_CANONICAL_HEADERS - set(header_map.values())
    if missing_headers:
        return {
            "accepted": 0,
            "rejected": [
                {
                    "row": 1,
                    "reason": f"Missing required columns: {', '.join(sorted(missing_headers))}",
                }
            ],
            "total_rows": 0,
            "rows_to_insert": [],
            "studio_id": studio_id,
        }

    seen_hashes: Set[str] = set()
    accepted_rows: List[Dict[str, Any]] = []
    rejected_rows: List[Dict[str, Any]] = []
    total_data_rows = 0

    # Cache FX rates encountered during import to minimize redundant async lookups
    fx_rate_cache: Dict[str, float] = {"USD": 1.0}

    for row_idx, row_values in enumerate(reader, start=2):
        if not row_values or all(not str(v).strip() for v in row_values):
            continue
        total_data_rows += 1

        record: Dict[str, Any] = {}
        for col_idx, val in enumerate(row_values):
            col_name = header_map.get(col_idx)
            if col_name:
                record[col_name] = str(val).strip()

        # 1. Date validation
        raw_date = record.get("date", "")
        parsed_dt = parse_date(raw_date)
        if not parsed_dt:
            rejected_rows.append(
                {"row": row_idx, "reason": f"Invalid date '{raw_date}' (must be 2000-2030)"}
            )
            continue

        # 2. Disruption type validation
        raw_disruption = normalize_string_key(record.get("disruption_type", ""))
        if raw_disruption not in ALLOWED_DISRUPTION_TYPES:
            rejected_rows.append(
                {
                    "row": row_idx,
                    "reason": f"Invalid disruption_type '{record.get('disruption_type')}'",
                }
            )
            continue

        # 3. Severity validation
        raw_severity = record.get("severity", "").strip().lower()
        if raw_severity not in ALLOWED_SEVERITIES:
            rejected_rows.append(
                {
                    "row": row_idx,
                    "reason": f"Invalid severity '{record.get('severity')}' (must be low/medium/high)",
                }
            )
            continue

        # 4. Strategy validation
        raw_strategy = normalize_string_key(record.get("strategy", ""))
        if raw_strategy not in ALLOWED_STRATEGIES:
            rejected_rows.append(
                {
                    "row": row_idx,
                    "reason": f"Invalid strategy '{record.get('strategy')}'",
                }
            )
            continue

        # 5. Cost overrun validation
        raw_cost = record.get("cost_overrun", "")
        try:
            cost_val = float(raw_cost.replace("$", "").replace(",", ""))
            if cost_val < 0:
                raise ValueError("Cost overrun cannot be negative")
        except ValueError:
            rejected_rows.append(
                {"row": row_idx, "reason": f"Invalid cost_overrun '{raw_cost}'"}
            )
            continue

        # 6. Delay hours validation
        raw_delay = record.get("delay_hours", "")
        try:
            delay_val = float(raw_delay.replace(",", ""))
            if delay_val < 0 or delay_val > 500:
                raise ValueError("Delay hours must be between 0 and 500")
        except ValueError:
            rejected_rows.append(
                {"row": row_idx, "reason": f"Invalid delay_hours '{raw_delay}'"}
            )
            continue

        # 7. Optional satisfaction score
        raw_satisfaction = record.get("satisfaction", "")
        satisfaction_score = 0.8  # default baseline
        if raw_satisfaction:
            try:
                s_val = float(raw_satisfaction)
                if s_val > 1.0:
                    satisfaction_score = max(0.0, min(1.0, s_val / 10.0))
                else:
                    satisfaction_score = max(0.0, min(1.0, s_val))
            except ValueError:
                satisfaction_score = 0.8

        # 8. Currency & FX Normalization
        currency = record.get("currency", "USD").strip().upper() or "USD"
        if currency not in fx_rate_cache:
            res_rate = await get_exchange_rate(currency, "USD")
            fx_rate_cache[currency] = float(res_rate.get("rate", 1.0))

        applied_fx_rate = fx_rate_cache[currency]
        cost_overrun_usd = int(round(cost_val * applied_fx_rate))

        # 9. Deduplication check
        row_hash = f"{parsed_dt.strftime('%Y-%m-%d')}|{raw_disruption}|{raw_severity}|{raw_strategy}|{cost_overrun_usd}|{round(delay_val, 1)}"
        if row_hash in seen_hashes:
            rejected_rows.append({"row": row_idx, "reason": "Duplicate entry"})
            continue
        seen_hashes.add(row_hash)

        # Notes with FX provenance
        user_notes = record.get("notes", "").strip()
        fx_note = f"Imported from {currency} (fx_rate: {applied_fx_rate:.4f})" if currency != "USD" else ""
        combined_notes = f"{user_notes} | {fx_note}".strip(" |")

        role = "lead" if "actor" in raw_disruption else "location" if "location" in raw_disruption else "department"

        accepted_rows.append({
            "disruption_id": f"imp_{uuid.uuid4().hex[:10]}",
            "production_type": "feature",
            "disruption_type": raw_disruption,
            "severity": raw_severity,
            "affected_role": role,
            "affected_scene_count": 2,
            "resolution_strategy": raw_strategy,
            "cost_overrun_usd": cost_overrun_usd,
            "schedule_delay_hours": float(round(delay_val, 2)),
            "continuity_risk_score": 0.25 if raw_severity == "high" else 0.15,
            "compliance_risk_score": 0.1,
            "success_score": float(round(satisfaction_score, 2)),
            "notes": combined_notes,
            "created_at": parsed_dt,
            "studio_id": studio_id,
        })

    return {
        "accepted": len(accepted_rows),
        "rejected": rejected_rows,
        "total_rows": total_data_rows,
        "rows_to_insert": accepted_rows,
        "studio_id": studio_id,
    }


async def import_historical_data(
    csv_content: str, studio_id: str = "global"
) -> Dict[str, Any]:
    """Validate, normalize, and batch-insert disruption history rows into ClickHouse."""
    validation = await parse_and_validate_csv(csv_content, studio_id=studio_id)
    rows_to_insert = validation.pop("rows_to_insert", [])

    inserted_count = 0
    if rows_to_insert:
        # Batch insert in chunks of 10,000 rows
        BATCH_SIZE = 10000
        for i in range(0, len(rows_to_insert), BATCH_SIZE):
            chunk = rows_to_insert[i : i + BATCH_SIZE]
            await clickhouse_client.insert_disruption_history_rows(chunk)
            inserted_count += len(chunk)

    # Fetch updated studio sample count
    new_sample_size = await clickhouse_client.fetch_studio_history_count(studio_id)

    validation["inserted"] = inserted_count
    validation["new_sample_size"] = new_sample_size
    return validation


def generate_template_csv() -> str:
    """Generate a clean, documented template CSV for disruption history import."""
    headers = [
        "date",
        "disruption_type",
        "severity",
        "strategy",
        "cost_overrun",
        "delay_hours",
        "satisfaction",
        "currency",
        "notes",
    ]
    sample_rows = [
        [
            "2025-10-14",
            "lead_actor_unavailable",
            "high",
            "shoot_cover_scenes",
            "34500",
            "4.5",
            "8.5",
            "USD",
            "Swapped to Scene 42 interior cover set",
        ],
        [
            "2025-11-02",
            "location_unavailable",
            "medium",
            "swap_locations",
            "28000",
            "2.0",
            "9.0",
            "EUR",
            "Stage 4 soundstage fallback with 48h notice",
        ],
        [
            "2025-12-05",
            "equipment_failure",
            "low",
            "use_stand_in",
            "12000",
            "1.5",
            "7.5",
            "GBP",
            "B-camera backup rig deployed on crane setup",
        ],
        [
            "2026-01-20",
            "weather_delay",
            "high",
            "move_to_later_day",
            "42000",
            "8.0",
            "6.5",
            "USD",
            "Heavy rainstorm on exterior ridge shoot day",
        ],
        [
            "2026-02-11",
            "supporting_actor_unavailable",
            "medium",
            "split_scene",
            "19500",
            "3.0",
            "8.0",
            "CAD",
            "Shot single coverage while holding two-shot setup",
        ],
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for r in sample_rows:
        writer.writerow(r)
    return output.getvalue()
