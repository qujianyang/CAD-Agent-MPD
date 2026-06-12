"""
Tests for mobility_scenarios.py (pure scenario-construction layer).

Reference values come from the SAR Appendix B measured wheel loads
(same numbers as tests/test_sar_report.py):
  FL=4000, FR=3975, RL=4750, RR=5125  ->  GW=17850 kg,
  Xcg=2655.4621848739494 mm, Ycg=20.470588235294144 mm
"""

import math

import pytest

from mobility_engine import Vehicle, run_mobility_analysis
from mobility_scenarios import (
    FRONT_AXLE_TO_ISO_PLANE_MM,
    MassChange,
    OEM_MARGIN_CORNERING,
    OEM_MARGIN_LATERAL,
    OEM_MARGIN_LONGITUDINAL,
    VERDICT_BELOW,
    VERDICT_MEETS,
    VERDICT_UNSTABLE,
    apply_mass_changes,
    axle_x_to_iso_x,
    baseline_delta,
    check_cg_plausibility,
    iso_x_to_axle_x,
    margin_for_direction,
    sf_verdict,
    vehicle_from_certified_cg,
    vehicle_from_wheel_loads,
    zcg_from_tilt_tests,
)

# Measured Spinel E2 wheel loads (avg readings, SAR Appendix B)
FL, FR, RL, RR = 4000.0, 3975.0, 4750.0, 5125.0
WB, TRACK = 4800.0, 2088.0
ZCG = 1617.8285033663278


def spinel_from_wheels() -> Vehicle:
    return vehicle_from_wheel_loads(FL, FR, RL, RR, WB, TRACK, ZCG,
                                    zcg_source="tilt test")


# ---------------------------------------------------------------------------
# Wheel-load derivation
# ---------------------------------------------------------------------------

class TestWheelLoadDerivation:
    def test_reproduces_spinel_measured_cg(self):
        v = spinel_from_wheels()
        assert v.gw_kg == pytest.approx(17850.0)
        assert v.xcg_mm == pytest.approx(2655.4621848739494)
        assert v.ycg_mm == pytest.approx(20.470588235294144)
        assert v.zcg_mm == pytest.approx(ZCG)
        assert v.wheelbase_mm == WB
        assert v.track_mm == TRACK

    def test_spinel_vendor_limits_default(self):
        v = spinel_from_wheels()
        assert v.front_axle_limit_kg == 8000.0
        assert v.rear_axle_limit_kg == 10600.0
        assert v.gvw_limit_kg == 18600.0

    def test_zcg_source_recorded_in_name(self):
        v = spinel_from_wheels()
        assert "tilt test" in v.name

    def test_ycg_sign_convention_right_heavy_is_positive(self):
        # Engine convention: +Ycg toward driverside/right
        # (kerbside lever = track/2 + Ycg). Heavier right side must give +Ycg.
        v = vehicle_from_wheel_loads(1000, 2000, 1000, 2000, WB, TRACK,
                                     1500, zcg_source="CAD model")
        assert v.ycg_mm > 0
        v2 = vehicle_from_wheel_loads(2000, 1000, 2000, 1000, WB, TRACK,
                                      1500, zcg_source="CAD model")
        assert v2.ycg_mm < 0
        assert v.ycg_mm == pytest.approx(-v2.ycg_mm)

    def test_symmetric_loads_give_centreline_cg(self):
        v = vehicle_from_wheel_loads(1000, 1000, 1500, 1500, WB, TRACK,
                                     1500, zcg_source="CAD model")
        assert v.ycg_mm == pytest.approx(0.0)
        assert v.xcg_mm == pytest.approx(WB * 3000 / 5000)

    @pytest.mark.parametrize("bad", [0.0, -50.0])
    @pytest.mark.parametrize("pos", range(4))
    def test_rejects_non_positive_wheel_loads(self, bad, pos):
        loads = [FL, FR, RL, RR]
        loads[pos] = bad
        with pytest.raises(ValueError):
            vehicle_from_wheel_loads(*loads, WB, TRACK, ZCG,
                                     zcg_source="tilt test")

    @pytest.mark.parametrize("kw", ["wheelbase_mm", "track_mm", "zcg_mm"])
    def test_rejects_non_positive_dimensions(self, kw):
        kwargs = dict(wheelbase_mm=WB, track_mm=TRACK, zcg_mm=ZCG)
        kwargs[kw] = 0.0
        with pytest.raises(ValueError):
            vehicle_from_wheel_loads(FL, FR, RL, RR,
                                     zcg_source="tilt test", **kwargs)

    @pytest.mark.parametrize("src", [None, "", "   "])
    def test_rejects_missing_zcg_source(self, src):
        with pytest.raises(ValueError):
            vehicle_from_wheel_loads(FL, FR, RL, RR, WB, TRACK, ZCG,
                                     zcg_source=src)


