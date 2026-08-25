# Studio Historical Data Onboarding & Tenant-Isolated Cold-Start Blending

This document outlines the data specification, ingestion pipeline, multi-currency normalization, and Bayesian cold-start blending model powering Continuity Council's tenant-isolated intelligence.

---

## 1. Overview & Privacy Architecture

Continuity Council allows film studios and production companies to upload their proprietary disruption logs to personalize recovery option predictions.

- **Strict Tenant Isolation**: All ingested rows are stored in ClickHouse tagged with the production's unique `studio_id`.
- **Zero Cross-Tenant Data Leakage**: Studio rows are strictly quarantined. Competing studios and standard users only query their own cohort or the anonymized global industry baseline (`studio_id = 'global'`).
- **Sub-Second Columnar Aggregations**: Queries run in **<15ms** across millions of rows via ClickHouse MergeTree indexing.

---

## 2. CSV File Specification

Studios can upload historical logs via the web UI (`Create Production Wizard` or `Data & Methodology` page) or through the REST API.

### Column Definitions

| Header | Canonical Key | Required? | Data Type | Permitted Values / Constraints | Example |
|---|---|---|---|---|---|
| `date` | `date` | **Yes** | ISO Date / String | YYYY-MM-DD (2000-01-01 to 2030-12-31) | `2025-10-14` |
| `disruption_type` | `disruption_type` | **Yes** | Enum String | `lead_actor_unavailable`, `supporting_actor_unavailable`, `location_unavailable`, `equipment_failure`, `weather_delay`, `permit_issue` | `lead_actor_unavailable` |
| `severity` | `severity` | **Yes** | Enum String | `low`, `medium`, `high` | `high` |
| `strategy` | `strategy` | **Yes** | Enum String | `shoot_cover_scenes`, `swap_locations`, `move_to_later_day`, `wait_for_actor`, `recast_scene`, `split_scene`, `use_stand_in` | `shoot_cover_scenes` |
| `cost_overrun` | `cost_overrun` | **Yes** | Float / Integer | $\ge 0$ (Currency symbol or commas stripped) | `34500` |
| `delay_hours` | `delay_hours` | **Yes** | Float | $0.0 \le \text{hours} \le 500.0$ | `4.5` |
| `satisfaction` | `satisfaction` | No | Float | $0.0 \dots 10.0$ (normalized to $0.0 \dots 1.0$ score) | `8.5` |
| `currency` | `currency` | No | ISO-4217 String | `USD`, `EUR`, `GBP`, `CAD`, `AUD`, `JPY`, etc. Default: `USD` | `EUR` |
| `notes` | `notes` | No | String | Free-form resolution context | `Swapped to Scene 42 interior` |

### Supported Header Aliases
The parser automatically normalizes common header variations:
- `timestamp`, `created_at`, `shoot_date` $\rightarrow$ `date`
- `type`, `disruption` $\rightarrow$ `disruption_type`
- `resolution_strategy`, `resolution` $\rightarrow$ `strategy`
- `cost_overrun_usd`, `cost`, `overrun` $\rightarrow$ `cost_overrun`
- `schedule_delay_hours`, `delay`, `hours_delayed` $\rightarrow$ `delay_hours`
- `success_score`, `score` $\rightarrow$ `satisfaction`

---

## 3. Ingestion & Validation Pipeline

1. **Header Verification**: Ensures all 6 required canonical columns exist.
2. **Type & Range Sanitization**:
   - Dates validated within bounds [2000, 2030].
   - Numeric costs and delays validated non-negative.
   - Enums checked against strict allowlists (ignoring casing and hyphens).
3. **Multi-Currency Normalization**:
   - Non-USD costs are converted to USD at import time using live rates from the European Central Bank (ECB) via Frankfurter.
   - Applied FX rate is permanently stamped into the row audit note (e.g. `Imported from EUR (fx_rate: 1.0850)`).
4. **Deduplication**:
   - Calculates a deterministic fingerprint: `hash(date | disruption_type | severity | strategy | cost_usd | delay_hours)`.
   - Rejects intra-batch duplicates with explicit line error tracking.
5. **High-Throughput Insertion**:
   - Inserted in chunks of 10,000 rows directly into `continuity_council.disruption_history`.

---

## 4. Cold-Start Blending Formula

When a studio has limited historical samples, purely studio-specific averages are noisy, while purely global averages lack studio-specific cost structures. We apply an adaptive 200-sample cold-start blending function:

$$\text{Sample Weight } w = \min\left(1.0, \frac{N_{\text{studio}}}{200}\right)$$

For each disruption recovery strategy:

$$\text{Blended Metric} = w \cdot \bar{X}_{\text{studio}} + (1 - w) \cdot \bar{X}_{\text{global}}$$

