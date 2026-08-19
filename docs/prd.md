<!-- 01_product_requirements.md -->
# Product Requirements Document

## Product Name

**Continuity Council**

## One-Line Pitch

Continuity Council is a multi-agent production recovery system that helps film producers respond to schedule disruptions by using ClickHouse historical data to rank recovery options by cost, delay, continuity risk, and operational feasibility.

---

## Problem Statement

Film and media productions are highly fragile systems. A single disruption, such as a lead actor becoming unavailable, a location permit failing, weather damage, or equipment failure, can cause:

- Shooting schedule delays
- Budget overruns
- Continuity errors
- Union or compliance violations
- Crew overtime
- Wasted location rental costs
- Creative compromises

The core problem is not just detecting the disruption. The problem is deciding quickly:

> “What is the safest, cheapest, and most feasible recovery option right now?”

Today, producers, line producers, and assistant directors make these decisions under pressure using experience, spreadsheets, and fragmented historical knowledge. There is no unified decision engine that grounds recovery options in historical production data.

---

## Target Users

### Primary User

**Producer / Line Producer**

Needs to make fast recovery decisions when a disruption occurs.

### Secondary Users

- Assistant Director
- Production Manager
- Studio Operations Team
- Post-Production Supervisor
- Compliance or Legal Operations

---

## Value Proposition

Continuity Council turns production chaos into structured, data-grounded decision-making.

Instead of guessing, the producer receives:

1. Multiple recovery options
2. Estimated cost impact
3. Estimated delay impact
4. Continuity risk warnings
5. Compliance warnings
6. Historical evidence from similar past disruptions
7. A recommended option
8. An auditable decision trail

---

## Product Goals

### Primary Goal

Build a working MVP where a producer can:

1. Report a production disruption
2. Receive multiple recovery options
3. See historical cost and delay evidence from ClickHouse
4. Choose one option
5. Update the schedule
6. Save an auditable decision record

---

## Non-Goals for MVP

The MVP will not include:

- Full production budgeting software
- Full union rule engine
- Real-time crew payroll calculation
- Full script breakdown automation
- Multi-production enterprise tenant management
- Real studio ERP integration
- Automatic contract or legal compliance checks
- Full casting availability integration
- Full location permitting integration

---

## MVP Scenario

### Production Setup

A fictional production has:

- 3 shoot days
- 10 scenes
- 3 locations
- 1 lead actor
- 2 supporting actors
- 1 cover scene set available

### Disruption

The lead actor is unavailable on Day 2.

### Expected System Behavior

The system generates recovery options such as:

1. **Shoot cover scenes**
   - Shoot scenes that do not require the lead actor
   - Move lead-actor scenes to Day 3

2. **Swap locations**
   - Move interior scenes to Day 2
   - Move exterior scenes to Day 3

3. **Wait for actor**
   - Delay affected scenes
   - Accept higher cost and delay

Each option is scored using:

- Estimated cost overrun
- Estimated delay hours
- Continuity risk
- Compliance feasibility
- Historical evidence from ClickHouse

---

## Core Features

## 1. Disruption Reporting

The producer reports a disruption using a simple form.

Fields:

- Production ID
- Disruption type
- Affected day
- Affected cast member or location
- Severity
- Notes

Example disruption types:

- `lead_actor_unavailable`
- `supporting_actor_unavailable`
- `location_unavailable`
- `equipment_failure`
- `weather_delay`
- `permit_issue`

---

## 2. Orchestrator Agent

The Orchestrator receives the disruption and coordinates specialist agents.

Responsibilities:

- Create a disruption case
- Dispatch specialist agents
- Collect findings
- Merge option proposals
- Rank options
- Present final recommendation
- Trigger approval workflow
- Write audit trail after approval

---

## 3. Schedule Optimizer Agent

The Schedule Optimizer proposes alternative shooting schedules.

It checks:

- Which scenes can be shot without the unavailable actor
- Which scenes must be moved
- Which locations can be swapped
- Which day is least affected
- Whether a cover scene exists
- What order minimizes delay

Output:

- 2 to 4 recovery options
- Scene movements
- Location changes
- Day changes
- Expected operational impact

---

## 4. Budget Sentinel Agent

This is the main ClickHouse-powered agent.

It queries historical production-disruption data to answer:

- What happened in similar past disruptions?
- What was the average cost overrun?
- What was the average delay?
- Which recovery strategy performed best?
- Which strategy had the highest success rate?

Example output:

