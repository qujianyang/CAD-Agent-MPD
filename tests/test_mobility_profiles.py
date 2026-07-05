"""
Vehicle-profile tests.

A profile bundles a vehicle family's fixed assumptions (geometry, grouped
axle limits, aero, SAR angle/trig conventions, OEM margins, ISO-plane datum)
and builds a mobility_engine.Vehicle from a CG state.

T1 anchor: make_vehicle(...) + the existing engine reproduces the workbook
axle loads (front group 12625, rear group 13550) and slope SFs (asc60 2.4074,
kerb30 1.9775) -- proving the profile feeds the engine correctly with zero
engine changes.
"""
import pytest

from mobility_engine import run_mobility_analysis, slope_stability, side_slope_stability
from mobility_profiles import (
    Axle, AxleGroup, VehicleProfile, E2_PROFILE, T1_PROFILE,
    PROFILES, get_profile, slope_kwargs_for,
)

# Measured T1 laden CG (T1 Measured CG sheet)
T1_GW, T1_X, T1_Y, T1_Z = 26175.0, 2717.765042979943, -13.037249283667734, 1750.3799217829044


def test_t1_profile_constants():
    p = T1_PROFILE
    assert p.key == "t1"
    assert p.support_model == "four_axle_grouped"
    assert (p.wheelbase_mm, p.track_mm) == (5250.0, 2100.0)
    assert (p.front_group_limit_kg, p.rear_group_limit_kg, p.gvw_limit_kg) == (16000.0, 20000.0, 36000.0)
    assert p.default_radius_m == 14.0
    assert p.trig_dp == 3
    # amendment fields
    assert p.iso_plane_offset_mm == 2400.0
    assert p.oem_margin_long == 1.5 and p.oem_margin_lat == 1.5
    assert "no tilt test" in p.zcg_source_default.lower() or "cad" in p.zcg_source_default.lower()


def test_t1_axle_positions():
    """Datum = front group centre; axles 1..4 at -875/875/4525/5975."""
    xs = {a.name: a.x_mm for a in T1_PROFILE.axles}
    assert xs["Axle 1"] == -875.0
    assert xs["Axle 2"] == 875.0
    assert xs["Axle 3"] == 4525.0
    assert xs["Axle 4"] == 5975.0
    assert len(T1_PROFILE.groups) == 2


def test_t1_make_vehicle_reproduces_axle_loads():
    v = T1_PROFILE.make_vehicle("T1 laden", T1_GW, T1_X, T1_Y, T1_Z)
    assert v.wheelbase_mm == 5250.0
    assert v.front_axle_limit_kg == 16000.0
    assert v.rear_axle_limit_kg == 20000.0
    assert v.gvw_limit_kg == 36000.0
    rep = run_mobility_analysis(v)
    assert abs(rep.axle.front_kg - 12625.0) < 0.5
    assert abs(rep.axle.rear_kg - 13550.0) < 0.5
    assert abs(rep.axle.front_pct - 48.233) < 0.01


def test_t1_make_vehicle_reproduces_slope_sfs():
    v = T1_PROFILE.make_vehicle("T1 laden", T1_GW, T1_X, T1_Y, T1_Z)
    kw = slope_kwargs_for(T1_PROFILE, "ascending", 60)
    assert abs(slope_stability(v, 60, "ascending", **kw).SF - 2.4074) < 1e-3
    kw2 = slope_kwargs_for(T1_PROFILE, "kerbside", 30)
    assert abs(side_slope_stability(v, 30, "kerbside", **kw2).SF - 1.9775) < 1e-3


def test_slope_kwargs_uses_rounded_sar_angles():
    assert slope_kwargs_for(T1_PROFILE, "ascending", 60) == {"angle_deg": 31.0, "trig_dp": 3}
    assert slope_kwargs_for(T1_PROFILE, "kerbside", 30) == {"angle_deg": 16.7, "trig_dp": 3}
    # side 25% is also a rounded SAR angle (14.0 deg), verified vs stored SFs
    assert slope_kwargs_for(T1_PROFILE, "kerbside", 25) == {"angle_deg": 14.0, "trig_dp": 3}


def test_side_25_reproduces_stored_sf():
    """T1 side 25% at 14.0 deg reproduces the workbook kerb25/road25 SFs."""
    v = T1_PROFILE.make_vehicle("T1 laden", T1_GW, T1_X, T1_Y, T1_Z)
    kw = slope_kwargs_for(T1_PROFILE, "kerbside", 25)
    assert abs(side_slope_stability(v, 25, "kerbside", **kw).SF - 2.3745821642653673) < 1e-9
    assert abs(side_slope_stability(v, 25, "roadside", **kw).SF - 2.4342911935408993) < 1e-9


def test_e2_profile_preserved():
    p = E2_PROFILE
    assert p.key == "e2"
    assert (p.wheelbase_mm, p.track_mm) == (4800.0, 2088.0)
    assert (p.front_group_limit_kg, p.rear_group_limit_kg, p.gvw_limit_kg) == (8000.0, 10600.0, 18600.0)
    assert p.default_radius_m == 11.0
    assert p.iso_plane_offset_mm == 1450.0   # E2 datum offset (distinct from T1's 2400)


def test_registry_lookup():
    assert get_profile("t1") is T1_PROFILE
    assert get_profile("e2") is E2_PROFILE
    assert set(PROFILES) == {"e2", "t1"}
    with pytest.raises(KeyError):
        get_profile("nope")


def test_grade_without_rounded_angle_falls_back_to_atan():
    """A grade not in the SAR map (e.g. 50%) uses exact atan (angle_deg=None)."""
    kw = slope_kwargs_for(T1_PROFILE, "ascending", 50)
    assert kw["angle_deg"] is None
    assert kw["trig_dp"] == 3
