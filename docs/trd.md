<!-- 02_technical_requirements.md -->
# Technical Requirements Document

## Project Name

**Continuity Council**

## Selected Hackathon Track

**ClickHouse**

---

## Technical Objective

Build a functional agentic application where Gemini-based agents use the official ClickHouse MCP server at runtime to query historical production disruption data and support producer decision-making.

---

## Core Technical Requirements

### 1. ClickHouse Requirement

The project must actively use ClickHouse at runtime.

The application must use:

- ClickHouse Cloud or self-hosted ClickHouse
- Official ClickHouse MCP server: `mcp-clickhouse`
- Runtime queries triggered by the agent workflow
- Visible evidence of ClickHouse usage in code and demo

The README alone is not enough.

The code must show ClickHouse being queried during the disruption-response workflow.

---

### 2. Google Cloud Requirement

The project must use Google Cloud and Gemini.

Recommended stack:

- Gemini Enterprise / Vertex AI Gemini model
- Google Cloud Agent Builder or Agent Development Kit
- Cloud Run for hosting
- Secret Manager for credentials
- Cloud Logging for observability
- IAM service accounts with least privilege

---

### 3. Agent Requirement

The system must implement a deterministic multi-step agent workflow.

Agents:

1. Orchestrator Agent
2. Schedule Optimizer Agent
3. Budget Sentinel Agent
4. Continuity Memory Agent
5. Compliance Agent
6. Auditor Agent

The Orchestrator must coordinate the workflow and merge results.

---

## High-Level Architecture

```text
Producer UI
    ↓
FastAPI Backend
    ↓
Gemini Agent Orchestrator
    ↓
Specialist Agents
    ↓
Tool Layer
    ↓
ClickHouse MCP Server
    ↓
ClickHouse Cloud
```

---

## Recommended Stack

### Frontend

Simple production dashboard.

Options:

- Next.js deployed to Cloud Run
- React single-page app served by FastAPI
- Simple HTML + Tailwind + HTMX for fastest MVP

Recommended for hackathon speed:

- FastAPI backend
- Jinja templates or simple React frontend
- Deploy as one Cloud Run service

---

### Backend

- Python 3.11+
- FastAPI
- Pydantic models
- Gemini agent orchestration
- MCP client for ClickHouse

---

### AI Layer

- Gemini model via Google Cloud
- Agent tools/functions:
  - `get_current_schedule`
  - `generate_schedule_options`
  - `query_disruption_history`
  - `validate_continuity`
  - `validate_compliance`
  - `write_decision_ledger`

---

### Data Layer

- ClickHouse Cloud
- Official `mcp-clickhouse` server
- Synthetic production disruption dataset

---

## MCP Integration

The Budget Sentinel agent must use ClickHouse MCP at runtime.

Example tool call:

```json
{
  "tool": "clickhouse_query",
  "arguments": {
    "query": "SELECT resolution_strategy, AVG(cost_overrun_usd) AS avg_cost, AVG(schedule_delay_hours) AS avg_delay, COUNT(*) AS cases FROM continuity_council.disruption_history WHERE disruption_type = 'lead_actor_unavailable' GROUP BY resolution_strategy ORDER BY avg_cost ASC"
  }
}
```

For safety, the backend should not allow arbitrary free-form SQL from the LLM without constraints.

Recommended approach:

- Use templated queries
- Allow only SELECT queries
- Restrict access to analytics tables
- Validate query shape before execution

---

## Agent Tool Definitions

### Tool 1: `get_current_schedule`

Input:

```json
{
  "production_id": "prod_001"
}
```

Output:

```json
{
  "production_id": "prod_001",
  "shoot_days": 3,
  "scenes": [
    {
      "scene_id": "sc_014",
      "shoot_day": 2,
      "location": "stage_a",
      "required_cast": ["lead_actor"],
      "is_cover_scene": false
    }
  ]
}
```

---

### Tool 2: `generate_schedule_options`

Input:

```json
{
  "production_id": "prod_001",
  "disruption_type": "lead_actor_unavailable",
  "affected_day": 2
}
```

Output:

```json
{
  "options": [
    {
      "option_id": "option_a",
      "name": "Shoot cover scenes",
      "description": "Move lead-actor scenes to Day 3 and shoot supporting-character scenes on Day 2.",
      "scene_changes": [
        {
          "scene_id": "sc_014",
          "from_day": 2,
          "to_day": 3
        }
      ]
    }
  ]
}
```

---

### Tool 3: `query_disruption_history`

Input:

```json
{
  "disruption_type": "lead_actor_unavailable"
}
```

Output:

```json
{
  "evidence": [
    {
      "resolution_strategy": "shoot_cover_scenes",
      "avg_cost_overrun_usd": 18400,
      "avg_delay_hours": 3.8,
      "cases": 412,
      "success_score": 0.84
    }
  ]
}
```

---

### Tool 4: `validate_continuity`

Input:

```json
{
  "production_id": "prod_001",
  "option_id": "option_a"
}
```

Output:

```json
{
  "continuity_risks": [
    {
      "scene_ids": ["sc_012", "sc_013"],
      "risk": "Costume state continuity may be affected if scenes are separated."
    }
  ],
  "continuity_risk_score": 0.35
}
```

---

### Tool 5: `validate_compliance`

Input:

```json
{
  "production_id": "prod_001",
  "option_id": "option_b"
}
```

Output:

