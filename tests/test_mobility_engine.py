"""
Mobility engine tests — verified anchors from 'E2 Measured Mobility Analysis' sheet.
Run: .\\mpd\\Scripts\\python.exe test_mobility_engine.py

Excel uses rounded angles (cos31°, sin16.7°) rather than exact atan().
Tolerance for slope SFs is 0.5% to account for that; cornering is exact.
"""

from mobility_engine import (
    G, Vehicle, Aero, AxleResult, SlopeResult, CornerResult,
    axle_loads, slope_stability, side_slope_stability, cornering_stability,
    approach_departure_check, run_mobility_analysis,
    format_mobility_report, format_slope_table,
)

# Spinel E2 — Measured CG (from E2 Measured CG sheet, cells D6-D12)
SPINEL = Vehicle(
    name="Spinel E2 (Measured CG)",
    gw_kg=17850.0,
    xcg_mm=2655.4621848739494,
    ycg_mm=20.470588235294144,
    zcg_mm=1617.8285033663278,
    wheelbase_mm=4800.0,
    track_mm=2088.0,
    front_axle_limit_kg=8000.0,
    rear_axle_limit_kg=10600.0,
    gvw_limit_kg=18600.0,
)

TOL_SF   = 0.01     # 1% absolute — Excel rounds angles to 0.1° (e.g. 31° vs atan(0.6)=30.96°)
TOL_LOAD = 0.5      # 0.5 kg for axle loads
TOL_MOM  = 300.0    # 300 Nm — angle rounding propagates ~230 Nm in worst case


# ---------------------------------------------------------------------------
# Axle loading tests
# ---------------------------------------------------------------------------

def test_front_axle_load():
    ax = axle_loads(SPINEL)
    assert abs(ax.front_kg - 7975.0) < TOL_LOAD, ax.front_kg

def test_rear_axle_load():
    ax = axle_loads(SPINEL)
    assert abs(ax.rear_kg - 9875.0) < TOL_LOAD, ax.rear_kg

def test_front_axle_pct():
    ax = axle_loads(SPINEL)
    assert abs(ax.front_pct - 44.678) < 0.01, ax.front_pct

def test_driverside_load():
    ax = axle_loads(SPINEL)
    # Sheet P30=9100 kg
    assert abs(ax.driverside_kg - 9100.0) < TOL_LOAD, ax.driverside_kg

def test_kerbside_load():
    ax = axle_loads(SPINEL)
    # Sheet Q34=8750 kg
    assert abs(ax.kerbside_kg - 8750.0) < TOL_LOAD, ax.kerbside_kg

def test_axle_limits_pass():
    ax = axle_loads(SPINEL)
    assert ax.front_ok and ax.rear_ok and ax.gvw_ok and ax.steer_ok
    assert ax.all_ok

def test_steer_fail_when_front_low():
    light = Vehicle("light", gw_kg=1000, xcg_mm=3800, ycg_mm=0, zcg_mm=1000,
                    wheelbase_mm=4800, track_mm=2088)
    ax = axle_loads(light)
    # front = 1000*(4800-3800)/4800 = 208.3 kg = 20.8% < 25%
    assert not ax.steer_ok


# ---------------------------------------------------------------------------
# Longitudinal slope stability — verified against AA17, AA40, AA65, AA88
# ---------------------------------------------------------------------------

def test_ascending_60():
    r = slope_stability(SPINEL, 60, "ascending")
    # Sheet AA17=2.2058, AA8=321826.47, AA12=145897.19, AA24=52.969 deg
    assert abs(r.SF - 2.2058) < TOL_SF, r.SF
    assert abs(r.stab_Nm - 321826.47) < TOL_MOM, r.stab_Nm
    assert abs(r.over_Nm - 145897.19) < TOL_MOM, r.over_Nm
    assert abs(r.crit_angle_deg - 52.969) < 0.05, r.crit_angle_deg

def test_descending_60():
    r = slope_stability(SPINEL, 60, "descending")
    # Sheet AA40=2.7314, AA31=398499.86, AA44=58.648 deg
    assert abs(r.SF - 2.7314) < TOL_SF, r.SF
    assert abs(r.stab_Nm - 398499.86) < TOL_MOM, r.stab_Nm
    assert abs(r.crit_angle_deg - 58.648) < 0.05, r.crit_angle_deg

def test_ascending_50():
    r = slope_stability(SPINEL, 50, "ascending")
    # Sheet AA65=2.6511
    assert abs(r.SF - 2.6511) < TOL_SF, r.SF

def test_descending_50():
    r = slope_stability(SPINEL, 50, "descending")
    # Sheet AA88=3.2827
    assert abs(r.SF - 3.2827) < TOL_SF, r.SF

def test_ascending_lever():
    r = slope_stability(SPINEL, 60, "ascending")
    expected = SPINEL.wheelbase_mm - SPINEL.xcg_mm
    assert abs(r.lever_mm - expected) < 0.01, r.lever_mm

def test_descending_lever():
    r = slope_stability(SPINEL, 60, "descending")
    assert abs(r.lever_mm - SPINEL.xcg_mm) < 0.01, r.lever_mm


# ---------------------------------------------------------------------------
# Side slope stability — verified against AJ17, AJ40, AJ65, AJ88
# ---------------------------------------------------------------------------

def test_kerbside_30():
    r = side_slope_stability(SPINEL, 30, "kerbside")
    # Sheet AJ17=2.1963, AK8=178569.14, AK12=81305.81, AJ24=33.343 deg
    assert abs(r.SF - 2.1963) < TOL_SF, r.SF
    assert abs(r.stab_Nm - 178569.14) < TOL_MOM, r.stab_Nm
    assert abs(r.over_Nm - 81305.81) < TOL_MOM, r.over_Nm
    assert abs(r.crit_angle_deg - 33.343) < 0.05, r.crit_angle_deg

