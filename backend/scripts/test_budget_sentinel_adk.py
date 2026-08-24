"""Test Budget Sentinel ADK Agent Integration.

Verifies:
  - Budget Sentinel ADK Agent initialization
  - ADK FunctionTool integration with ClickHouse Safe Query Builder & MCP client
  - Realistic mock disruption payload execution via Runner.run_async
  - Tool call parameter validation and execution against ClickHouse MCP
  - Structured output parsing and assertion against BudgetSentinelResult Pydantic schema
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Search for .env
for env_path in (
    backend_dir / ".env",
    backend_dir.parent / ".env",
    Path(".env"),
):
    if env_path.exists():
        load_dotenv(env_path)
        break

from google.adk import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from agents.budget_sentinel import create_budget_sentinel_agent, run_budget_sentinel_adk
from models import (
    BudgetSentinelResult,
    CaseState,
    DisruptionReport,
    EvidenceRow,
    new_case,
)


async def run_test():
    print("=" * 70)
    print("BUDGET SENTINEL ADK AGENT TEST: Isolated Execution Verification")
    print("=" * 70)

    # 1. Create a realistic mock disruption case
    report = DisruptionReport(
        production_id="prod_dharwad_001",
        disruption_type="lead_actor_unavailable",
        affected_day=2,
        affected_cast_id="cast_dharwad_lead",
        affected_location_id="loc_heritage_court",
        severity="medium",
        reported_by="1st AD Marcus Sterling",
        notes="Lead actor suffered acute throat infection and is on medical voice rest for Day 2.",
    )
    case: CaseState = new_case(report)
    case.case_id = "case_budget_adk_test_001"
    case.studio_id = "global"

    print(f"[1] Seeded Disruption Case: id={case.case_id}, type={report.disruption_type}, severity={report.severity}")

    # 2. Instantiate ADK Agent & Runner
    session_service = InMemorySessionService()
    agent = create_budget_sentinel_agent()
    app_name = "budget_sentinel_test_app"
    runner = Runner(
        app_name=app_name,
        agent=agent,
        session_service=session_service,
    )
    print(f"[2] ADK Agent '{agent.name}' created with tools: {[t.name for t in agent.tools]}")

    # 3. Create Session
    user_id = "test_producer"
    session_id = f"session_{case.case_id}"
    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )
    print(f"[3] Session created: id={session_id}")

    # 4. Dispatch query to Agent
    user_prompt = (
        f"Analyze historical evidence for case '{case.case_id}': "
        f"disruption_type='{report.disruption_type}', severity='{report.severity}', studio_id='{case.studio_id}'. "
        f"Call query_disruption_history with template_id='strategy_performance' to retrieve resolution strategy benchmarks."
    )
    print(f"[4] Sending prompt to agent:\n'{user_prompt}'")
    print("-" * 70)

    user_msg = types.Content(
        role="user",
        parts=[types.Part(text=user_prompt)],
    )

    tool_calls_detected = []
    tool_responses_detected = []
    final_text = ""

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_msg,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    fc = part.function_call
                    tool_calls_detected.append((fc.name, fc.args))
                    print(f"--> [TOOL CALL] {fc.name}(args={dict(fc.args or {})})")
                if part.function_response:
                    fr = part.function_response
                    fr_dict = fr.response or {}
                    tool_responses_detected.append((fr.name, fr_dict))
                    rows_count = len(fr_dict.get("evidence_rows", []))
                    sql_executed = fr_dict.get("sql", "")
                    print(f"<-- [TOOL RESPONSE] {fr.name}: returned {rows_count} rows via MCP")
                    print(f"    [GENERATED SQL]: {sql_executed}")
                if part.text:
                    final_text += part.text

    print("-" * 70)
    print(f"[AGENT NARRATIVE SYNTHESIS]:\n{final_text.strip()}")
    print("=" * 70)

    # 5. Schema Validation & Assertions
    assert len(tool_calls_detected) > 0, "Agent failed to make any tool calls"
    assert tool_calls_detected[0][0] == "query_disruption_history", "Expected call to query_disruption_history"
    assert len(tool_responses_detected) > 0, "Expected tool response from MCP execution"
    
    fr_data = tool_responses_detected[0][1]
    assert "evidence_rows" in fr_data, "Expected evidence_rows in tool response payload"
    raw_rows = fr_data.get("evidence_rows", [])
    assert len(raw_rows) > 0, "Expected at least 1 evidence row from ClickHouse"

    # 6. Test Structured Pydantic result mapping
    evidence_models = [EvidenceRow(**r) for r in raw_rows]
    result = BudgetSentinelResult(
        studio_id=case.studio_id,
        evidence_cohort="global",
        evidence_footnote=f"industry baseline (n={sum(e.past_cases for e in evidence_models):,})",
        evidence_narrative=final_text.strip(),
        evidence_rows=evidence_models,
    )

    print(f"[5] Validated BudgetSentinelResult Pydantic Schema:")
    print(f"    - Studio ID: {result.studio_id}")
    print(f"    - Evidence Rows Count: {len(result.evidence_rows)}")
    print(f"    - Sample Top Strategy: {result.evidence_rows[0].resolution_strategy} (${result.evidence_rows[0].avg_cost_overrun_usd:,.0f} overrun)")
    print(f"    - Evidence Footnote: {result.evidence_footnote}")
    print("=" * 70)
    print("BUDGET SENTINEL ADK AGENT TEST: PASSED SUCCESSFULLY")


if __name__ == "__main__":
    asyncio.run(run_test())
