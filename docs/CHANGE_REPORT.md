# Continuity Council — Complete Change Report

## Phase 0 — Initial build (Emergent era)
| Area | Changes |
|---|---|
| Core app | FastAPI backend + React CRA frontend; 6-agent council (Orchestrator, Schedule Optimizer, Budget Sentinel, Continuity Memory, Compliance, Auditor); Gemini via google-genai; runtime mcp-clickhouse integration; ClickHouse schema (productions, scenes/schedule, disruption_history, decision_ledger); 6k-row seed; demo reset; deterministic fallback badge; evidence drilldown |
| Multi-tenancy | Onboarding wizard: production creation, cast/location CSV import, production switcher |
| Performance v1 | Parallel specialists, combined synthesis, warm-up, caching → ~9s investigations |

## Phase 1 — Local migration & hardening (VS Code era)
| Area | Changes |
|---|---|
| Dev environment | venv + deps, backend/.env secrets, frontend/.env.local, dev.bat |
| ClickHouse depth | strategy_performance_mv (AggregatingMergeTree, POPULATE); evidence via avgMerge/countMerge through MCP |
| Feature | Location-unavailable disruption type end-to-end (impact preview, compliance hard-fail, alternate-location options, ledger affected_location_id, seed cohort, tests) |
| Ops | GitHub Actions CI; README enterprise sections + CI badge; single-container Dockerfile (Python+Node), SPA served by FastAPI, .dockerignore, DEPLOYMENT.md |
| QA | Cold-start banner + retry, console sweep, empty states, a11y labels/focus, design audit; 26 tests |
| Hygiene | .gitignore platform artifacts; Emergent trace scrub; design_guidelines → docs/DESIGN.md |
| Packaging | docs/ARCHITECTURE.md (Mermaid), docs/DEVPOST_PITCH.md |

## Phase 2 — Scale, realism & enterprise features (Antigravity era)
| Area | Changes |
|---|---|
| Data scale | 6-production catalog (160/66/20/18/15-day shoots, 9–26 cast, 5–12 locations); disruption_history → 200k+ rows; live dashboard counts |
| UX | Date-aware shooting-day calendar + global "Day N · date" labels |
| Performance v2 | Persistent MCP singleton, asyncio.gather, Gemini budget ≤4 calls, 8s timeouts → 2.1s investigations |
| Cost engine | rate_cards table (indie/mid/tentpole benchmarks), cast day rates, location fees; bottom-up estimate + 0.7/0.3 historical calibration; cost breakdown accordion; COST_METHODOLOGY.md |
| Live signals | Open-Meteo weather risk, Nominatim geocoding + Haversine distance compliance (>100mi/<4h hard-fail), Frankfurter/ECB FX; TTL caches; live badges |
| Transparency | Data & Methodology page, global footer attribution, DATA_SOURCES.md |
| Enterprise ingest | Studio CSV import pipeline (validation, FX normalization, 10k batching), studio_id tenant isolation, cold-start blending (<200 → industry baseline) |
| Maps | Leaflet location picker; theme-aware CARTO Positron/Dark Matter basemaps, Esri satellite toggle, OSM fallback |
| Design | Apple-minimalist overhaul via Google Stitch MCP (tokens, light/dark, component system) |
| Geo intelligence | World Bank GDP-PPP country factors, OSM population city tiers, ISO-4217 currencies, user overrides; full Settings page |
| Repo | Single-commit history cleanup; CI clean-env fixes |
