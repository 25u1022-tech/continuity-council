"""Production Integration Test: Verifies ADK Runner drives the Orchestration Pipeline.

Guarantees:
  1. POST /api/disruptions -> orchestrator.run_investigation genuinely executes via ADK Runner (Runner.run_async).
  2. The agent hierarchy matches ADK SequentialAgent -> [Generate, ParallelAgent(4 specialists), Synthesis].
  3. CaseState is updated properly and transitions to options_ready.
  4. Fails if execution is reverted to custom asyncio.gather or non-ADK orchestration.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from google.adk import Runner
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.sequential_agent import SequentialAgent

import case_store
from agents import orchestrator
from models import DisruptionReport, EvidenceRow, new_case
from services import clickhouse_client


def test_production_investigation_executes_via_adk_runner():
    """Verify that run_investigation executes the ADK SequentialAgent hierarchy via Runner.run_async."""
    async def _test():
        # 1. Create realistic disruption case
        report = DisruptionReport(
            production_id="prod_001",
            disruption_type="lead_actor_unavailable",
            affected_day=2,
            affected_cast_id="lead_001",
            affected_location_id="harbor_exterior",
            severity="medium",
            notes="Production integration test for ADK Runner verification.",
        )
        case = new_case(report)
        case_store.put(case)

        # 2. Build mock production bundle
        bundle = {
            "production": {
                "production_id": "prod_001",
                "title": "The Long Dark Take",
                "total_shoot_days": 3,
                "start_date": "2026-01-01",
                "currency": "USD",
                "studio_id": "global",
            },
            "locations": [
                {"location_id": "stage_a", "name": "Stage A", "location_type": "stage", "capacity": 100, "notes": ""},
                {"location_id": "harbor_exterior", "name": "Harbor", "location_type": "exterior", "capacity": 200, "notes": ""},
            ],
            "cast_members": [
                {"cast_id": "lead_001", "name": "Mara Voss", "role_type": "lead"},
                {"cast_id": "supp_001", "name": "Dev Okafor", "role_type": "supporting"},
            ],
            "scenes": [
                {"scene_id": "sc_005", "scene_title": "Interrogation", "shoot_day": 2, "sequence_order": 5,
                 "location_id": "stage_a", "required_cast": ["lead_001", "supp_001"], "scene_type": "interior",
                 "is_cover_scene": False, "priority": 1, "continuity_tags": ["costume_interrogation"],
                 "depends_on": [], "status": "scheduled"},
                {"scene_id": "sc_006", "scene_title": "Confrontation", "shoot_day": 2, "sequence_order": 6,
                 "location_id": "stage_a", "required_cast": ["lead_001"], "scene_type": "interior",
                 "is_cover_scene": False, "priority": 1, "continuity_tags": ["costume_interrogation"],
                 "depends_on": ["sc_005"], "status": "scheduled"},
                {"scene_id": "sc_008", "scene_title": "Stakeout", "shoot_day": 2, "sequence_order": 8,
                 "location_id": "harbor_exterior", "required_cast": ["supp_001"], "scene_type": "exterior",
                 "is_cover_scene": False, "priority": 3, "continuity_tags": [], "depends_on": [], "status": "scheduled"},
                {"scene_id": "sc_009", "scene_title": "Cover set", "shoot_day": 3, "sequence_order": 9,
                 "location_id": "stage_a", "required_cast": ["supp_001"], "scene_type": "cover",
                 "is_cover_scene": True, "priority": 4, "continuity_tags": [], "depends_on": [], "status": "scheduled"},
                {"scene_id": "sc_010", "scene_title": "Finale", "shoot_day": 3, "sequence_order": 10,
                 "location_id": "stage_a", "required_cast": ["lead_001", "supp_001"], "scene_type": "interior",
                 "is_cover_scene": False, "priority": 1, "continuity_tags": [], "depends_on": ["sc_006"], "status": "scheduled"},
            ],
            "location_availability": [
                {"location_id": loc, "shoot_day": day,
                 "available": not (loc == "harbor_exterior" and day == 3), "notes": ""}
                for loc in ("stage_a", "harbor_exterior")
                for day in (1, 2, 3)
            ],
            "cast_availability": [
                {"cast_id": cid, "shoot_day": day, "available": True, "reason": ""}
                for cid in ("lead_001", "supp_001")
                for day in (1, 2, 3)
            ],
        }

        # 3. Spy on Runner.run_async
        original_run_async = Runner.run_async
        runner_calls = []

        async def spy_run_async(self, *args, **kwargs):
            runner_calls.append({
                "runner_agent": self.agent,
                "app_name": self.app_name,
                "session_service": self.session_service,
                "args": args,
                "kwargs": kwargs,
            })
            async for event in original_run_async(self, *args, **kwargs):
                yield event

        async def mock_budget_run(c):
            c.evidence_rows = [
                EvidenceRow(
                    resolution_strategy="shoot_cover_scenes",
                    avg_cost_overrun_usd=15000.0,
                    avg_delay_hours=3.5,
                    avg_continuity_risk=0.2,
                    avg_compliance_risk=0.1,
                    avg_success_score=0.85,
                    past_cases=120,
                )
            ]
            c.evidence_narrative = "Historical data favors shooting cover scenes."

        with patch.object(clickhouse_client, "get_current_schedule", new=AsyncMock(return_value=bundle)), \
             patch("agents.budget_sentinel.run", side_effect=mock_budget_run), \
             patch("agents.budget_sentinel.calibrate_option_economics", new=AsyncMock(return_value=None)), \
             patch.object(Runner, "run_async", side_effect=spy_run_async, autospec=True):

            await orchestrator.run_investigation(case.case_id)

        # 4. Assert ADK Runner was called
        assert len(runner_calls) >= 1, "CRITICAL: orchestrator.run_investigation did NOT execute through ADK Runner!"
        
        call_info = runner_calls[0]
        top_agent = call_info["runner_agent"]

        # 5. Verify ADK Agent Hierarchy
        assert isinstance(top_agent, SequentialAgent), f"Expected SequentialAgent, got {type(top_agent)}"
        assert top_agent.name == "orchestrator_agent"
        assert len(top_agent.sub_agents) == 3, f"Expected 3 stages, got {len(top_agent.sub_agents)}"

        stage1, stage2, stage3 = top_agent.sub_agents
        assert stage1.name == "generate_agent"
        
        assert isinstance(stage2, ParallelAgent), f"Expected ParallelAgent for stage 2, got {type(stage2)}"
        assert stage2.name == "parallel_evaluator"
        assert len(stage2.sub_agents) == 4, f"Expected 4 parallel specialist agents, got {len(stage2.sub_agents)}"

        sub_names = [s.name for s in stage2.sub_agents]
        assert "budget_sentinel_agent" in sub_names
        assert "continuity_memory_agent" in sub_names
        assert "compliance_agent" in sub_names
        assert "schedule_optimizer_agent" in sub_names

        assert stage3.name == "synthesis_agent"

        # 6. Verify CaseState final transition
        updated_case = case_store.get(case.case_id)
        assert updated_case is not None
        assert updated_case.status == "options_ready"
        assert len(updated_case.options) >= 2
        assert updated_case.recommendation_rationale != ""

    asyncio.run(_test())
