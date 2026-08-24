# 🎬 Continuity Council

![CI](https://github.com/25u1022-tech/continuity-council/actions/workflows/ci.yml/badge.svg)

> **Multi-agent film production recovery system — powered by ClickHouse Cloud + Gemini.**
>
> Built for the **"Lights. Camera. Code."** Hackathon — **ClickHouse Track**.

When a production disruption hits (lead actor out, location lost, weather, equipment failure), a council of six Gemini agents investigates, queries **5,000+ historical disruption records in ClickHouse through the official `mcp-clickhouse` MCP server at runtime**, ranks recovery options by cost / delay / continuity risk / compliance, and writes the producer's approved decision to an immutable ClickHouse ledger.

- **Hosted URL:** [HOSTED_URL]
- **Demo video:** _TODO — add YouTube/Vimeo link after recording (3-minute walkthrough of the demo loop below)_
- **License:** MIT

---

## Architecture

```text
Producer UI (React + Tailwind + shadcn/ui, Apple/macOS-inspired dark interface)
        │
        ▼
FastAPI Backend  (/api/*)
        │
        ▼
Orchestrator Agent ──── typed async state machine (Pydantic)
   ├── Schedule Optimizer  → generates 2-4 recovery options (scene moves/swaps)
   ├── Budget Sentinel     → Gemini tool-calling loop
   │        │  tool: query_disruption_history (Safe Query Builder templates ONLY)
   │        ▼
   │   MCP ClientSession (stdio) ──► official mcp-clickhouse server ──► ClickHouse Cloud
   ├── Continuity Memory   → dependency / costume / narrative risk analysis
   ├── Compliance          → deterministic constraint solver (availability, day limits)
   └── Auditor             → appends decision_ledger + schedule_changes to ClickHouse
```

**The workflow loop:** Disruption → Agents investigate → ClickHouse evidence → Ranked options → Producer approval → Schedule update → Audit ledger.

- [Enterprise Architecture](docs/ARCHITECTURE.md)
- [Cost Estimation Methodology & Calibration Engine](docs/COST_METHODOLOGY.md)
- [Live External Data Sources & Attribution Specification](docs/DATA_SOURCES.md)
- [Studio Historical Data Ingestion & Tenant Blending](docs/DATA_ONBOARDING.md)
- [Complete Change Report (Phases 0–2)](docs/CHANGE_REPORT.md)

## Tech Stack (track requirements)

| Layer | Technology |
|---|---|
| Database | **ClickHouse Cloud** (`clickhouse-connect` + official **`mcp-clickhouse`** MCP server) |
| AI | **Google Gemini** via the official **`google-genai`** SDK (function calling + structured output) |
| Agents | 6-agent orchestration: Orchestrator, Schedule Optimizer, Budget Sentinel, Continuity Memory, Compliance, Auditor |
| Backend | Python 3.11 + FastAPI + Pydantic |
| Frontend | React + Tailwind CSS + shadcn/ui |

## Runtime ClickHouse MCP usage (judge checklist)

1. `backend/services/mcp_client.py` — spawns the **official `mcp-clickhouse` server via stdio** and opens a real MCP `ClientSession` (`initialize` → `list_tools` → `call_tool("run_query")`).
2. `backend/agents/budget_sentinel.py` — Gemini's **only tool** is `query_disruption_history`; every execution goes through the MCP layer. The LLM **never writes raw SQL** — it picks a template from `backend/services/safe_query_builder.py` (SELECT-only, allowlisted params, banned-keyword scan).
3. The UI **Agent Investigation** screen shows a **Live MCP Call Log** — the exact SQL, latency (ms), and row counts of each MCP call, in real time.
4. The **Recovery Options** screen shows **"Historical Evidence (ClickHouse)"** side-by-side with the options.
5. `scripts/test_mcp.py` — standalone on-camera proof: spawns the MCP server, runs the evidence query, prints rows + latency.
6. MCP layer is **read-only** (`CLICKHOUSE_ALLOW_WRITE_ACCESS=false`); ledger writes use `clickhouse-connect` directly (append-only event tables).

## 🤖 Built with Google Agent Development Kit (ADK)

Continuity Council is engineered on Google's **Agent Development Kit (ADK)** (`google-adk`), orchestrating specialist agents through native hierarchical composition (`SequentialAgent` and `ParallelAgent`). ADK provides predictable state management, typed session memory, robust async generator execution (`runner.run_async`), and production-grade tool calling schemas.

### The 6 ADK Specialist Agents & Roles

- **Orchestrator (`SequentialAgent`)**: Coordinates the top-level recovery pipeline by chaining candidate option generation, parallel multi-agent evaluation, and Gemini-driven executive synthesis.
- **Budget Sentinel (`Agent` + `FunctionTool`)**: Invokes `query_disruption_history` to query ClickHouse empirical disruption benchmarks through the official `mcp-clickhouse` MCP server with zero SQL injection risk.
- **Schedule Optimizer (`Agent` + `FunctionTool`)**: Generates candidate slates (`generate_recovery_options_tool`) and polishes recovery plans into crisp, producer-grade descriptions via structured LLM generation.
- **Continuity Memory (`Agent` + `FunctionTool`)**: Evaluates scene dependency DAGs, narrative order prerequisites, and costume/wardrobe tag splits (`evaluate_continuity_risks_tool`).
- **Compliance (`Agent` + `FunctionTool`)**: Solves location/cast union availability, working-hour limits, and enforces the 100-mile same-day geographic transit constraint (`validate_compliance_rules_tool`).
- **Auditor (`Agent` + `FunctionTool`)**: Appends producer-approved recovery decisions and granular scene change records into immutable ClickHouse event tables (`write_decision_ledger_tool`).

### How to Verify (Judge CLI Demo)

Run the judge-facing interactive ADK console demonstration:

```bash
python backend/scripts/demo_adk_council.py
```

## Setup

### 1. Prerequisites
- Python 3.11+, Node 18+ (yarn)
- A [ClickHouse Cloud](https://clickhouse.cloud) service (free trial works)
- A [Gemini API key](https://aistudio.google.com/app/apikey) from Google AI Studio

### 2. Install

```bash
pip install -r backend/requirements.txt   # includes clickhouse-connect, mcp, mcp-clickhouse, google-genai
cd frontend && yarn install
```

### 3. Environment variables

Copy `.env.example` → `backend/.env` and fill in:

| Variable | Description | Example |
|---|---|---|
| `CLICKHOUSE_HOST` | ClickHouse Cloud HTTPS host | `abc123.us-central1.gcp.clickhouse.cloud` |
| `CLICKHOUSE_PORT` | HTTPS port | `8443` |
| `CLICKHOUSE_USER` | DB user | `default` |
| `CLICKHOUSE_PASSWORD` | DB password | `••••••` |
| `CLICKHOUSE_DATABASE` | Database name | `continuity_council` |
| `CLICKHOUSE_SECURE` | TLS | `true` |
| `GEMINI_API_KEY` | Google AI Studio key | `AIza…` |
| `GEMINI_MODEL` | Gemini model | `gemini-3.6-flash` |

Frontend needs `frontend/.env` → `REACT_APP_BACKEND_URL=<backend origin>`.

### 4. Create schema + seed data

```bash
python clickhouse/seed.py
```

Creates the `continuity_council` database, all **10 tables** (`clickhouse/schema.sql`), seeds 6 realistic demo productions spanning diverse shoot archetypes (*The Long Dark Take*, *IRON HORIZON*, *THE LAST REEL*, *NIGHTFALL PROTOCOL*, *SALT & SMOKE*, *CRIMSON STATIC*) and generates **200,000+ realistic synthetic `disruption_history` rows** with the distributions from the schema doc.

### 5. Run the MCP proof (on camera)

```bash
python scripts/test_mcp.py     # official mcp-clickhouse round-trip: tools list → SELECT → rows + latency
python scripts/test_core.py    # full core POC: clickhouse-connect + MCP + Gemini function-calling
```

### 6. Start

```bash
# backend
uvicorn server:app --host 0.0.0.0 --port 8001 --reload   # from backend/
# frontend
cd frontend && yarn start
```

## mcp-clickhouse server configuration

See [`mcp/clickhouse_mcp_config.md`](mcp/clickhouse_mcp_config.md). The backend spawns the server itself (stdio) — no separate process needed. Standalone equivalent:

```bash
CLICKHOUSE_HOST=... CLICKHOUSE_USER=default CLICKHOUSE_PASSWORD=... \
CLICKHOUSE_SECURE=true CLICKHOUSE_MCP_SERVER_TRANSPORT=stdio mcp-clickhouse
```

Tools exposed: `list_databases`, `list_tables`, `run_query` (read-only).

## API

All TRD endpoints are implemented verbatim, served under the `/api` prefix (required by the hosting ingress, which routes `/api/*` to the backend):

| TRD endpoint | Implementation | Purpose |
|---|---|---|
| `GET /productions/{id}` | `GET /api/productions/{id}` | Production summary + schedule (with change overlay) |
| `POST /disruptions` | `POST /api/disruptions` | Report disruption → creates case → dispatches agents |
| `GET /cases/{case_id}` | `GET /api/cases/{case_id}` | Live investigation state: agent statuses, MCP call log, ranked options |
| `POST /cases/{case_id}/approve` | `POST /api/cases/{case_id}/approve` | Producer approval → Auditor writes ClickHouse ledger |
| `GET /audit/{production_id}` | `GET /api/audit/{production_id}` | Decision ledger + schedule changes |
| — | `GET /api/health` | ClickHouse connection status + Gemini config |
| — | `POST /api/demo/reset` | Restore clean pre-disruption baseline (clears event tables) |
| — | `GET /api/evidence/drilldown` | Raw `disruption_history` rows behind one evidence bar (Safe Query Builder template `raw_history_samples`; params: `disruption_type`, `strategy`, optional `severity`, `limit` ≤ 100) |

## Agent tools (TRD Tool Definitions)

| TRD tool | Implementation |
|---|---|
| `get_current_schedule` | `backend/services/clickhouse_client.py::get_current_schedule` |
| `generate_schedule_options` | `backend/agents/schedule_optimizer.py::generate_schedule_options` |
| `query_disruption_history` | `backend/agents/budget_sentinel.py` (Gemini tool → Safe Query Builder → **mcp-clickhouse**) |
| `validate_continuity` | `backend/agents/continuity_memory.py::validate_continuity` |
| `validate_compliance` | `backend/agents/compliance.py::validate_compliance` |
| `write_decision_ledger` | `backend/agents/auditor.py::write_decision_ledger` |

## Tests

```bash
python -m pytest tests/test_units.py -v   # 19 unit tests: option generation, TRD scoring formula,
                                          # compliance validation, continuity risk, safe query builder
python scripts/test_core.py               # integration: ClickHouse + MCP round-trip + Gemini
python scripts/test_mcp.py                # standalone MCP proof (on camera)
```

## Option Scoring Model (TRD)

```text
score = 0.40 × cost_saving_score      (normalized from ClickHouse historical cost overrun)
      + 0.30 × delay_saving_score     (normalized from ClickHouse historical delay hours)
      + 0.20 × (1 − continuity_risk_score)
      + 0.10 × (1 − compliance_risk_score)
```
Options failing hard compliance constraints are marked **Invalid** and heavily penalized (×0.25).

## Repository layout

```text
backend/            FastAPI app, 6 agents, MCP client, safe query builder, scoring
frontend/           React SPA — 5 screens (Dashboard, Report, Investigation, Options, Ledger)
clickhouse/         schema.sql, seed.py, queries.sql
mcp/                mcp-clickhouse configuration notes
scripts/            test_mcp.py (MCP proof), test_core.py (core POC harness)
docs/               PRD, TRD, app flow, schema, implementation plan
```

## Demo flow (3 minutes)

1. Dashboard: *The Long Dark Take* — 3-day schedule, cast/location availability, 200,000+ row ClickHouse history.
2. Report: **Lead actor unavailable — Day 2 — High severity.**
3. Investigation: watch 6 agents run; **Live MCP Call Log** shows real SQL against ClickHouse Cloud with latency + row counts.
4. Options: 3 ranked recovery options with **Historical Evidence (ClickHouse)** side-by-side; option B blocked by compliance (harbor permit expired Day 3).
5. Approve "Shoot cover scenes" → Auditor writes the decision.
6. Ledger: immutable decision + schedule changes, straight from `continuity_council.decision_ledger`.

## Why ClickHouse

Recovery decisions require instant aggregation over thousands of historical
disruptions (avg cost overrun, avg delay, sample size per strategy). ClickHouse's
columnar engine delivers sub-100ms analytical queries where row-stores degrade.
The official `mcp-clickhouse` server exposes this data to the agent council at
runtime via the Model Context Protocol — the AI doesn't guess, it queries.
A pre-aggregating materialized view (`strategy_performance_mv`) keeps evidence lookups fast as history grows.

## Security Posture

- Secrets live only in environment variables; `.env.example` ships placeholders.
- TLS-encrypted ClickHouse Cloud connections (port 8443).
- Budget Sentinel uses predefined, parameterized query templates — the LLM can
        never author raw SQL (no injection, no hallucinated tables).
- Immutable decision ledger: approved decisions are append-only audit records.
- Roadmap: studio accounts + RBAC, per-tenant ClickHouse isolation (SOC2 path).

## Roadmap

1. Multi-tenant production onboarding at scale (CSV/Sheets sync)
2. Per-studio historical evidence (data moat: every resolved case compounds)
3. Streaming schedule diffs via WebSockets

## Local Development

Prerequisites: Python 3.11, Node 18+, Yarn.
1. `cd backend && python -m venv .venv && .venv\Scripts\python.exe -m pip install -r requirements.txt`
2. Copy `.env.example` to `backend/.env` and fill in your secrets.
3. `cd frontend && echo REACT_APP_BACKEND_URL=http://localhost:8000 > .env.local && yarn install`
4. Run `dev.bat` (starts backend on :8000 and frontend on :3000).

## Deployment

The production Docker image serves the built React UI and FastAPI API from one web service and one origin on port 8000, so no CORS or proxy configuration is required. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for Render.com deployment steps.
