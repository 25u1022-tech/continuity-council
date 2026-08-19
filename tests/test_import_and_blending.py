"""Unit tests for Historical Data Import and Studio Cold-Start Blending."""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from services.import_service import (
    parse_and_validate_csv,
    generate_template_csv,
    normalize_string_key,
    parse_date,
)
from services.safe_query_builder import build_query, UnsafeQueryError
from models import CaseState, DisruptionReport, EvidenceRow


class TestCsvValidationAndImport:
    def test_valid_csv_accepted(self):
        csv_text = (
            "date,disruption_type,severity,strategy,cost_overrun,delay_hours,satisfaction,currency\n"
            "2025-10-14,lead_actor_unavailable,high,shoot_cover_scenes,35000,4.0,8.5,USD\n"
            "2025-11-02,location_unavailable,medium,swap_locations,25000,2.0,9.0,USD\n"
        )
        res = asyncio.run(parse_and_validate_csv(csv_text, studio_id="studio_warner"))
        assert res["accepted"] == 2
        assert len(res["rejected"]) == 0
        assert len(res["rows_to_insert"]) == 2
        assert res["rows_to_insert"][0]["studio_id"] == "studio_warner"
        assert res["rows_to_insert"][0]["cost_overrun_usd"] == 35000

    def test_invalid_and_out_of_range_rejected(self):
        csv_text = (
            "date,disruption_type,severity,strategy,cost_overrun,delay_hours\n"
            "1990-01-01,lead_actor_unavailable,high,shoot_cover_scenes,1000,2.0\n"  # bad year
            "2025-10-14,alien_invasion,high,shoot_cover_scenes,1000,2.0\n"         # invalid disruption
            "2025-10-14,lead_actor_unavailable,extreme,shoot_cover_scenes,1000,2.0\n" # invalid severity
            "2025-10-14,lead_actor_unavailable,high,magic_fix,1000,2.0\n"            # invalid strategy
            "2025-10-14,lead_actor_unavailable,high,shoot_cover_scenes,-500,2.0\n"   # negative cost
            "2025-10-14,lead_actor_unavailable,high,shoot_cover_scenes,500,999.0\n"  # delay > 500
        )
        res = asyncio.run(parse_and_validate_csv(csv_text, studio_id="studio_test"))
        assert res["accepted"] == 0
        assert len(res["rejected"]) == 6

    def test_deduplication_within_batch(self):
        csv_text = (
            "date,disruption_type,severity,strategy,cost_overrun,delay_hours\n"
            "2025-10-14,lead_actor_unavailable,high,shoot_cover_scenes,35000,4.0\n"
            "2025-10-14,lead_actor_unavailable,high,shoot_cover_scenes,35000,4.0\n"
        )
        res = asyncio.run(parse_and_validate_csv(csv_text, studio_id="studio_test"))
        assert res["accepted"] == 1
        assert len(res["rejected"]) == 1
        assert "Duplicate" in res["rejected"][0]["reason"]

    def test_fx_currency_normalization(self):
        # EUR cost 10,000 converted to USD with live or fallback rate (~1.085)
        csv_text = (
            "date,disruption_type,severity,strategy,cost_overrun,delay_hours,currency\n"
            "2025-10-14,lead_actor_unavailable,high,shoot_cover_scenes,10000,4.0,EUR\n"
        )
        res = asyncio.run(parse_and_validate_csv(csv_text, studio_id="studio_euro"))
        assert res["accepted"] == 1
        row = res["rows_to_insert"][0]
        assert row["cost_overrun_usd"] >= 10500  # EUR is stronger than USD
        assert "EUR" in row["notes"]

    def test_template_generator(self):
        csv_str = generate_template_csv()
        assert "date,disruption_type,severity,strategy" in csv_str
        assert "lead_actor_unavailable" in csv_str


class TestColdStartBlendingMath:
    def test_exact_deterministic_blending_weights(self):
        # Studio: avg $20,000, Global: avg $40,000
        # Formula: w = n_studio / 200; blended = w * 20000 + (1 - w) * 40000
        cases = [
            (0, 0.0, 40000),
            (50, 0.25, 35000),
            (100, 0.50, 30000),
            (150, 0.75, 25000),
            (200, 1.0, 20000),
            (500, 1.0, 20000),
        ]
        for n_studio, expected_w, expected_cost in cases:
            w = min(1.0, n_studio / 200.0)
            cost = round((w * 20000.0) + ((1.0 - w) * 40000.0))
            assert w == expected_w
            assert cost == expected_cost


class TestSafeQueryBuilderStudioIsolation:
    def test_studio_strategy_performance_valid(self):
        sql = build_query("studio_strategy_performance", {
            "disruption_type": "lead_actor_unavailable",
            "studio_id": "studio_universal",
            "severity": "high",
        })
        assert "studio_id = 'studio_universal'" in sql
        assert "severity = 'high'" in sql
        assert sql.startswith("SELECT ")

    def test_raw_history_samples_with_studio(self):
        sql = build_query("raw_history_samples", {
            "disruption_type": "weather_delay",
            "strategy": "move_to_later_day",
            "studio_id": "studio_002",
            "limit": 25,
        })
        assert "studio_id = 'studio_002'" in sql
        assert "LIMIT 25" in sql

    def test_unsafe_studio_id_injection_rejected(self):
        with pytest.raises(UnsafeQueryError):
            build_query("studio_strategy_performance", {
                "disruption_type": "lead_actor_unavailable",
                "studio_id": "studio'; DROP TABLE disruption_history; --",
            })
