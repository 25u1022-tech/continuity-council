<!-- 05_implementation_plan.md -->
# Implementation Plan

## Objective

Ship a working ClickHouse-track MVP for Continuity Council that demonstrates:

1. A production disruption
2. Multi-agent investigation
3. Runtime ClickHouse MCP queries
4. Ranked recovery options
5. Producer approval
6. Auditable decision ledger
7. Hosted project URL
8. 3-minute demo video

---

## Team Roles

### Builder 1: Agent / Backend Lead

Responsible for:

- FastAPI backend
- Gemini agent orchestration
- MCP integration
- Tool definitions
- API endpoints

---

### Builder 2: Data / ClickHouse Lead

Responsible for:

- ClickHouse Cloud setup
- Schema creation
- Synthetic data generation
- Query testing
- Decision ledger writes

---

### Builder 3: UI / Demo Lead

Responsible for:

- Producer dashboard
- Disruption form
- Option comparison UI
- Evidence panel
- Demo script
- Demo video

If team size is smaller, combine roles.

---

## Phase 0: Setup

### Tasks

1. Create public GitHub repository.
2. Add MIT or Apache 2.0 license.
3. Create Google Cloud project.
4. Enable required APIs.
5. Create ClickHouse Cloud account.
6. Redeem ClickHouse credits.
7. Create ClickHouse service.
8. Install `mcp-clickhouse`.
9. Create `.env.example`.
10. Create repository folder structure.

---

## Repository Structure

```text
continuity-council/
├── app/
│   ├── main.py
│   ├── api/
│   ├── agents/
│   ├── tools/
│   ├── services/
│   ├── models/
│   └── ui/
├── clickhouse/
│   ├── schema.sql
│   ├── seed.py
│   └── queries.sql
├── mcp/
│   └── clickhouse_mcp_config.md
├── docs/
│   ├── product_requirements.md
│   ├── technical_requirements.md
│   ├── app_flow.md
│   ├── backend_schema_clickhouse.md
│   └── implementation_plan.md
├── scripts/
│   ├── deploy.sh
│   └── test_mcp.py
├── LICENSE
├── README.md
└── requirements.txt
```

---

## Phase 1: ClickHouse Foundation

### Goal

ClickHouse must be running, seeded, and queryable.

### Tasks

1. Create database: `continuity_council`
2. Create all tables
3. Seed current production:
   - 1 production
   - 3 shoot days
   - 10 scenes
   - 3 locations
   - 1 lead actor
   - 2 supporting actors
4. Seed location availability
5. Seed cast availability
6. Generate historical disruption data
7. Test Budget Sentinel query manually

### Definition of Done

This query returns meaningful results:

```sql
SELECT
    resolution_strategy,
    AVG(cost_overrun_usd) AS avg_cost_overrun,
    AVG(schedule_delay_hours) AS avg_delay_hours,
    COUNT(*) AS past_cases
FROM continuity_council.disruption_history
WHERE disruption_type = 'lead_actor_unavailable'
GROUP BY resolution_strategy
ORDER BY avg_cost_overrun ASC;
```

---

## Phase 2: MCP Integration

### Goal

The backend must query ClickHouse through the official MCP server.

### Tasks

1. Configure `mcp-clickhouse`
2. Create MCP client wrapper
3. Implement `query_clickhouse` tool
4. Restrict queries to SELECT statements
5. Add query logging
6. Test query from Python
7. Add error handling

### Definition of Done

The backend can call:

```python
result = mcp_client.call_tool(
    "clickhouse_query",
    {
        "query": "SELECT COUNT(*) FROM continuity_council.disruption_history"
    }
)
```

and receive a valid response.

---

## Phase 3: Agent Workflow

### Goal

The Orchestrator must coordinate specialist agents.

### Tasks

1. Define Orchestrator prompt
2. Define Schedule Optimizer prompt
3. Define Budget Sentinel prompt
4. Define Continuity Memory prompt
5. Define Compliance Agent prompt
6. Define Auditor Agent prompt
7. Create tool schemas
8. Implement parallel agent dispatch
9. Merge agent outputs
10. Implement option scoring

### Definition of Done

Given:

```json
{
  "production_id": "prod_001",
  "disruption_type": "lead_actor_unavailable",
  "affected_day": 2
}
```

The system returns at least two recovery options with evidence.

---

## Phase 4: Backend API

### Goal

Expose the workflow through API endpoints.

### Endpoints

```text
GET  /productions/{production_id}
POST /disruptions
GET  /cases/{case_id}
POST /cases/{case_id}/approve
GET  /audit/{production_id}
```

### Tasks

1. Create Pydantic request/response models
2. Implement production dashboard endpoint
3. Implement disruption reporting endpoint
4. Implement case status endpoint
5. Implement approval endpoint
6. Implement audit endpoint
7. Add logging
8. Add error handling

### Definition of Done

The full workflow can be triggered using API calls.

---

## Phase 5: Frontend UI

### Goal

Build a simple but polished producer dashboard.

