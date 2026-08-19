# ClickHouse MCP Server Configuration

Continuity Council uses the **official `mcp-clickhouse` server** (pip package
[`mcp-clickhouse`](https://github.com/ClickHouse/mcp-clickhouse)) at runtime.
The Budget Sentinel agent talks to ClickHouse Cloud **exclusively through a real
MCP `ClientSession`** — see `backend/services/mcp_client.py`.

## How the backend spawns the server

The FastAPI backend spawns the MCP server as a stdio subprocess and opens an MCP
client session over it:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server = StdioServerParameters(
    command="mcp-clickhouse",   # official console script installed via pip
    args=[],
    env={
        "CLICKHOUSE_HOST": "<your ClickHouse Cloud host>",
        "CLICKHOUSE_PORT": "8443",
        "CLICKHOUSE_USER": "default",
        "CLICKHOUSE_PASSWORD": "***",
        "CLICKHOUSE_SECURE": "true",
        "CLICKHOUSE_MCP_SERVER_TRANSPORT": "stdio",
        "CLICKHOUSE_ALLOW_WRITE_ACCESS": "false",   # MCP layer is read-only
    },
)
```

## Tools exposed by mcp-clickhouse 0.4.x

| Tool | Purpose |
|---|---|
| `list_databases` | List databases |
| `list_tables` | List tables in a database |
| `run_query` | Execute a SQL query (read-only unless write access enabled) |

> Note: older releases named the query tool `run_select_query`. Our client
> calls `list_tools()` at startup and resolves whichever name is present.

## Safety hardening in this project

- `CLICKHOUSE_ALLOW_WRITE_ACCESS=false` — MCP layer can never write.
- The LLM **never writes raw SQL**. It selects from predefined query templates
  in `backend/services/safe_query_builder.py`; parameters are validated against
  allowlists before the SQL string is built.
- Every MCP call is wrapped in a timeout with one retry and logged
  (tool, SQL, row count, latency) — surfaced live in the UI investigation panel.

## Standalone proof

```bash
python scripts/test_mcp.py
```

spawns the server, lists tools, runs the Budget Sentinel evidence query and
prints rows + latency.