> “Historically, shooting cover scenes after lead actor unavailability reduced cost overrun by 62% compared with waiting for the actor.”

This agent prevents the system from guessing.

---

## 5. Continuity Memory Agent

This agent checks creative and continuity risks.

For MVP, it checks:

- Scenes involving the unavailable actor
- Related scenes that should stay together
- Costume or character-state dependencies
- Location continuity issues
- Risk of moving scenes out of narrative order

Example output:

> “Scene 12 and Scene 13 should remain adjacent because the lead actor has a costume state change.”

---

## 6. Compliance Agent

This agent checks operational constraints.

For MVP, it checks:

- Is the new schedule possible within the 3-day shoot?
- Are locations available on the proposed days?
- Are required cast members available?
- Does the option create impossible dependencies?
- Does the option exceed simple working-hour constraints?

Example output:

> “Option B is cheaper, but Location 2 is not available on Day 2.”

---

## 7. Auditor Agent

After the producer approves an option, the Auditor Agent writes the decision trail.

It records:

- Disruption event
- Options considered
- Evidence used
- Selected option
- Human approval
- Schedule change
- Timestamp

This makes the final output queryable and transparent.

---

## User Stories

### Producer

> As a producer, I want to report a disruption and immediately see recovery options so I can make a fast decision.

> As a producer, I want to see the estimated cost and delay impact of each option so I can protect the budget.

> As a producer, I want historical evidence supporting each option so I can trust the recommendation.

> As a producer, I want the final decision recorded so the production office can audit what happened.

---

### Production Manager

> As a production manager, I want to see which scenes are affected by a disruption so I can coordinate the schedule.

> As a production manager, I want compliance warnings before approving an option so I do not create an invalid schedule.

---

### Studio Executive

> As a studio executive, I want a decision ledger so I can understand how disruptions affected cost and schedule.

---

## MVP Acceptance Criteria

The MVP is complete when:

1. The user can select a production.
2. The user can report a disruption.
3. The Orchestrator Agent creates a disruption case.
4. The Schedule Optimizer generates at least 2 recovery options.
5. The Budget Sentinel queries ClickHouse at runtime through MCP.
6. The UI displays historical cost and delay evidence.
7. The Continuity Memory agent flags at least one creative risk.
8. The Compliance agent validates each option.
9. The Orchestrator ranks the options.
10. The producer can approve one option.
11. The system updates the schedule or shows the schedule change.
12. The decision is written to the ClickHouse decision ledger.
13. The demo video shows the full workflow in under 3 minutes.

---

## Key Metrics

### Product Metrics

- Time from disruption to recommended option
- Number of recovery options generated
- Percentage of options with historical evidence
- Percentage of options blocked by compliance warnings
- Producer approval rate

### Demo Metrics

- ClickHouse query completes successfully during demo
- Agent returns grounded evidence, not generic advice
- UI clearly compares options
- Decision ledger record is visible after approval

---

## Judging Criteria Alignment

### Technological Implementation

The project uses:

- Gemini
- Google Cloud Agent Builder / Agent Platform
- Official ClickHouse MCP server
- Runtime ClickHouse queries
- Multi-agent orchestration

### Design

The product is not just a chatbot. It provides:

- Disruption intake
- Agent investigation
- Option ranking
- Human approval
- Schedule update
- Audit trail

### Potential Impact

The project addresses a real M&E problem:

- Production delays are expensive
- Recovery decisions are time-sensitive
- Historical knowledge is usually fragmented
- Poor decisions cause budget overruns and continuity issues

### Quality of Idea

This is a non-obvious use of ClickHouse:

> Using real-time analytics as the memory layer for agentic production recovery decisions.

---

## Demo Narrative

The demo should follow this exact story:

1. A 3-day production is scheduled.
2. The lead actor becomes unavailable for Day 2.
3. The producer reports the disruption.
4. The Orchestrator activates specialist agents.
5. The Schedule Optimizer proposes recovery options.
6. The Budget Sentinel queries ClickHouse for historical evidence.
7. The Continuity Memory agent flags creative risk.
8. The Compliance agent checks feasibility.
9. The producer sees ranked options.
10. The producer approves the best option.
11. The schedule updates.
12. The decision is written to the ledger.

---

## One-Line Version for Judges

> “Continuity Council coordinates specialist agents to respond to production disruptions, using ClickHouse historical data to ground cost and delay estimates, while validating creative continuity and operational constraints before the producer approves the final decision.”