### Screens

#### Screen 1: Production Dashboard

Shows:

- Production title
- Shoot days
- Scene schedule
- Cast availability
- Location availability
- Active disruptions

---

#### Screen 2: Report Disruption

Form fields:

- Disruption type
- Affected day
- Affected cast/location
- Severity
- Notes

---

#### Screen 3: Agent Investigation

Shows:

- Case ID
- Agent status
- Ongoing investigations
- ClickHouse evidence loading state

---

#### Screen 4: Recovery Options

Shows:

- Option name
- Description
- Estimated cost
- Estimated delay
- Continuity risk
- Compliance warnings
- Historical evidence
- Recommended badge
- Approve button

---

#### Screen 5: Decision Ledger

Shows:

- Decision ID
- Case ID
- Selected option
- Cost estimate
- Delay estimate
- Approved by
- Timestamp
- Evidence summary

### Definition of Done

A judge can understand the full workflow without explanation.

---

## Phase 6: Decision Ledger

### Goal

Approved decisions must be written to ClickHouse.

### Tasks

1. Generate decision ID
2. Store selected option
3. Store evidence JSON
4. Store approval metadata
5. Write schedule changes
6. Display ledger in UI

### Definition of Done

After approval, this query returns a new row:

```sql
SELECT *
FROM continuity_council.decision_ledger
ORDER BY approved_at DESC
LIMIT 1;
```

---

## Phase 7: Deployment

### Goal

Host the project at a public URL.

### Recommended Deployment

- Dockerized FastAPI app
- Deploy to Google Cloud Run
- Inject secrets from Google Cloud Secret Manager
- Serve frontend from same service

### Tasks

1. Write Dockerfile
2. Test locally
3. Deploy to Cloud Run
4. Configure environment variables
5. Test public URL
6. Verify ClickHouse MCP connection in deployed environment

### Definition of Done

The hosted URL works and can run the full demo flow.

---

## Phase 8: Demo Video

### Goal

Create a clear 3-minute demo video.

### Video Structure

#### 0:00 to 0:20 — Problem

Show production schedule.

Narration:

> “Film productions lose money when disruptions happen. The challenge is choosing the best recovery option quickly.”

---

#### 0:20 to 0:40 — Disruption

Producer reports:

> “Lead actor unavailable tomorrow.”

---

#### 0:40 to 1:20 — Agent Investigation

Show:

- Orchestrator creating case
- Agents investigating
- Budget Sentinel querying ClickHouse MCP
- Evidence returned

---

#### 1:20 to 2:00 — Ranked Options

Show:

- Option A
- Option B
- Option C
- Cost comparison
- Delay comparison
- Continuity warnings
- Compliance warnings

---

#### 2:00 to 2:30 — Approval

Producer approves best option.

Schedule updates.

---

#### 2:30 to 3:00 — Audit Trail

Show decision ledger.

Narration:

> “Continuity Council turns production chaos into grounded, auditable decision-making.”

---

## Phase 9: Submission Checklist

Before submitting:

- [ ] Hosted project URL works
- [ ] Public GitHub repository exists
- [ ] LICENSE file exists
- [ ] README includes setup instructions
- [ ] README includes environment variables
- [ ] README includes ClickHouse MCP setup
- [ ] README includes demo video link
- [ ] ClickHouse usage is visible in code
- [ ] ClickHouse usage is visible in demo
- [ ] Google Cloud usage is visible
- [ ] Gemini usage is visible
- [ ] Demo video is public
- [ ] Demo video is under 3 minutes
- [ ] Demo video is in English or has English subtitles
- [ ] Devpost form is complete
- [ ] Selected ClickHouse track

---

## Timeline

### Day 1: Data and MCP

- Set up ClickHouse
- Create schema
- Seed synthetic data
- Connect MCP
- Validate runtime query

---

### Day 2: Agents and Backend

- Build Orchestrator
- Build specialist agents
- Implement option scoring
- Build API endpoints
- Connect frontend to backend

---

### Day 3: UI, Ledger, and Demo

- Polish dashboard
- Implement approval flow
- Write decision ledger
- Deploy to Cloud Run
- Record demo video
- Final README cleanup

---

## Critical Risks

### Risk 1: Too many agents

Mitigation:

- Keep agents lightweight
- Use deterministic tools instead of long LLM reasoning
- Merge Continuity and Compliance if needed

---

### Risk 2: ClickHouse query failure

Mitigation:

- Use templated queries
- Pre-test queries
- Cache evidence for demo safety

---

### Risk 3: Weak synthetic data

Mitigation:

- Generate enough rows
- Use realistic distributions
- Show case counts in UI

---

### Risk 4: Demo complexity

Mitigation:

- Use one production
- One disruption
- Three options
- One approval

---

## Final MVP Rule

Do not build more features.

Ship this exact loop:

```text
Disruption
  → Agents investigate
  → ClickHouse evidence
  → Ranked options
  → Producer approval
  → Schedule update
  → Audit ledger
```

That is the winning demo.