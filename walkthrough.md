# Walkthrough: Rate-Card Cost Engine + Live External Signals + Methodology Surface

## Commit
`ab85fc3` — `feat: rate-card cost engine + live external signals + methodology surface`
26 files changed, 1,824 insertions, 354 deletions.

---

## What Was Built

### 1. Backend — Rate-Card Cost Engine & External Services

| File | What |
|---|---|
| [weather_service.py](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/backend/services/weather_service.py) | Open-Meteo 5-year climate risk model, 7d TTL cache, deterministic biome fallback |
| [finance_service.py](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/backend/services/finance_service.py) | Frankfurter/ECB live FX conversion, 24h TTL cache, benchmark rate fallback |
| [geo_service.py](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/backend/services/geo_service.py) | Haversine great-circle distance + Nominatim geocoder (1 req/s) |
| [budget_sentinel.py](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/backend/agents/budget_sentinel.py) | `calibrate_option_economics` — bottom-up rate card + 70/30 ClickHouse calibration |
| [compliance.py](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/backend/agents/compliance.py) | Haversine >100 mile same-day transit hard-fail rule |
| [models.py](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/backend/models.py) | `CostLineItem`, `CostBreakdown`, live signal fields on `RecoveryOption` |

### 2. Frontend — Global dayLabel + Live Signal Badges + Methodology Page

| File | What |
|---|---|
| [days.js](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/frontend/src/lib/days.js) | `dayToDate`, `dateToDay`, `dayLabel` → "Day 12 · Tue, Mar 3" |
| [dataSources.js](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/frontend/src/lib/dataSources.js) | Metadata for all 4 external data sources, signal impacts, rate card benchmarks |
| [DataMethodologyPage.jsx](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/frontend/src/pages/DataMethodologyPage.jsx) | Full methodology page: 70/30 formula, rate card table, 4 data source cards, signal impact matrix |
| [RecoveryOptionsPage.jsx](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/frontend/src/pages/RecoveryOptionsPage.jsx) | Cost breakdown accordion + live signal badges (weather, FX, transit) + dayLabel |
| [InvestigationPage.jsx](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/frontend/src/pages/InvestigationPage.jsx) | Live signals strip + dayLabel in header |
| [DashboardPage.jsx](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/frontend/src/pages/DashboardPage.jsx) | dayLabel on schedule timeline rows |
| [DecisionLedgerPage.jsx](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/frontend/src/pages/DecisionLedgerPage.jsx) | dayLabel on schedule change diffs (gold → green) |
| [ReportDisruptionPage.jsx](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/frontend/src/pages/ReportDisruptionPage.jsx) | Native `<input type="date">` constrained to shoot dates + live caption |
| [Shell.jsx](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/frontend/src/components/layout/Shell.jsx) | `/methodology` sidebar nav + global footer |
| [App.js](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/frontend/src/App.js) | `/methodology` route registered |

### 3. Documentation

| File | What |
|---|---|
| [COST_METHODOLOGY.md](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/docs/COST_METHODOLOGY.md) | Full breakdown: crew burn, cast holds, location fees × FX, weather contingency, 70/30 calibration |
| [DATA_SOURCES.md](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/docs/DATA_SOURCES.md) | Open-Meteo, OpenStreetMap, ECB, ClickHouse MCP — endpoints, TTLs, fallbacks, attribution |
| [README.md](file:///c:/Users/VH/Downloads/divya's-desk%20(1)/continuity-council/README.md) | Updated with links to both docs |

---

## Test Results

| Suite | Result |
|---|---|
| `pytest tests/test_units.py` | **31/31 passed** (3.86s) — includes Haversine, rate-card calibration, FX conversion |
| `yarn test --watchAll=false` | **5/5 passed** (26.3s) — days.js utility: dayToDate, dateToDay, dayLabel, getShootDateRange, fallbacks |
| `yarn build` | **Compiled successfully** (170.5 kB gzipped JS, 11.8 kB CSS) |
| `scripts/test_mcp.py` | **MCP round-trip SUCCESS** — 7 strategies, 200k rows, 8.6s total |
| Live investigation poll | **options_ready in 2.1 seconds** — cost breakdown + weather signal populated |

---

## Key Design Decisions

- **70/30 calibration** avoids pure hallucinated costs while leveraging real ClickHouse history
- **All external calls have 3s timeouts** + deterministic fallbacks — 15s SLA is never breached
- **dayLabel gracefully degrades**: if production has no dates → falls back to "Day N"
- **No new dependencies** except `httpx` (already present for async HTTP)
- **Attribution mandatory**: Open-Meteo (CC-BY 4.0), OpenStreetMap (ODbL), ECB via Frankfurter
