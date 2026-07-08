"""vehicle_cg_viz geometry lock: the drawn tip-line angles must equal the
engine's crit_angle_deg, CG markers must land at the exact vehicle coords, and
the mass-change overlay must plot the modified CG. If any of these drift the
picture would lie about the physics, so they are asserted, not eyeballed."""
import math

import plotly.graph_objects as go
import pytest

import vehicle_cg_viz as viz
from mobility_engine import Vehicle, slope_stability, side_slope_stability
from mobility_scenarios import MassChange, apply_mass_changes


def make_vehicle(**over):
    base = dict(name="test", gw_kg=17850.0, xcg_mm=2655.5, ycg_mm=20.5,
                zcg_mm=1617.8, wheelbase_mm=4800.0, track_mm=2088.0)
    base.update(over)
    return Vehicle(**base)


def trace(fig, name):
    return next(t for t in fig.data if t.name == name)


def line_angle_from_vertical(pivot_x, cg_x, cg_z):
    return math.degrees(math.atan(abs(cg_x - pivot_x) / cg_z))


# ------------------------------------------------------------- crit angles

def test_crit_angles_match_engine():
    v = make_vehicle()
    ca = viz.crit_angles(v)
    assert ca["ascending"] == pytest.approx(
        slope_stability(v, 60, "ascending").crit_angle_deg)
    assert ca["descending"] == pytest.approx(
        slope_stability(v, 60, "descending").crit_angle_deg)
    assert ca["kerbside"] == pytest.approx(
        side_slope_stability(v, 30, "kerbside").crit_angle_deg)
    assert ca["roadside"] == pytest.approx(
        side_slope_stability(v, 30, "roadside").crit_angle_deg)


# ------------------------------------------------------------- side view

class TestSideView:
    def test_returns_figure(self):
        assert isinstance(viz.side_view_figure(make_vehicle()), go.Figure)

    def test_cg_marker_at_vehicle_coords(self):
        v = make_vehicle()
        cg = trace(viz.side_view_figure(v), "cg_baseline")
        assert cg.x[0] == pytest.approx(v.xcg_mm)
        assert cg.y[0] == pytest.approx(v.zcg_mm)

    def test_ascending_tip_line_pivots_on_rear_contact(self):
        v = make_vehicle()
        t = trace(viz.side_view_figure(v), "tip_ascending")
        assert (t.x[0], t.y[0]) == pytest.approx((v.wheelbase_mm, 0.0))
        assert (t.x[1], t.y[1]) == pytest.approx((v.xcg_mm, v.zcg_mm))

    def test_descending_tip_line_pivots_on_front_contact(self):
        v = make_vehicle()
        t = trace(viz.side_view_figure(v), "tip_descending")
        assert (t.x[0], t.y[0]) == pytest.approx((0.0, 0.0))

    def test_tip_line_angles_equal_crit_angles(self):
        v = make_vehicle()
        ca = viz.crit_angles(v)
        asc = trace(viz.side_view_figure(v), "tip_ascending")
        des = trace(viz.side_view_figure(v), "tip_descending")
        assert line_angle_from_vertical(asc.x[0], asc.x[1], asc.y[1]) == \
            pytest.approx(ca["ascending"], abs=0.05)
        assert line_angle_from_vertical(des.x[0], des.x[1], des.y[1]) == \
            pytest.approx(ca["descending"], abs=0.05)

    def test_ground_and_two_wheels_present(self):
        fig = viz.side_view_figure(make_vehicle())
        assert any(t.name == "ground" for t in fig.data)
        assert sum(t.name == "wheel" for t in fig.data) == 2

    def test_equal_aspect_locked(self):
        fig = viz.side_view_figure(make_vehicle())
        assert fig.layout.yaxis.scaleanchor == "x"
        assert fig.layout.yaxis.scaleratio == 1


# ------------------------------------------------------------- rear view

class TestRearView:
    def test_cg_marker_uses_ycg(self):
        v = make_vehicle(ycg_mm=120.0)
        cg = trace(viz.rear_view_figure(v), "cg_baseline")
        assert cg.x[0] == pytest.approx(120.0)
        assert cg.y[0] == pytest.approx(v.zcg_mm)

    def test_kerbside_pivots_left_roadside_pivots_right(self):
        v = make_vehicle()
        half = v.track_mm / 2
        ker = trace(viz.rear_view_figure(v), "tip_kerbside")
        road = trace(viz.rear_view_figure(v), "tip_roadside")
        assert ker.x[0] == pytest.approx(-half)
        assert road.x[0] == pytest.approx(half)

    def test_tip_line_angles_equal_crit_angles(self):
        v = make_vehicle(ycg_mm=60.0)
        ca = viz.crit_angles(v)
        ker = trace(viz.rear_view_figure(v), "tip_kerbside")
        road = trace(viz.rear_view_figure(v), "tip_roadside")
        assert line_angle_from_vertical(ker.x[0], ker.x[1], ker.y[1]) == \
            pytest.approx(ca["kerbside"], abs=0.05)
        assert line_angle_from_vertical(road.x[0], road.x[1], road.y[1]) == \
            pytest.approx(ca["roadside"], abs=0.05)


# ------------------------------------------------------------- overlay

class TestMassChangeOverlay:
    def _modified(self, v):
        return apply_mass_changes(
            v, [MassChange("add", "genset", 300.0, new_xyz_mm=(4000, 0, 1500))])

    def test_no_overlay_without_modified(self):
        fig = viz.side_view_figure(make_vehicle())
        assert not any(t.name == "cg_modified" for t in fig.data)

    def test_side_overlay_plots_modified_cg(self):
        v = make_vehicle()
        m = self._modified(v)
        cg = trace(viz.side_view_figure(v, modified=m), "cg_modified")
        assert cg.x[0] == pytest.approx(m.xcg_mm)
        assert cg.y[0] == pytest.approx(m.zcg_mm)
        assert m.xcg_mm > v.xcg_mm       # 300 kg at X 4000 shifts CG aft

    def test_rear_overlay_plots_modified_cg(self):
        v = make_vehicle()
        m = self._modified(v)
        cg = trace(viz.rear_view_figure(v, modified=m), "cg_modified")
        assert cg.x[0] == pytest.approx(m.ycg_mm)
        assert cg.y[0] == pytest.approx(m.zcg_mm)


def test_determinism():
    v = make_vehicle()
    a = viz.side_view_figure(v)
    b = viz.side_view_figure(v)
    assert [(t.name, tuple(t.x or []), tuple(t.y or [])) for t in a.data] == \
           [(t.name, tuple(t.x or []), tuple(t.y or [])) for t in b.data]
