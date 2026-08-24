"""
Continuity Council — Combined Core POC Harness

Proves the three failure-prone integrations in isolation BEFORE the app is trusted:
  (a) clickhouse-connect direct connection + seeded data sanity checks
  (b) Official mcp-clickhouse MCP server round-trip SELECT (stdio ClientSession)
  (c) Gemini via OFFICIAL google-genai SDK: text + function-calling round

Usage:
    python scripts/test_core.py          # run all
Exits non-zero if any check fails.
"""
import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env")

RESULTS = {}


def check_a_clickhouse_connect() -> bool:
    """Direct clickhouse-connect connection + seeded data sanity."""
    print("\n[A] clickhouse-connect direct connection ...")
    import clickhouse_connect

    client = clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", "8443")),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        secure=True,
    )
    version = client.command("SELECT version()")
    print(f"    Connected. ClickHouse version: {version}")

    n_hist = client.command("SELECT COUNT(*) FROM continuity_council.disruption_history")
    n_scenes = client.command("SELECT COUNT(*) FROM continuity_council.production_schedule WHERE production_id='prod_001'")
    print(f"    disruption_history rows: {n_hist} (need >= 5000)")
    print(f"    prod_001 scenes: {n_scenes} (need 10)")
    assert int(n_hist) >= 5000, "disruption_history has fewer than 5000 rows — run clickhouse/seed.py"
    assert int(n_scenes) == 10, "prod_001 must have exactly 10 scenes — run clickhouse/seed.py"

    res = client.query(
        "SELECT resolution_strategy, round(AVG(cost_overrun_usd)) AS avg_cost, COUNT(*) c "
        "FROM continuity_council.disruption_history "
        "WHERE disruption_type = 'lead_actor_unavailable' GROUP BY resolution_strategy ORDER BY avg_cost ASC"
    )
    assert len(res.result_rows) >= 3, "Expected >= 3 strategies for lead_actor_unavailable"
    for row in res.result_rows:
        print(f"    {row[0]:<22} avg_cost=${row[1]:>8} cases={row[2]}")
    return True


async def check_b_mcp_roundtrip() -> bool:
    """Official mcp-clickhouse stdio round-trip."""
    print("\n[B] Official mcp-clickhouse MCP server round-trip (stdio) ...")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = {
        **os.environ,
        "CLICKHOUSE_SECURE": "true",
        "CLICKHOUSE_MCP_SERVER_TRANSPORT": "stdio",
        "CLICKHOUSE_ALLOW_WRITE_ACCESS": "false",
    }
    import shutil
    binary = (
        shutil.which("mcp-clickhouse")
        or shutil.which("mcp-clickhouse", path=os.path.dirname(sys.executable))
        or "mcp-clickhouse"
    )
    server = StdioServerParameters(command=binary, args=[], env=env)

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            print(f"    MCP tools: {sorted(names)}")
            tool = "run_select_query" if "run_select_query" in names else "run_query"

            t0 = time.perf_counter()
            result = await asyncio.wait_for(
                session.call_tool(tool, {"query": "SELECT COUNT(*) AS n FROM continuity_council.disruption_history"}),
                timeout=30,
            )
            ms = (time.perf_counter() - t0) * 1000
            assert not result.isError, f"MCP tool error: {result.content}"
            data = json.loads(result.content[0].text)
            print(f"    MCP `{tool}` OK in {ms:.0f} ms -> {data['rows'][0][0]} rows in disruption_history")
    return True


async def check_c_gemini() -> bool:
    """Gemini via official google-genai SDK: text + one function-calling round."""
    print("\n[C] Gemini (official google-genai SDK) ...")
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY", "")
    assert api_key, "GEMINI_API_KEY not set in backend/.env"
    client = genai.Client(api_key=api_key)
    model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

    # (1) plain structured output
    resp = await client.aio.models.generate_content(
        model=model,
        contents="Reply with valid JSON: {\"status\": \"ok\"}",
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
    )
    parsed = json.loads(resp.text)
    print(f"    Structured output OK: {parsed}")

    # (2) function-calling round (the Budget Sentinel pattern)
    tool = types.Tool(function_declarations=[types.FunctionDeclaration(
        name="query_disruption_history",
        description="Query historical production disruption analytics from ClickHouse using a safe template.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "disruption_type": {"type": "STRING", "description": "e.g. lead_actor_unavailable"},
            },
            "required": ["disruption_type"],
        },
    )])
    resp = await client.aio.models.generate_content(
        model=model,
        contents="The lead actor is unavailable on day 2. Query the disruption history for evidence.",
        config=types.GenerateContentConfig(tools=[tool], temperature=0),
    )
    calls = resp.function_calls or []
    assert calls, "Gemini did not emit a function call"
    assert calls[0].name == "query_disruption_history", f"Unexpected tool: {calls[0].name}"
    print(f"    Function-calling OK: {calls[0].name}({dict(calls[0].args)})")
    return True


async def main() -> int:
    failures = []
    for label, fn in [
        ("A: clickhouse-connect", check_a_clickhouse_connect),
        ("B: mcp-clickhouse round-trip", check_b_mcp_roundtrip),
        ("C: gemini google-genai", check_c_gemini),
    ]:
        try:
            result = fn()
            if asyncio.iscoroutine(result):
                result = await result
            RESULTS[label] = "PASS"
        except Exception as exc:
            RESULTS[label] = f"FAIL: {exc}"
            failures.append(label)
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("CORE POC RESULTS")
    for label, status in RESULTS.items():
        print(f"  {label:<32} {status}")
    print("=" * 60)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