# ---------------------------------------------------------------------------
# Certified CG entry (advanced path)
# ---------------------------------------------------------------------------

class TestCertifiedCG:
    def test_builds_vehicle_with_source_label(self):
        v = vehicle_from_certified_cg(17850, 2655.5, 20.5, 1617.8, WB, TRACK,
                                      source="OEM cert 123-A")
        assert "OEM cert 123-A" in v.name
        assert v.gw_kg == 17850

    def test_negative_ycg_allowed(self):
        v = vehicle_from_certified_cg(17850, 2655.5, -35.0, 1617.8, WB, TRACK,
                                      source="ref")
        assert v.ycg_mm == -35.0

    def test_rejects_missing_source(self):
        with pytest.raises(ValueError):
            vehicle_from_certified_cg(17850, 2655.5, 20.5, 1617.8, WB, TRACK,
                                      source="")

    @pytest.mark.parametrize("field, val", [
        ("gw_kg", 0), ("xcg_mm", -1), ("zcg_mm", 0),
        ("wheelbase_mm", 0), ("track_mm", -5),
    ])
    def test_rejects_non_positive_required_values(self, field, val):
        kwargs = dict(gw_kg=17850, xcg_mm=2655.5, ycg_mm=20.5,
                      zcg_mm=1617.8, wheelbase_mm=WB, track_mm=TRACK,
                      source="ref")
        kwargs[field] = val
        with pytest.raises(ValueError):
            vehicle_from_certified_cg(**kwargs)


# ---------------------------------------------------------------------------
# Mass changes (design / modification study)
# ---------------------------------------------------------------------------

BASE = Vehicle("test base", gw_kg=1000.0, xcg_mm=2000.0, ycg_mm=0.0,
               zcg_mm=1500.0, wheelbase_mm=4000.0, track_mm=2000.0)


