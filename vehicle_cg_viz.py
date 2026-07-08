"""Deterministic vehicle CG / stability visualizer for the mobility tab.

Two orthographic views drawn straight from a `mobility_engine.Vehicle`:

  - side_view_figure  (X-Z): longitudinal tip geometry. Wheels on the ground,
    CG dot at (xcg, zcg), and the two tip lines from each wheel contact to the
    CG whose angles ARE the engine's ascending / descending crit_angle_deg.
  - rear_view_figure  (Y-Z): lateral tip geometry. Track, CG at (ycg, zcg),
    kerbside / roadside tip lines.

Every mark is computed; no model draws anything. Crit angles are read back
from the engine (slope_stability / side_slope_stability) so this module can
never drift from the physics. An optional `modified` Vehicle overlays a
before -> after CG shift (the mass-change / relocation what-if).

Pure module: no streamlit, no LLM. Returns plotly figures.

Coordinate datum (matches mobility_engine.Vehicle):
  X longitudinal, mm from FRONT axle, +rearward
  Y lateral, mm from centreline, +driverside / right
  Z vertical, mm above ground
"""
from __future__ import annotations

import math
from typing import Optional

import plotly.graph_objects as go

from mobility_engine import (
    Vehicle, side_slope_stability, slope_stability,
)

BASELINE_COLOR = "#2a78d6"   # blue  (dataviz categorical slot 1)
MODIFIED_COLOR = "#d85a30"   # coral (change / after)
STRUCT_COLOR = "#888780"     # muted gray, identical in light & dark
GRID_COLOR = "rgba(136,135,128,0.25)"


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def crit_angles(v: Vehicle) -> dict:
    """The four tip-over critical angles (deg), read from the engine so the
    drawing and the safety-factor math share one source of truth. Grade does
    not affect crit_angle_deg, so a placeholder grade is fine."""
    return {
        "ascending":  slope_stability(v, 60.0, "ascending").crit_angle_deg,
        "descending": slope_stability(v, 60.0, "descending").crit_angle_deg,
        "kerbside":   side_slope_stability(v, 30.0, "kerbside").crit_angle_deg,
        "roadside":   side_slope_stability(v, 30.0, "roadside").crit_angle_deg,
    }


def _circle(cx: float, cz: float, r: float, n: int = 48):
    """Closed polyline approximating a circle, for a plotly line trace."""
    xs = [cx + r * math.cos(2 * math.pi * i / n) for i in range(n + 1)]
    zs = [cz + r * math.sin(2 * math.pi * i / n) for i in range(n + 1)]
    return xs, zs


def _wheel(fig: go.Figure, cx: float, cz: float, r: float):
    xs, zs = _circle(cx, cz, r)
    fig.add_trace(go.Scatter(
        x=xs, y=zs, mode="lines", line=dict(color=STRUCT_COLOR, width=2),
        hoverinfo="skip", showlegend=False, name="wheel"))


def _dim_line(fig: go.Figure, x0, x1, z, label):
    """A horizontal dimension line with end ticks and a centered label."""
    fig.add_trace(go.Scatter(
        x=[x0, x1], y=[z, z], mode="lines",
        line=dict(color=STRUCT_COLOR, width=1),
        hoverinfo="skip", showlegend=False, name="dim"))
    for x in (x0, x1):
        fig.add_trace(go.Scatter(
            x=[x, x], y=[z - r_tick(z), z + r_tick(z)], mode="lines",
            line=dict(color=STRUCT_COLOR, width=1),
            hoverinfo="skip", showlegend=False, name="dim_tick"))
    fig.add_annotation(x=(x0 + x1) / 2, y=z, text=label, showarrow=False,
                       yshift=-12, font=dict(color=STRUCT_COLOR, size=12))


def r_tick(z: float) -> float:
    return 40.0  # fixed tick half-height in mm; views are equal-aspect


def _cg_marker(fig: go.Figure, x: float, z: float, color: str, name: str,
               label: Optional[str] = None):
    fig.add_trace(go.Scatter(
        x=[x], y=[z], mode="markers", name=name,
        marker=dict(size=12, color=color, line=dict(color="white", width=1.5)),
        hovertemplate=f"{name}<br>%{{x:.0f}}, %{{y:.0f}} mm<extra></extra>"))
    if label:
        fig.add_annotation(x=x, y=z, text=label, showarrow=False, yshift=16,
                           font=dict(color=color, size=12))


def _tip_line(fig: go.Figure, pivot_x: float, cg_x: float, cg_z: float,
              angle_deg: float, name: str, label_side: str):
    fig.add_trace(go.Scatter(
        x=[pivot_x, cg_x], y=[0.0, cg_z], mode="lines",
        line=dict(color=BASELINE_COLOR, width=1.5, dash="dash"),
        hoverinfo="skip", showlegend=False, name=name))
    mx, mz = (pivot_x + cg_x) / 2, cg_z / 2
    xshift = 46 if label_side == "right" else -46
    fig.add_annotation(x=mx, y=mz, text=f"{angle_deg:.1f}°",
                       showarrow=False, xshift=xshift,
                       font=dict(color=BASELINE_COLOR, size=12))


def _overlay_shift(fig: go.Figure, x0, z0, x1, z1, delta_label: str):
    """Baseline -> modified CG shift: an arrow plus a delta annotation."""
    fig.add_annotation(x=x1, y=z1, ax=x0, ay=z0, xref="x", yref="y",
                       axref="x", ayref="y", showarrow=True, arrowhead=3,
                       arrowwidth=2, arrowcolor=MODIFIED_COLOR, text="")
    fig.add_annotation(x=x1, y=z1, text=delta_label, showarrow=False,
                       yshift=-16, font=dict(color=MODIFIED_COLOR, size=12))


