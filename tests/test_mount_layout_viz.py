"""Layer 1 mount-layout visualizer: lock the 'counts and dimensions are exact'
promise -- the entire reason this is parametric drawing, not diffusion.

No physics/network. A tiny stub stands in for a catalog.CatalogCandidate so the
axis-mapping test does not depend on the engine."""
from dataclasses import dataclass

import plotly.graph_objects as go
import pytest

import mount_layout_viz as mlv


# --------------------------------------------------------------- placement

class TestBottomPlacement:
    @pytest.mark.parametrize("n", [1, 4, 6, 8, 12])
    def test_exact_count(self, n):
        assert len(mlv.bottom_mount_positions(600, 400, n)) == n

    @pytest.mark.parametrize("n", [4, 6, 8])
    def test_all_points_on_perimeter(self, n):
        W, D = 600.0, 400.0
        for x, y in mlv.bottom_mount_positions(W, D, n):
            on_x_edge = x in (0.0, W)
            on_y_edge = y in (0.0, D)
            assert on_x_edge or on_y_edge, (x, y)
            assert 0.0 <= x <= W and 0.0 <= y <= D

    def test_four_mounts_are_corners(self):
        pts = set(mlv.bottom_mount_positions(600, 400, 4))
        assert pts == {(0.0, 0.0), (600.0, 0.0), (600.0, 400.0), (0.0, 400.0)}

    def test_zero_and_negative(self):
        assert mlv.bottom_mount_positions(600, 400, 0) == []
        with pytest.raises(ValueError):
            mlv.bottom_mount_positions(0, 400, 4)


class TestWallPlacement:
    @pytest.mark.parametrize("n", [1, 2, 4, 6])
    def test_exact_count(self, n):
        assert len(mlv.wall_mount_positions(600, 1200, n)) == n

    def test_row_at_constant_height(self):
        pts = mlv.wall_mount_positions(600, 1200, 4, height_frac=0.5)
        assert all(z == 600.0 for _, z in pts)
        xs = [a for a, _ in pts]
        assert xs == sorted(xs)  # left-to-right, evenly spaced

    @pytest.mark.parametrize("face", ["back", "front", "left", "right"])
    def test_3d_points_on_correct_face(self, face):
        W, D, H = 600.0, 400.0, 1200.0
        pts = mlv._wall_positions_3d(W, D, H, 4, face)
        assert len(pts) == 4
        for x, y, _z in pts:
            if face == "back":
                assert y == D
            elif face == "front":
                assert y == 0.0
            elif face == "left":
                assert x == 0.0
            else:
                assert x == W

    def test_bad_face_rejected(self):
        with pytest.raises(ValueError):
            mlv._wall_positions_3d(600, 400, 1200, 4, "diagonal")


# --------------------------------------------------------------- deflection map

@dataclass
class _Dir:
    delta_mm: float


@dataclass
class _Cand:
    comp_bottom: _Dir
    comp_wall: _Dir
    roll_wall: _Dir
    roll_bottom: _Dir


class TestAxisDeflections:
    def test_tuple_passthrough(self):
        assert mlv.axis_deflections((3.0, 5.0, 7.0)) == (3.0, 5.0, 7.0)

    def test_candidate_mapping(self):
        # comp_bottom=Z, comp_wall=Y, roll_wall=X&Z, roll_bottom=X&Y
        cand = _Cand(comp_bottom=_Dir(19.0), comp_wall=_Dir(22.0),
                     roll_wall=_Dir(8.0), roll_bottom=_Dir(6.0))
        dX, dY, dZ = mlv.axis_deflections(cand)
        assert dX == max(8.0, 6.0) == 8.0     # roll_wall vs roll_bottom
        assert dY == max(22.0, 6.0) == 22.0   # comp_wall vs roll_bottom
        assert dZ == max(19.0, 8.0) == 19.0   # comp_bottom vs roll_wall

    def test_bad_tuple_length(self):
        with pytest.raises(ValueError):
            mlv.axis_deflections((1.0, 2.0))


# --------------------------------------------------------------- clearance

class TestClearanceReport:
    def test_interference_when_sway_exceeds_clearance(self):
        rep = mlv.clearance_report((5.0, 22.0, 19.0), (30.0, 20.0, 40.0))
        assert rep["X"]["interference"] is False
        assert rep["Y"]["interference"] is True     # 22 > 20
        assert rep["Z"]["interference"] is False
        assert rep["Y"]["margin_mm"] == pytest.approx(-2.0)
        assert rep["X"]["margin_mm"] == pytest.approx(25.0)

    def test_no_limit_variants_never_interfere(self):
        rep = mlv.clearance_report((100.0, 100.0, 100.0),
                                   (None, 0.0, mlv.NO_CLEARANCE_MM))
        for axis in "XYZ":
            assert rep[axis]["interference"] is False
            assert rep[axis]["clearance_mm"] is None
            assert rep[axis]["margin_mm"] is None


# --------------------------------------------------------------- summary/figure

class TestLayoutSummary:
    def test_true_scale_envelope_extents(self):
        s = mlv.layout_summary(600, 400, 1200, 6, 4,
                               deflections=(5.0, 22.0, 19.0))
        env = s["movement_envelope_mm"]
        assert env["x"] == [-5.0, 605.0]      # box + 2*sway spread over both faces
        assert env["y"] == [-22.0, 422.0]
        assert env["z"] == [-19.0, 1219.0]

    def test_any_interference_flag(self):
        s = mlv.layout_summary(600, 400, 1200, 6, 4,
                               deflections=(5.0, 22.0, 19.0),
                               clearances=(30.0, 20.0, 40.0))
        assert s["any_interference"] is True
        assert len(s["bottom_positions_xy"]) == 6
        assert len(s["wall_positions_xyz"]) == 4


class TestBuildFigure:
    def test_returns_figure(self):
        fig = mlv.build_layout_figure(600, 400, 1200, 6, 4,
                                      deflections=(5.0, 22.0, 19.0))
        assert isinstance(fig, go.Figure)

    def test_marker_counts_survive_into_figure(self):
        fig = mlv.build_layout_figure(600, 400, 1200, 6, 4)
        bottom = next(t for t in fig.data if t.name.startswith("Bottom mounts"))
        wall = next(t for t in fig.data if t.name.startswith("Wall mounts"))
        assert len(bottom.x) == 6
        assert len(wall.x) == 4

    def test_interference_recolors_envelope_red(self):
        fig = mlv.build_layout_figure(600, 400, 1200, 6, 4,
                                      deflections=(5.0, 22.0, 19.0),
                                      clearances=(30.0, 20.0, 40.0))
        env = next(t for t in fig.data if t.name.startswith("Movement envelope"))
        assert env.line.color == "#d62728"
        assert "interference" in env.name.lower()

    def test_no_interference_envelope_green(self):
        fig = mlv.build_layout_figure(600, 400, 1200, 6, 4,
                                      deflections=(5.0, 5.0, 5.0),
                                      clearances=(30.0, 30.0, 30.0))
        env = next(t for t in fig.data if t.name.startswith("Movement envelope"))
        assert env.line.color == "#2ca02c"


class TestDeterminism:
    def test_positions_stable(self):
        a = mlv.bottom_mount_positions(637, 419, 6)
        b = mlv.bottom_mount_positions(637, 419, 6)
        assert a == b