class TestMassChanges:
    def test_empty_change_list_preserves_baseline_exactly(self):
        out = apply_mass_changes(BASE, [])
        assert out == BASE
        assert out is not BASE   # never the same object

    def test_add_component(self):
        # Hand-computed: 200 kg at (3000, 100, 1000) on 1000 kg base
        out = apply_mass_changes(BASE, [
            MassChange("add", "winch", 200, new_xyz_mm=(3000, 100, 1000)),
        ])
        assert out.gw_kg == pytest.approx(1200.0)
        assert out.xcg_mm == pytest.approx(2_600_000 / 1200)   # 2166.667
        assert out.ycg_mm == pytest.approx(20_000 / 1200)      # 16.667
        assert out.zcg_mm == pytest.approx(1_700_000 / 1200)   # 1416.667

    def test_remove_round_trips_add(self):
        added = apply_mass_changes(BASE, [
            MassChange("add", "winch", 200, new_xyz_mm=(3000, 100, 1000)),
        ])
        removed = apply_mass_changes(added, [
            MassChange("remove", "winch", 200, old_xyz_mm=(3000, 100, 1000)),
        ])
        assert removed.gw_kg == pytest.approx(BASE.gw_kg)
        assert removed.xcg_mm == pytest.approx(BASE.xcg_mm)
        assert removed.ycg_mm == pytest.approx(BASE.ycg_mm)
        assert removed.zcg_mm == pytest.approx(BASE.zcg_mm)

    def test_relocate_keeps_mass_moves_cg(self):
        out = apply_mass_changes(BASE, [
            MassChange("relocate", "battery", 100,
                       old_xyz_mm=(1000, 0, 500),
                       new_xyz_mm=(3000, 200, 1500)),
        ])
        assert out.gw_kg == pytest.approx(BASE.gw_kg)
        assert out.xcg_mm == pytest.approx(2000 + 100 * 2000 / 1000)  # 2200
        assert out.ycg_mm == pytest.approx(100 * 200 / 1000)          # 20
        assert out.zcg_mm == pytest.approx(1500 + 100 * 1000 / 1000)  # 1600

    def test_relocate_no_op_preserves_cg(self):
        out = apply_mass_changes(BASE, [
            MassChange("relocate", "noop", 100,
                       old_xyz_mm=(1000, 50, 500),
                       new_xyz_mm=(1000, 50, 500)),
        ])
        assert out.gw_kg == pytest.approx(BASE.gw_kg)
        assert out.xcg_mm == pytest.approx(BASE.xcg_mm)
        assert out.ycg_mm == pytest.approx(BASE.ycg_mm)
        assert out.zcg_mm == pytest.approx(BASE.zcg_mm)

    def test_multiple_simultaneous_changes(self):
        out = apply_mass_changes(BASE, [
            MassChange("add", "shelter", 500, new_xyz_mm=(2500, 0, 2000)),
            MassChange("remove", "ballast", 300, old_xyz_mm=(3500, 0, 800)),
            MassChange("relocate", "spare", 100,
                       old_xyz_mm=(4000, -500, 900),
                       new_xyz_mm=(200, 500, 900)),
        ])
        m = 1000 + 500 - 300
        mx = 1000 * 2000 + 500 * 2500 - 300 * 3500 + 100 * (200 - 4000)
        my = 0 + 0 - 0 + 100 * (500 - (-500))
        mz = 1000 * 1500 + 500 * 2000 - 300 * 800
        assert out.gw_kg == pytest.approx(m)
        assert out.xcg_mm == pytest.approx(mx / m)
        assert out.ycg_mm == pytest.approx(my / m)
        assert out.zcg_mm == pytest.approx(mz / m)

    def test_limits_inherited_from_baseline(self):
        out = apply_mass_changes(BASE, [
            MassChange("add", "x", 10, new_xyz_mm=(0, 0, 100)),
        ])
        assert out.front_axle_limit_kg == BASE.front_axle_limit_kg
        assert out.rear_axle_limit_kg == BASE.rear_axle_limit_kg
        assert out.gvw_limit_kg == BASE.gvw_limit_kg
        assert out.wheelbase_mm == BASE.wheelbase_mm
        assert out.track_mm == BASE.track_mm

    # -- rejection cases ----------------------------------------------------

    def test_rejects_non_positive_final_mass(self):
        with pytest.raises(ValueError, match="non-positive"):
            apply_mass_changes(BASE, [
                MassChange("remove", "too much", 1200,
                           old_xyz_mm=(2000, 0, 1500)),
            ])

    @pytest.mark.parametrize("mass", [0.0, -10.0])
    def test_rejects_non_positive_component_mass(self, mass):
        with pytest.raises(ValueError):
            apply_mass_changes(BASE, [
                MassChange("add", "bad", mass, new_xyz_mm=(0, 0, 100)),
            ])

    def test_rejects_unknown_action(self):
        with pytest.raises(ValueError, match="unknown action"):
            apply_mass_changes(BASE, [
                MassChange("move", "bad", 10,
                           old_xyz_mm=(0, 0, 100), new_xyz_mm=(0, 0, 100)),
            ])

    def test_rejects_missing_coords_for_action(self):
        with pytest.raises(ValueError, match="requires"):
            apply_mass_changes(BASE, [MassChange("add", "no pos", 10)])
        with pytest.raises(ValueError, match="requires"):
            apply_mass_changes(BASE, [MassChange("remove", "no pos", 10)])
        with pytest.raises(ValueError, match="requires"):
            apply_mass_changes(BASE, [
                MassChange("relocate", "half", 10, old_xyz_mm=(0, 0, 100)),
            ])

    def test_rejects_non_positive_component_z(self):
        with pytest.raises(ValueError):
            apply_mass_changes(BASE, [
                MassChange("add", "underground", 10, new_xyz_mm=(0, 0, -5)),
            ])

    def test_baseline_never_mutated(self):
        before = replace_copy = Vehicle(**vars(BASE))
        apply_mass_changes(BASE, [
            MassChange("add", "x", 500, new_xyz_mm=(100, 100, 100)),
        ])
        assert BASE == before == replace_copy


