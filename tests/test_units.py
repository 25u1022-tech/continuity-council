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


