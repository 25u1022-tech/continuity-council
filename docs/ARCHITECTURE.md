# Continuity Council architecture

```mermaid
flowchart TD
    subgraph Frontend[Frontend layer]
        SPA[React frontend SPA]
    end

    subgraph Backend[Backend layer - single container]
        API[FastAPI backend<br/>/api routes + SPA serving]
        ORCH[Orchestrator]
        OPT[Schedule Optimizer]
        SENT[Budget Sentinel]
        MEM[Continuity Memory]
        COMP[Compliance]
        AUD[Auditor]
    end

    subgraph MCP[MCP protocol layer]
        BRIDGE[mcp-clickhouse<br/>typed protocol bridge]
    end

    subgraph Database[Database layer - ClickHouse Cloud cluster]
        PROD[(Production data<br/>productions + schedules)]
        HIST[(Historical evidence<br/>200,000+ disruptions)]
        MV[(Materialized views<br/>strategy performance)]
        LEDGER[(Immutable ledger<br/>decision_ledger + schedule_changes)]
    end

    SPA -->|same-origin HTTP| API
    API --> ORCH
    ORCH --> OPT
    ORCH --> SENT
    ORCH --> MEM
    ORCH --> COMP
    ORCH --> AUD

    ORCH -->|typed agent workflow| BRIDGE
    OPT -->|typed constraints| BRIDGE
    SENT -->|predefined evidence template| BRIDGE
    MEM -->|typed schedule context| BRIDGE
    COMP -->|typed availability context| BRIDGE
    AUD -->|append-only decision record| PROD
    AUD -->|append-only audit write| LEDGER

    BRIDGE -->|read-only MCP queries| PROD
    BRIDGE -->|read-only MCP queries| HIST
    BRIDGE -->|avgMerge / countMerge| MV
    HIST -->|aggregated by strategy| MV

    classDef frontend fill:#1B1B21,stroke:#FFC24B,color:#F5F5F7;
    classDef backend fill:#1B1B21,stroke:#A1A1A6,color:#F5F5F7;
    classDef mcp fill:#1B1B21,stroke:#30D158,color:#F5F5F7;
    classDef database fill:#1B1B21,stroke:#FFD60A,color:#F5F5F7;
    class SPA frontend;
    class API,ORCH,OPT,SENT,MEM,COMP,AUD backend;
    class BRIDGE mcp;
    class PROD,HIST,MV,LEDGER database;
```

MCP provides a typed, observable protocol boundary between the agent council and ClickHouse instead of allowing agents to compose raw SQL. Predefined parameterized tools preserve provenance, prevent hallucinated queries, and keep evidence access read-only and auditable.