# ---------------------------------------------------------------------------
# Deltas + plausibility warnings
# ---------------------------------------------------------------------------

class TestDeltaAndWarnings:
    def test_baseline_delta(self):
        out = apply_mass_changes(BASE, [
            MassChange("add", "winch", 200, new_xyz_mm=(3000, 100, 1000)),
        ])
        d = baseline_delta(BASE, out)
        assert d["gw_kg"] == pytest.approx(200.0)
        assert d["xcg_mm"] == pytest.approx(out.xcg_mm - BASE.xcg_mm)
        assert d["ycg_mm"] == pytest.approx(out.ycg_mm)
        assert d["zcg_mm"] == pytest.approx(out.zcg_mm - BASE.zcg_mm)

    def test_normal_vehicle_has_no_warnings(self):
        assert check_cg_plausibility(spinel_from_wheels()) == []

    def test_warns_xcg_outside_wheelbase(self):
        v = vehicle_from_certified_cg(1000, 4500, 0, 1500, 4000, 2000,
                                      source="ref")
        warns = check_cg_plausibility(v)
        assert any("Xcg" in w for w in warns)

    def test_warns_extreme_ycg(self):
        v = vehicle_from_certified_cg(1000, 2000, 600, 1500, 4000, 2000,
                                      source="ref")
        assert any("Ycg" in w for w in warns_list(v))

    def test_warns_very_high_zcg(self):
        v = vehicle_from_certified_cg(1000, 2000, 0, 2500, 4000, 2000,
                                      source="ref")
        assert any("Zcg" in w for w in warns_list(v))

    def test_warnings_are_ascii(self):
        v = vehicle_from_certified_cg(1000, 4500, 600, 2500, 4000, 2000,
                                      source="ref")
        for w in check_cg_plausibility(v):
            w.encode("ascii")   # raises if non-ASCII sneaks in


def warns_list(v):
    return check_cg_plausibility(v)


# ---------------------------------------------------------------------------
# Three-tier verdicts vs OEM margins
# ---------------------------------------------------------------------------

class TestVerdicts:
    def test_default_margins(self):
        assert OEM_MARGIN_LONGITUDINAL == 2.0
        assert OEM_MARGIN_LATERAL == 2.2
        assert OEM_MARGIN_CORNERING == 2.2

    @pytest.mark.parametrize("sf, expected", [
        (0.99, VERDICT_UNSTABLE),
        (0.0, VERDICT_UNSTABLE),
        (1.0, VERDICT_BELOW),
        (1.99, VERDICT_BELOW),
        (2.0, VERDICT_MEETS),
        (3.5, VERDICT_MEETS),
    ])
    def test_three_tiers_at_margin_2(self, sf, expected):
        assert sf_verdict(sf, 2.0) == expected

    def test_rejects_margin_below_one(self):
        with pytest.raises(ValueError):
            sf_verdict(1.5, 0.9)

    def test_structural_verdict_distinct(self):
        """VERDICT_STRUCTURAL (axle/GVW/steer failure) outranks the stability tiers and
        must never collide with their labels."""
        from mobility_scenarios import VERDICT_STRUCTURAL
        assert VERDICT_STRUCTURAL not in (VERDICT_UNSTABLE, VERDICT_BELOW, VERDICT_MEETS)
        assert "STRUCTURAL" in VERDICT_STRUCTURAL

    def test_margin_for_direction(self):
        assert margin_for_direction("ascending") == OEM_MARGIN_LONGITUDINAL
        assert margin_for_direction("descending") == OEM_MARGIN_LONGITUDINAL
        assert margin_for_direction("kerbside") == OEM_MARGIN_LATERAL
        assert margin_for_direction("roadside") == OEM_MARGIN_LATERAL
        with pytest.raises(ValueError):
            margin_for_direction("sideways")

    def test_custom_margins_override(self):
        assert margin_for_direction("ascending", long_margin=3.0) == 3.0
        assert margin_for_direction("kerbside", lat_margin=2.5) == 2.5


