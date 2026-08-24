# Continuity Council Architecture

```mermaid
flowchart TD
    subgraph Frontend[Frontend Layer]
        SPA[React 18 SPA<br/>Real-time Decision Cockpit]
    end

    subgraph API_Layer[API Layer - FastAPI]
        API[FastAPI Backend /api<br/>Routes & SPA Serving]
    end

    subgraph ADK_Engine[Google ADK Multi-Agent Council Engine]
        RUNNER[ADK Runner<br/>Runner.run_async]
        
        subgraph SEQ[SequentialAgent: orchestrator_agent]
            STG1[Stage 1: GenerateOptionsAgent<br/>generate_options_tool]
            
            subgraph PAR[Stage 2: ParallelAgent: parallel_evaluator]
                BS[Budget Sentinel Agent<br/>ClickHouse MCP Evidence Query]
                CM[Continuity Memory Agent<br/>Scene Dependency & Costume DAG]
                CP[Compliance Agent<br/>100mi Transit & Union Limits]
                SO[Schedule Optimizer Polish<br/>Gemini Copy & Action Descriptions]
            end
            
            STG3[Stage 3: SynthesisAgent<br/>Rate-Card Pricing & TRD Scoring]
        end
    end

    subgraph Post_Approval[Post-Approval Audit]
        AUD[Auditor Agent (ADK)<br/>write_decision_ledger]
    end

    subgraph MCP[MCP Protocol Layer]
        BRIDGE[mcp-clickhouse<br/>Official Stdio Server]
    end

    subgraph Database[Database Layer - ClickHouse Cloud]
        PROD[(Production Data<br/>productions & schedules)]
        HIST[(Historical Evidence<br/>200,000+ disruptions)]
        MV[(Materialized Views<br/>strategy_performance_mv)]
        LEDGER[(Immutable Audit Ledger<br/>decision_ledger & schedule_changes)]
    end

    SPA -->|POST /api/disruptions| API
    API -->|Async Task Trigger| RUNNER
    RUNNER --> SEQ
    STG1 -->|Candidate Options| PAR
    PAR --> BS & CM & CP & SO
    BS & CM & CP & SO -->|Specialist Outputs| STG3
    STG3 -->|options_ready & ranked options| API
    
    BS -->|templated query via safe_query_builder| BRIDGE
    BRIDGE -->|read-only analytical queries| MV
    HIST -->|aggregated into| MV
    
    SPA -->|POST /api/cases/{id}/approve| API
    API -->|Execute Audit Write| AUD
    AUD -->|Immutable Append| LEDGER
    AUD -->|Update Schedules| PROD

    classDef frontend fill:#1B1B21,stroke:#FFC24B,color:#F5F5F7;
    classDef backend fill:#1B1B21,stroke:#A1A1A6,color:#F5F5F7;
    classDef adk fill:#1B1B21,stroke:#0A84FF,color:#F5F5F7;
    classDef mcp fill:#1B1B21,stroke:#30D158,color:#F5F5F7;
    classDef database fill:#1B1B21,stroke:#FFD60A,color:#F5F5F7;
    class SPA frontend;
    class API backend;
    class RUNNER,SEQ,STG1,PAR,BS,CM,CP,SO,STG3,AUD adk;
    class BRIDGE mcp;
    class PROD,HIST,MV,LEDGER database;
```

### Google Agent Development Kit (ADK) Composition
The Council is built natively using Google ADK (`google-adk`):
1. **Sequential Pipeline**: The `SequentialAgent` drives three consecutive orchestration stages.
2. **Parallel Specialist Concurrency**: The `ParallelAgent` evaluates the ClickHouse MCP empirical baseline, scene continuity DAG, union compliance constraints, and description polish concurrently.
3. **Execution Runtime**: Driven through `Runner.run_async()` backed by typed session state (`InMemorySessionService`).
4. **Post-Approval Isolation**: The `Auditor Agent` is decoupled from the investigation loop, executing only upon explicit producer approval to record immutable decision and schedule change ledgers.

