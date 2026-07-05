"""
Four-axle (T1) wheel-load scenario tests.

The T1 is an 8x8: four axles, each with a left/right wheel-group load. The
scenario layer collapses the eight loads into the two support groups the
validated engine already understands (axles 1+2 -> front, 3+4 -> rear) and
derives the same Vehicle the workbook uses.

Anchor (T1 measured wheel loads, summing to the workbook CG):
  axle totals  : 5950 / 6675 / 6875 / 6675  -> GW 26175
  front group  : 12625   rear group : 13550
  Xcg = 2717.765042979943   Ycg = -13.037249283667734
so run_mobility_analysis on the derived vehicle reproduces front 12625 / rear 13550.
"""
import pytest

from mobility_engine import run_mobility_analysis
from mobility_scenarios import (
    derive_4axle_wheel_load_summary, vehicle_from_4axle_wheel_loads,
)

# A per-wheel split whose group/side sums match the workbook (only group and
# side totals drive the CG, so any consistent split reproduces it).
LOADS = dict(
    a1_left_kg=3000, a1_right_kg=2950,   # axle1 total 5950
    a2_left_kg=3350, a2_right_kg=3325,   # axle2 total 6675
    a3_left_kg=3450, a3_right_kg=3425,   # axle3 total 6875
    a4_left_kg=3450, a4_right_kg=3225,   # axle4 total 6675
)
GEOM = dict(wheelbase_mm=5250.0, track_mm=2100.0,
            zcg_mm=1750.3799217829044, zcg_source="CAD model")


def test_summary_group_totals():
    s = derive_4axle_wheel_load_summary(**LOADS, **GEOM)
    assert s.axle_totals_kg == (5950.0, 6675.0, 6875.0, 6675.0)
    assert s.front_group_kg == 12625.0
    assert s.rear_group_kg == 13550.0
    assert s.front_group_left_kg == 6350.0
    assert s.front_group_right_kg == 6275.0
    assert s.rear_group_left_kg == 6900.0
    assert s.rear_group_right_kg == 6650.0
    assert s.left_side_kg == 13250.0
    assert s.right_side_kg == 12925.0


def test_summary_reproduces_workbook_cg():
    s = derive_4axle_wheel_load_summary(**LOADS, **GEOM)
    v = s.vehicle
    assert abs(v.gw_kg - 26175.0) < 1e-9
    assert abs(v.xcg_mm - 2717.765042979943) < 1e-9
    assert abs(v.ycg_mm - (-13.037249283667734)) < 1e-9
    assert abs(v.zcg_mm - 1750.3799217829044) < 1e-12
    # grouped limits default to T1 vendor values
    assert v.front_axle_limit_kg == 16000.0
    assert v.rear_axle_limit_kg == 20000.0
    assert v.gvw_limit_kg == 36000.0


def test_derived_vehicle_reproduces_axle_split():
    v = vehicle_from_4axle_wheel_loads(**LOADS, **GEOM)
    rep = run_mobility_analysis(v)
    assert abs(rep.axle.front_kg - 12625.0) < 1e-6
    assert abs(rep.axle.rear_kg - 13550.0) < 1e-6


def test_vehicle_name_carries_zcg_source():
    v = vehicle_from_4axle_wheel_loads(**LOADS, **GEOM)
    assert "CAD model" in v.name


def test_negative_load_rejected():
    bad = dict(LOADS, a3_right_kg=-1)
    with pytest.raises(ValueError):
        derive_4axle_wheel_load_summary(**bad, **GEOM)


def test_missing_zcg_source_rejected():
    geom = dict(GEOM, zcg_source="")
    with pytest.raises(ValueError):
        derive_4axle_wheel_load_summary(**LOADS, **geom)
