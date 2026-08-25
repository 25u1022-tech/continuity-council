# 🎬 Continuity Council

![CI](https://github.com/25u1022-tech/continuity-council/actions/workflows/ci.yml/badge.svg)

> **Multi-agent film production recovery system — powered by Google Agent Development Kit (ADK), ClickHouse Cloud, and Google Gemini.**
>
> Built for the **"Lights. Camera. Code."** Hackathon — **ClickHouse Track**.

When a production disruption hits (lead actor out, location lost, weather delay, equipment failure), Continuity Council triggers an autonomous multi-agent recovery council built on **Google Agent Development Kit (ADK)**. The council investigates constraints, queries **historical disruption records in ClickHouse through the official `mcp-clickhouse` MCP server at runtime**, evaluates bottom-up rate-card economics with live weather and FX data, ranks recovery options via the TRD weighted scoring formula, and commits producer-approved decisions to an immutable ClickHouse ledger.

- **Hosted URL:** [HOSTED_URL]
- **License:** MIT

---

## 🏗️ Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│               Producer UI (React 18 + Tailwind CSS + shadcn/ui)             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ REST / JSON (HTTP)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (server.py on port 8000)                 │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ POST /api/disruptions
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ADK Runner (Runner.run_async)                         │
│                                      │                                      │
│  ┌───────────────────────────────────▼───────────────────────────────────┐  │
│  │       orchestrator_agent (Google ADK SequentialAgent Pipeline)        │  │
│  │                                                                       │  │
│  │  STAGE 1: Candidate Generation                                       │  │
│  │  └─► generate_agent (ADK BaseAgent)                                  │  │
│  │        └─► generate_schedule_options (2-4 candidate schedule moves)   │  │
│  │                                                                       │  │
│  │  STAGE 2: Parallel Specialist Evaluation                             │  │
│  │  └─► parallel_evaluator (Google ADK ParallelAgent)                    │  │
│  │        ├─► budget_sentinel_agent (MCP Historical Query Engine)        │  │
│  │        │     └─► SafeQueryBuilder (SELECT-only templates)             │  │
│  │        │           └─► Persistent MCP Client (stdio)                  │  │
│  │        │                 └─► official mcp-clickhouse server           │  │
│  │        │                       └─► ClickHouse Cloud (MV query)        │  │
│  │        ├─► continuity_memory_agent (DAG & Narrative Integrity)       │  │
│  │        │     └─► validate_continuity (prerequisites & costume tags)   │  │
│  │        ├─► compliance_agent (Operational Constraints)                 │  │
│  │        │     └─► validate_compliance (100mi transit & permit bounds)  │  │
│  │        └─► schedule_optimizer_agent (Description Polishing)           │  │
│  │              └─► polish_descriptions (Gemini 3.6-flash generation)   │  │
│  │                                                                       │  │
│  │  STAGE 3: Calibration & Executive Synthesis                          │  │
│  │  └─► synthesis_agent (ADK BaseAgent)                                 │  │
│  │        ├─► Rate-Card Pricing (Crew/Cast/Location bottom-up economics) │  │
│  │        ├─► Live External Signals (Open-Meteo weather + ECB FX rates)  │  │
│  │        ├─► 70/30 Blended Calibration (Bottom-up + ClickHouse history) │  │
│  │        ├─► TRD Formula Scoring (Normalized Cost, Delay, Risk weights) │  │
│  │        └─► Executive Briefing Generation (Gemini 3.6-flash)           │  │
│  └───────────────────────────────────┬───────────────────────────────────┘  │
└──────────────────────────────────────┼──────────────────────────────────────┘
                                       │ case.status = "options_ready"
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Producer Review & Option Approval                        │
│                     (POST /api/cases/{case_id}/approve)                     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│           POST-APPROVAL AUDIT COMMIT: Auditor Agent (ADK Agent)             │
│   └─► write_decision_ledger (Direct ClickHouse TLS Client)                  │
│         ├─► Appends immutable record to continuity_council.decision_ledger  │
│         └─► Records granular scene changes to schedule_changes table        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**The Workflow Loop:**
1. **Natural-language Disruption Reporting** $\rightarrow$ Producer enters free-text incidents ("Sarah broke her wrist, can't shoot Tuesday"); calendar-aware entity and day resolution pre-fills structured form.
2. **ADK Orchestration** $\rightarrow$ `Runner.run_async()` launches `SequentialAgent`.
3. **Stage 1 (Generation)** $\rightarrow$ Deterministic formulation of viable recovery moves.
4. **Stage 2 (Parallel Specialists)** $\rightarrow$ `ParallelAgent` evaluates ClickHouse MCP empirical benchmarks, narrative continuity DAGs, union/transit compliance, and option copy.
5. **Stage 3 (Synthesis)** $\rightarrow$ Bottom-up rate cards calibrated with live weather & FX signals, scored via TRD formula, with one-line natural-language explainability justifications citing ClickHouse evidence.
6. **Producer Review** $\rightarrow$ Producer reviews grounded options with plain-English justifications and selects the optimal recovery plan.
7. **Post-Approval Audit** $\rightarrow$ `Auditor` commits immutable audit ledger and schedule delta records to ClickHouse Cloud.

---

## 🤖 Built with Google Agent Development Kit (ADK)

Continuity Council is engineered natively on Google's **Agent Development Kit (ADK)** (`google-adk`), orchestrating specialist agents through hierarchical multi-agent composition (`SequentialAgent` and `ParallelAgent`). ADK provides predictable state management, typed session memory (`InMemorySessionService`), robust async generator execution (`Runner.run_async`), and production-grade tool calling schemas (`FunctionTool`).

### The Council Agents & Responsibilities

| Agent | ADK Class | Role in Pipeline | Primary Mechanism / Tools |
|---|---|---|---|
| **Orchestrator** | `SequentialAgent` | Top-level pipeline coordinator | Drives Stage 1 $\rightarrow$ Stage 2 $\rightarrow$ Stage 3 via `Runner.run_async` |
| **Generate Agent** | `BaseAgent` | Candidate schedule recovery generator | `generate_options_tool` formulation of scene swaps, holds, and cover pulls |
| **Budget Sentinel** | `BaseAgent` / `Agent` | ClickHouse empirical cost & delay benchmark engine | `query_disruption_history_tool` via official `mcp-clickhouse` MCP server |
| **Continuity Memory** | `BaseAgent` / `Agent` | Narrative sequence & costume continuity solver | `evaluate_continuity_risks_tool` dependency DAG & wardrobe tag validation |
| **Compliance** | `BaseAgent` / `Agent` | Operational feasibility & union rule validator | `validate_compliance_rules_tool` enforcing permits, hours, and 100mi transit rule |
| **Schedule Optimizer** | `BaseAgent` / `Agent` | Recovery description refiner | `generate_recovery_options_tool` + Gemini 3.6-flash structured polishing |
| **Synthesis Agent** | `BaseAgent` / `Agent` | Economic calibration & executive rationale | `calibrate_and_synthesize_tool` combining rate cards, weather, FX & TRD scoring |
| **Auditor** *(Post-Approval)* | `Agent` | Immutable ledger writer | `write_decision_ledger_tool` writing to ClickHouse `decision_ledger` |

> [!IMPORTANT]
> **Architectural Segregation of the Auditor Agent**:
> The `Auditor` is deliberately decoupled from the initial disruption investigation pipeline. It executes strictly upon human producer approval (`POST /api/cases/{case_id}/approve`), guaranteeing that unapproved options never pollute permanent ClickHouse ledger records.

---

## ⚡ Runtime ClickHouse MCP Usage (Judge Checklist)

1. **Official `mcp-clickhouse` Stdio Server**:
   [`backend/services/mcp_client.py`](backend/services/mcp_client.py) spawns the official `mcp-clickhouse` server as a persistent stdio subprocess and manages a singleton `ClientSession` (`initialize` $\rightarrow$ `list_tools` $\rightarrow$ `call_tool("run_query")`).
2. **Safe Query Builder (Zero Raw SQL Injection)**:
   [`backend/services/safe_query_builder.py`](backend/services/safe_query_builder.py) enforces that the LLM never generates raw SQL. Queries are constructed exclusively from predefined, parameter-allowlisted SELECT templates with banned-keyword validation against the `strategy_performance_mv` materialized view.
3. **Live MCP Ticker & Evidence Logs**:
   The frontend displays real-time MCP call metrics (exact sanitized SQL, execution latency in milliseconds, row counts, and transport status) alongside side-by-side ClickHouse historical benchmarks.
4. **Strict Security Boundaries**:
   The MCP server runs in read-only mode (`CLICKHOUSE_ALLOW_WRITE_ACCESS=false`). Ledger writes are executed directly via `clickhouse-connect` append-only event tables.

---

## 🛠️ Tech Stack

| Layer | Technology | Implementation Details |
|---|---|---|
| **Database** | **ClickHouse Cloud** | `clickhouse-connect` (v1.7.1) + official **`mcp-clickhouse`** (v0.4.1) FastMCP stdio server |
| **Agent Framework** | **Google ADK** | `google-adk` (v2.7.1) with `SequentialAgent`, `ParallelAgent`, `Runner`, and `FunctionTool` |
| **AI / LLM** | **Google Gemini** | `gemini-3.6-flash` via official `google-genai` SDK with resilient backoff & JSON repair |
| **Backend API** | **FastAPI + Python 3.11** | High-performance async ASGI server with Pydantic v2 schemas and Uvicorn |
| **Frontend UI** | **React 18** | Tailwind CSS + Radix UI / shadcn/ui dark cinema interface with live polling |
| **Live Signals** | **Open-Meteo & ECB/Frankfurter** | Real-time weather precipitation risk and live ISO currency exchange rates |

---

## 📁 Repository Layout

```text
continuity-council/
├── Dockerfile                     # Multi-stage production container (React build + FastAPI)
├── README.md                      # Comprehensive project documentation
├── backend/                       # Python 3.11 FastAPI backend
│   ├── server.py                  # API routes, middleware, SPA static handler, startup lifecycle
│   ├── models.py                  # Pydantic v2 domain schemas (CaseState, RecoveryOption, etc.)
│   ├── case_store.py              # In-memory thread-safe active case registry
│   ├── scoring.py                 # TRD weighted scoring formula implementation
│   ├── requirements.txt           # Pinned production dependencies (ADK, Gemini, ClickHouse, MCP)
│   ├── agents/                    # Council agents
│   │   ├── orchestrator.py        # ADK SequentialAgent + ParallelAgent + Runner investigation pipeline
│   │   ├── budget_sentinel.py     # MCP historical query engine + rate-card calibration
│   │   ├── continuity_memory.py   # Narrative sequence DAG & wardrobe continuity solver
│   │   ├── compliance.py          # Availability, permits, and 100mi transit rule validator
│   │   ├── schedule_optimizer.py  # Candidate option generator + description polisher
│   │   └── auditor.py             # ClickHouse immutable decision ledger writer
│   ├── services/                  # Supporting service modules
│   │   ├── clickhouse_client.py   # Native clickhouse-connect queries & schema manager
│   │   ├── mcp_client.py          # Persistent stdio client for official mcp-clickhouse server
│   │   ├── safe_query_builder.py  # Allowlisted, parameter-checked SELECT query templates
│   │   ├── gemini_client.py       # Resilient Gemini 3.6-flash wrapper with quota recovery
│   │   ├── geo_service.py         # Haversine distance, city tiers, and World Bank PPP factors
│   │   ├── weather_service.py     # Open-Meteo forecast API integration
│   │   └── finance_service.py     # Frankfurter / ECB live foreign exchange conversion
│   └── scripts/                   # Test & verification harnesses
│       ├── demo_adk_council.py    # Judge-facing Rich CLI interactive demonstration
│       ├── test_orchestrator_adk.py # End-to-end multi-agent investigation verification
│       ├── test_budget_sentinel_adk.py # Budget Sentinel MCP ADK test
│       └── adk_smoke_test.py      # Basic ADK Runner smoke test
├── clickhouse/                    # ClickHouse SQL schema and seed scripts
│   ├── schema.sql                 # 10 tables + strategy_performance_mv materialized view
│   ├── seed.py                    # Seeds 6 diverse demo productions + 200,000+ synthetic disruptions
│   └── queries.sql                # Benchmark queries
├── frontend/                      # React 18 single-page application
│   ├── src/                       # UI components, pages, hooks, and API client (lib/api.js)
│   └── package.json               # Frontend dependencies (Tailwind, Lucide, Radix UI)
├── tests/                         # Automated test suite
│   ├── test_units.py              # 61 domain unit tests (solvers, TRD scoring, safety, geo)
│   └── test_adk_production_orchestrator.py # Production ADK Runner integration test
├── scripts/                       # Root-level proof scripts
│   ├── test_mcp.py                # Standalone MCP stdio tool calling round-trip proof
│   └── test_core.py               # Core ClickHouse + MCP + Gemini proof
└── docs/                          # In-depth architectural and design documentation
    ├── ARCHITECTURE.md            # Detailed enterprise system architecture
    ├── COST_METHODOLOGY.md        # 70/30 rate-card and historical calibration math
    ├── DATA_SOURCES.md            # Live signal attribution specification
    ├── DATA_ONBOARDING.md         # Studio historical data ingestion specification
    └── DEPLOYMENT.md              # Deployment guide (Render.com Docker runtime)
```

---

## 🚀 Setup & Local Installation

### 1. Prerequisites
- **Python 3.11+**
- **Node.js 18+** & **Yarn**
- A **ClickHouse Cloud** instance (Free trial works)
- A **Google Gemini API Key** from [Google AI Studio](https://aistudio.google.com/app/apikey)

### 2. Environment Configuration
Create `backend/.env` (copy from `.env.example`):

```bash
# ClickHouse Cloud Configuration
CLICKHOUSE_HOST=your-instance.region.gcp.clickhouse.cloud
CLICKHOUSE_PORT=8443
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your-clickhouse-password
CLICKHOUSE_DATABASE=continuity_council
CLICKHOUSE_SECURE=true

# Google AI Studio / Gemini Configuration
GEMINI_API_KEY=AIzaSyYourGeminiApiKey
GEMINI_MODEL=gemini-3.6-flash
```

Create `frontend/.env` (or `frontend/.env.local` for local dev):
```bash
REACT_APP_BACKEND_URL=http://localhost:8000
```

### 3. Dependency Installation
```bash
# Backend installation
pip install -r backend/requirements.txt

# Frontend installation
cd frontend && yarn install && cd ..
```

### 4. Database Initialization & Seeding
Initialize the 10 ClickHouse tables and generate 200,000+ historical disruption benchmark rows:
```bash
python clickhouse/seed.py
```

### 5. Running the Application Locally
```bash
# Terminal 1: Backend API (from repository root)
cd backend && uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend Dev Server
cd frontend && yarn start
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🧪 Verification & Test Suite

The repository includes a comprehensive, verified test suite covering unit solvers, safety allowlists, live MCP round-trips, and production ADK Runner execution.

```bash
# 1. Run the dedicated ADK Production Orchestrator Integration Test
python -m pytest tests/test_adk_production_orchestrator.py -v

# 2. Run the full unit and integration test suite (62 passed, 2 skipped)
python -m pytest tests/ -v

# 3. Execute the Judge-Facing Interactive CLI Demonstration
python backend/scripts/demo_adk_council.py

# 4. Verify Live ClickHouse MCP Server stdio Tool Calling
python scripts/test_mcp.py

# 5. Verify End-to-End ADK Orchestrator with live ClickHouse MCP
python backend/scripts/test_orchestrator_adk.py
```

---

## 📡 REST API Reference

All backend API routes are served under the `/api` prefix:

| Method & Route | Purpose | Key Request / Response Parameters |
|---|---|---|
| `GET /api/health` | Service health status | Returns ClickHouse ping, Gemini model status, and MCP readiness |
| `GET /api/productions` | List all productions | Production metadata, total days, active locations, and studio IDs |
| `GET /api/productions/{id}` | Get production schedule | Full scene breakdown, cast availability, and current schedule overlays |
| `POST /api/productions` | Create custom production | Onboards new production with cast, locations, and shoot schedule |
| `POST /api/productions/{id}/import-history` | Import studio CSV | Bulk ingests historical disruptions for tenant cohort blending |
| `GET /api/disruptions/impact-preview` | Pre-flight impact preview | Evaluates scenes directly blocked by cast or location unavailability |
| `POST /api/disruptions` | Report disruption & start council | Spawns background ADK `Runner.run_async` multi-agent investigation |
| `GET /api/cases/{case_id}` | Live investigation polling | Real-time agent statuses, MCP call logs, ranked options, and rationale |
| `POST /api/cases/{case_id}/approve` | Producer approval | Triggers `Auditor` to append immutable decision to ClickHouse ledger |
| `GET /api/audit/{production_id}` | Retrieve audit trail | Complete decision ledger rows and granular schedule change events |
| `GET /api/activity` | Live MCP activity ticker | Real-time stream of executed ClickHouse SQL queries and latencies |
| `GET /api/evidence/drilldown` | Historical row drilldown | Inspects raw `disruption_history` rows matching selected strategy |
| `POST /api/demo/reset` | Restore demo baseline | Clears volatile event tables to reset the demonstration state |

---

## ⚖️ Option Scoring Model (TRD Formula)

Candidate recovery options are ranked using the exact TRD weighted utility formula:

$$\text{Score} = 0.40 \cdot \text{CostSavingScore} + 0.30 \cdot \text{DelaySavingScore} + 0.20 \cdot (1 - \text{ContinuityRisk}) + 0.10 \cdot (1 - \text{ComplianceRisk})$$

- **Cost Saving Score**: Normalized from grounded 70/30 calibrated financial estimate.
- **Delay Saving Score**: Normalized from historical ClickHouse schedule disruption benchmarks.
- **Continuity Risk Score**: Evaluated by Continuity Memory (prerequisite DAGs and costume tag breaks).
- **Compliance Risk Score**: Evaluated by Compliance Agent (permits, maximum working hours, union rest).
- **Hard Constraint Penalty**: Options violating hard operational rules (e.g. $>100\text{mi}$ same-day transit or missing location permits) are flagged as **Blocked** and penalized by $\times 0.25$.

---

## 🚢 Deployment

Continuity Council is packaged as a unified, single-container multi-stage Docker build that compiles the React frontend into static assets and serves both the SPA and FastAPI backend from a single origin on port `8000`.

### Production Container (`Dockerfile`)
```dockerfile
# Multi-stage build:
# 1. node:18-alpine builds the React application
# 2. python:3.11-nodejs18-slim installs dependencies and runs FastAPI
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Render.com Deployment
1. Create a **New Web Service** pointing to the repository.
2. Select **Docker** as the environment.
3. Configure the environment variables (`CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DATABASE`, `CLICKHOUSE_SECURE`, `GEMINI_API_KEY`, `GEMINI_MODEL`).
4. Set Health Check path to `/api/health`.
5. Deploy. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for further details.

---

## 🎬 Judge Walkthrough (3-Minute Evaluation Loop)

1. **Dashboard Overview**:
   Select *The Long Dark Take* (`prod_001`). View the baseline 3-day production schedule, cast/location matrix, and 200,000+ row historical ClickHouse dataset.
2. **Report a Disruption**:
   Navigate to **Report Disruption**. File a disruption: *Lead Actor Unavailable* on **Day 2** (Severity: *Medium*, Lead Actor: *Mara Voss*).
3. **Watch ADK Multi-Agent Council Execute**:
   Navigate to **Investigation**. Observe live progress across all agents as the ADK `SequentialAgent` and `ParallelAgent` coordinate via `Runner.run_async()`. Inspect the **Live MCP Call Log** displaying actual SQL executed against ClickHouse Cloud in $\sim 100\text{--}200\text{ms}$.
4. **Compare Grounded Recovery Options**:
   Review the ranked recovery slates:
   - **Option 1 (Shoot cover scenes)**: Lowest grounded cost and minimal delay, fully compliant.
   - **Option 2 (Swap shoot days)**: Higher delay, blocked by Day 3 harbor permit constraints.
   - **Option 3 (Wait for actor)**: High cost overrun and 11+ hour delay.
5. **Inspect Historical Evidence & Rate-Card Calibration**:
   Examine side-by-side ClickHouse empirical benchmarks and the 70% bottom-up + 30% historical blended cost calibration.
6. **Producer Approval & Ledger Commit**:
   Click **Approve Strategy** on Option 1. The `Auditor` agent immediately writes the immutable decision and schedule change records to ClickHouse Cloud.
7. **Verify Decision Ledger**:
   Navigate to **Decision Ledger** to view the permanent, append-only record with cryptographic IDs and timestamped scene shifts.
