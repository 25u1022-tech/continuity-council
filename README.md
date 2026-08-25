# 🎬 Continuity Council

![CI](https://github.com/25u1022-tech/continuity-council/actions/workflows/ci.yml/badge.svg)

> **Multi-agent film production recovery system — powered by Google Agent Development Kit (ADK), ClickHouse Cloud, and Google Gemini.**
>
> Built for the **"Lights. Camera. Code."** Hackathon — **ClickHouse Track**.

When a production disruption hits (lead actor injury/illness, extreme weather, lost location permit, equipment breakdown), Continuity Council dispatches an autonomous multi-agent recovery council built on the **Google Agent Development Kit (ADK)**. The council investigates constraints, queries **200,000+ historical disruption benchmarks in ClickHouse Cloud through the official `mcp-clickhouse` MCP server at runtime**, computes bottom-up rate-card economics with live weather and FX data, ranks recovery options via the TRD weighted utility formula, and commits producer-approved decisions to an immutable ClickHouse audit ledger.

- **Hosted URL:** [HOSTED_URL]
- **License:** MIT

---

## 🏗️ System Architecture

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
│  │        │     └─► SafeQueryBuilder (SELECT-only allowlisted templates) │  │
│  │        │           └─► Persistent MCP Client (stdio)                  │  │
│  │        │                 └─► official mcp-clickhouse server           │  │
│  │        │                       └─► ClickHouse Cloud (MV query)        │  │
│  │        ├─► continuity_memory_agent (DAG & Narrative Integrity)       │  │
│  │        │     └─► validate_continuity (prerequisites & costume tags)   │  │
│  │        ├─► compliance_agent (Operational Constraints)                 │  │
│  │        │     └─► validate_compliance (100mi transit, turnaround, SAG) │  │
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

---

## 🤖 Multi-Agent Architecture (Google ADK)

Continuity Council's core investigation pipeline is built natively with Google's **Agent Development Kit (ADK)** (`google-adk`). It coordinates specialized agents through hierarchical composition (`SequentialAgent` and `ParallelAgent`), asynchronous execution (`Runner.run_async`), typed in-memory session management (`InMemorySessionService`), and typed tool declarations (`FunctionTool`).

### The Council Agents

| Agent | ADK Class | Role in Pipeline | Primary Mechanism / Tools |
|---|---|---|---|
| **Orchestrator** | `SequentialAgent` | Top-level pipeline coordinator | Executes Stage 1 $\rightarrow$ Stage 2 $\rightarrow$ Stage 3 via `Runner.run_async` |
| **Generate Agent** | `BaseAgent` | Candidate schedule recovery generator | `generate_options_tool` generates 2–4 deterministic schedule permutations |
| **Budget Sentinel** | `BaseAgent` / `Agent` | ClickHouse empirical benchmark engine | `query_disruption_history_tool` queries ClickHouse via official `mcp-clickhouse` FastMCP |
| **Continuity Memory** | `BaseAgent` / `Agent` | Narrative sequence & wardrobe solver | `evaluate_continuity_risks_tool` validates prerequisite DAGs & costume tags |
| **Compliance Sentinel** | `BaseAgent` / `Agent` | Operational feasibility & union rule validator | `validate_compliance_rules_tool` enforces SAG-AFTRA 12h turnaround & 100mi transit limit |
| **Schedule Optimizer** | `BaseAgent` / `Agent` | Recovery description refiner | `generate_recovery_options_tool` + Gemini structured text polishing |
| **Synthesis Agent** | `BaseAgent` / `Agent` | Economic calibration & executive rationale | `calibrate_and_synthesize_tool` combines rate cards, weather, FX & TRD ranking |
| **Auditor** *(Post-Approval)* | `Agent` | Immutable ledger writer | `write_decision_ledger_tool` writes tamper-evident SHA-256 records to ClickHouse |

> [!IMPORTANT]
> **Architectural Segregation of the Auditor Agent**:
> The `Auditor` agent is strictly decoupled from initial candidate investigation. It runs **only after human producer approval** (`POST /api/cases/{case_id}/approve`), guaranteeing that unapproved options never contaminate ClickHouse audit tables.

---

## ⚡ ClickHouse Cloud & MCP Runtime Integration

1. **Official `mcp-clickhouse` Stdio Server**:
   [`backend/services/mcp_client.py`](backend/services/mcp_client.py) manages a persistent stdio subprocess running the official `mcp-clickhouse` FastMCP server with session lifecycle handling (`initialize` $\rightarrow$ `list_tools` $\rightarrow$ `call_tool("run_query")`).
2. **Safe Query Builder (Zero SQL Injection)**:
   [`backend/services/safe_query_builder.py`](backend/services/safe_query_builder.py) ensures LLMs never emit raw SQL. All analytical queries use predefined, parameter-allowlisted SELECT templates with banned-keyword validation against the `strategy_performance_mv` materialized view.
3. **Live MCP Ticker & Evidence Logs**:
   The UI streams real-time MCP call metrics (sanitized SQL, execution latency in milliseconds, row count, transport status) alongside historical benchmarks from 200,000+ synthetic disruptions.
4. **Security Boundaries**:
   The MCP server runs in strict read-only mode (`CLICKHOUSE_ALLOW_WRITE_ACCESS=false`). Permanent audit records are written directly via `clickhouse-connect` append-only tables.

---

## 💬 Council Reasoning Chatbot (Gemini Function Calling)

The **Council Reasoning** drawer provides a conversational interface for producers to inspect the council's reasoning.

```text
Producer Query ("Why was Option 1 recommended?")
       ↓
CouncilChatbot.ask() (backend/agents/council_chatbot.py)
       ↓
Gemini 3.6-flash (google-genai SDK)
       ↓
Autonomous Function Calling Loop (up to 3 turns)
  ├── search_disruption_history (Historical ClickHouse benchmarks via SafeQueryBuilder)
  ├── get_case_details (Active investigation status & generated recovery slates)
  ├── explain_option_ranking (Option breakdown, TRD score, compliance checks)
  └── check_shoot_plan (Production schedule + live Open-Meteo weather risk)
       ↓
Synthesized Grounded Response with Source Citations
```

- **SDK Architecture:** Built on the official **`google-genai` SDK** using native `FunctionDeclaration` tool schemas and multi-turn tool execution. *(Note: The chatbot uses `google-genai` function calling, while the core multi-agent pipeline uses Google ADK.)*
- **Offline / Quota-Hit Deterministic Fallback:** If Gemini is unavailable or rate-limited, `_deterministic_fallback()` routes queries directly to the tools or knowledge bases (`HELP_KB`, `GENERAL_KB`) without downtime.
- **Producer Guidance:** When asked about approving options, the chatbot provides clear instructions directing the user to the Recovery Options UI so the Auditor agent is triggered with human consent.
- **Voice Accessibility:** Optional text-to-speech powered by `gemini-3.1-flash-tts` with client-side playback.

---

## ⚖️ Recovery Strategy Ranking (TRD Formula)

Candidate recovery options are ranked using the calibrated TRD weighted utility formula:

$$\text{Score} = 0.40 \cdot \text{CostSavingScore} + 0.30 \cdot \text{DelaySavingScore} + 0.20 \cdot (1 - \text{ContinuityRisk}) + 0.10 \cdot (1 - \text{ComplianceRisk})$$

- **Cost Saving Score (40%)**: Grounded 70% bottom-up rate card economics (crew, cast, stage fees) + 30% ClickHouse historical overrun benchmarks.
- **Delay Saving Score (30%)**: Normalized against ClickHouse schedule delay distribution for the matching disruption type.
- **Continuity Risk Score (20%)**: Evaluated by Continuity Memory against narrative DAG sequence dependencies and costume/prop continuity tags.
- **Compliance Risk Score (10%)**: Evaluated by Compliance Sentinel against SAG-AFTRA turnaround rules (12h minimum rest), location permit windows, and the 100-mile same-day transit limit.
- **Hard Constraint Penalty**: Options violating hard constraints (e.g. missing location permit, transit $>100\text{mi}$, or unavailable lead actor) are flagged as **Blocked** and penalized by $\times 0.25$.

---

## 🎬 End-to-End User Workflow

1. **Schedule Ingestion (PDF / Custom)**:
   Upload a call-sheet or shooting-schedule PDF for automated Gemini document understanding, or create a production via the interactive wizard.
2. **Disruption Reporting**:
   Enter natural-language text (*"Sarah broke her ankle, cannot shoot Tuesday"*) or use the structured form with real-time **Impact Preview** to see blocked scenes.
3. **Dispatch Investigation Council**:
   Click **Dispatch Investigation Council** to spawn the background ADK `Runner.run_async` pipeline.
4. **Live Multi-Agent Investigation**:
   Watch agents evaluate candidate slates in parallel, querying ClickHouse historical evidence via FastMCP.
5. **Review Ranked Recovery Strategies**:
   Compare grounded options with plain-English justifications, cost breakdowns, weather summaries, and on-demand **Imagen 3 visual mood-boards** for alternate locations.
6. **Producer Approval**:
   Select and approve the preferred strategy.
7. **Immutable Audit Commit**:
   The `Auditor` agent appends a permanent record with SHA-256 hash to ClickHouse `decision_ledger` and logs scene shifts to `schedule_changes`.

---

## 🛠️ Tech Stack

| Layer | Technology | Implementation Details |
|---|---|---|
| **Database** | **ClickHouse Cloud** | `clickhouse-connect` (v1.7.1) + official **`mcp-clickhouse`** (v0.4.1) FastMCP stdio server |
| **Agent Framework** | **Google ADK** | `google-adk` (v2.7.1) with `SequentialAgent`, `ParallelAgent`, `Runner`, and `FunctionTool` |
| **AI / LLM** | **Google Gemini** | `gemini-3.6-flash` via official `google-genai` SDK with resilient backoff & JSON repair |
| **Visual AI** | **Google Imagen 3** | `imagen-3.0-generate-002` on-demand 16:9 cinematic mood-boards with dual cache |
| **Voice AI / TTS** | **Google Gemini TTS** | `gemini-3.1-flash-tts` speech synthesis with in-memory hash cache |
| **Backend API** | **FastAPI + Python 3.11** | Async ASGI server with Pydantic v2 domain schemas |
| **Frontend UI** | **React 18** | Tailwind CSS + Radix UI / shadcn/ui dark cinema interface |
| **Live Signals** | **Open-Meteo & ECB/Frankfurter** | Real-time hourly weather forecast risk and live foreign exchange conversion |

---

## 📁 Project Structure

```text
continuity-council/
├── Dockerfile                     # Multi-stage production container (React build + FastAPI)
├── README.md                      # Comprehensive project documentation
├── backend/                       # Python 3.11 FastAPI backend
│   ├── server.py                  # API routes, middleware, SPA static handler, startup lifecycle
│   ├── models.py                  # Pydantic v2 domain schemas (CaseState, RecoveryOption, etc.)
│   ├── case_store.py              # In-memory thread-safe active case registry
│   ├── scoring.py                 # TRD weighted scoring formula implementation
│   ├── pytest.ini                 # Pytest configuration with fixed xdist workers
│   ├── requirements.txt           # Pinned production dependencies (ADK, Gemini, ClickHouse, MCP)
│   ├── agents/                    # Council agents
│   │   ├── orchestrator.py        # ADK SequentialAgent + ParallelAgent + Runner investigation pipeline
│   │   ├── budget_sentinel.py     # MCP historical query engine + rate-card calibration
│   │   ├── continuity_memory.py   # Narrative sequence DAG & wardrobe continuity solver
│   │   ├── compliance.py          # Availability, permits, and 100mi transit rule validator
│   │   ├── schedule_optimizer.py  # Candidate option generator + description polisher
│   │   ├── auditor.py             # ClickHouse immutable decision ledger writer
│   │   └── council_chatbot.py     # Gemini function-calling conversational reasoning agent
│   ├── services/                  # Supporting service modules
│   │   ├── clickhouse_client.py   # Native clickhouse-connect queries & schema manager
│   │   ├── mcp_client.py          # Persistent stdio client for official mcp-clickhouse server
│   │   ├── safe_query_builder.py  # Allowlisted, parameter-checked SELECT query templates
│   │   ├── gemini_client.py       # Resilient Gemini wrapper with quota recovery
│   │   ├── justification_service.py # Natural-language explainability justifications
│   │   ├── schedule_extractor.py  # PDF shooting-schedule ingestion via Gemini
│   │   ├── moodboard_service.py   # Imagen 3 location visual mood-board generator
│   │   ├── tts_service.py         # Gemini TTS speech synthesis service
│   │   ├── nl_parser.py           # Natural-language disruption parser
│   │   ├── geo_service.py         # Haversine distance, city tiers, and World Bank PPP factors
│   │   ├── weather_service.py     # Open-Meteo forecast API integration
│   │   └── finance_service.py     # Frankfurter / ECB live foreign exchange conversion
│   └── scripts/                   # Verification harnesses & proof scripts
│       ├── test_orchestrator_adk.py # ADK multi-agent investigation verification
│       └── test_budget_sentinel_adk.py # Budget Sentinel MCP ADK test
├── clickhouse/                    # ClickHouse SQL schema and seed scripts
│   ├── schema.sql                 # 10 tables + strategy_performance_mv materialized view
│   ├── seed.py                    # Seeds 6 demo productions + 200,000+ synthetic disruptions
│   └── queries.sql                # Benchmark queries
├── frontend/                      # React 18 single-page application
│   ├── src/
│   │   ├── components/            # UI components (CouncilChatbot, ActivityTicker, etc.)
│   │   ├── pages/                 # Pages (Dashboard, Report, Investigation, Options, Ledger, Settings)
│   │   ├── lib/api.js             # API client with error handling & cold start detection
│   │   └── App.js                 # App routes and shell wrapper
│   └── package.json               # Frontend dependencies (Tailwind, Lucide, Radix UI)
├── tests/                         # Automated test suite
│   ├── test_units.py              # Unit tests (solvers, TRD scoring, chatbot, PDF, TTS, moodboard)
│   ├── test_import_and_blending.py # CSV import & studio cohort blending tests
│   └── test_adk_production_orchestrator.py # Production ADK Runner integration test
└── docs/                          # In-depth architectural documentation
    ├── ARCHITECTURE.md            # Detailed system architecture
    ├── COST_METHODOLOGY.md        # 70/30 rate-card and historical calibration math
    └── DEPLOYMENT.md              # Deployment guide (Render.com / Docker)
```

---

## 🚀 Setup & Local Installation

### 1. Prerequisites
- **Python 3.11+**
- **Node.js 18+** & **Yarn**
- A **ClickHouse Cloud** instance (Free trial works)
- A **Google Gemini API Key** from [Google AI Studio](https://aistudio.google.com/app/apikey)

### 2. Environment Configuration
Create `backend/.env` (copy from `backend/.env.example` if available):

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

Create `frontend/.env` (or `frontend/.env.local`):
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
Initialize the 10 ClickHouse tables and generate 200,000+ historical disruption benchmarks:
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

The automated test suite verifies all unit solvers, ADK agent execution, ClickHouse queries, safe query templates, and frontend components.

```bash
# 1. Run all backend unit & integration tests
python -m pytest tests/ -v

# 2. Run the dedicated ADK Production Orchestrator test
python -m pytest tests/test_adk_production_orchestrator.py -v

# 3. Run the frontend test suite
cd frontend && yarn test --watchAll=false
```

**Current Verified Test Results:**
- **Backend Test Suite (`pytest`):** `107 passed, 2 skipped, 0 failed`
- **Frontend Test Suite (`yarn test`):** `7 test suites passed, 30 passed, 0 failed`

---

## 📡 REST API Reference

All backend API routes are served under the `/api` prefix:

| Method & Route | Purpose | Key Request / Response Parameters |
|---|---|---|
| `GET /api/health` | Health check | ClickHouse ping, Gemini model status, MCP readiness |
| `GET /api/productions` | List productions | Production titles, shoot spans, active locations |
| `GET /api/productions/{id}` | Get production schedule | Full scene breakdown, cast availability, current schedule |
| `POST /api/productions` | Create custom production | Onboards title with cast, locations, and shoot schedule |
| `POST /api/productions/{id}/import-schedule` | Upload schedule PDF | Asynchronously extracts schedule via Gemini document understanding |
| `GET /api/imports/{job_id}` | Poll PDF import status | Job status and extracted schedule preview |
| `POST /api/imports/{job_id}/confirm` | Confirm PDF import | Persists confirmed schedule rows into ClickHouse |
| `POST /api/productions/{id}/import-history` | Import studio CSV | Bulk ingests historical disruptions for studio cohort blending |
| `GET /api/disruptions/impact-preview` | Pre-flight impact preview | Evaluates scenes directly blocked by cast or location unavailability |
| `POST /api/disruptions/parse-nl` | Parse natural language | Parses free-text incident descriptions into structured disruption payload |
| `POST /api/disruptions` | Report disruption | Dispatches background ADK `Runner.run_async` multi-agent investigation |
| `GET /api/cases/{case_id}` | Live investigation polling | Real-time agent statuses, MCP call logs, ranked options, and rationale |
| `POST /api/cases/{case_id}/approve` | Producer approval | Triggers `Auditor` agent to append immutable record to ClickHouse |
| `GET /api/locations/{id}/moodboard` | Location mood-board | On-demand Imagen 3 cinematic visual mood-board generation |
| `POST /api/chat` | Council Reasoning Chat | Gemini function-calling agent with ClickHouse source citations |
| `POST /api/chat/tts/generate` | Generate TTS audio | Asynchronously generates speech audio via Gemini TTS |
| `GET /api/chat/tts` | Retrieve TTS audio | Streams cached audio stream (`audio/wav`) |
| `GET /api/audit/{production_id}` | Retrieve audit trail | Append-only decision ledger entries and granular schedule change events |
| `GET /api/activity` | Live MCP activity ticker | Stream of executed ClickHouse SQL queries and latencies |
| `GET /api/evidence/drilldown` | Evidence row drilldown | Inspects raw `disruption_history` benchmark rows |
| `POST /api/demo/reset` | Restore demo baseline | Clears volatile event rows to reset demo state |

---

## 🚢 Deployment

Continuity Council is packaged as a unified multi-stage Docker container that builds the React frontend and serves both the SPA static assets and FastAPI backend from a single origin on port `8000`.

### Production Container (`Dockerfile`)
```dockerfile
# Multi-stage build:
# 1. node:18-alpine builds the React application
# 2. python:3.11-nodejs18-slim installs dependencies and runs FastAPI
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for full deployment instructions on Render.com, Cloud Run, or any Docker-compatible host.
