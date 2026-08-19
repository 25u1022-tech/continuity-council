## Title
Continuity Council: The AI Production Risk Officer

## Short Description
An autonomous, multi-agent recovery system that turns film production disruptions into grounded, auditable decisions using ClickHouse historical evidence and the Model Context Protocol.

## The Problem
In film production, a single disruption (lead actor sick, location permit lost) costs studios up to $100,000 in an afternoon. Recovery decisions are currently made under extreme pressure, relying on fragmented spreadsheets and gut feeling. There is no "institutional memory" — every production repeats the same costly mistakes.

## The Solution
Continuity Council acts as an AI Production Risk Officer. When a disruption occurs, a council of six specialized agents investigates the schedule, queries 200,000+ historical disruptions via ClickHouse, and presents the producer with ranked, compliant recovery options. Every decision is logged to an immutable audit ledger.

## How It's Built (The Tech Stack)
- Orchestration: Google Gemini via google-genai SDK, executing a typed state machine across 6 specialist agents.
- Database: ClickHouse Cloud. Chosen specifically for sub-100ms analytical aggregations over historical disruption cohorts, utilizing Materialized Views for real-time evidence panels.
- AI-Data Bridge: The official mcp-clickhouse server. Agents never author raw SQL. They invoke predefined, parameterized MCP tools, ensuring zero hallucinations and complete data provenance.
- Frontend/Backend: React + FastAPI in a single-container deployment for same-origin API calls and zero CORS friction.

## Core Features
1. Multi-Tenant Production Onboarding: Studios upload their own cast and location sheets to instantiate a production.
2. Deterministic Guardrails: The Compliance agent hard-fails options that violate physical constraints (e.g., harbor permits), preventing the LLM from suggesting impossible schedules.
3. Immutable Audit Ledger: Every disruption, evidence query, and approval is appended to the decision_ledger table, creating a SOC2-ready audit trail.