```json
{
  "valid": false,
  "warnings": [
    "Location 2 is not available on Day 2."
  ],
  "compliance_risk_score": 0.9
}
```

---

### Tool 6: `write_decision_ledger`

Input:

```json
{
  "case_id": "case_001",
  "production_id": "prod_001",
  "selected_option": "option_a",
  "estimated_cost_usd": 18400,
  "estimated_delay_hours": 3.8,
  "approved_by": "producer"
}
```

Output:

```json
{
  "decision_id": "dec_123",
  "status": "written"
}
```

---

## Option Scoring Model

The Orchestrator should rank options using a weighted score.

Recommended formula:

```text
score =
  0.40 * cost_saving_score
+ 0.30 * delay_saving_score
+ 0.20 * continuity_safety_score
+ 0.10 * compliance_safety_score
```

Where:

- `cost_saving_score` is normalized from historical cost overrun
- `delay_saving_score` is normalized from historical delay hours
- `continuity_safety_score = 1 - continuity_risk_score`
- `compliance_safety_score = 1 - compliance_risk_score`

If an option fails compliance hard constraints, it should be marked invalid or heavily penalized.

---

## API Endpoints

### Production Dashboard

```text
GET /productions/{production_id}
```

Returns production summary and current schedule.

---

### Report Disruption

```text
POST /disruptions
```

Body:

```json
{
  "production_id": "prod_001",
  "disruption_type": "lead_actor_unavailable",
  "affected_day": 2,
  "affected_cast_id": "lead_actor",
  "severity": "high",
  "notes": "Lead actor unavailable due to illness."
}
```

---

### Get Case Status

```text
GET /cases/{case_id}
```

Returns agent investigation status and generated options.

---

### Approve Option

```text
POST /cases/{case_id}/approve
```

Body:

```json
{
  "option_id": "option_a",
  "approved_by": "producer"
}
```

---

### Get Decision Ledger

```text
GET /audit/{production_id}
```

Returns decision history.

---

## Data Requirements

The MVP needs synthetic but realistic data.

### Required Tables

1. `productions`
2. `locations`
3. `cast_members`
4. `production_schedule`
5. `location_availability`
6. `cast_availability`
7. `disruption_history`
8. `disruption_cases`
9. `decision_ledger`
10. `schedule_changes`

---

## Synthetic Dataset Requirements

The ClickHouse historical dataset should include:

- At least 5,000 historical disruption records
- Multiple disruption types
- Multiple resolution strategies
- Realistic cost ranges
- Realistic delay ranges
- Continuity risk scores
- Compliance risk scores
- Success scores

Important:

The data can be synthetic, but it must look believable.

---

## Security Requirements

### Secrets

Store credentials in Google Cloud Secret Manager.

Required secrets:

- `CLICKHOUSE_HOST`
- `CLICKHOUSE_USER`
- `CLICKHOUSE_PASSWORD`
- `CLICKHOUSE_DATABASE`
- `GEMINI_API_KEY` or Google Cloud auth configuration

Do not commit secrets to GitHub.

---

### IAM

Use least privilege:

- ClickHouse service user should only access required database
- Cloud Run service account should only access required secrets
- Gemini API access should be restricted to the app backend

---

## Observability

Minimum observability:

- Backend logs
- Agent tool call logs
- ClickHouse query logs
- Error handling logs

Optional but impressive:

- Grafana AI Observability for agent traces
- Token usage tracking
- MCP tool call monitoring

If using Grafana, keep it optional and secondary. ClickHouse must remain the track requirement.

---

## Deployment Requirements

The hosted project must have a public URL.

Recommended deployment:

- Google Cloud Run
- Dockerized FastAPI app
- Public service URL
- Environment variables injected from Secret Manager

---

## Repository Requirements

The GitHub repository must include:

- All source code
- Frontend code
- Backend code
- Agent code
- ClickHouse schema
- Seed scripts
- MCP configuration
- Setup instructions
- Environment variable template
- Open-source license file
- Demo video link
- Hosted project URL

Recommended license:

- MIT or Apache 2.0

---

## Testing Requirements

### Unit Tests

- Schedule option generation
- Option scoring
- Compliance validation
- Continuity risk scoring

### Integration Tests

- ClickHouse connection
- MCP query execution
- Decision ledger write

### End-to-End Test

Full demo path:

1. Report disruption
2. Agents investigate
3. ClickHouse query executes
4. Options are returned
5. Producer approves option
6. Ledger is written

---

## Failure Mitigation

### Risk 1: LLM generates bad SQL

Mitigation:

- Use templated queries
- Do not allow unrestricted SQL generation
- Validate queries before execution

---

### Risk 2: ClickHouse connection fails during demo

Mitigation:

- Pre-warm connection
- Cache last successful evidence result
- Have fallback recorded demo path

---

### Risk 3: Agent response is slow

Mitigation:

- Limit number of agent steps
- Use streaming if possible
- Show “agents investigating” status in UI

---

### Risk 4: Demo data looks fake

Mitigation:

- Generate thousands of synthetic records
- Use realistic cost distributions
- Show aggregate counts in UI

---

## Definition of Done

The project is done when:

1. ClickHouse MCP is called at runtime.
2. The agent workflow produces ranked recovery options.
3. Historical evidence is visible in the UI.
4. The producer can approve an option.
5. The decision is written to ClickHouse.
6. The app is hosted at a public URL.
7. The repo is public with license.
8. The 3-minute demo video is complete.