def test_roadside_30():
    r = side_slope_stability(SPINEL, 30, "roadside")
    # Sheet AJ40=2.1118, AJ46=32.320 deg
    assert abs(r.SF - 2.1118) < TOL_SF, r.SF
    assert abs(r.crit_angle_deg - 32.320) < 0.05, r.crit_angle_deg

def test_kerbside_25():
    r = side_slope_stability(SPINEL, 25, "kerbside")
    # Sheet AJ65=2.6373
    assert abs(r.SF - 2.6373) < TOL_SF, r.SF

def test_roadside_25():
    r = side_slope_stability(SPINEL, 25, "roadside")
    # Sheet AJ88=2.5359
    assert abs(r.SF - 2.5359) < TOL_SF, r.SF

def test_kerbside_lever():
    r = side_slope_stability(SPINEL, 30, "kerbside")
    expected = SPINEL.track_mm / 2 + SPINEL.ycg_mm   # 1064.47 mm
    assert abs(r.lever_mm - expected) < 0.01

def test_roadside_lever():
    r = side_slope_stability(SPINEL, 30, "roadside")
    expected = SPINEL.track_mm / 2 - SPINEL.ycg_mm   # 1023.53 mm
    assert abs(r.lever_mm - expected) < 0.01


# ---------------------------------------------------------------------------
# Cornering — verified against BH58, BI61, BH65, BH72, BH77
# ---------------------------------------------------------------------------

def test_cornering_Fc():
    aero = Aero()
    c = cornering_stability(SPINEL, aero, speed_kmh=15.0, radius_m=11.0, wind_kmh=60.0)
    # Sheet BH58=28172.35
    assert abs(c.Fc_N - 28172.35) < 1.0, c.Fc_N

def test_cornering_over_fc():
    aero = Aero()
    c = cornering_stability(SPINEL, aero, speed_kmh=15.0, radius_m=11.0, wind_kmh=60.0)
    # Sheet BI61=45578.03
    assert abs(c.over_fc_Nm - 45578.03) < 1.0, c.over_fc_Nm

def test_cornering_over_total():
    aero = Aero()
    c = cornering_stability(SPINEL, aero, speed_kmh=15.0, radius_m=11.0, wind_kmh=60.0)
    # Sheet BH65=57511.76
    assert abs(c.over_total_Nm - 57511.76) < 1.0, c.over_total_Nm

def test_cornering_resist():
    aero = Aero()
    c = cornering_stability(SPINEL, aero, speed_kmh=15.0, radius_m=11.0, wind_kmh=60.0)
    # Sheet BH72=179228.70
    assert abs(c.resist_Nm - 179228.70) < 1.0, c.resist_Nm

def test_cornering_SF():
    aero = Aero()
    c = cornering_stability(SPINEL, aero, speed_kmh=15.0, radius_m=11.0, wind_kmh=60.0)
    # Sheet BH77=3.1163834
    assert abs(c.SF - 3.1164) < 1e-3, c.SF

def test_cornering_yprime():
    aero = Aero()
    c = cornering_stability(SPINEL, aero, speed_kmh=15.0, radius_m=11.0, wind_kmh=60.0)
    # Sheet uses 1023.529 mm (= track/2 - ycg; left turn is less stable)
    assert abs(c.yprime_mm - 1023.529) < 0.01, c.yprime_mm

def test_cornering_no_wind():
    aero = Aero()
    c = cornering_stability(SPINEL, aero, speed_kmh=15.0, radius_m=11.0, wind_kmh=0.0)
    assert c.Fw_N == 0.0
    assert c.over_total_Nm == c.over_fc_Nm
    assert c.SF > 3.9    # without wind, SF is higher

def test_max_safe_speed_positive():
    aero = Aero()
    c = cornering_stability(SPINEL, aero, speed_kmh=15.0, radius_m=11.0, wind_kmh=60.0)
    assert c.max_safe_speed_kmh > 0


# ---------------------------------------------------------------------------
# Approach / departure
# ---------------------------------------------------------------------------

def test_approach_departure_suitable():
    r = approach_departure_check(32.4, 31.0, required_grade_pct=60.0)
    # tan(32.4°)*100 = 63.4% > 60% -> suitable
    assert r.approach_ok
    # tan(31.0°)*100 = 60.0% >= 60% -> suitable (borderline)
    assert r.departure_ok


# ---------------------------------------------------------------------------
# run_mobility_analysis integration
# ---------------------------------------------------------------------------

def test_run_analysis_all_pass():
    report = run_mobility_analysis(SPINEL, approach_deg=32.4, departure_deg=31.0)
    assert report.all_passed

def test_governing_is_roadside_30():
    report = run_mobility_analysis(SPINEL)
    gov = report.governing_slope()
    assert gov is not None
    assert gov.direction == "roadside" and gov.grade_pct == 30

def test_format_mobility_report_has_key_fields():
    report = run_mobility_analysis(SPINEL)
    txt = format_mobility_report(report)
    assert "MOBILITY ANALYSIS" in txt
    assert "AXLE LOADINGS" in txt
    assert "SLOPE STABILITY" in txt
    assert "CORNERING" in txt
    assert "Spinel E2" in txt

def test_format_slope_table_has_all_grades():
    report = run_mobility_analysis(SPINEL)
    txt = format_slope_table(report)
    assert "60%" in txt and "50%" in txt
    assert "30%" in txt and "25%" in txt
    assert "2.2" in txt   # ascending 60% SF prefix


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _run():
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"[PASS] {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"[FAIL] {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"[ERROR] {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run()
