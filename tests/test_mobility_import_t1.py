"""
T1 workbook importer tests -- anchored to the T1 Measured CG workbook.

The workbook is sensitive defence data and is NOT committed; these tests read
it from T1_MOBILITY_XLSX (or the known local Downloads path) and SKIP cleanly
when the file is absent, so CI without the workbook stays green.

Anchors (verified against the file):
  measured vehicle : GW 26175, Xcg 2717.765, Ycg -13.037, Zcg 1750.380
  theory   vehicle : GW 26042.9, Xcg 2843.918, Ycg 10.167, Zcg 1750.380
  measured SF      : asc60 2.4074, desc60 2.5838, kerb30 1.9775, road30 2.0272, corner 3.6015
  theory   SF      : asc60 2.2875, desc60 2.7037, kerb30 2.0217, road30 1.9830, corner 3.6073
  measured axle    : front 12625, rear 13550   (theory 11935.5 / 14107.4)
  components       : 75 rows, mass sum 10492.9, first = "Structure frame" 2300 kg @ X3124.24 Z922.03
  payload rev-CG   : 9725 kg, X 4021.851, Y -62.082, Z 2821.753
"""
import os

import pytest

from mobility_engine import run_mobility_analysis, slope_stability, side_slope_stability
from mobility_profiles import T1_PROFILE, slope_kwargs_for
import mobility_import_t1 as t1

_WB = t1.workbook_path()
requires_wb = pytest.mark.skipif(
    _WB is None, reason="T1 workbook not found (set T1_MOBILITY_XLSX)")

TOL = 1e-3


@requires_wb
def test_measured_vehicle_cg():
    v = t1.vehicle_measured_t1()
    assert abs(v.gw_kg - 26175.0) < 1e-6
    assert abs(v.xcg_mm - 2717.765042979943) < TOL
    assert abs(v.ycg_mm - (-13.037249283667734)) < TOL
    assert abs(v.zcg_mm - 1750.3799217829044) < TOL
    # grouped limits threaded through T1_PROFILE
    assert v.front_axle_limit_kg == 16000.0
    assert v.rear_axle_limit_kg == 20000.0
    assert v.gvw_limit_kg == 36000.0
    assert v.wheelbase_mm == 5250.0


@requires_wb
def test_theory_vehicle_cg():
    v = t1.vehicle_theory_t1()
    assert abs(v.gw_kg - 26042.9) < 1e-6
    assert abs(v.xcg_mm - 2843.9176311009905) < TOL
    assert abs(v.ycg_mm - 10.166663466818212) < TOL
    assert abs(v.zcg_mm - 1750.3799217829044) < TOL


@requires_wb
def test_measured_vehicle_reproduces_workbook_axle_loads():
    """The importer + engine reproduce the workbook's own axle split."""
    v = t1.vehicle_measured_t1()
    rep = run_mobility_analysis(v)
    assert abs(rep.axle.front_kg - 12625.0) < 0.5
    assert abs(rep.axle.rear_kg - 13550.0) < 0.5


@requires_wb
def test_stored_sf_map_measured():
    sf = t1.stored_sf_map_t1(variant="measured")
    assert abs(sf["asc_60"] - 2.4073834454365226) < TOL
    assert abs(sf["desc_60"] - 2.583765994904149) < TOL
    assert abs(sf["kerb_30"] - 1.9774906808241164) < TOL
    assert abs(sf["road_30"] - 2.027214817866116) < TOL
    assert abs(sf["corner"] - 3.601540982344649) < TOL


@requires_wb
def test_stored_sf_map_theory():
    sf = t1.stored_sf_map_t1(variant="theory")
    assert abs(sf["asc_60"] - 2.2874507940845428) < TOL
    assert abs(sf["desc_60"] - 2.7036986462561283) < TOL
    assert abs(sf["kerb_30"] - 2.0217406031969736) < TOL
    assert abs(sf["road_30"] - 1.9829648954932593) < TOL
    assert abs(sf["corner"] - 3.607274924989593) < TOL


@requires_wb
def test_engine_reproduces_stored_measured_sfs():
    """End-to-end: importer vehicle + SAR angle convention == stored SFs."""
    v = t1.vehicle_measured_t1()
    stored = t1.stored_sf_map_t1(variant="measured")
    kw = slope_kwargs_for(T1_PROFILE, "ascending", 60)
    assert abs(slope_stability(v, 60, "ascending", **kw).SF - stored["asc_60"]) < TOL
    kw2 = slope_kwargs_for(T1_PROFILE, "kerbside", 30)
    assert abs(side_slope_stability(v, 30, "kerbside", **kw2).SF - stored["kerb_30"]) < TOL


@requires_wb
def test_stored_axle_map():
    am = t1.stored_axle_map_t1(variant="measured")
    assert abs(am["front_kg"] - 12625.0) < TOL
    assert abs(am["rear_kg"] - 13550.0) < TOL
    at = t1.stored_axle_map_t1(variant="theory")
    assert abs(at["front_kg"] - 11935.497623809526) < TOL
    assert abs(at["rear_kg"] - 14107.402376190475) < TOL


@requires_wb
def test_shelter_components():
    comps = t1.shelter_components_t1()
    assert len(comps) == 75
    assert abs(sum(c.total_mass_kg for c in comps) - 10492.9) < 1e-3
    first = comps[0]
    assert "structure frame" in first.description.lower()
    assert abs(first.total_mass_kg - 2300.0) < 1e-6
    assert abs(first.x_mm - 3124.24) < 1e-2
    assert abs(first.z_mm - 922.03) < 1e-2


@requires_wb
def test_payload_cg_from_measured():
    """Reverse-CG: measured laden (26175) minus unladen transporter (16450)."""
    pl = t1.payload_cg_from_measured_t1()
    assert abs(pl.mass_kg - 9725.0) < 1e-6
    assert abs(pl.x_mm - 4021.850899742931) < TOL
    assert abs(pl.y_mm - (-62.08226221079726)) < TOL
    assert abs(pl.z_mm - 2821.752642947817) < TOL
