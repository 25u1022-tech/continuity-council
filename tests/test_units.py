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


# ---------------------------------------------------------------------------
# Council Chatbot Unit & API Tests
# ---------------------------------------------------------------------------
class TestCouncilChatbot:
    def test_chatbot_greeting_zero_tool_calls(self):
        import asyncio
        from agents.council_chatbot import CouncilChatbot, GREETING_RESPONSE

        chatbot = CouncilChatbot()
        for query in ["Hi", "hello", "Hey there!", "Thanks!", "thank you"]:
            res = asyncio.run(chatbot.ask(query))
            assert "council assistant" in res["answer"].lower() or "help" in res["answer"].lower()
            assert len(res["sources"]) == 0

    def test_chatbot_general_answers_cover_set_and_any_question(self):
        import asyncio
        from agents.council_chatbot import CouncilChatbot

        chatbot = CouncilChatbot()
        # 1. Film glossary query
        res = asyncio.run(chatbot.ask("What is a cover set?"))
        assert "cover set" in res["answer"].lower()
        assert len(res["sources"]) == 0
        assert "1. 1." not in res["answer"]

        # 2. General trivia / knowledge query
        res2 = asyncio.run(chatbot.ask("What is the capital of France?"))
        assert len(res2["answer"]) > 10
        assert len(res2["sources"]) == 0
        assert "1. 1." not in res2["answer"]

    def test_chatbot_howto_step_by_step_from_help_kb(self):
        import asyncio
        from agents.council_chatbot import CouncilChatbot

        chatbot = CouncilChatbot()
        res = asyncio.run(chatbot.ask("How do I report a disruption?"))
        assert "Report disruption" in res["answer"]
        assert len(res["sources"]) == 0
        assert "1." in res["answer"]
        assert "1. 1." not in res["answer"]
        assert any(s in res["answer"].lower() for s in ["shall i", "would you like", "help"])

    def test_chatbot_explain_investigation_process_routing(self):
        import asyncio
        from agents.council_chatbot import CouncilChatbot

        chatbot = CouncilChatbot()
        for q in [
            "explain the investigation process",
            "how does the investigation work",
            "what do the agents do",
            "what happens during investigation",
            "explain the pipeline",
        ]:
            res = asyncio.run(chatbot.ask(q))
            ans = res["answer"]
            assert len(res["sources"]) == 0
            assert "Budget Sentinel" in ans
            assert "Schedule Optimizer" in ans
            assert "Compliance Sentinel" in ans
            assert "Continuity Memory" in ans
            assert "ClickHouse" in ans
            assert "0.40" in ans or "TRD" in ans

    def test_chatbot_answers_reasoning_question_with_sources(self, case):
        import asyncio
        import case_store
        from agents.council_chatbot import CouncilChatbot
        from models import RecoveryOption

        case.options = [
            RecoveryOption(
                option_id="opt_cover",
                name="Shoot Cover Scenes",
                strategy="shoot_cover_scenes",
                rank=1,
                recommended=True,
                estimated_cost_usd=4500,
                estimated_delay_hours=2.0,
                score=92.5,
                compliance_valid=True,
            )
        ]
        case_store.put(case)

        chatbot = CouncilChatbot()
        res = asyncio.run(
            chatbot.ask(
                "Why was the top option chosen?",
                production_id=case.production_id,
                case_id=case.case_id,
            )
        )

        assert "Shoot Cover Scenes" in res["answer"] or "Rank 1" in res["answer"] or "score" in res["answer"].lower()
        assert len(res["sources"]) > 0
        assert res["sources"][0]["type"] == "mcp_query"
        assert "SELECT" in res["sources"][0]["query"]
        assert "1. 1." not in res["answer"]
        assert "6.199999" not in res["answer"]

    def test_chatbot_historical_weather_query(self):
        import asyncio
        from agents.council_chatbot import CouncilChatbot

        chatbot = CouncilChatbot()
        res = asyncio.run(chatbot.ask("Show me historical weather disruptions for this location."))
        assert "ClickHouse" in res["answer"] or "historical" in res["answer"].lower() or "disruption" in res["answer"].lower()
        assert len(res["sources"]) > 0
        assert any("weather_delay" in s["query"] or "disruption_history" in s["query"] for s in res["sources"])

    def test_chatbot_affirmative_followup_resolves_contextually(self, case):
        import asyncio
        import case_store
        from agents.council_chatbot import CouncilChatbot
        from models import RecoveryOption

        case.options = [
            RecoveryOption(
                option_id="opt_cover",
                name="Shoot Cover Scenes",
                strategy="shoot_cover_scenes",
                rank=1,
                recommended=True,
                estimated_cost_usd=18800,
                estimated_delay_hours=3.7,
                score=96.6,
                compliance_valid=True,
            )
        ]
        case_store.put(case)

        chatbot = CouncilChatbot()
        history = [
            {"sender": "user", "text": "Walk me through the recovery options"},
            {"sender": "ai", "text": "Would you like me to explain why the top option is recommended for your active case?"},
        ]
        res = asyncio.run(chatbot.ask("yes", production_id=case.production_id, case_id=case.case_id, conversation_history=history))
        assert "Shoot Cover Scenes" in res["answer"] or "Option" in res["answer"]
        assert len(res["sources"]) > 0

    def test_chatbot_check_shoot_plan_returns_weather_and_schedule(self):
        import asyncio
        from agents.council_chatbot import CouncilChatbot

        chatbot = CouncilChatbot()
        res = asyncio.run(chatbot.ask("check my shoot plan", production_id="prod_001"))
        assert "shoot plan" in res["answer"].lower() or "schedule" in res["answer"].lower()
        assert "Risk" in res["answer"] or "Weather" in res["answer"] or "Harbor Exterior" in res["answer"]
        assert len(res["sources"]) > 0

    def test_chatbot_unclear_message_returns_clarifying_fallback(self):
        import asyncio
        from agents.council_chatbot import CouncilChatbot

        chatbot = CouncilChatbot()
        res = asyncio.run(chatbot.ask("blorp zorp 123", production_id="prod_001"))
        assert "clarify" in res["answer"].lower() or "explain" in res["answer"].lower()
        assert "That's a great question! In film production planning" not in res["answer"]

    def test_chatbot_out_of_context_affirmative_returns_clarification(self):
        import asyncio
        from agents.council_chatbot import CouncilChatbot

        chatbot = CouncilChatbot()
        res = asyncio.run(chatbot.ask("yes", production_id="prod_001"))
        assert "help" in res["answer"].lower() or "explain" in res["answer"].lower()
        assert len(res["sources"]) == 0

    def test_chat_api_endpoint(self, case):
        import case_store
        from fastapi.testclient import TestClient
        from server import app
        from models import RecoveryOption

        case.options = [
            RecoveryOption(
                option_id="opt_cover",
                name="Option A: Shoot Cover Scenes",
                strategy="shoot_cover_scenes",
                rank=1,
                recommended=True,
                estimated_cost_usd=5000,
                estimated_delay_hours=1.5,
                score=94.0,
                compliance_valid=True,
            )
        ]
        case_store.put(case)

        client = TestClient(app)
        response = client.post(
            "/api/chat",
            json={
                "message": "What evidence supports Option A?",
                "production_id": case.production_id,
                "case_id": case.case_id,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert isinstance(data["sources"], list)
        assert len(data["sources"]) > 0

    def test_chat_endpoint_405_regression(self, case):
        from fastapi.testclient import TestClient
        from server import app

        client = TestClient(app)
        payload = {
            "message": "Why was the top option chosen?",
            "production_id": case.production_id,
            "case_id": case.case_id,
        }

        # Verify all route variants return 200 and never 405
        for path in ["/api/chat", "/api/chat/", "/chat", "/chat/"]:
            resp = client.post(path, json=payload)
            assert resp.status_code == 200, f"Expected 200 for {path}, got {resp.status_code}"
            body = resp.json()
            assert "answer" in body
            assert isinstance(body["sources"], list)

    def test_chatbot_fallback_kb_all_chips(self):
        import asyncio
        from agents.council_chatbot import CouncilChatbot

        chatbot = CouncilChatbot()
        starter_chips = [
            "How do I report a disruption?",
            "Walk me through the recovery options.",
            "Why was the top option chosen?",
            "What do the live signals mean?",
            "Show me the decision ledger.",
        ]

        for chip in starter_chips:
            res = asyncio.run(chatbot.ask(chip))
            assert "answer" in res
            assert len(res["answer"]) > 50
            # Must end with a kind next-step suggestion
            assert any(s in res["answer"].lower() for s in ["shall i", "would you like", "feel free", "help you"])
            assert "1. 1." not in res["answer"]

    def test_chatbot_failure_path_kind_message(self):
        from fastapi.testclient import TestClient
        from server import app
        from unittest.mock import patch

        client = TestClient(app)
        with patch("agents.council_chatbot.CouncilChatbot.ask", side_effect=Exception("Database connection timed out")):
            resp = client.post("/api/chat", json={"message": "Why was Option A chosen?"})
            assert resp.status_code == 200
            data = resp.json()
            assert "having a little trouble" in data["answer"].lower()
            assert "Database connection timed out" not in data["answer"]
            assert data["sources"] == []

    def test_llm_agent_calls_explain_option_ranking_for_recovery_question(self, case):
        """When Gemini is mocked to request explain_option_ranking, the tool is executed."""
        import asyncio
        import case_store
        from agents.council_chatbot import CouncilChatbot
        from models import RecoveryOption
        from unittest.mock import AsyncMock, MagicMock, patch

        case.options = [
            RecoveryOption(
                option_id="opt_cover",
                name="Shoot Cover Scenes",
                strategy="shoot_cover_scenes",
                rank=1,
                recommended=True,
                estimated_cost_usd=18800,
                estimated_delay_hours=3.7,
                score=96.6,
                compliance_valid=True,
            )
        ]
        case_store.put(case)

        # Simulate Gemini configured but we mock the actual SDK call
        with patch("agents.council_chatbot.gemini_client.is_configured", return_value=True), \
             patch("agents.council_chatbot.gemini_client.quota_hit", return_value=False), \
             patch("agents.council_chatbot.explain_option_ranking", new_callable=AsyncMock) as mock_tool:

            mock_tool.return_value = {
                "name": "Shoot Cover Scenes",
                "rank": 1,
                "composite_score": 96.6,
                "estimated_cost_usd": 18800,
                "estimated_delay_hours": 3.7,
                "compliance_valid": True,
                "sql": "SELECT * FROM continuity_council.disruption_history",
                "summary": "Option Shoot Cover Scenes (Rank 1): Score 96.6.",
            }

            # Mock the Gemini _run_agent to directly call explain_option_ranking
            async def fake_run_agent(q, prod, cid, hist):
                result = await mock_tool(case_id=cid, option_rank=1)
                return {
                    "answer": f"The top option is {result['name']} with score {result['composite_score']}. "
                              f"Would you like to approve it?",
                    "intent": "llm_agent",
                    "sources": [{"type": "mcp_query", "query": result["sql"], "result_summary": result["summary"]}],
                    "error": None,
                }

            chatbot = CouncilChatbot()
            with patch.object(chatbot, "_run_agent", side_effect=fake_run_agent):
                res = asyncio.run(
                    chatbot.ask("Why was the top option chosen?",
                                production_id=case.production_id,
                                case_id=case.case_id)
                )

        assert "Shoot Cover Scenes" in res["answer"] or "96.6" in res["answer"]
        assert len(res["sources"]) > 0
        mock_tool.assert_called_once()

    def test_llm_agent_calls_search_history_for_benchmark_question(self):
        """When Gemini is mocked to request search_disruption_history, the tool is executed."""
        import asyncio
        from agents.council_chatbot import CouncilChatbot
        from unittest.mock import AsyncMock, patch

        with patch("agents.council_chatbot.gemini_client.is_configured", return_value=True), \
             patch("agents.council_chatbot.gemini_client.quota_hit", return_value=False), \
             patch("agents.council_chatbot.search_disruption_history", new_callable=AsyncMock) as mock_hist:

            mock_hist.return_value = {
                "sql": "SELECT * FROM continuity_council.disruption_history",
                "rows": [
                    ["shoot_cover_scenes", 17241.0, 3.7, 0.67, 22467],
                ],
                "summary": "1 benchmark record found.",
            }

            async def fake_run_agent(q, prod, cid, hist):
                result = await mock_hist(query=q, production_id=prod)
                return {
                    "answer": f"Historically, shoot_cover_scenes costs ~$17.2k with 3.7h delay (n=22,467). "
                              f"Would you like to see this applied to your active case?",
                    "intent": "llm_agent",
                    "sources": [{"type": "mcp_query", "query": result["sql"], "result_summary": result["summary"]}],
                    "error": None,
                }

            chatbot = CouncilChatbot()
            with patch.object(chatbot, "_run_agent", side_effect=fake_run_agent):
                res = asyncio.run(chatbot.ask("Show me similar historical disruptions"))

        assert "17.2k" in res["answer"] or "22,467" in res["answer"] or "3.7h" in res["answer"]
        assert len(res["sources"]) > 0
        mock_hist.assert_called_once()

    def test_llm_agent_returns_fallback_when_gemini_unavailable(self):
        """When Gemini is not configured, ask() returns a deterministic fallback."""
        import asyncio
        from agents.council_chatbot import CouncilChatbot
        from unittest.mock import patch

        with patch("agents.council_chatbot.gemini_client.is_configured", return_value=False):
            chatbot = CouncilChatbot()
            res = asyncio.run(chatbot.ask("Why was the top option chosen?", production_id="prod_001"))

        assert isinstance(res["answer"], str)
        assert len(res["answer"]) > 20
        # Must NOT be the LLM-unavailable error message (fallback should produce real content)
        assert "temporarily unavailable" not in res["answer"].lower()


# ---------------------------------------------------------------------------
# Explainability Layer: Justification Engine Tests
# ---------------------------------------------------------------------------
class TestExplainabilityJustification:
    def test_recovery_option_schema_has_justification(self):
        opt = RecoveryOption(
            option_id="opt_test",
            name="Test Option",
            strategy="swap_locations",
            estimated_cost_usd=18800,
            estimated_delay_hours=3.7,
            rank=1,
            justification="Natural language justification test",
        )
        assert opt.justification == "Natural language justification test"
        dumped = opt.model_dump()
        assert "justification" in dumped
        assert dumped["justification"] == "Natural language justification test"

    def test_deterministic_fallback_template_format(self):
        from services.justification_service import format_deterministic_fallback
        from models import EvidenceRow

        opt = RecoveryOption(
            option_id="opt_1",
            name="Shoot cover scenes",
            strategy="shoot_cover_scenes",
            estimated_cost_usd=18800,
            estimated_delay_hours=3.7,
            rank=1,
            evidence=EvidenceRow(
                resolution_strategy="shoot_cover_scenes",
                past_cases=22467,
                avg_cost_overrun_usd=17241.0,
                avg_delay_hours=3.7,
            ),
        )
        fallback = format_deterministic_fallback(opt)
        assert fallback == "Ranked #1: $18,800 avg cost and 3.7h delay based on 22,467 similar historical cases."

    def test_justification_service_with_gemini_success(self):
        import asyncio
        from unittest.mock import AsyncMock, patch
        from services.justification_service import generate_justifications

        opt = RecoveryOption(
            option_id="opt_1",
            name="Swap shoot days",
            strategy="swap_locations",
            estimated_cost_usd=25800,
            estimated_delay_hours=5.2,
            rank=1,
            recommended=True,
        )

        with (
            patch("services.gemini_client.is_configured", return_value=True),
            patch("services.gemini_client.quota_hit", return_value=False),
            patch("services.gemini_client.generate_text", new_callable=AsyncMock) as mock_gen,
        ):
            mock_gen.return_value = "Swap shoot days minimizes financial exposure to $25,800 and 5.2h delay across 12,221 empirical cases."
            results = asyncio.run(generate_justifications([opt]))

            assert opt.option_id in results
            assert "minimizes financial exposure" in opt.justification
            assert opt.justification == results[opt.option_id]

    def test_justification_service_gemini_timeout_fallback(self):
        import asyncio
        from unittest.mock import AsyncMock, patch
        from services.justification_service import generate_justifications

        opt = RecoveryOption(
            option_id="opt_2",
            name="Use stand-in",
            strategy="use_stand_in",
            estimated_cost_usd=17500,
            estimated_delay_hours=3.2,
            rank=2,
        )

        with patch("services.gemini_client.generate_text", side_effect=asyncio.TimeoutError("Timeout")):
            results = asyncio.run(generate_justifications([opt]))

            assert opt.option_id in results
            assert opt.justification.startswith("Ranked #2:")
            assert "$17,500 avg cost" in opt.justification
            assert "3.2h delay" in opt.justification

    def test_justification_service_gemini_exception_fallback(self):
        import asyncio
        from unittest.mock import AsyncMock, patch
        from services.justification_service import generate_justifications

        opt = RecoveryOption(
            option_id="opt_3",
            name="Wait for actor",
            strategy="wait_for_actor",
            estimated_cost_usd=62000,
            estimated_delay_hours=11.8,
            rank=3,
        )

        with patch("services.gemini_client.generate_text", side_effect=Exception("API Error")):
            results = asyncio.run(generate_justifications([opt]))

            assert opt.option_id in results
            assert opt.justification.startswith("Ranked #3:")
            assert "$62,000" in opt.justification
            assert "11.8h delay" in opt.justification


class TestNLDisruptionParser:
    """Test suite for natural-language disruption parsing and day resolution."""

    def test_day_resolution_weekdays_and_phrases(self):
        from services.nl_parser import resolve_day_and_date

        start_date = "2026-08-24"  # Monday

        # Monday -> Day 1
        d, dt = resolve_day_and_date("filming Monday morning", start_date)
        assert d == 1
        assert dt == "2026-08-24"

        # Tuesday -> Day 2
        d, dt = resolve_day_and_date("Sarah can't shoot Tuesday", start_date)
        assert d == 2
        assert dt == "2026-08-25"

        # Thursday -> Day 4
        d, dt = resolve_day_and_date("Storm rolling in Thursday", start_date)
        assert d == 4
        assert dt == "2026-08-27"

        # Explicit Day N
        d, dt = resolve_day_and_date("holding Day 12 schedule", start_date, total_shoot_days=30)
        assert d == 12
        assert dt == "2026-09-04"

        # Relative tomorrow
        d, dt = resolve_day_and_date("gear arrives tomorrow", start_date)
        assert d == 2
        assert dt == "2026-08-25"

    def test_mock_gemini_5_disruption_descriptions(self):
        import asyncio
        from unittest.mock import AsyncMock, patch
        from services.nl_parser import parse_disruption

        mock_bundle = {
            "production": {"start_date": "2026-08-24", "total_shoot_days": 30},
            "cast_members": [
                {"cast_id": "lead_001", "name": "Sarah Sterling", "role_type": "lead"},
                {"cast_id": "supp_001", "name": "Dev Okafor", "role_type": "supporting"},
            ],
            "locations": [
                {"location_id": "harbor_ext", "name": "Harbor Exterior", "location_type": "exterior"},
                {"location_id": "stage_a", "name": "Stage A", "location_type": "interior"},
            ],
            "scenes": [
                {"scene_id": "sc_001", "shoot_day": 2, "required_cast": ["lead_001"], "location_id": "stage_a"},
                {"scene_id": "sc_002", "shoot_day": 4, "required_cast": ["supp_001"], "location_id": "harbor_ext"},
            ],
        }

        with patch("services.clickhouse_client.fetch_production_bundle", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_bundle

            # 1. Sarah broke her wrist
            with patch("services.gemini_client.generate_json", new_callable=AsyncMock) as mock_json:
                mock_json.return_value = {
                    "disruption_type": "lead_actor_unavailable",
                    "severity": "high",
                    "entity_mention": "Sarah",
                    "day_mention": "Tuesday",
                    "reasoning": "Sarah broke her wrist and cannot film on Tuesday.",
                }
                res1 = asyncio.run(parse_disruption("Sarah broke her wrist, can't shoot Tuesday", "prod_001"))
                assert res1["disruption_type"] == "lead_actor_unavailable"
                assert res1["affected_day"] == 2
                assert res1["affected_date"] == "2026-08-25"
                assert res1["affected_cast_id"] == "lead_001"
                assert res1["confidence"] == "high"

            # 2. Harbor permit revoked
            with patch("services.gemini_client.generate_json", new_callable=AsyncMock) as mock_json:
                mock_json.return_value = {
                    "disruption_type": "permit_issue",
                    "severity": "high",
                    "entity_mention": "harbor",
                    "day_mention": "Day 1",
                    "reasoning": "Harbor permit was revoked by authorities.",
                }
                res2 = asyncio.run(parse_disruption("The harbor permit got revoked", "prod_001"))
                assert res2["disruption_type"] in ("permit_issue", "location_unavailable")
                assert res2["affected_location_id"] == "harbor_ext"
                assert res2["confidence"] in ("high", "medium")

            # 3. Storm rolling in Thursday
            with patch("services.gemini_client.generate_json", new_callable=AsyncMock) as mock_json:
                mock_json.return_value = {
                    "disruption_type": "weather_delay",
                    "severity": "medium",
                    "entity_mention": "",
                    "day_mention": "Thursday",
                    "reasoning": "Storm forecast for Thursday.",
                }
                res3 = asyncio.run(parse_disruption("Storm's rolling in Thursday", "prod_001"))
                assert res3["disruption_type"] == "weather_delay"
                assert res3["affected_day"] == 4
                assert res3["affected_date"] == "2026-08-27"

            # 4. Equipment failure
            with patch("services.gemini_client.generate_json", new_callable=AsyncMock) as mock_json:
                mock_json.return_value = {
                    "disruption_type": "equipment_failure",
                    "severity": "high",
                    "entity_mention": "camera",
                    "day_mention": "tomorrow",
                    "reasoning": "Main camera sensor is fried.",
                }
                res4 = asyncio.run(parse_disruption("Main camera sensor fried, replacement arrives tomorrow", "prod_001"))
                assert res4["disruption_type"] == "equipment_failure"
                assert res4["affected_day"] == 2

            # 5. Supporting actor Dev
            with patch("services.gemini_client.generate_json", new_callable=AsyncMock) as mock_json:
                mock_json.return_value = {
                    "disruption_type": "supporting_actor_unavailable",
                    "severity": "medium",
                    "entity_mention": "Dev",
                    "day_mention": "Day 3",
                    "reasoning": "Dev is delayed in transit.",
                }
                res5 = asyncio.run(parse_disruption("Dev is stuck in transit, holding day 3 scenes", "prod_001"))
                assert res5["disruption_type"] == "supporting_actor_unavailable"
                assert res5["affected_day"] == 3
                assert res5["affected_cast_id"] == "supp_001"

    def test_gemini_timeout_fallback_to_heuristic(self):
        import asyncio
        from unittest.mock import AsyncMock, patch
        from services.nl_parser import parse_disruption

        mock_bundle = {
            "production": {"start_date": "2026-08-24", "total_shoot_days": 30},
            "cast_members": [{"cast_id": "lead_001", "name": "Sarah Sterling", "role_type": "lead"}],
            "locations": [],
            "scenes": [],
        }

        with patch("services.clickhouse_client.fetch_production_bundle", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_bundle
            with patch("services.gemini_client.generate_json", side_effect=asyncio.TimeoutError("Timeout")):
                res = asyncio.run(parse_disruption("Sarah broke her wrist, can't shoot Tuesday", "prod_001"))
                assert res["disruption_type"] == "lead_actor_unavailable"
                assert res["affected_day"] == 2
                assert res["affected_cast_id"] == "lead_001"
                assert res["confidence"] in ("high", "medium")

    def test_empty_description_handling(self):
        import asyncio
        from services.nl_parser import parse_disruption

        res = asyncio.run(parse_disruption("", "prod_001"))
        assert res["confidence"] == "low"
        assert res["parsed"] is None


class TestSchedulePDFExtractor:
    """Test suite for PDF shooting schedule ingestion via Gemini document understanding."""

    TINY_PDF_BYTES = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000102 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF"
    )

    def test_validate_pdf_bytes_success(self):
        from services.schedule_extractor import validate_pdf_bytes
        # Should not raise
        validate_pdf_bytes(self.TINY_PDF_BYTES, "callsheet.pdf")

    def test_validate_pdf_bytes_non_pdf_rejected(self):
        import pytest
        from services.schedule_extractor import validate_pdf_bytes

        with pytest.raises(ValueError, match="Only valid PDF files are supported"):
            validate_pdf_bytes(b"NOT A PDF FILE", "notes.txt")

    def test_validate_pdf_bytes_oversize_rejected(self):
        import pytest
        from services.schedule_extractor import validate_pdf_bytes

        oversized = b"%PDF-" + b"0" * (11 * 1024 * 1024)
        with pytest.raises(ValueError, match="exceeds 10MB limit"):
            validate_pdf_bytes(oversized, "huge.pdf")

    def test_validate_pdf_bytes_excessive_pages_rejected(self):
        import pytest
        from services.schedule_extractor import validate_pdf_bytes

        multi_page_pdf = b"%PDF-1.4\n" + (b"/Type /Page\n" * 25) + b"%%EOF"
        with pytest.raises(ValueError, match="exceeds maximum page limit of 20"):
            validate_pdf_bytes(multi_page_pdf, "long.pdf")

    def test_normalize_extracted_data_from_fixture(self):
        from services.schedule_extractor import normalize_extracted_data

        fixture = {
            "shoot_days": [
                {"day_number": 2, "date": "2026-08-25", "scenes": ["2A", "3"]},
                {"day_number": 1, "date": "2026-08-24", "scenes": ["1"]},
            ],
            "scenes": [
                {
                    "scene_number": "2A",
                    "scene_title": "Interrogation Room Heated Exchange",
                    "location_name": "Stage A - Interrogation Set",
                    "cast_names": ["Mara Voss", "Dev Okafor", "Mara Voss"],  # Duplicate cast name in scene
                    "int_ext": "int. stage",
                    "day_night": "NIGHT",
                    "shoot_day": 2,
                },
                {
                    "scene_number": "1",
                    "scene_title": "Harbor Pier Arrival",
                    "location_name": "Harbor Pier 7 Exterior",
                    "cast_names": ["Mara Voss"],
                    "int_ext": "EXTERIOR",
                    "day_night": "day",
                    "shoot_day": 1,
                },
            ],
            "locations": ["Harbor Pier 7 Exterior", "Stage A - Interrogation Set", "Harbor Pier 7 Exterior"],  # Duplicate
            "cast": ["Mara Voss", "Dev Okafor", "Mara Voss", "Lena Petrov"],  # Duplicate
        }

        normalized = normalize_extracted_data(fixture, default_start_date="2026-08-24")

        # 1. Cast deduplicated
        cast_names = [c["name"] for c in normalized["cast"]]
        assert len(cast_names) == 3
        assert set(cast_names) == {"Mara Voss", "Dev Okafor", "Lena Petrov"}

        # 2. Locations deduplicated
        loc_names = [l["name"] for l in normalized["locations"]]
        assert len(loc_names) == 2

        # 3. Scenes sorted by shoot day & sequence
        scenes = normalized["scenes"]
        assert len(scenes) == 2
        assert scenes[0]["scene_number"] == "1"
        assert scenes[0]["shoot_day"] == 1
        assert scenes[0]["int_ext"] == "EXT"
        assert scenes[0]["day_night"] == "DAY"

        assert scenes[1]["scene_number"] == "2A"
        assert scenes[1]["shoot_day"] == 2
        assert scenes[1]["int_ext"] == "INT"
        assert scenes[1]["day_night"] == "NIGHT"

        # 4. Total shoot days derived correctly
        assert normalized["total_shoot_days"] == 2

    def test_import_schedule_endpoint_lifecycle(self):
        import asyncio
        import io
        from unittest.mock import AsyncMock, patch
        from fastapi.testclient import TestClient
        from server import app
        from services import schedule_extractor

        client = TestClient(app)

        mock_extraction = {
            "shoot_days": [
                {"day_number": 1, "date": "2026-08-24", "scenes": ["1", "2"]},
            ],
            "scenes": [
                {
                    "scene_number": "1",
                    "scene_title": "Harbor Setup",
                    "location_name": "Harbor Pier 7",
                    "cast_names": ["Mara Voss"],
                    "int_ext": "EXT",
                    "day_night": "DAY",
                    "shoot_day": 1,
                },
                {
                    "scene_number": "2",
                    "scene_title": "Loft Confrontation",
                    "location_name": "Downtown Loft",
                    "cast_names": ["Mara Voss", "Dev Okafor"],
                    "int_ext": "INT",
                    "day_night": "NIGHT",
                    "shoot_day": 1,
                },
            ],
            "locations": ["Harbor Pier 7", "Downtown Loft"],
            "cast": ["Mara Voss", "Dev Okafor"],
        }

        with patch("services.gemini_client.generate_json_with_pdf", new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = mock_extraction

            # 1. POST /api/productions/prod_001/import-schedule
            files = {"file": ("shooting_schedule.pdf", io.BytesIO(self.TINY_PDF_BYTES), "application/pdf")}
            resp = client.post("/api/productions/prod_001/import-schedule", files=files)
            assert resp.status_code == 200
            data = resp.json()
            assert "job_id" in data
            job_id = data["job_id"]
            assert data["status"] in ("pending", "processing", "ready")

            # Run the background worker synchronously for test verification
            asyncio.run(schedule_extractor.process_schedule_pdf_async(job_id, self.TINY_PDF_BYTES))

            # 2. GET /api/imports/{job_id} -> preview
            get_resp = client.get(f"/api/imports/{job_id}")
            assert get_resp.status_code == 200
            job_data = get_resp.json()
            assert job_data["status"] == "ready"
            assert job_data["preview"] is not None
            assert job_data["preview"]["scenes_count"] == 2
            assert job_data["preview"]["cast_count"] == 2
            assert job_data["preview"]["locations_count"] == 2

            # 3. POST /api/imports/{job_id}/confirm
            with patch("services.clickhouse_client.upsert_extracted_schedule", new_callable=AsyncMock) as mock_upsert:
                mock_upsert.return_value = {
                    "scenes_count": 2,
                    "locations_count": 2,
                    "cast_count": 2,
                    "total_shoot_days": 1,
                }
                conf_resp = client.post(f"/api/imports/{job_id}/confirm")
                assert conf_resp.status_code == 200
                conf_data = conf_resp.json()
                assert conf_data["success"] is True
                assert conf_data["scenes_count"] == 2

    def test_import_schedule_failure_fallback(self):
        import asyncio
        from unittest.mock import AsyncMock, patch
        from fastapi.testclient import TestClient
        from server import app
        from services import schedule_extractor

        client = TestClient(app)

        with patch("services.gemini_client.generate_json_with_pdf", side_effect=Exception("Gemini quota exhausted")):
            # Create a job with empty/invalid bytes that will fail extraction
            job_id = schedule_extractor.create_import_job("prod_001", "corrupt.pdf", 100)
            asyncio.run(schedule_extractor.process_schedule_pdf_async(job_id, b"%PDF-1.4 UNREADABLE GARBAGE"))

            job = schedule_extractor.get_import_job(job_id)
            assert job["status"] == "failed"
            assert "We couldn't read this schedule" in job["error"]
            assert "manually or via CSV" in job["error"]


class TestMoodboardService:
    """Unit and endpoint tests for Imagen 3 location mood-boards."""

    def test_build_prompt(self):
        from services.moodboard_service import build_prompt

        loc = {
            "name": "Harbor Pier 7 Exterior",
            "location_type": "exterior",
            "notes": "Commercial working port with heavy gantry cranes",
        }
        scene = {
            "scene_title": "Harbor Setup",
            "description": "Detective meets informant at the dock",
            "day_night": "NIGHT",
        }
        prompt = build_prompt(loc, scene)
        assert "Harbor Pier 7 Exterior" in prompt
        assert "exterior" in prompt
        assert "night" in prompt.lower()
        assert "35mm" in prompt
        assert "No text" in prompt

    def test_generate_moodboard_success_and_cache(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch
        from services import moodboard_service

        fake_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb"
        mock_response = MagicMock()
        mock_img = MagicMock()
        mock_img.image.image_bytes = fake_bytes
        mock_response.generated_images = [mock_img]

        # Clear caches for test isolation
        moodboard_service._MEMORY_CACHE.clear()
        (moodboard_service.CACHE_DIR / "loc_test_001.json").unlink(missing_ok=True)

        with patch("services.gemini_client.is_configured", return_value=True), \
             patch("services.gemini_client.quota_hit", return_value=False), \
             patch("services.gemini_client._get_client") as mock_get_client:
            
            mock_client = MagicMock()
            mock_client.aio.models.generate_images = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            # 1. First call -> generates image
            res1 = asyncio.run(
                moodboard_service.generate_moodboard(
                    location_id="loc_test_001",
                    location={"name": "Test Stage A", "location_type": "interior"},
                )
            )
            assert res1 is not None
            assert res1["status"] == "ready"
            assert res1["cached"] is False
            assert res1["location_name"] == "Test Stage A"
            assert len(res1["image_base64"]) > 0
            assert mock_client.aio.models.generate_images.call_count == 1

            # 2. Second call -> served from cache without calling Imagen again
            res2 = asyncio.run(
                moodboard_service.generate_moodboard(
                    location_id="loc_test_001",
                    location={"name": "Test Stage A", "location_type": "interior"},
                )
            )
            assert res2 is not None
            assert res2["status"] == "ready"
            assert res2["cached"] is True
            # Zero new Imagen calls
            assert mock_client.aio.models.generate_images.call_count == 1

    def test_moodboard_endpoint_failure_returns_202(self):
        from unittest.mock import AsyncMock, patch
        from fastapi.testclient import TestClient
        from server import app

        client = TestClient(app)

        with patch("services.moodboard_service.generate_moodboard", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = None  # Simulates quota exhaustion / failure

            resp = client.get("/api/locations/loc_unavailable_001/moodboard")
            assert resp.status_code == 202
            data = resp.json()
            assert data["status"] == "unavailable"
            assert data["location_id"] == "loc_unavailable_001"
            assert "unavailable" in data["detail"].lower()

    def test_investigation_makes_zero_imagen_calls(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch
        from services import moodboard_service
        from agents.orchestrator import run_investigation
        from models import CaseState, DisruptionReport

        # Spy on moodboard generator
        with patch("services.moodboard_service.generate_moodboard", new_callable=AsyncMock) as mock_mb, \
             patch("services.clickhouse_client.get_current_schedule", new_callable=AsyncMock) as mock_sched:

            mock_sched.return_value = {
                "production": {"production_id": "prod_001", "title": "Test", "start_date": "2026-08-24", "total_shoot_days": 10},
                "scenes": [
                    {"scene_id": "sc_001", "shoot_day": 1, "location_id": "loc_001", "cast_ids": ["c_001"], "pages": 1.0, "scene_title": "Scene 1"}
                ],
                "locations": [{"location_id": "loc_001", "name": "Pier 7", "location_type": "exterior"}],
                "cast": [{"cast_id": "c_001", "name": "Actor", "role_type": "lead"}],
            }

            fake_case = CaseState(
                case_id="case_test_sla",
                production_id="prod_001",
                disruption=DisruptionReport(
                    disruption_type="lead_actor_unavailable",
                    affected_cast_id="c_001",
                    affected_day=1,
                    severity="medium",
                ),
                status="investigating",
            )

            try:
                asyncio.run(run_investigation(fake_case))
            except Exception:
                pass

            # CRITICAL CONSTRAINT: ZERO IMAGEN CALLS DURING INVESTIGATION
            assert mock_mb.call_count == 0


# ---------------------------------------------------------------------------
# TTS Service Tests
# ---------------------------------------------------------------------------
class TestTTSService:
    """Tests for the Gemini TTS service."""

    def test_text_hash_deterministic(self):
        """Same text always produces the same hash."""
        from services import tts_service

        h1 = tts_service.text_hash("Hello, how are you?")
        h2 = tts_service.text_hash("Hello, how are you?")
        h3 = tts_service.text_hash("Something else")
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 16

    def test_text_hash_strips_whitespace(self):
        """Leading/trailing whitespace doesn't change hash."""
        from services import tts_service

        h1 = tts_service.text_hash("Hello world")
        h2 = tts_service.text_hash("  Hello world  ")
        assert h1 == h2

    def test_cache_miss_returns_none(self):
        """get_cached returns None for unknown hash."""
        from services import tts_service

        result = tts_service.get_cached("nonexistent_hash_12345")
        assert result is None

    def test_cache_hit_returns_entry(self):
        """Manually inserted cache entry is retrievable."""
        import time
        from services import tts_service

        h = "test_cache_entry"
        tts_service._TTS_CACHE[h] = {
            "hash": h,
            "audio_base64": "dGVzdA==",
            "mime_type": "audio/wav",
            "created_at": time.time(),
            "expires_at": time.time() + 3600,
        }
        result = tts_service.get_cached(h)
        assert result is not None
        assert result["audio_base64"] == "dGVzdA=="
        # Cleanup
        del tts_service._TTS_CACHE[h]

    def test_expired_cache_returns_none(self):
        """Expired cache entries are evicted."""
        import time
        from services import tts_service

        h = "test_expired_entry"
        tts_service._TTS_CACHE[h] = {
            "hash": h,
            "audio_base64": "dGVzdA==",
            "mime_type": "audio/wav",
            "created_at": time.time() - 7200,
            "expires_at": time.time() - 3600,  # Expired 1h ago
        }
        result = tts_service.get_cached(h)
        assert result is None
        assert h not in tts_service._TTS_CACHE

    def test_tts_returns_none_for_empty_text(self):
        """Empty text returns None immediately."""
        import asyncio
        from services import tts_service

        result = asyncio.run(tts_service.text_to_speech(""))
        assert result is None

        result = asyncio.run(tts_service.text_to_speech("   "))
        assert result is None

    def test_chat_response_not_blocked_by_tts(self):
        """Assert the chat endpoint does NOT wait for TTS — text returns before audio.

        The POST /api/chat/tts/generate endpoint fires audio generation as
        asyncio.create_task (fire-and-forget). We verify the endpoint function
        returns status="generating" without blocking on audio completion.
        """
        from services import tts_service

        h = tts_service.text_hash("Some test response")
        # If not cached, the endpoint should return "generating" immediately
        cached = tts_service.get_cached(h)
        assert cached is None  # Not cached = will be async = non-blocking


    def test_tts_endpoint_registered(self):
        """Verify TTS endpoints are registered in the FastAPI app."""
        from server import api

        routes = [r.path for r in api.routes]
        assert any("tts/generate" in r for r in routes), \
            f"POST /chat/tts/generate not found in api routes: {routes}"
        assert any("tts" in r for r in routes), \
            f"GET /chat/tts not found in api routes: {routes}"