# ---------------------------------------------------------------------------
# Tilt-test Zcg derivation (four-test SAR method)
# ---------------------------------------------------------------------------

# Spinel E2 tilt-test data (SAR): level rear-axle load = RL + RR
F_LEVEL = RL + RR          # 9875 kg
GW = FL + FR + RL + RR     # 17850 kg
WHEEL_R = 580.0
E2_TILT_TESTS = [
    (10.2, 10550.0),
    (12.3, 10700.0),
    (8.2, 10450.0),
    (6.2, 10300.0),
]


class TestTiltTestZcg:
    def test_reproduces_four_e2_zcg_values(self):
        results, _ = zcg_from_tilt_tests(F_LEVEL, GW, WB, E2_TILT_TESTS,
                                         wheel_radius_mm=WHEEL_R)
        zs = [r.zcg_mm for r in results]
        assert zs[0] == pytest.approx(1588.8, abs=0.1)
        assert zs[1] == pytest.approx(1597.5, abs=0.1)
        assert zs[2] == pytest.approx(1653.0, abs=0.1)
        assert zs[3] == pytest.approx(1632.0, abs=0.1)

    def test_average_matches_workbook_zcg(self):
        _, avg = zcg_from_tilt_tests(F_LEVEL, GW, WB, E2_TILT_TESTS,
                                     wheel_radius_mm=WHEEL_R)
        assert avg == pytest.approx(1617.8, abs=0.1)

    def test_default_wheel_radius_is_580(self):
        _, avg_default = zcg_from_tilt_tests(F_LEVEL, GW, WB, E2_TILT_TESTS)
        _, avg_explicit = zcg_from_tilt_tests(F_LEVEL, GW, WB, E2_TILT_TESTS,
                                              wheel_radius_mm=580.0)
        assert avg_default == pytest.approx(avg_explicit)

    def test_results_keep_input_order_and_inputs(self):
        results, _ = zcg_from_tilt_tests(F_LEVEL, GW, WB, E2_TILT_TESTS)
        assert [(r.angle_deg, r.rear_load_kg) for r in results] == E2_TILT_TESTS

    def test_average_feeds_wheel_load_vehicle(self):
        _, avg = zcg_from_tilt_tests(F_LEVEL, GW, WB, E2_TILT_TESTS)
        v = vehicle_from_wheel_loads(FL, FR, RL, RR, WB, TRACK, avg,
                                     zcg_source="tilt test")
        assert v.zcg_mm == pytest.approx(ZCG, abs=0.1)

    @pytest.mark.parametrize("angle", [0.0, -5.0, 90.0, 95.0])
    def test_rejects_out_of_range_angle(self, angle):
        with pytest.raises(ValueError):
            zcg_from_tilt_tests(F_LEVEL, GW, WB, [(angle, 10500.0)])

    @pytest.mark.parametrize("load", [0.0, -100.0])
    def test_rejects_non_positive_rear_load(self, load):
        with pytest.raises(ValueError):
            zcg_from_tilt_tests(F_LEVEL, GW, WB, [(10.0, load)])

    @pytest.mark.parametrize("kw", ["f_level_kg", "gw_kg", "wheelbase_mm",
                                    "wheel_radius_mm"])
    def test_rejects_non_positive_scalars(self, kw):
        kwargs = dict(f_level_kg=F_LEVEL, gw_kg=GW, wheelbase_mm=WB,
                      wheel_radius_mm=WHEEL_R)
        kwargs[kw] = 0.0
        with pytest.raises(ValueError):
            zcg_from_tilt_tests(tests=E2_TILT_TESTS, **kwargs)

    def test_rejects_empty_test_list(self):
        with pytest.raises(ValueError):
            zcg_from_tilt_tests(F_LEVEL, GW, WB, [])