def _finalize(fig: go.Figure, xr, zr, title: str):
    fig.update_layout(
        title=dict(text=title, x=0.5, font=dict(size=14)),
        showlegend=False, margin=dict(l=8, r=8, t=40, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=xr, zeroline=False, showgrid=True, gridcolor=GRID_COLOR,
                   title="", constrain="domain"),
        yaxis=dict(range=zr, zeroline=False, showgrid=True, gridcolor=GRID_COLOR,
                   title="", scaleanchor="x", scaleratio=1),
    )
    return fig


def _ground(fig: go.Figure, x0: float, x1: float):
    fig.add_trace(go.Scatter(
        x=[x0, x1], y=[0.0, 0.0], mode="lines",
        line=dict(color=STRUCT_COLOR, width=2),
        hoverinfo="skip", showlegend=False, name="ground"))


# ---------------------------------------------------------------------------
# Side view (X-Z): longitudinal tip geometry
# ---------------------------------------------------------------------------

def side_view_figure(vehicle: Vehicle,
                     modified: Optional[Vehicle] = None) -> go.Figure:
    v = vehicle
    r = v.rstat_mm
    wb = v.wheelbase_mm
    ca = crit_angles(v)
    fig = go.Figure()

    pad = 0.18 * wb
    _ground(fig, -pad, wb + pad)
    _wheel(fig, 0.0, r, r)              # front axle at X = 0
    _wheel(fig, wb, r, r)              # rear axle at X = wheelbase
    # schematic chassis line at hub height, purely for grounding the eye
    fig.add_trace(go.Scatter(
        x=[0.0, wb], y=[r, r], mode="lines",
        line=dict(color=STRUCT_COLOR, width=1, dash="dot"),
        hoverinfo="skip", showlegend=False, name="chassis"))

    # Tip lines: ascending pivots on the REAR contact, descending on the FRONT.
    _tip_line(fig, wb, v.xcg_mm, v.zcg_mm, ca["ascending"],
              "tip_ascending", "left")
    _tip_line(fig, 0.0, v.xcg_mm, v.zcg_mm, ca["descending"],
              "tip_descending", "right")

    _cg_marker(fig, v.xcg_mm, v.zcg_mm, BASELINE_COLOR, "cg_baseline", "CG")

    top = v.zcg_mm + r
    _dim_line(fig, 0.0, wb, -0.5 * r, f"wheelbase {wb:,.0f} mm")

    if modified is not None:
        _cg_marker(fig, modified.xcg_mm, modified.zcg_mm, MODIFIED_COLOR,
                   "cg_modified")
        dx = modified.xcg_mm - v.xcg_mm
        dz = modified.zcg_mm - v.zcg_mm
        _overlay_shift(fig, v.xcg_mm, v.zcg_mm, modified.xcg_mm,
                       modified.zcg_mm,
                       f"X {dx:+.0f} / Z {dz:+.0f} mm")
        top = max(top, modified.zcg_mm + r)

    xr = [-pad, wb + pad]
    zr = [-1.1 * r, 1.35 * top]
    return _finalize(fig, xr, zr,
                     "Side view (X–Z): longitudinal tip geometry")


# ---------------------------------------------------------------------------
# Rear view (Y-Z): lateral tip geometry
# ---------------------------------------------------------------------------

def rear_view_figure(vehicle: Vehicle,
                     modified: Optional[Vehicle] = None) -> go.Figure:
    v = vehicle
    r = v.rstat_mm
    half = v.track_mm / 2
    ca = crit_angles(v)
    fig = go.Figure()

    pad = 0.30 * v.track_mm
    _ground(fig, -half - pad, half + pad)
    _wheel(fig, -half, r, r)          # left wheel  (-track/2)
    _wheel(fig, half, r, r)           # right wheel (+track/2)
    fig.add_trace(go.Scatter(
        x=[-half, half], y=[r, r], mode="lines",
        line=dict(color=STRUCT_COLOR, width=1, dash="dot"),
        hoverinfo="skip", showlegend=False, name="chassis"))

    # kerbside pivots on the LEFT contact, roadside on the RIGHT contact.
    _tip_line(fig, -half, v.ycg_mm, v.zcg_mm, ca["kerbside"],
              "tip_kerbside", "left")
    _tip_line(fig, half, v.ycg_mm, v.zcg_mm, ca["roadside"],
              "tip_roadside", "right")

    _cg_marker(fig, v.ycg_mm, v.zcg_mm, BASELINE_COLOR, "cg_baseline",
               f"CG (Ycg {v.ycg_mm:+.0f})")

    top = v.zcg_mm + r
    _dim_line(fig, -half, half, -0.5 * r, f"track {v.track_mm:,.0f} mm")

    if modified is not None:
        _cg_marker(fig, modified.ycg_mm, modified.zcg_mm, MODIFIED_COLOR,
                   "cg_modified")
        dy = modified.ycg_mm - v.ycg_mm
        dz = modified.zcg_mm - v.zcg_mm
        _overlay_shift(fig, v.ycg_mm, v.zcg_mm, modified.ycg_mm,
                       modified.zcg_mm,
                       f"Y {dy:+.0f} / Z {dz:+.0f} mm")
        top = max(top, modified.zcg_mm + r)

    xr = [-half - pad, half + pad]
    zr = [-1.1 * r, 1.35 * top]
    return _finalize(fig, xr, zr,
                     "Rear view (Y–Z): lateral tip geometry")