### Convergence Properties:
- **$N_{\text{studio}} = 0$**: 100% Industry Baseline ($w = 0.0$). Footnote: `industry baseline (n=200,000)`.
- **$N_{\text{studio}} = 50$**: 25% Studio Data + 75% Global Baseline ($w = 0.25$). Footnote: `blended with industry baseline (studio n=50, industry n=200,000)`.
- **$N_{\text{studio}} = 100$**: 50% Studio Data + 50% Global Baseline ($w = 0.50$).
- **$N_{\text{studio}} \ge 200$**: 100% Studio Cohort ($w = 1.0$). Footnote: `100% studio cohort (n=...)`.

---

## 5. API Reference

### `POST /api/productions/{id}/import-history`
Upload a multipart CSV file to ingest historical rows for a production studio.

**Request**:
```http
POST /api/productions/prod_002/import-history HTTP/1.1
Content-Type: multipart/form-data; boundary=---Boundary

---Boundary
Content-Disposition: form-data; name="file"; filename="studio_history.csv"
Content-Type: text/csv

date,disruption_type,severity,strategy,cost_overrun,delay_hours,currency
2025-11-01,lead_actor_unavailable,high,shoot_cover_scenes,28000,3.0,EUR
---Boundary--
```

**Response (`200 OK`)**:
```json
{
  "status": "ok",
  "production_id": "prod_002",
  "studio_id": "studio_prod_002",
  "accepted": 1,
  "rejected": [],
  "total_rows": 1,
  "inserted": 1,
  "new_sample_size": 1
}
```

### `GET /api/templates/disruption-history.csv`
Download the canonical CSV template pre-populated with documentation and sample rows.

### `GET /api/productions/{id}/studio-cohort`
Inspect the studio dataset size and current blending weight.

---

## 6. Shooting Schedule & Call Sheet PDF Ingestion (Gemini Document Understanding)

Producers can upload production shooting schedules, one-liners, and daily call sheets in PDF format. Gemini natively extracts the production structure into ClickHouse.

### Pipeline Architecture
1. **Upload & Bounds Validation**:
   - Accepts multipart PDF (`application/pdf`, up to 10MB, max 20 pages).
   - Validates `%PDF-` binary magic header.
   - Creates an asynchronous import job returning `{job_id, status: "pending"}`.
2. **Gemini Multimodal Document Extraction**:
   - Feeds the raw PDF bytes directly to Gemini (`gemini-3.6-flash`) with structured JSON schema.
   - Extracts shoot days, dates, scenes, cast members, and locations with a 30s timeout.
3. **Normalization & Deduplication**:
   - Case-insensitive cast and location name deduplication.
   - Standardizes `int_ext` (`INT`, `EXT`, `INT/EXT`) and `day_night` (`DAY`, `NIGHT`).
   - Automatically orders scenes by shoot day and sequence order.
4. **Interactive Preview**:
   - The UI polls `GET /api/imports/{job_id}` to display summary counts (days, scenes, cast, locations) and sample extracted breakdown tables.
5. **Confirmation & ClickHouse Upsert**:
   - `POST /api/imports/{job_id}/confirm` persists new locations to `continuity_council.locations`, cast members to `continuity_council.cast_members`, updates `continuity_council.productions.total_shoot_days`, and replaces `continuity_council.production_schedule`.

### Expected Extraction Payload Schema
```json
{
  "shoot_days": [
    {
      "day_number": 1,
      "date": "2026-08-24",
      "scenes": ["1", "2A"]
    }
  ],
  "scenes": [
    {
      "scene_number": "1",
      "scene_title": "Harbor Setup & Briefing",
      "description": "Detective meets informant at the dock",
      "location_name": "Harbor Pier 7 Exterior",
      "cast_names": ["Mara Voss", "Dev Okafor"],
      "int_ext": "EXT",
      "day_night": "DAY",
      "pages": 1.2,
      "shoot_day": 1
    }
  ],
  "locations": ["Harbor Pier 7 Exterior", "Stage A - Interrogation Set"],
  "cast": ["Mara Voss", "Dev Okafor", "Lena Petrov"]
}
```

---

## 7. Enterprise Roadmap
- [x] Phase 1: CSV Multipart Ingest + Validation Engine + ECB FX Normalization + $N/200$ Blending.
- [x] Phase 2: Native PDF Shooting Schedule & Call Sheet Ingestion via Gemini document understanding.
- [ ] Phase 3: Movie Magic Budgeting (MMB) & Entertainment Partners (EP) native file importers.
- [ ] Phase 4: Studio-specific rate card override sync via ClickHouse dictionary.
