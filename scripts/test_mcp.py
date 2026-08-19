"""
Continuity Council — MCP Round-Trip Proof Script

Spawns the OFFICIAL mcp-clickhouse MCP server via stdio, opens a real MCP
ClientSession, lists tools, and executes a templated SELECT against
ClickHouse Cloud through the MCP `run_query` tool.

This is the on-camera proof of runtime ClickHouse MCP usage.

Usage:
    python scripts/test_mcp.py
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env")

SQL = (
    "SELECT resolution_strategy, "
    "round(AVG(cost_overrun_usd)) AS avg_cost_overrun_usd, "
    "round(AVG(schedule_delay_hours), 1) AS avg_delay_hours, "
    "round(AVG(success_score), 2) AS avg_success_score, "
    "COUNT(*) AS past_cases "
    "FROM continuity_council.disruption_history "
    "WHERE disruption_type = 'lead_actor_unavailable' "
    "GROUP BY resolution_strategy "
    "ORDER BY avg_cost_overrun_usd ASC"
)

MV_SQL = (
    "SELECT strategy, "
    "round(avgMerge(avg_cost)) AS avg_cost_overrun_usd, "
    "round(avgMerge(avg_delay), 1) AS avg_delay_hours, "
    "countMerge(sample_size) AS past_cases "
    "FROM continuity_council.strategy_performance_mv "
    "WHERE disruption_type = 'lead_actor_unavailable' "
    "GROUP BY strategy "
    "ORDER BY avg_cost_overrun_usd ASC"
)


async def main() -> int:
    host = os.environ.get("CLICKHOUSE_HOST", "")
    if not host:
        print("ERROR: CLICKHOUSE_HOST not set in backend/.env")
        return 1

    env = {
        **os.environ,
        "CLICKHOUSE_HOST": host,
        "CLICKHOUSE_PORT": os.environ.get("CLICKHOUSE_PORT", "8443"),
        "CLICKHOUSE_USER": os.environ.get("CLICKHOUSE_USER", "default"),
        "CLICKHOUSE_PASSWORD": os.environ.get("CLICKHOUSE_PASSWORD", ""),
        "CLICKHOUSE_SECURE": "true",
        "CLICKHOUSE_VERIFY": "true",
        "CLICKHOUSE_MCP_SERVER_TRANSPORT": "stdio",
        "CLICKHOUSE_ALLOW_WRITE_ACCESS": "false",  # MCP layer is read-only
        "CLICKHOUSE_ENABLED": "true",
    }

    print("=" * 70)
    print("CONTINUITY COUNCIL -- ClickHouse MCP round-trip proof")
    print("=" * 70)
    import shutil
    binary = (
        shutil.which("mcp-clickhouse")
        or shutil.which("mcp-clickhouse", path=os.path.dirname(sys.executable))
        or "mcp-clickhouse"
    )
    server = StdioServerParameters(command=binary, args=[], env=env)

    t0 = time.perf_counter()
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print(f"MCP tools exposed by server: {names}")

            tool_name = "run_select_query" if "run_select_query" in names else "run_query"
            print(f"\nCalling MCP tool `{tool_name}` with templated SELECT:\n  {SQL}\n")

            q0 = time.perf_counter()
            result = await session.call_tool(tool_name, {"query": SQL})
            latency_ms = (time.perf_counter() - q0) * 1000

            if result.isError:
                print("MCP TOOL ERROR:", result.content)
                return 1

            payload = result.content[0].text if result.content else "{}"
            data = json.loads(payload)
            cols = data.get("columns", [])
            rows = data.get("rows", [])

            print(f"Query latency: {latency_ms:.0f} ms | rows returned: {len(rows)}")
            print("-" * 70)
            print(" | ".join(f"{c:<22}" for c in cols))
            for r in rows:
                print(" | ".join(f"{str(v):<22}" for v in r))
            print("-" * 70)

            print(f"\nCalling MCP tool `{tool_name}` with materialized-view SELECT:\n  {MV_SQL}\n")
            mv_q0 = time.perf_counter()
            mv_result = await session.call_tool(tool_name, {"query": MV_SQL})
            mv_latency_ms = (time.perf_counter() - mv_q0) * 1000
            if mv_result.isError:
                print("MATERIALIZED VIEW MCP TOOL ERROR:", mv_result.content)
                return 1

            mv_payload = mv_result.content[0].text if mv_result.content else "{}"
            mv_data = json.loads(mv_payload)
            mv_cols = mv_data.get("columns", [])
            mv_rows = mv_data.get("rows", [])
            print(f"Materialized-view query latency: {mv_latency_ms:.0f} ms | rows returned: {len(mv_rows)}")
            print(" | ".join(f"{c:<22}" for c in mv_cols))
            for r in mv_rows:
                print(" | ".join(f"{str(v):<22}" for v in r))

    total = (time.perf_counter() - t0) * 1000
    print(f"TOTAL MCP round-trip (spawn + init + query): {total:.0f} ms")
    print("MCP ROUND-TRIP PROOF: SUCCESS (raw history + strategy_performance_mv)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

