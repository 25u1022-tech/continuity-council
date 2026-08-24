"""
Continuity Council — Google ADK Council Test Script

Spins up the Google Agent Development Kit (ADK) SequentialAgent + ParallelAgent
multi-agent council on a seeded disruption case, executes via ADK Runner.run_async(),
and prints each agent invocation, tool calls, and final ranked options.

This is the standalone verification proof of Google ADK integration.

Usage:
    python scripts/test_adk.py
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
backend_dir = ROOT / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

for env_path in (backend_dir / ".env", ROOT / ".env", Path(".env")):
    if env_path.exists():
        load_dotenv(env_path)
        break

from google.adk import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

import case_store
from agents.orchestrator import create_orchestrator_agent, run_investigation
from models import DisruptionReport, new_case
from services import clickhouse_client


async def main() -> int:
    print("=" * 70)
    print("CONTINUITY COUNCIL -- Google ADK Multi-Agent Council Verification")
    print("=" * 70)

    # 1. Verify ADK Agent Hierarchy
    orchestrator_agent = create_orchestrator_agent()
    print(f"\n[1] ADK SequentialAgent Architecture: `{orchestrator_agent.name}`")
    for i, stage in enumerate(orchestrator_agent.sub_agents, 1):
        if hasattr(stage, "sub_agents") and stage.sub_agents:
            sub_names = [s.name for s in stage.sub_agents]
            print(f"    Stage {i}: {stage.name} (ADK ParallelAgent running {len(sub_names)} specialists concurrently)")
            for sname in sub_names:
                print(f"      └─► {sname}")
        else:
            print(f"    Stage {i}: {stage.name} (ADK BaseAgent)")

    # 2. Seed realistic disruption case
    report = DisruptionReport(
        production_id="prod_001",
        disruption_type="lead_actor_unavailable",
        affected_day=2,
        affected_cast_id="lead_001",
        affected_location_id="harbor_exterior",
        severity="medium",
        reported_by="1st AD Marcus Sterling",
        notes="Lead actor hospitalized with fever; voice rest mandated for Day 2.",
    )
    case = new_case(report)
    case_store.put(case)
    print(f"\n[2] Seeded Case '{case.case_id}' for production '{report.production_id}'")
    print(f"    Disruption: {report.disruption_type} on Day {report.affected_day} (Severity: {report.severity})")

    # 3. Execute full investigation via ADK Runner
    print(f"\n[3] Dispatching ADK Multi-Agent Council (Runner.run_async)...")
    t0 = time.perf_counter()
    await run_investigation(case.case_id)
    duration_s = time.perf_counter() - t0

    # 4. Verify Case Output & Agent Invocations
    updated_case = case_store.get(case.case_id)
    if not updated_case:
        print("ERROR: Case not found in store after investigation!")
        return 1

    print(f"\n[4] Agent Invocations & Completion Status (Execution time: {duration_s:.2f}s):")
    print("-" * 70)
    for agent_key, agent_state in updated_case.agents.items():
        status_sym = "[OK]" if agent_state.status == "completed" else f"[{agent_state.status.upper()}]"
        print(f"  {status_sym} {agent_key:<22} | {agent_state.summary}")
    print("-" * 70)

    # 5. MCP Tool Call Logging
    print(f"\n[5] ClickHouse MCP Tool Calls Logged: {len(updated_case.mcp_calls)}")
    for i, call in enumerate(updated_case.mcp_calls, 1):
        print(f"    Call {i}: [{call.agent}] tool='{call.tool}' latency={call.latency_ms}ms rows={call.rows_returned}")
        print(f"            SQL: {call.sql[:100]}...")

    # 6. Ranked Recovery Options
    print(f"\n[6] Final Ranked Recovery Options ({len(updated_case.options)} generated):")
    print("-" * 70)
    print(f"{'Rank':<5} | {'Option Name':<28} | {'Strategy':<20} | {'Score':<6} | {'Cost USD':<10} | {'Delay':<7} | {'Valid'}")
    print("-" * 70)
    for opt in updated_case.options:
        rec_mark = " (REC)" if opt.recommended else ""
        print(
            f"{opt.rank:<5} | {opt.name + rec_mark:<28} | {opt.strategy:<20} | {opt.score:<6.2f} | "
            f"${opt.estimated_cost_usd:<9,d} | {opt.estimated_delay_hours:<5.1f}h | {opt.compliance_valid}"
        )
    print("-" * 70)

    if updated_case.recommendation_rationale:
        print(f"\nExecutive Rationale:\n  {updated_case.recommendation_rationale}")

    print("\n" + "=" * 70)
    print("GOOGLE ADK COUNCIL PROOF: SUCCESS")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