# ---------------------------------------------------------------------------
# ISO twist-lock plane datum conversion
# ---------------------------------------------------------------------------

class TestIsoDatumConversion:
    def test_offset_constant(self):
        assert FRONT_AXLE_TO_ISO_PLANE_MM == 1450.0

    def test_iso_origin_maps_to_1450_from_axle(self):
        assert iso_x_to_axle_x(0.0) == pytest.approx(1450.0)

    def test_e2_xcg_in_iso_datum(self):
        assert axle_x_to_iso_x(2655.5) == pytest.approx(1205.5)

    def test_round_trip_identity(self):
        for x in (-500.0, 0.0, 1450.0, 2655.5, 7000.0):
            assert axle_x_to_iso_x(iso_x_to_axle_x(x)) == pytest.approx(x)

    def test_mass_change_identical_either_datum(self):
        """Entering positions from the ISO datum (converted) must give exactly
        the same modified vehicle as entering axle-datum positions directly."""
        x_iso_old, x_iso_new = 1000.0, 3000.0
        via_axle = apply_mass_changes(BASE, [
            MassChange("relocate", "genset", 250,
                       old_xyz_mm=(x_iso_old + 1450.0, 100, 800),
                       new_xyz_mm=(x_iso_new + 1450.0, -100, 1200)),
        ])
        via_iso = apply_mass_changes(BASE, [
            MassChange("relocate", "genset", 250,
                       old_xyz_mm=(iso_x_to_axle_x(x_iso_old), 100, 800),
                       new_xyz_mm=(iso_x_to_axle_x(x_iso_new), -100, 1200)),
        ])
        assert via_iso == via_axle


# ---------------------------------------------------------------------------
# Integration: every scenario feeds the same engine entry point
# ---------------------------------------------------------------------------

class TestEngineIntegration:
    def test_wheel_load_vehicle_runs_full_analysis(self):
        report = run_mobility_analysis(spinel_from_wheels())
        assert report.axle.front_kg + report.axle.rear_kg == pytest.approx(17850)
        assert len(report.slope_results) == 8   # (60,50)x(asc,desc) + (30,25)x(kerb,road)
        gov = report.governing_slope()
        assert gov is not None and gov.SF > 0

    def test_modified_vehicle_runs_full_analysis(self):
        modified = apply_mass_changes(spinel_from_wheels(), [
            MassChange("add", "roof load", 300, new_xyz_mm=(2400, 0, 3000)),
        ])
        base_report = run_mobility_analysis(spinel_from_wheels())
        mod_report = run_mobility_analysis(modified)
        # Raising CG must reduce the governing slope SF
        assert (mod_report.governing_slope().SF
                < base_report.governing_slope().SF)

    def test_wheel_load_vehicle_matches_certified_entry(self):
        # Same numbers via either construction path -> identical physics
        vw = spinel_from_wheels()
        vc = vehicle_from_certified_cg(vw.gw_kg, vw.xcg_mm, vw.ycg_mm,
                                       vw.zcg_mm, WB, TRACK, source="ref")
        rw = run_mobility_analysis(vw)
        rc = run_mobility_analysis(vc)
        assert rw.governing_slope().SF == pytest.approx(rc.governing_slope().SF)
        assert rw.axle.front_kg == pytest.approx(rc.axle.front_kg)
