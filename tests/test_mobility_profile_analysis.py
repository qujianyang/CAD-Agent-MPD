"""
Profile-based mobility runner tests.

Pins that run_profile_mobility_analysis (engine + T1 profile conventions)
reproduces the T1 workbook safety factors exactly for both CG variants -- the
end-to-end proof that a new vehicle family drops in via a profile with zero
changes to the validated engine.
"""
import pytest

from mobility_engine import Vehicle
from mobility_profiles import T1_PROFILE
from mobility_profile_analysis import (
    run_profile_mobility_analysis, format_profile_axle_context,
)
from mobility_scenarios import derive_4axle_wheel_load_summary

TOL = 1e-9

# Measured + theory T1 CG states (from the workbook)
V_MEAS = T1_PROFILE.make_vehicle(
    "T1 measured", 26175.0, 2717.765042979943, -13.037249283667734, 1750.3799217829044)
V_THEO = T1_PROFILE.make_vehicle(
    "T1 theory", 26042.9, 2843.9176311009905, 10.166663466818212, 1750.3799217829044)

MEAS_SF = {"asc_60": 2.4073834454365226, "desc_60": 2.583765994904149,
           "kerb_30": 1.9774906808241164, "road_30": 2.027214817866116,
           "corner": 3.601540982344649}
THEO_SF = {"asc_60": 2.2874507940845428, "desc_60": 2.7036986462561283,
           "kerb_30": 2.0217406031969736, "road_30": 1.9829648954932593,
           "corner": 3.607274924989593}


def _sf(rep):
    by = {(r.grade_pct, r.direction): r for r in rep.slope_results}
    return {
        "asc_60": by[(60, "ascending")].SF,
        "desc_60": by[(60, "descending")].SF,
        "kerb_30": by[(30, "kerbside")].SF,
        "road_30": by[(30, "roadside")].SF,
        "corner": rep.corner.SF,
    }


def test_measured_axle_loads():
    rep = run_profile_mobility_analysis(V_MEAS, T1_PROFILE)
    assert abs(rep.axle.front_kg - 12625.0) < 1e-6
    assert abs(rep.axle.rear_kg - 13550.0) < 1e-6


def test_theory_axle_loads():
    rep = run_profile_mobility_analysis(V_THEO, T1_PROFILE)
    assert abs(rep.axle.front_kg - 11935.497623809526) < 1e-6
    assert abs(rep.axle.rear_kg - 14107.402376190475) < 1e-6


def test_measured_slope_and_corner_sfs():
    got = _sf(run_profile_mobility_analysis(V_MEAS, T1_PROFILE))
    for k, want in MEAS_SF.items():
        assert abs(got[k] - want) < TOL, f"{k}: {got[k]} != {want}"


def test_theory_slope_and_corner_sfs():
    got = _sf(run_profile_mobility_analysis(V_THEO, T1_PROFILE))
    for k, want in THEO_SF.items():
        assert abs(got[k] - want) < TOL, f"{k}: {got[k]} != {want}"


def test_grades_absent_from_map_fall_back_to_atan():
    """50%/25% grades are still computed (via exact atan), not dropped."""
    rep = run_profile_mobility_analysis(V_MEAS, T1_PROFILE)
    dirs = {(r.grade_pct, r.direction) for r in rep.slope_results}
    assert (50, "ascending") in dirs and (25, "kerbside") in dirs


def test_axle_context_describes_grouping():
    txt = format_profile_axle_context(T1_PROFILE)
    assert "four_axle_grouped" in txt
    assert "Axle 1" in txt and "Axle 3" in txt


def test_t1_report_headline_matches_ui():
    """Regression for the Streamlit T1 tab headline: with the profile's default
    radius (14 m) the governing slope is kerbside 30% (SF 1.9775) and cornering
    SF is 3.6015 -- the exact figures the Mobility tab displays for measured T1."""
    rep = run_profile_mobility_analysis(V_MEAS, T1_PROFILE)  # radius_m=None -> 14 m
    gov = rep.governing_slope()
    assert (gov.grade_pct, gov.direction) == (30, "kerbside")
    assert abs(gov.SF - 1.9774906808241164) < 1e-9
    assert abs(rep.corner.SF - 3.601540982344649) < 1e-9
    assert abs(rep.axle.front_kg - 12625.0) < 1e-6
    assert abs(rep.axle.rear_kg - 13550.0) < 1e-6


def test_axle_context_with_wheel_summary():
    s = derive_4axle_wheel_load_summary(
        a1_left_kg=3000, a1_right_kg=2950, a2_left_kg=3350, a2_right_kg=3325,
        a3_left_kg=3450, a3_right_kg=3425, a4_left_kg=3450, a4_right_kg=3225,
        wheelbase_mm=5250.0, track_mm=2100.0,
        zcg_mm=1750.38, zcg_source="CAD model")
    txt = format_profile_axle_context(T1_PROFILE, wheel_summary=s)
    assert "Front group 12,625" in txt
    assert "Rear group 13,550" in txt
