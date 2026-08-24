"""Continuity Council — unit tests (TRD Testing Requirements).

Covers the four required unit areas:
  1. Schedule option generation   (generate_schedule_options)
  2. Option scoring               (score_options — exact TRD weighted formula)
  3. Compliance validation        (validate_compliance)
  4. Continuity risk scoring      (validate_continuity)
Plus the Safe Query Builder allowlist (LLM must never write raw SQL).

Run:  cd /app && python -m pytest tests/test_units.py -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from agents.compliance import validate_compliance  # noqa: E402
from agents.continuity_memory import validate_continuity  # noqa: E402
from agents.schedule_optimizer import generate_schedule_options  # noqa: E402
from server import _impact_preview_scenes  # noqa: E402
from models import DisruptionReport, RecoveryOption, SceneChange, new_case  # noqa: E402
from scoring import score_options  # noqa: E402
from services.safe_query_builder import UnsafeQueryError, build_query  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture: a miniature production bundle mirroring the seeded demo world
# ---------------------------------------------------------------------------
@pytest.fixture()
def bundle():
    scenes = [
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
    ]
    location_availability = [
        {"location_id": loc, "shoot_day": day,
         "available": not (loc == "harbor_exterior" and day == 3), "notes": ""}
        for loc in ("stage_a", "loft_interior", "harbor_exterior")
        for day in (1, 2, 3)
    ]
    cast_availability = [
        {"cast_id": cid, "shoot_day": day, "available": True, "reason": ""}
        for cid in ("lead_001", "supp_001")
        for day in (1, 2, 3)
    ]
    return {
        "production": {"production_id": "prod_001", "title": "Test", "total_shoot_days": 3,
                       "start_date": "2026-01-01", "currency": "USD"},
        "locations": [
            {"location_id": "stage_a", "name": "Stage A", "location_type": "stage", "capacity": 100, "notes": ""},
            {"location_id": "harbor_exterior", "name": "Harbor", "location_type": "exterior", "capacity": 200, "notes": ""},
        ],
        "cast_members": [
            {"cast_id": "lead_001", "name": "Mara Voss", "role_type": "lead"},
            {"cast_id": "supp_001", "name": "Dev Okafor", "role_type": "supporting"},
        ],
        "scenes": scenes,
        "location_availability": location_availability,
        "cast_availability": cast_availability,
    }


@pytest.fixture()
def case():
    return new_case(DisruptionReport(
        production_id="prod_001",
        disruption_type="lead_actor_unavailable",
        affected_day=2,
        affected_cast_id="lead_001",
        severity="high",
        notes="test",
    ))


@pytest.fixture()
def location_case():
    return new_case(DisruptionReport(
        production_id="prod_001",
        disruption_type="location_unavailable",
        affected_day=2,
        affected_location_id="stage_a",
        severity="high",
        notes="location closed",
    ))


# ---------------------------------------------------------------------------
# 1. Schedule option generation
# ---------------------------------------------------------------------------
class TestGenerateScheduleOptions:
    def test_produces_two_to_four_options(self, case, bundle):
        options = generate_schedule_options(case, bundle)
        assert 2 <= len(options) <= 4

    def test_identifies_affected_lead_scenes(self, case, bundle):
        generate_schedule_options(case, bundle)
        assert set(case.affected_scene_ids) == {"sc_005", "sc_006"}

    def test_strategies_map_to_history_taxonomy(self, case, bundle):
        options = generate_schedule_options(case, bundle)
        allowed = {"shoot_cover_scenes", "swap_locations", "move_to_later_day", "wait_for_actor"}
        assert all(o.strategy in allowed for o in options)

    def test_cover_option_moves_affected_scenes_off_disrupted_day(self, case, bundle):
        options = generate_schedule_options(case, bundle)
        cover = next(o for o in options if o.strategy == "shoot_cover_scenes")
        moved = {c.scene_id: c.to_day for c in cover.scene_changes}
        assert moved["sc_005"] == 3 and moved["sc_006"] == 3

    def test_location_options_target_blocked_scenes(self, location_case, bundle):
        options = generate_schedule_options(location_case, bundle)
        assert set(location_case.affected_scene_ids) == {"sc_005", "sc_006"}
        alternate = next(o for o in options if o.option_id == "option_location")
        assert all(c.to_location == "harbor_exterior" for c in alternate.scene_changes)


# ---------------------------------------------------------------------------
# 2. Option scoring (exact TRD weighted formula)
# ---------------------------------------------------------------------------
class TestOptionScoring:
    def _mk(self, oid, cost, delay, cont, comp, valid=True):
        return RecoveryOption(
            option_id=oid, name=oid, strategy="shoot_cover_scenes",
            estimated_cost_usd=cost, estimated_delay_hours=delay,
            continuity_risk_score=cont, compliance_risk_score=comp,
            compliance_valid=valid,
        )

    def test_cheapest_fastest_safest_wins(self):
        a = self._mk("a", 18000, 4.0, 0.1, 0.1)
        b = self._mk("b", 60000, 12.0, 0.2, 0.2)
        ranked = score_options([a, b])
        assert ranked[0].option_id == "a"
        assert ranked[0].recommended is True
        assert ranked[0].rank == 1

    def test_exact_weighted_formula(self):
        a = self._mk("a", 10000, 2.0, 0.2, 0.1)
        b = self._mk("b", 50000, 10.0, 0.4, 0.3)
        ranked = score_options([a, b])
        best = next(o for o in ranked if o.option_id == "a")
        # a: cost_saving=1, delay_saving=1, continuity_safety=0.8, compliance_safety=0.9
        expected = 0.40 * 1 + 0.30 * 1 + 0.20 * 0.8 + 0.10 * 0.9
        assert best.score == pytest.approx(expected, abs=0.001)

    def test_hard_compliance_failure_is_heavily_penalized(self):
        cheap_invalid = self._mk("bad", 5000, 1.0, 0.05, 0.9, valid=False)
        pricey_valid = self._mk("ok", 70000, 14.0, 0.3, 0.2, valid=True)
        ranked = score_options([cheap_invalid, pricey_valid])
        assert ranked[0].option_id == "ok"
        assert next(o for o in ranked if o.option_id == "ok").recommended is True
        assert next(o for o in ranked if o.option_id == "bad").recommended is False


# ---------------------------------------------------------------------------
# 3. Compliance validation
# ---------------------------------------------------------------------------
class TestComplianceValidation:
    def test_valid_move_passes(self, case, bundle):
        option = RecoveryOption(
            option_id="x", name="x", strategy="shoot_cover_scenes",
            scene_changes=[SceneChange(scene_id="sc_005", from_day=2, to_day=3,
                                       from_location="stage_a", to_location="stage_a"),
                           SceneChange(scene_id="sc_006", from_day=2, to_day=3,
                                       from_location="stage_a", to_location="stage_a")],
        )
        valid, warnings, risk = validate_compliance(case, option, bundle)
        assert valid is True
        assert risk < 0.9

    def test_unavailable_location_blocks_option(self, case, bundle):
        option = RecoveryOption(
            option_id="x", name="x", strategy="swap_locations",
            scene_changes=[SceneChange(scene_id="sc_008", from_day=2, to_day=3,
                                       from_location="harbor_exterior", to_location="harbor_exterior")],
        )
        valid, warnings, risk = validate_compliance(case, option, bundle)
        assert valid is False
        assert any("not available on Day 3" in w for w in warnings)
        assert risk == pytest.approx(0.9)

    def test_live_disruption_blocks_lead_on_affected_day(self, case, bundle):
        # Moving a lead scene INTO the disrupted day must fail
        option = RecoveryOption(
            option_id="x", name="x", strategy="swap_locations",
            scene_changes=[SceneChange(scene_id="sc_010", from_day=3, to_day=2,
                                       from_location="stage_a", to_location="stage_a")],
        )
        valid, warnings, risk = validate_compliance(case, option, bundle)
        assert valid is False
        assert any("unavailable on Day 2" in w for w in warnings)

    def test_day_bounds_enforced(self, case, bundle):
        option = RecoveryOption(
            option_id="x", name="x", strategy="move_to_later_day",
            scene_changes=[SceneChange(scene_id="sc_005", from_day=2, to_day=4,
                                       from_location="stage_a", to_location="stage_a")],
        )
        valid, warnings, _ = validate_compliance(case, option, bundle)
        assert valid is False

    def test_live_location_disruption_blocks_same_location_and_day(self, location_case, bundle):
        option = RecoveryOption(
            option_id="x", name="x", strategy="move_to_later_day",
            scene_changes=[],
        )
        valid, warnings, risk = validate_compliance(location_case, option, bundle)
        assert valid is False
        assert any("Stage A" in w and "Day 2" in w for w in warnings)
        assert risk == pytest.approx(0.9)

    def test_location_preview_returns_only_blocked_scenes(self, location_case, bundle):
        preview = _impact_preview_scenes(
            bundle, location_case.disruption.disruption_type,
            location_case.disruption.affected_day,
            affected_location_id=location_case.disruption.affected_location_id,
        )
        assert [s["scene_id"] for s in preview] == ["sc_005", "sc_006"]

    def test_blocked_location_option_ranks_below_valid_option(self, location_case, bundle):
        invalid = RecoveryOption(
            option_id="blocked", name="blocked", strategy="move_to_later_day",
            estimated_cost_usd=1, estimated_delay_hours=1,
            scene_changes=[],
        )
        valid = RecoveryOption(
            option_id="valid", name="valid", strategy="swap_locations",
            estimated_cost_usd=90000, estimated_delay_hours=20,
            scene_changes=[
                SceneChange(
                    scene_id="sc_005", from_day=2, to_day=2,
                    from_location="stage_a", to_location="harbor_exterior",
                ),
                SceneChange(
                    scene_id="sc_006", from_day=2, to_day=2,
                    from_location="stage_a", to_location="harbor_exterior",
                ),
            ],
        )
        for option in (invalid, valid):
            option.compliance_valid, option.compliance_warnings, option.compliance_risk_score = (
                validate_compliance(location_case, option, bundle)
            )
        ranked = score_options([invalid, valid])
        assert ranked[0].option_id == "valid"


# ---------------------------------------------------------------------------
# 4. Continuity risk scoring
# ---------------------------------------------------------------------------
class TestContinuityRiskScoring:
    def test_dependency_order_violation_raises_risk(self, bundle):
        # sc_010 depends on sc_006; moving sc_010 before sc_006 breaks order
        option = RecoveryOption(
            option_id="x", name="x", strategy="swap_locations",
            scene_changes=[SceneChange(scene_id="sc_010", from_day=3, to_day=1,
                                       from_location="stage_a", to_location="stage_a")],
        )
        validate_continuity(option, bundle["scenes"])
        assert option.continuity_risk_score >= 0.3
        assert any("before" in r.risk for r in option.continuity_risks)

    def test_no_changes_is_low_risk(self, bundle):
        option = RecoveryOption(option_id="x", name="x", strategy="wait_for_actor", scene_changes=[])
        validate_continuity(option, bundle["scenes"])
        assert option.continuity_risk_score <= 0.1

    def test_splitting_shared_costume_tags_flags_risk(self, bundle):
        # sc_005 and sc_006 share 'costume_interrogation'; separating them flags a risk
        option = RecoveryOption(
            option_id="x", name="x", strategy="move_to_later_day",
            scene_changes=[SceneChange(scene_id="sc_006", from_day=2, to_day=3,
                                       from_location="stage_a", to_location="stage_a")],
        )
        validate_continuity(option, bundle["scenes"])
        assert option.continuity_risk_score > 0.1
        assert len(option.continuity_risks) >= 1


# ---------------------------------------------------------------------------
# Safe Query Builder (LLM never writes raw SQL)
# ---------------------------------------------------------------------------
class TestSafeQueryBuilder:
    def test_valid_template_builds_select_only(self):
        sql = build_query("strategy_performance", {"disruption_type": "lead_actor_unavailable"})
        assert sql.lower().startswith("select")
        assert "strategy_performance_mv" in sql
        assert "avgMerge(avg_cost)" in sql
        assert "avgMerge(avg_delay)" in sql
        assert "countMerge(sample_size)" in sql
        assert ";" not in sql

    def test_unlisted_disruption_type_rejected(self):
        with pytest.raises(UnsafeQueryError):
            build_query("strategy_performance", {"disruption_type": "1; DROP TABLE x --"})

    def test_unknown_template_rejected(self):
        with pytest.raises(UnsafeQueryError):
            build_query("free_form_sql", {"disruption_type": "lead_actor_unavailable"})

    def test_invalid_severity_rejected(self):
        with pytest.raises(UnsafeQueryError):
            build_query("strategy_performance_by_severity",
                        {"disruption_type": "weather_delay", "severity": "catastrophic"})

    def test_days_clamped_to_safe_range(self):
        sql = build_query("recent_strategy_performance",
                          {"disruption_type": "weather_delay", "days": 999999})
        assert "INTERVAL 1095 DAY" in sql

    # --- raw_history_samples (evidence drilldown) ---------------------------
    def test_raw_samples_builds_select_only(self):
        sql = build_query("raw_history_samples", {
            "disruption_type": "lead_actor_unavailable",
            "strategy": "shoot_cover_scenes",
            "severity": "high",
            "limit": 25,
        })
        assert sql.lower().startswith("select")
        assert "resolution_strategy = 'shoot_cover_scenes'" in sql
        assert "severity = 'high'" in sql
        assert "LIMIT 25" in sql
        assert ";" not in sql

    def test_raw_samples_rejects_unlisted_strategy(self):
        with pytest.raises(UnsafeQueryError):
            build_query("raw_history_samples", {
                "disruption_type": "lead_actor_unavailable",
                "strategy": "1; DROP TABLE disruption_history --",
            })

    def test_raw_samples_limit_clamped_and_severity_optional(self):
        sql = build_query("raw_history_samples", {
            "disruption_type": "weather_delay",
            "strategy": "swap_locations",
            "limit": 99999,
        })
        assert "LIMIT 100" in sql
        assert "severity =" not in sql


# ---------------------------------------------------------------------------
# Geographic Haversine & Distance Compliance Tests
# ---------------------------------------------------------------------------
class TestDistanceCompliance:
    def test_haversine_formula(self):
        from services.geo_service import haversine_miles
        # LA to San Francisco (~347 miles)
        dist = haversine_miles(34.0522, -118.2437, 37.7749, -122.4194)
        assert 340 <= dist <= 360
        # Same point = 0
        assert haversine_miles(34.05, -118.25, 34.05, -118.25) == 0.0

    def test_transit_over_100_miles_hard_fails_compliance(self, bundle, case):
        # Add coordinates to locations: Stage A in Abu Dhabi, Jordan canyon 1,200 miles away
        bundle["locations"] = [
            {"location_id": "loc_abu_dhabi", "name": "Abu Dhabi Stage", "location_type": "stage",
             "latitude": 24.4539, "longitude": 54.3773, "daily_fee_usd": 15000, "currency_code": "AED"},
            {"location_id": "loc_jordan_canyon", "name": "Jordan Canyon", "location_type": "exterior",
             "latitude": 29.5760, "longitude": 35.4190, "daily_fee_usd": 18000, "currency_code": "JOD"},
        ]
        # Proposed move on the same day from Abu Dhabi to Jordan (>1,000 miles)
        option = RecoveryOption(
            option_id="opt_move_far",
            name="Emergency Move to Jordan",
            strategy="swap_locations",
            scene_changes=[
                SceneChange(scene_id="sc_005", from_day=2, to_day=2,
                            from_location="loc_abu_dhabi", to_location="loc_jordan_canyon"),
            ],
        )
        valid, warnings, risk = validate_compliance(case, option, bundle)
        assert valid is False
        assert option.transit_distance_miles > 100.0
        assert any("exceeds 100-mile" in w for w in warnings)


# ---------------------------------------------------------------------------
# Rate Card & 70/30 Economic Calibration Tests
# ---------------------------------------------------------------------------
class TestRateCardsAndEconomics:
    @pytest.mark.skip(reason="Requires live ClickHouse connection")
    def test_bottom_up_calibration_formula(self, bundle, case):
        import asyncio
        from agents import budget_sentinel
        from models import EvidenceRow

        case.evidence_rows = [
            EvidenceRow(resolution_strategy="shoot_cover_scenes", avg_cost_overrun_usd=20000.0, avg_delay_hours=3.0, past_cases=100)
        ]
        option = RecoveryOption(
            option_id="opt_cover",
            name="Shoot cover scenes",
            strategy="shoot_cover_scenes",
            scene_changes=[],
        )

        asyncio.run(budget_sentinel.calibrate_option_economics(case, [option], bundle))
        assert option.estimated_cost_usd > 0
        assert option.cost_breakdown is not None
        assert len(option.cost_breakdown.breakdown) >= 2
        # Check calibration metadata
        assert "70% bottom-up" in option.cost_breakdown.calibration_method


# ---------------------------------------------------------------------------
# External Signal Services (Mocked for CI)
# ---------------------------------------------------------------------------
class TestExternalSignals:
    def test_weather_fallback_deterministic(self):
        from services.weather_service import _biome_fallback
        res = _biome_fallback(34.05, -118.25)
        assert 0 <= res["risk_score"] <= 100
        assert "Open-Meteo" in res["source"]

    def test_finance_service_conversion(self):
        import asyncio
        from services.finance_service import convert_currency
        # 1000 EUR to USD at benchmark rate (~1085 USD)
        usd, rate = asyncio.run(convert_currency(1000, "EUR", "USD"))
        assert usd > 1000
        assert rate > 1.0

        # USD to USD = parity
        usd2, rate2 = asyncio.run(convert_currency(500, "USD", "USD"))
        assert usd2 == 500
        assert rate2 == 1.0


# ---------------------------------------------------------------------------
# Global Geo-Aware Costing (World Bank + OSM Population + ISO 4217 Currency)
# ---------------------------------------------------------------------------
class TestGlobalGeoCosting:
    def test_city_tier_thresholds(self):
        from services.geo_service import determine_city_tier

        # Mumbai: 12.5M population >= 5M -> tier_1 (1.0x)
        tier_mumbai, mult_mumbai = determine_city_tier(12_500_000, is_capital=False, city_name="Mumbai")
        assert tier_mumbai == "tier_1"
        assert mult_mumbai == 1.0

        # London: 8.9M population >= 5M (also capital) -> tier_1 (1.0x)
        tier_london, mult_london = determine_city_tier(8_900_000, is_capital=True, city_name="London")
        assert tier_london == "tier_1"
        assert mult_london == 1.0

        # Dharwad: 500k-600k population (200k-1M) -> tier_2 (0.5x)
        tier_dharwad, mult_dharwad = determine_city_tier(550_000, is_capital=False, city_name="Dharwad")
        assert tier_dharwad == "tier_2"
        assert mult_dharwad == 0.5

        # Hubballi: 900k population (200k-1M) -> tier_2 (0.5x)
        tier_hubballi, mult_hubballi = determine_city_tier(900_000, is_capital=False, city_name="Hubballi")
        assert tier_hubballi == "tier_2"
        assert mult_hubballi == 0.5

        # 50k-pop town: 50,000 population (<200k) -> tier_3 (0.35x)
        tier_50k, mult_50k = determine_city_tier(50_000, is_capital=False, city_name="Smallville")
        assert tier_50k == "tier_3"
        assert mult_50k == 0.35

    def test_city_tier_fallback_when_population_missing(self):
        from services.geo_service import determine_city_tier

        # Capital city with missing pop -> tier_1
        tier_cap, mult_cap = determine_city_tier(None, is_capital=True, city_name="Brasilia")
        assert tier_cap == "tier_1"
        assert mult_cap == 1.0

        # Top megacity with missing pop -> tier_1
        tier_mega, mult_mega = determine_city_tier(None, is_capital=False, city_name="Tokyo")
        assert tier_mega == "tier_1"
        assert mult_mega == 1.0

        # Regular regional town with missing pop -> tier_2
        tier_reg, mult_reg = determine_city_tier(None, is_capital=False, city_name="RandomTown")
        assert tier_reg == "tier_2"
        assert mult_reg == 0.5

    def test_clamp_math_country_factor(self):
        from services.geo_service import clamp_country_mult

        # US benchmark: 80,000 / 80,000 = 1.0 ** 0.6 = 1.00
        assert clamp_country_mult(80000.0, 80000.0) == 1.0

        # Very low GDP PPP: 2,000 -> (2000/80000)**0.6 = 0.108 -> clamped to minimum 0.25
        assert clamp_country_mult(2000.0, 80000.0) == 0.25

        # Very high GDP PPP: 140,000 -> (140000/80000)**0.6 = 1.399 -> clamped to maximum 1.10
        assert clamp_country_mult(140000.0, 80000.0) == 1.10

        # India benchmark (~10,120) -> (10120/80000)**0.6 = ~0.29
        assert clamp_country_mult(10120.0, 80000.0) == pytest.approx(0.29, abs=0.02)

        # UK benchmark (~58,200) -> (58200/80000)**0.6 = ~0.83
        assert clamp_country_mult(58200.0, 80000.0) == pytest.approx(0.83, abs=0.02)

    def test_world_bank_fallback_table(self):
        import asyncio
        from services.geo_service import get_country_factor

        # Test India factor
        factor_in = asyncio.run(get_country_factor("IN"))
        assert factor_in["country_code"] == "IN"
        assert 0.25 <= factor_in["country_mult"] <= 0.35

        # Test UK factor
        factor_gb = asyncio.run(get_country_factor("GB"))
        assert factor_gb["country_code"] == "GB"
        assert 0.75 <= factor_gb["country_mult"] <= 0.95

        # Test Brazil factor
        factor_br = asyncio.run(get_country_factor("BR"))
        assert factor_br["country_code"] == "BR"
        assert 0.35 <= factor_br["country_mult"] <= 0.55

        # Test Nigeria factor (clamped minimum 0.25)
        factor_ng = asyncio.run(get_country_factor("NG"))
        assert factor_ng["country_code"] == "NG"
        assert 0.25 <= factor_ng["country_mult"] <= 0.35



    def test_unknown_country_fallback(self):
        import asyncio
        from services.geo_service import get_country_factor

        # Unknown 2-letter country code -> 1.0 with warning badge
        factor_unknown = asyncio.run(get_country_factor("ZZ"))
        assert factor_unknown["country_mult"] == 1.0
        assert factor_unknown["is_fallback"] is True
        assert "Unknown country" in factor_unknown["warning"]

    def test_iso_4217_currency_mapping(self):
        from services.geo_service import country_to_currency

        assert country_to_currency("IN") == "INR"
        assert country_to_currency("IND") == "INR"
        assert country_to_currency("GB") == "GBP"
        assert country_to_currency("GBR") == "GBP"
        assert country_to_currency("BR") == "BRL"
        assert country_to_currency("NG") == "NGN"
        assert country_to_currency("US") == "USD"
        assert country_to_currency("FR") == "EUR"
        assert country_to_currency("DE") == "EUR"
        assert country_to_currency("AE") == "AED"
        assert country_to_currency("JO") == "JOD"
        assert country_to_currency("JP") == "JPY"
        # Unknown fallback
        assert country_to_currency("ZZ") == "USD"

    def test_dharwad_geo_economics_resolution(self):
        import asyncio
        from services.geo_service import resolve_geo_economics

        # Dharwad test
        res = asyncio.run(resolve_geo_economics("Dharwad, Karnataka, India"))
        assert res["country_code"] == "IN"
        assert res["currency_code"] == "INR"
        assert res["city_tier"] == "tier_2"
        assert res["tier_mult"] == 0.5
        # Compound geo multiplier: ~0.29 * 0.5 = ~0.15
        assert 0.13 <= res["geo_mult"] <= 0.17
        assert "World Bank" in res["source_note"]

    @pytest.mark.skip(reason="Requires live ClickHouse connection")
    def test_budget_sentinel_with_geo_multiplier(self, bundle, case):
        import asyncio
        from agents import budget_sentinel
        from models import EvidenceRow, RecoveryOption, SceneChange

        # Configure location in Dharwad (IN, tier_2, geo_mult=0.15, INR)
        bundle["locations"] = [
            {
                "location_id": "loc_dharwad",
                "name": "Dharwad Heritage Stage",
                "location_type": "stage",
                "latitude": 15.4589,
                "longitude": 75.0078,
                "daily_fee_usd": 5000,
                "currency_code": "INR",
                "country_code": "IN",
                "city_tier": "tier_2",
                "country_mult": 0.29,
                "geo_mult": 0.15,
            }
        ]

        case.evidence_rows = [
            EvidenceRow(resolution_strategy="swap_locations", avg_cost_overrun_usd=10000.0, avg_delay_hours=4.0, past_cases=100)
        ]

        option = RecoveryOption(
            option_id="opt_dharwad",
            name="Relocate to Dharwad Stage",
            strategy="swap_locations",
            scene_changes=[
                SceneChange(scene_id="sc_005", from_day=2, to_day=2, to_location="loc_dharwad")
            ],
        )

        asyncio.run(budget_sentinel.calibrate_option_economics(case, [option], bundle))
        assert option.cost_breakdown is not None
        # Check transparent Geo Adjustment line item
        geo_lines = [l for l in option.cost_breakdown.breakdown if "Geo adjustment" in l.line]
        assert len(geo_lines) >= 1
        assert "IN" in geo_lines[0].line
        assert "tier-2" in geo_lines[0].line
        assert "World Bank" in geo_lines[0].source


# ---------------------------------------------------------------------------
# 7. Production Validation & Shoot Day Bounds
# ---------------------------------------------------------------------------
class TestProductionValidationAndDayBounds:
    def test_affected_day_over_30_accepted_in_model(self):
        report_45 = DisruptionReport(
            production_id="prod_001",
            disruption_type="weather_delay",
            affected_day=45,
            severity="high",
        )
        assert report_45.affected_day == 45

        report_90 = DisruptionReport(
            production_id="prod_001",
            disruption_type="equipment_failure",
            affected_day=90,
            severity="medium",
        )
        assert report_90.affected_day == 90

    def test_affected_day_invalid_values_rejected_in_model(self):
        from pydantic import ValidationError

        # Negative
        with pytest.raises(ValidationError):
            DisruptionReport(
                production_id="prod_001",
                disruption_type="weather_delay",
                affected_day=-5,
            )

        # Zero
        with pytest.raises(ValidationError):
            DisruptionReport(
                production_id="prod_001",
                disruption_type="weather_delay",
                affected_day=0,
            )

        # Absurdly large (> 3650)
        with pytest.raises(ValidationError):
            DisruptionReport(
                production_id="prod_001",
                disruption_type="weather_delay",
                affected_day=5000,
            )

    def test_impact_preview_endpoint_accepts_day_over_30(self, monkeypatch, bundle):
        from fastapi.testclient import TestClient
        from server import app
        import services.clickhouse_client as ch

        monkeypatch.setattr(ch, "is_configured", lambda: True)

        async def mock_fetch(pid):
            b = dict(bundle)
            b["scenes"] = b["scenes"] + [
                {"scene_id": "sc_045", "scene_title": "Day 45 Scene", "shoot_day": 45,
                 "sequence_order": 45, "location_id": "stage_a", "required_cast": ["supp_001"],
                 "scene_type": "interior", "is_cover_scene": False, "priority": 1,
                 "continuity_tags": [], "depends_on": [], "status": "scheduled"}
            ]
            return b

        monkeypatch.setattr(ch, "fetch_production_bundle", mock_fetch)

        client = TestClient(app)
        res = client.get(
            "/api/disruptions/impact-preview",
            params={
                "production_id": "prod_001",
                "disruption_type": "weather_delay",
                "affected_day": 45,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["affected_day"] == 45
        assert len(data["scenes"]) == 1
        assert data["scenes"][0]["scene_id"] == "sc_045"

    def test_impact_preview_endpoint_rejects_invalid_day(self, monkeypatch):
        from fastapi.testclient import TestClient
        from server import app
        import services.clickhouse_client as ch

        monkeypatch.setattr(ch, "is_configured", lambda: True)
        client = TestClient(app)

        # Day 0
        res = client.get(
            "/api/disruptions/impact-preview",
            params={
                "production_id": "prod_001",
                "disruption_type": "weather_delay",
                "affected_day": 0,
            },
        )
        assert res.status_code == 422

        # Negative day
        res_neg = client.get(
            "/api/disruptions/impact-preview",
            params={
                "production_id": "prod_001",
                "disruption_type": "weather_delay",
                "affected_day": -10,
            },
        )
        assert res_neg.status_code == 422

        # Absurdly large (> 3650)
        res_huge = client.get(
            "/api/disruptions/impact-preview",
            params={
                "production_id": "prod_001",
                "disruption_type": "weather_delay",
                "affected_day": 99999,
            },
        )
        assert res_huge.status_code == 422

        # Non-numeric
        res_str = client.get(
            "/api/disruptions/impact-preview",
            params={
                "production_id": "prod_001",
                "disruption_type": "weather_delay",
                "affected_day": "forty-two",
            },
        )
        assert res_str.status_code == 422

    def test_malformed_production_id_returns_422(self, monkeypatch):
        from fastapi.testclient import TestClient
        from server import app
        import services.clickhouse_client as ch

        monkeypatch.setattr(ch, "is_configured", lambda: True)
        client = TestClient(app)

        # Illegal characters in path parameter
        res = client.get("/api/productions/bad@id!#")
        assert res.status_code == 422

        # Too short (< 3 chars)
        res_short = client.get("/api/productions/ab")
        assert res_short.status_code == 422

        # Malformed in audit endpoint
        res_audit = client.get("/api/audit/invalid$$$")
        assert res_audit.status_code == 422

        # Malformed in studio cohort endpoint
        res_cohort = client.get("/api/productions/spaces in id/studio-cohort")
        assert res_cohort.status_code == 422

    def test_nonexistent_production_id_returns_404(self, monkeypatch):
        from fastapi.testclient import TestClient
        from server import app
        import services.clickhouse_client as ch

        monkeypatch.setattr(ch, "is_configured", lambda: True)

        async def mock_fetch_none(pid):
            return None

        async def mock_exists_false(pid):
            return False

        monkeypatch.setattr(ch, "fetch_production_bundle", mock_fetch_none)
        monkeypatch.setattr(ch, "production_exists", mock_exists_false)

        client = TestClient(app)

        # GET /productions/{id}
        res_get = client.get("/api/productions/prod_nonexistent")
        assert res_get.status_code == 404

        # GET /productions/{id}/studio-cohort
        res_cohort = client.get("/api/productions/prod_nonexistent/studio-cohort")
        assert res_cohort.status_code == 404

        # GET /audit/{id}
        res_audit = client.get("/api/audit/prod_nonexistent")
        assert res_audit.status_code == 404

        # GET /disruptions/impact-preview
        res_preview = client.get(
            "/api/disruptions/impact-preview",
            params={
                "production_id": "prod_nonexistent",
                "disruption_type": "weather_delay",
                "affected_day": 2,
            },
        )
        assert res_preview.status_code == 404

        # POST /disruptions with nonexistent production
        res_report = client.post(
            "/api/disruptions",
            json={
                "production_id": "prod_nonexistent",
                "disruption_type": "weather_delay",
                "affected_day": 2,
                "severity": "high",
            },
        )
        assert res_report.status_code == 404


# ---------------------------------------------------------------------------
# 8. Gemini Client Quota, Cooldown & JSON Parsing Resilience
# ---------------------------------------------------------------------------
class TestGeminiClientQuotaAndResilience:
    @pytest.fixture(autouse=True)
    def reset_gemini_state(self, monkeypatch):
        import services.gemini_client as gc
        monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
        gc._quota_reset_at = None
        yield
        gc._quota_reset_at = None

    def test_quota_error_sets_cooldown_and_resumes_after_expiry(self, monkeypatch):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        import services.gemini_client as gc

        mock_client = MagicMock()
        mock_models = MagicMock()
        mock_content = AsyncMock(side_effect=Exception("429 Resource exhausted: quota exceeded"))
        mock_models.generate_content = mock_content
        mock_client.aio.models = mock_models
        monkeypatch.setattr(gc, "_get_client", lambda: mock_client)

        current_time = 1000.0
        monkeypatch.setattr("time.time", lambda: current_time)

        # First call triggers 429
        res = asyncio.run(gc.generate_text("Hello"))
        assert res is None
        assert gc.quota_hit() is True
        assert mock_content.call_count == 1

        # Second call within cooldown is skipped without calling generate_content
        res2 = asyncio.run(gc.generate_text("Hello again"))
        assert res2 is None
        assert mock_content.call_count == 1

        # Advance time past default 60s cooldown (61s)
        current_time = 1061.0
        assert gc.quota_hit() is False

        # Next call succeeds
        resp_obj = MagicMock()
        resp_obj.text = "Recovered answer"
        mock_content.side_effect = None
        mock_content.return_value = resp_obj

        res3 = asyncio.run(gc.generate_text("Hello third time"))
        assert res3 == "Recovered answer"
        assert mock_content.call_count == 2
        assert gc.quota_hit() is False

    def test_retry_after_extraction_and_custom_cooldown(self, monkeypatch):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        import services.gemini_client as gc

        mock_client = MagicMock()
        mock_models = MagicMock()
        mock_models.generate_content = AsyncMock(
            side_effect=Exception("429 Quota limit reached; retry in 20.0s")
        )
        mock_client.aio.models = mock_models
        monkeypatch.setattr(gc, "_get_client", lambda: mock_client)

        current_time = 1000.0
        monkeypatch.setattr("time.time", lambda: current_time)

        asyncio.run(gc.generate_text("Test prompt"))
        assert gc.quota_hit() is True

        # At +10s, still in cooldown
        current_time = 1010.0
        assert gc.quota_hit() is True

        # At +21s, cooldown has expired
        current_time = 1021.0
        assert gc.quota_hit() is False

    def test_json_decode_error_does_not_set_quota_cooldown(self, monkeypatch):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        import services.gemini_client as gc

        mock_client = MagicMock()
        mock_models = MagicMock()
        resp_invalid = MagicMock()
        resp_invalid.text = "This is not valid json at all!"
        mock_models.generate_content = AsyncMock(return_value=resp_invalid)
        mock_client.aio.models = mock_models
        monkeypatch.setattr(gc, "_get_client", lambda: mock_client)

        current_time = 1000.0
        monkeypatch.setattr("time.time", lambda: current_time)

        # Call generate_json with invalid response
        res = asyncio.run(gc.generate_json("Generate some json"))
        assert res is None

        # Verify quota_hit is NOT set by JSON parsing failure
        assert gc.quota_hit() is False
        assert gc._quota_reset_at is None

        # Subsequent call with valid JSON works immediately
        resp_valid = MagicMock()
        resp_valid.text = '{"status": "success", "count": 42}'
        mock_models.generate_content = AsyncMock(return_value=resp_valid)

        res2 = asyncio.run(gc.generate_json("Generate json again"))
        assert res2 == {"status": "success", "count": 42}
        assert gc.quota_hit() is False

    def test_non_quota_error_does_not_set_quota_cooldown(self, monkeypatch):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        import services.gemini_client as gc

        mock_client = MagicMock()
        mock_models = MagicMock()
        mock_models.generate_content = AsyncMock(side_effect=TimeoutError("Request timed out"))
        mock_client.aio.models = mock_models
        monkeypatch.setattr(gc, "_get_client", lambda: mock_client)

        res = asyncio.run(gc.generate_text("Test prompt"))
        assert res is None
        assert gc.quota_hit() is False
        assert gc._quota_reset_at is None


# ---------------------------------------------------------------------------
# 9. Batched Productions Query & Dashboard Optimization
# ---------------------------------------------------------------------------
class TestBatchedProductionsQuery:
    def test_list_productions_single_query_execution_and_shape(self, monkeypatch):
        import asyncio
        from unittest.mock import MagicMock
        from datetime import datetime, timezone
        import services.clickhouse_client as ch

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.result_rows = [
            (
                "prod_001",
                "The Long Dark Take",
                "2026-08-19",
                3,
                "USD",
                "Christopher Nolan",
                datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc),
                10,
                4,
                2,
            ),
            (
                "prod_002",
                "Iron Horizon",
                "2026-09-01",
                45,
                "EUR",
                "Denis Villeneuve",
                datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc),
                55,
                12,
                8,
            ),
        ]
        mock_client.query = MagicMock(return_value=mock_result)
        monkeypatch.setattr(ch, "_get_client", lambda: mock_client)

        prods = asyncio.run(ch.list_productions())

        # Exact single round trip executed
        assert mock_client.query.call_count == 1
        query_sql = mock_client.query.call_args[0][0]
        assert "LEFT JOIN" in query_sql
        assert "production_schedule" in query_sql
        assert "cast_members" in query_sql
        assert "locations" in query_sql

        # Validate shape and data accuracy
        assert len(prods) == 2
        p1 = prods[0]
        assert p1["production_id"] == "prod_001"
        assert p1["title"] == "The Long Dark Take"
        assert p1["total_shoot_days"] == 3
        assert p1["currency"] == "USD"
        assert p1["director"] == "Christopher Nolan"
        assert p1["is_demo"] is True
        assert p1["scene_count"] == 10
        assert p1["cast_count"] == 4
        assert p1["location_count"] == 2

        p2 = prods[1]
        assert p2["production_id"] == "prod_002"
        assert p2["title"] == "Iron Horizon"
        assert p2["total_shoot_days"] == 45
        assert p2["is_demo"] is False
        assert p2["scene_count"] == 55
        assert p2["cast_count"] == 12
        assert p2["location_count"] == 8


# ---------------------------------------------------------------------------
# 10. PR #4 Audit — Failing tests (bugs found, not yet fixed)
# ---------------------------------------------------------------------------
class TestPR4AuditBugs:
    """Failing tests that demonstrate real bugs found in the PR #4 audit.

    Each test is written to FAIL against the current unpatched code.
    After the corresponding fix is applied, the test will pass.
    """

    # --- Bug 1: Last shoot day disruption generates no-op scene changes ----
    def test_last_shoot_day_disruption_does_not_produce_noop_move(self):
        """When affected_day == total_shoot_days, _later_day() returns
        total_shoot_days (same value). Every option that calls to_day produces
        SceneChange(from_day=N, to_day=N) — a move that changes nothing.
        Compliance passes it silently, so the option looks valid but is a no-op.

        Bug location: backend/agents/schedule_optimizer.py line 30.
        """
        from agents.schedule_optimizer import generate_schedule_options
        from models import DisruptionReport, new_case

        total_days = 3
        disruption_day = total_days  # last day — triggers the bug

        last_day_bundle = {
            "production": {
                "production_id": "prod_test",
                "title": "Last Day Test",
                "total_shoot_days": total_days,
                "start_date": "2026-01-01",
                "currency": "USD",
            },
            "locations": [
                {"location_id": "stage_a", "name": "Stage A",
                 "location_type": "stage", "capacity": 100, "notes": ""},
            ],
            "cast_members": [
                {"cast_id": "lead_001", "name": "Mara Voss", "role_type": "lead"},
            ],
            "scenes": [
                {"scene_id": "sc_01", "scene_title": "Climax",
                 "shoot_day": disruption_day, "sequence_order": 1,
                 "location_id": "stage_a", "required_cast": ["lead_001"],
                 "scene_type": "interior", "is_cover_scene": False,
                 "priority": 1, "continuity_tags": [], "depends_on": [],
                 "status": "scheduled"},
                {"scene_id": "sc_02", "scene_title": "Cover",
                 "shoot_day": 1, "sequence_order": 2,
                 "location_id": "stage_a", "required_cast": [],
                 "scene_type": "cover", "is_cover_scene": True,
                 "priority": 4, "continuity_tags": [], "depends_on": [],
                 "status": "scheduled"},
            ],
            "location_availability": [
                {"location_id": "stage_a", "shoot_day": d,
                 "available": True, "notes": ""}
                for d in range(1, total_days + 1)
            ],
            "cast_availability": [
                {"cast_id": "lead_001", "shoot_day": d,
                 "available": True, "reason": ""}
                for d in range(1, total_days + 1)
            ],
        }

        case = new_case(DisruptionReport(
            production_id="prod_test",
            disruption_type="lead_actor_unavailable",
            affected_day=disruption_day,
            affected_cast_id="lead_001",
            severity="high",
        ))
        options = generate_schedule_options(case, last_day_bundle)

        # BUG: options contain SceneChange objects where from_day == to_day
        noop_changes = [
            ch
            for opt in options
            for ch in opt.scene_changes
            if ch.from_day == ch.to_day
        ]
        # This assertion FAILS before fix:
        assert len(noop_changes) == 0, (
            f"Bug: {len(noop_changes)} no-op scene change(s) with from_day == to_day "
            f"(disruption on last shoot day {disruption_day}/{total_days}). "
            "Schedule Optimizer must not generate changes that don't move a scene."
        )

    # --- Bug 2: Compliance transit check bypassed for lon=0.0 / lat=0.0 ---
    def test_transit_distance_checked_when_longitude_is_zero(self):
        """In compliance.py line 73: `if lat1 and lon1 and lat2 and lon2:`
        evaluates 0.0 as falsy. For locations on the Prime Meridian
        (e.g., Greenwich UK at lon=0.0) or Equator (lat=0.0), transit calculation
        is bypassed, and transit >100mi violations are silently ignored.

        Bug location: backend/agents/compliance.py line 73.
        """
        from agents.compliance import validate_compliance
        from models import DisruptionReport, RecoveryOption, SceneChange, new_case

        # Location 1: Greenwich, London (lat 51.48, lon 0.0)
        # Location 2: Manchester UK (lat 53.48, lon -2.24) -> ~160 miles away
        transit_bundle = {
            "production": {
                "production_id": "prod_uk",
                "title": "UK Shoot",
                "total_shoot_days": 3,
                "start_date": "2026-01-01",
                "currency": "GBP",
            },
            "locations": [
                {"location_id": "loc_greenwich", "name": "Greenwich Stage",
                 "location_type": "interior", "capacity": 100,
                 "latitude": 51.48, "longitude": 0.0, "notes": ""},
                {"location_id": "loc_manchester", "name": "Manchester Docks",
                 "location_type": "exterior", "capacity": 100,
                 "latitude": 53.48, "longitude": -2.24, "notes": ""},
            ],
            "cast_members": [
                {"cast_id": "lead_001", "name": "Dev", "role_type": "lead"},
            ],
            "scenes": [
                {"scene_id": "sc_10", "scene_title": "Docks Scene",
                 "shoot_day": 1, "sequence_order": 1,
                 "location_id": "loc_greenwich", "required_cast": ["lead_001"],
                 "scene_type": "interior", "is_cover_scene": False,
                 "priority": 1, "continuity_tags": [], "depends_on": [],
                 "status": "scheduled"},
            ],
            "location_availability": [
                {"location_id": loc, "shoot_day": d, "available": True, "notes": ""}
                for loc in ("loc_greenwich", "loc_manchester")
                for d in (1, 2, 3)
            ],
            "cast_availability": [
                {"cast_id": "lead_001", "shoot_day": d, "available": True, "reason": ""}
                for d in (1, 2, 3)
            ],
        }

        case = new_case(DisruptionReport(
            production_id="prod_uk",
            disruption_type="location_unavailable",
            affected_day=1,
            affected_location_id="loc_greenwich",
            severity="high",
        ))

        # Propose same-day move from Greenwich (lon=0.0) to Manchester (~160 mi away)
        option = RecoveryOption(
            option_id="opt_move_manchester",
            name="Move to Manchester",
            strategy="swap_locations",
            scene_changes=[
                SceneChange(
                    scene_id="sc_10",
                    from_day=1,
                    to_day=1,
                    from_location="loc_greenwich",
                    to_location="loc_manchester",
                    change_type="move_scene_location",
                )
            ],
        )

        valid, warnings, risk_score = validate_compliance(case, option, transit_bundle)

        # BUG: valid is True because lon1=0.0 evaluated as False, skipping the 100mi transit check.
        # This assertion FAILS before fix:
        assert valid is False, (
            "Bug: validate_compliance passed a 160-mile same-day location swap because "
            "Greenwich longitude (0.0) was treated as falsy in `if lat1 and lon1 and lat2 and lon2:`. "
            "It must fail compliance with a transit distance warning."
        )

    # --- Bug 3: CSV import parse_date rejects ISO timestamps with milliseconds ---
    def test_import_csv_accepts_iso_timestamps_with_milliseconds(self):
        """Standard ISO timestamps exported from modern JS tools (e.g. toISOString())
        have format 'YYYY-MM-DDTHH:mm:ss.sssZ'. parse_date() fails on these, causing
        valid CSV rows to be rejected.

        Bug location: backend/services/import_service.py lines 74-92.
        """
        from services.import_service import parse_date

        iso_with_ms = "2026-08-24T14:30:00.000Z"
        parsed = parse_date(iso_with_ms)

        # BUG: parse_date returns None because '%Y-%m-%dT%H:%M:%S.%fZ' is not in formats
        assert parsed is not None, (
            f"Bug: parse_date failed to parse standard ISO 8601 timestamp with milliseconds: '{iso_with_ms}'"
        )

    # --- Bug 4: Safe query builder crashes on empty studio_id in studio_strategy_performance ---
    def test_studio_strategy_performance_handles_empty_studio_id(self):
        """When params contains {'studio_id': ''} (e.g., from unassigned production),
        params.get('studio_id', 'global') evaluates to '' (in dict).
        _clean_identifier('') then raises UnsafeQueryError instead of defaulting to 'global'.

        Bug location: backend/services/safe_query_builder.py line 157.
        """
        from services.safe_query_builder import build_query

        # Should safely default to 'global' or generate valid query without raising UnsafeQueryError
        query = build_query(
            "studio_strategy_performance",
            {"disruption_type": "weather_delay", "studio_id": ""},
        )
        assert "studio_id = 'global'" in query, (
            f"Bug: build_query failed to default empty studio_id to 'global'. Generated: {query}"
        )


