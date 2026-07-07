"""Deterministic mount-layout visualizer (Layer 1).

Turns a shock-mount configuration (box size, mount counts, per-axis dynamic
deflection, installation clearance) into an interactive 3D Plotly figure. Every
element is drawn from real numbers -- no generative model, so mount counts and
dimensions are exact by construction. The LLM's only future role is to CALL
`build_layout_figure` / `layout_summary`; it never draws.

Coordinate frame: box origin at (0, 0, 0), extents +X = width, +Y = depth,
+Z = height. Bottom face is z = 0. Wall faces are the four vertical faces; the
"back" wall is the +Y (depth-max) face by default.

Per-axis dynamic sway is mapped from the four shock load cases (see
`axis_deflections`). Pure module: no `streamlit`, no LLM imports.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence, Union

import plotly.graph_objects as go

# Mirrors physics_engine._NO_CLEARANCE_MM: the "no clearance limit" sentinel the
# UI substitutes when a clearance field is left at 0. Anything >= this is treated
# as "unconstrained" (no interference possible on that axis).
NO_CLEARANCE_MM = 1.0e9

WALL_FACES = ("back", "front", "left", "right")

# Axis colours (X, Y, Z) reused for axis lines and per-axis annotations.
_AXIS_COLORS = {"X": "#d62728", "Y": "#2ca02c", "Z": "#1f77b4"}


# ---------------------------------------------------------------------------
# Mount placement (even-perimeter)
# ---------------------------------------------------------------------------

def _distribute_extras(n_extra: int, edge_lengths: Sequence[float]) -> list[int]:
    """Largest-remainder allocation of `n_extra` interior points across edges,
    proportional to edge length (longer edges get more)."""
    total = sum(edge_lengths)
    exact = [n_extra * L / total for L in edge_lengths]
    base = [int(math.floor(e)) for e in exact]
    leftover = n_extra - sum(base)
    order = sorted(range(len(edge_lengths)),
                   key=lambda i: exact[i] - base[i], reverse=True)
    for i in range(leftover):
        base[order[i]] += 1
    return base


def bottom_mount_positions(width_mm: float, depth_mm: float,
                           n: int) -> list[tuple[float, float]]:
    """`n` mounts placed even-perimeter, corners first (z = 0).

    Convention: the four base corners are always populated first (n >= 4); any
    remaining mounts are distributed onto the edges proportional to edge length
    and spaced evenly within each edge. So n = 4 gives the four corners, n = 6
    adds the two long-edge midpoints, n = 8 adds one midpoint per edge -- the
    patterns a mechanical engineer expects for a rack base. Deterministic.
    """
    if n <= 0:
        return []
    if width_mm <= 0 or depth_mm <= 0:
        raise ValueError("width_mm and depth_mm must be positive")

    W, D = float(width_mm), float(depth_mm)
    corners = [(0.0, 0.0), (W, 0.0), (W, D), (0.0, D)]
    if n <= 4:
        return corners[:n]

    # Edges walked in perimeter order; each contributes its start corner plus
    # its share of interior points.
    edges = [((0.0, 0.0), (W, 0.0)),   # bottom  (y = 0)
             ((W, 0.0), (W, D)),       # right   (x = W)
             ((W, D), (0.0, D)),       # top     (y = D)
             ((0.0, D), (0.0, 0.0))]   # left    (x = 0)
    extras = _distribute_extras(n - 4, [W, D, W, D])

    pts: list[tuple[float, float]] = []
    for (start, end), k in zip(edges, extras):
        pts.append(start)
        for j in range(1, k + 1):
            t = j / (k + 1)
            pts.append((start[0] + (end[0] - start[0]) * t,
                        start[1] + (end[1] - start[1]) * t))
    return [(round(x, 6), round(y, 6)) for x, y in pts]


def wall_mount_positions(wall_span_mm: float, height_mm: float, n: int,
                         height_frac: float = 0.5) -> list[tuple[float, float]]:
    """`n` points in a single evenly-spaced row across a wall face.

    Returns (a, z) in the wall's own plane: `a` runs 0..wall_span_mm along the
    wall's width, `z` is a constant representative height (`height_frac` of the
    box height). The caller maps (a, z) into 3D for the specific face.
    Endpoints are inset by half a step so mounts sit on the face, not its edges.
    """
    if n <= 0:
        return []
    if wall_span_mm <= 0 or height_mm <= 0:
        raise ValueError("wall_span_mm and height_mm must be positive")
    z = height_frac * height_mm
    step = wall_span_mm / n
    return [(round((i + 0.5) * step, 6), round(z, 6)) for i in range(n)]


def _wall_positions_3d(width_mm: float, depth_mm: float, height_mm: float,
                       n: int, wall_face: str,
                       height_frac: float = 0.5) -> list[tuple[float, float, float]]:
    """Map wall-plane (a, z) points onto the chosen 3D face."""
    if wall_face not in WALL_FACES:
        raise ValueError(f"wall_face must be one of {WALL_FACES}, got {wall_face!r}")
    span = width_mm if wall_face in ("back", "front") else depth_mm
    flat = wall_mount_positions(span, height_mm, n, height_frac)
    out: list[tuple[float, float, float]] = []
    for a, z in flat:
        if wall_face == "back":     # +Y face
            out.append((a, depth_mm, z))
        elif wall_face == "front":  # -Y face
            out.append((a, 0.0, z))
        elif wall_face == "left":   # -X face
            out.append((0.0, a, z))
        else:                       # "right", +X face
            out.append((width_mm, a, z))
    return out


# ---------------------------------------------------------------------------
# Physics -> per-axis sway + clearance verdict
# ---------------------------------------------------------------------------

def axis_deflections(
    source: Union["object", Sequence[float]]
) -> tuple[float, float, float]:
    """Per-axis peak dynamic sway (dX, dY, dZ) in mm.

    Accepts either a 3-tuple `(dX, dY, dZ)` (passthrough, for tests/agent) or a
    `catalog.CatalogCandidate`, from which the mapping is:
        dX = max(roll_wall,  roll_bottom).delta_mm   (both shear act in X)
        dY = max(comp_wall,  roll_bottom).delta_mm
        dZ = max(comp_bottom, roll_wall).delta_mm
    following the direction labels in physics_engine (Z=Comp-Bottom, Y=Comp-Wall,
    X&Z=Roll-Wall, X&Y=Roll-Bottom).
    """
    if isinstance(source, (tuple, list)):
        if len(source) != 3:
            raise ValueError("deflections tuple must be (dX, dY, dZ)")
        return (float(source[0]), float(source[1]), float(source[2]))
    cb = source.comp_bottom.delta_mm
    cw = source.comp_wall.delta_mm
    rw = source.roll_wall.delta_mm
    rb = source.roll_bottom.delta_mm
    dX = max(rw, rb)
    dY = max(cw, rb)
    dZ = max(cb, rw)
    return (float(dX), float(dY), float(dZ))


def _clearance_or_none(value: Optional[float]) -> Optional[float]:
    """Normalize a clearance input: None / 0 / >= sentinel -> None (no limit)."""
    if value is None:
        return None
    v = float(value)
    if v <= 0.0 or v >= NO_CLEARANCE_MM:
        return None
    return v


def clearance_report(
    deflections: tuple[float, float, float],
    clearances: Sequence[Optional[float]],
) -> dict:
    """Per-axis interference verdict: sway vs installation clearance.

    Returns {axis: {sway_mm, clearance_mm, interference, margin_mm}}. An axis
    with no clearance limit reports interference=False and margin_mm=None. This
    is a NEW deterministic engineering output the drawing annotates and the
    future agent tool can return verbatim.
    """
    report: dict = {}
    for axis, sway, clr in zip("XYZ", deflections, clearances):
        c = _clearance_or_none(clr)
        if c is None:
            report[axis] = {"sway_mm": round(float(sway), 3),
                            "clearance_mm": None, "interference": False,
                            "margin_mm": None}
        else:
            report[axis] = {"sway_mm": round(float(sway), 3),
                            "clearance_mm": round(c, 3),
                            "interference": float(sway) > c,
                            "margin_mm": round(c - float(sway), 3)}
    return report


def layout_summary(
    width_mm: float, depth_mm: float, height_mm: float,
    n_bottom: int, n_wall: int,
    deflections: Union["object", Sequence[float]] = (0.0, 0.0, 0.0),
    clearances: Sequence[Optional[float]] = (None, None, None),
    wall_face: str = "back",
) -> dict:
    """Structured, plotly-free description of the layout. Agent-tool ready."""
    d = axis_deflections(deflections)
    bottoms = bottom_mount_positions(width_mm, depth_mm, n_bottom)
    walls = _wall_positions_3d(width_mm, depth_mm, height_mm, n_wall, wall_face)
    clr = clearance_report(d, clearances)
    return {
        "box_mm": {"width": width_mm, "depth": depth_mm, "height": height_mm},
        "n_bottom": n_bottom, "n_wall": n_wall, "wall_face": wall_face,
        "bottom_positions_xy": bottoms,
        "wall_positions_xyz": walls,
        "sway_mm": {"X": d[0], "Y": d[1], "Z": d[2]},
        "clearance": clr,
        "any_interference": any(v["interference"] for v in clr.values()),
        "movement_envelope_mm": {
            "x": [-d[0], width_mm + d[0]],
            "y": [-d[1], depth_mm + d[1]],
            "z": [-d[2], height_mm + d[2]],
        },
    }


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def _box_edges(x0, y0, z0, x1, y1, z1):
    """8 corners + the 12-edge polyline (with None breaks) for a wire box."""
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
             (0, 4), (1, 5), (2, 6), (3, 7)]
    xs, ys, zs = [], [], []
    for a, b in edges:
        xs += [c[a][0], c[b][0], None]
        ys += [c[a][1], c[b][1], None]
        zs += [c[a][2], c[b][2], None]
    return xs, ys, zs


def build_layout_figure(
    width_mm: float, depth_mm: float, height_mm: float,
    n_bottom: int, n_wall: int,
    *,
    deflections: Union["object", Sequence[float]] = (0.0, 0.0, 0.0),
    clearances: Sequence[Optional[float]] = (None, None, None),
    wall_face: str = "back",
    envelope_scale: float = 1.0,
    title: Optional[str] = None,
) -> go.Figure:
    """Interactive 3D layout: equipment box, mount markers, axes, and the
    dynamic-sway / clearance envelopes. Marker counts equal `n_bottom` /
    `n_wall` exactly. `envelope_scale` != 1.0 exaggerates the sway box for
    visibility and is called out in the title so it can't mislead."""
    d = axis_deflections(deflections)
    clr = clearance_report(d, clearances)
    interfered = clr  # alias for readability
    any_interf = any(v["interference"] for v in clr.values())

    fig = go.Figure()

    # (a) equipment box
    ex, ey, ez = _box_edges(0, 0, 0, width_mm, depth_mm, height_mm)
    fig.add_trace(go.Scatter3d(
        x=ex, y=ey, z=ez, mode="lines", name="Equipment box",
        line=dict(color="#333", width=4), hoverinfo="skip"))

    # (b) bottom mounts
    bottoms = bottom_mount_positions(width_mm, depth_mm, n_bottom)
    if bottoms:
        bx, by = zip(*bottoms)
        fig.add_trace(go.Scatter3d(
            x=list(bx), y=list(by), z=[0.0] * len(bottoms),
            mode="markers", name=f"Bottom mounts ({n_bottom})",
            marker=dict(size=6, color="#1f77b4", symbol="square"),
            hovertemplate="bottom mount<br>x=%{x:.0f} y=%{y:.0f} mm<extra></extra>"))

    # (c) wall mounts
    walls = _wall_positions_3d(width_mm, depth_mm, height_mm, n_wall, wall_face)
    if walls:
        wx, wy, wz = zip(*walls)
        fig.add_trace(go.Scatter3d(
            x=list(wx), y=list(wy), z=list(wz),
            mode="markers", name=f"Wall mounts ({n_wall}, {wall_face})",
            marker=dict(size=6, color="#ff7f0e", symbol="diamond"),
            hovertemplate="wall mount<br>x=%{x:.0f} y=%{y:.0f} z=%{z:.0f} mm<extra></extra>"))

    # (d) coordinate axes through the origin, sized to the box
    axis_len = 1.15 * max(width_mm, depth_mm, height_mm)
    for axis, (dx, dy, dz) in {"X": (axis_len, 0, 0), "Y": (0, axis_len, 0),
                               "Z": (0, 0, axis_len)}.items():
        fig.add_trace(go.Scatter3d(
            x=[0, dx], y=[0, dy], z=[0, dz], mode="lines+text",
            line=dict(color=_AXIS_COLORS[axis], width=3),
            text=["", axis], textposition="top center",
            name=f"{axis} axis", hoverinfo="skip", showlegend=False))

    # (e) movement (sway) envelope: box grown by +/- sway per axis
    s = envelope_scale
    mx, my, mz = _box_edges(-d[0] * s, -d[1] * s, -d[2] * s,
                            width_mm + d[0] * s, depth_mm + d[1] * s,
                            height_mm + d[2] * s)
    env_color = "#d62728" if any_interf else "#2ca02c"
    fig.add_trace(go.Scatter3d(
        x=mx, y=my, z=mz, mode="lines",
        name="Movement envelope" + (" (interference!)" if any_interf else ""),
        line=dict(color=env_color, width=3, dash="dot"), hoverinfo="skip"))

    # (f) clearance envelope: only on axes with a real clearance limit
    def _cval(axis, default):
        v = clr[axis]["clearance_mm"]
        return v if v is not None else default
    has_clr = any(clr[a]["clearance_mm"] is not None for a in "XYZ")
    if has_clr:
        cx = _cval("X", d[0]); cy = _cval("Y", d[1]); cz = _cval("Z", d[2])
        gx, gy, gz = _box_edges(-cx, -cy, -cz,
                                width_mm + cx, depth_mm + cy, height_mm + cz)
        fig.add_trace(go.Scatter3d(
            x=gx, y=gy, z=gz, mode="lines", name="Clearance envelope",
            line=dict(color="#7f7f7f", width=2), opacity=0.6, hoverinfo="skip"))

    # (g) per-axis sway/clearance annotation
    lines = []
    for axis in "XYZ":
        r = clr[axis]
        seg = f"{axis}: sway {r['sway_mm']:.1f} mm"
        if r["clearance_mm"] is not None:
            mark = "INTERFERENCE" if r["interference"] else "ok"
            seg += f" / clr {r['clearance_mm']:.0f} mm [{mark}]"
        lines.append(seg)
    note = "  |  ".join(lines)
    if s != 1.0:
        note += f"  (envelope x{s:g} for visibility)"

    if title is None:
        title = f"Mount layout: {n_bottom} bottom + {n_wall} wall"
    fig.update_layout(
        title=dict(text=title, x=0.5),
        scene=dict(
            xaxis_title="X / width (mm)", yaxis_title="Y / depth (mm)",
            zaxis_title="Z / height (mm)", aspectmode="data"),
        margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=-0.08),
        annotations=[dict(text=note, showarrow=False, xref="paper", yref="paper",
                          x=0.5, y=0, font=dict(size=11))],
    )
    return fig
