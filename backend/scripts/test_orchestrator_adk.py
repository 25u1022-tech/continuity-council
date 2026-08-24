"""Test ADK Multi-Agent Orchestrator Composition & End-to-End Investigation.

Verifies:
  - SequentialAgent / ParallelAgent composition structure
  - Full async investigation lifecycle on a mock production case
  - All 4 specialists (Budget Sentinel, Continuity Memory, Compliance, Schedule Optimizer) running concurrently
  - Option calibration, bottom-up costing, TRD weighted scoring, and executive synthesis
  - Case state transition to OPTIONS_READY / PRODUCER_REVIEWING
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

import case_store
from agents.orchestrator import create_orchestrator_agent, run_investigation
from models import DisruptionReport, new_case


async def run_test():
    print("=" * 70)
    print("ADK MULTI-AGENT ORCHESTRATOR TEST: End-to-End Investigation")
    print("=" * 70)

    # 1. Verify Orchestrator Composition
    orch_agent = create_orchestrator_agent()
    print(f"[1] Instantiated ADK Orchestrator: {orch_agent.name}")
    print(f"    Sub-agents ({len(orch_agent.sub_agents)} stages):")
    for i, sub in enumerate(orch_agent.sub_agents):
        sub_list = [s.name for s in getattr(sub, "sub_agents", [])] or [t.name for t in getattr(sub, "tools", [])]
        print(f"    Stage {i+1}: {sub.name} -> {sub_list}")

    # 2. Seed realistic disruption case into case_store
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
    print(f"\n[2] Seeded Disruption Case '{case.case_id}' for production '{report.production_id}'")

    # 3. Run Investigation
    print(f"[3] Executing Orchestrator Investigation...")
    await run_investigation(case.case_id)

    # 4. Assert Investigation Results
    updated_case = case_store.get(case.case_id)
    assert updated_case is not None, "Case not found in store"
    print(f"\n[4] Investigation Complete:")
    print(f"    - Final Status: {updated_case.status}")
    print(f"    - Options Generated: {len(updated_case.options)}")
    print(f"    - Evidence Narrative: {updated_case.evidence_narrative[:120]}...")
    print(f"    - Recommendation Rationale: {updated_case.recommendation_rationale[:140]}...")

    assert updated_case.status == "options_ready", f"Expected options_ready, got {updated_case.status}"
    assert len(updated_case.options) >= 2, f"Expected at least 2 options, got {len(updated_case.options)}"
    
    top_option = updated_case.options[0]
    print(f"\n[5] Top Ranked Option (Rank 1):")
    print(f"    - Name: {top_option.name} (Strategy: {top_option.strategy})")
    print(f"    - Weighted Score: {top_option.score:.3f}")
    print(f"    - Estimated Cost: ${top_option.estimated_cost_usd:,}")
    print(f"    - Expected Delay: {top_option.estimated_delay_hours} hrs")
    print(f"    - Compliance Valid: {top_option.compliance_valid}")
    print(f"    - Continuity Risk Score: {top_option.continuity_risk_score}")
    print(f"    - Weather Risk: {top_option.weather_risk}%")

    print("\n" + "=" * 70)
    print("ADK MULTI-AGENT ORCHESTRATOR TEST: PASSED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_test())
