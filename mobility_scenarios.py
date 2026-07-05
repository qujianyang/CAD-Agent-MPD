"""
Pure scenario-construction layer for mobility analysis.

Builds a validated `mobility_engine.Vehicle` from any of the supported
vehicle-state sources, so every scenario feeds the SAME derived Vehicle
into the axle / slope / cornering physics:

  1. Workbook baseline        -- mobility_import.vehicle_measured / vehicle_theory
  2. Wheel-load measurement   -- vehicle_from_wheel_loads()  (this module)
  3. Design / modification    -- apply_mass_changes()        (this module)
  4. Advanced certified CG    -- vehicle_from_certified_cg() (this module)

Coordinate datum (matches mobility_engine.Vehicle):
  X : longitudinal, mm from FRONT axle, positive rearward
  Y : lateral, mm from vehicle centreline, positive toward DRIVERSIDE / RIGHT
  Z : vertical, mm above GROUND

Wheel-load CG derivation (SAR Appendix B method):
  GW  = FL + FR + RL + RR
  Xcg = WB * (RL + RR) / GW
  Ycg = Track * ((FR + RR) / GW - 0.5)      # right side heavier -> +Ycg
  Zcg cannot be derived from static wheel loads; the caller must supply a
  verified value with a provenance label (tilt test / CAD model / certified
  report).

No Streamlit, no I/O. Validation policy:
  - Physically impossible inputs raise ValueError (reject).
  - Unusual-but-possible CG positions only produce warnings
    (check_cg_plausibility) -- never rejected here.

This module does NOT contain physics. SF / axle / cornering math lives in
mobility_engine.py and is validated against the Spinel-E2 workbook.
"""

import math
from dataclasses import dataclass, replace
from typing import List, Optional, Sequence, Tuple

from mobility_engine import Vehicle

# ---------------------------------------------------------------------------
# Defaults (Spinel E2 vendor limits -- same values as Vehicle dataclass)
# ---------------------------------------------------------------------------

DEFAULT_FRONT_AXLE_LIMIT_KG = 8000.0
DEFAULT_REAR_AXLE_LIMIT_KG = 10600.0
DEFAULT_GVW_LIMIT_KG = 18600.0
DEFAULT_RSTAT_MM = 580.0

# Longitudinal offset from the FRONT AXLE to the front ISO twist-lock PLANE
# (E2 report). Engineers measure component positions rearward from the ISO
# plane; the mobility engine keeps its front-axle datum, so UI/tool layers
# convert with iso_x_to_axle_x() before calling apply_mass_changes().
FRONT_AXLE_TO_ISO_PLANE_MM = 1450.0

# Accepted provenance labels for a user-supplied Zcg (any non-empty string is
# allowed; these are the recommended choices the UI should offer).
ZCG_SOURCES = ("tilt test", "CAD model", "certified report")

_ACTIONS = ("add", "remove", "relocate")

# OEM recommended safety-factor margins (defaults for the Spinel E2 workflow;
# UI may let the user override them, source: SAR mobility appendices).
OEM_MARGIN_LONGITUDINAL = 2.0
OEM_MARGIN_LATERAL = 2.2
OEM_MARGIN_CORNERING = 2.2

# Three-tier verdict labels (plain ASCII)
VERDICT_UNSTABLE = "UNSTABLE"
VERDICT_BELOW = "STABLE, BELOW RECOMMENDED MARGIN"
VERDICT_MEETS = "MEETS RECOMMENDED MARGIN"

# Top-priority compliance verdict: an axle / GVW / steerability failure outranks every
# stability verdict -- an overloaded vehicle is non-compliant regardless of slope SFs.
# Distinct from UNSTABLE because "over axle limit" and "will tip" are different failure
# modes with different fixes (remove/move weight vs lower the CG).
VERDICT_STRUCTURAL = "FAILS STRUCTURAL LIMITS (axle/GVW/steer)"


def sf_verdict(sf: float, oem_margin: float) -> str:
    """
    Map a safety factor to the three-tier verdict:
      SF < 1.0           -> UNSTABLE
      1.0 <= SF < margin -> STABLE, BELOW RECOMMENDED MARGIN
      SF >= margin       -> MEETS RECOMMENDED MARGIN
    """
    if oem_margin < 1.0:
        raise ValueError(f"OEM margin must be >= 1.0, got {oem_margin}")
    if sf < 1.0:
        return VERDICT_UNSTABLE
    if sf < oem_margin:
        return VERDICT_BELOW
    return VERDICT_MEETS


def margin_for_direction(direction: str,
                         long_margin: float = OEM_MARGIN_LONGITUDINAL,
                         lat_margin: float = OEM_MARGIN_LATERAL) -> float:
    """OEM margin applicable to a slope-result direction."""
    if direction in ("ascending", "descending"):
        return long_margin
    if direction in ("kerbside", "roadside"):
        return lat_margin
    raise ValueError(f"unknown slope direction {direction!r}")


# ---------------------------------------------------------------------------
# Internal validation helpers
# ---------------------------------------------------------------------------

def _require_positive(value: float, label: str) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number, got {value!r}")
    if value <= 0:
        raise ValueError(f"{label} must be positive, got {value}")
    return value


def _require_label(text: Optional[str], label: str) -> str:
    if text is None or not str(text).strip():
        raise ValueError(f"{label} is required (got empty value)")
    return str(text).strip()


# ---------------------------------------------------------------------------
# Use case 2: wheel-load measurement
# ---------------------------------------------------------------------------

def vehicle_from_wheel_loads(
    fl_kg: float,
    fr_kg: float,
    rl_kg: float,
    rr_kg: float,
    wheelbase_mm: float,
    track_mm: float,
    zcg_mm: float,
    zcg_source: str,
    name: str = "Wheel-load derived",
    rstat_mm: float = DEFAULT_RSTAT_MM,
    front_axle_limit_kg: float = DEFAULT_FRONT_AXLE_LIMIT_KG,
    rear_axle_limit_kg: float = DEFAULT_REAR_AXLE_LIMIT_KG,
    gvw_limit_kg: float = DEFAULT_GVW_LIMIT_KG,
) -> Vehicle:
    """
    Derive a Vehicle from four measured wheel loads (kg).

    Xcg/Ycg follow the SAR Appendix B moment balance. Zcg must be a verified
    value supplied by the caller together with a non-empty `zcg_source`
    provenance label (e.g. one of ZCG_SOURCES).

    Raises ValueError on non-positive loads/dimensions or missing source.
    """
    fl = _require_positive(fl_kg, "FL wheel load")
    fr = _require_positive(fr_kg, "FR wheel load")
    rl = _require_positive(rl_kg, "RL wheel load")
    rr = _require_positive(rr_kg, "RR wheel load")
    wb = _require_positive(wheelbase_mm, "wheelbase")
    tr = _require_positive(track_mm, "track")
    z = _require_positive(zcg_mm, "Zcg")
    src = _require_label(zcg_source, "Zcg source")

    gw = fl + fr + rl + rr
    xcg = wb * (rl + rr) / gw
    ycg = tr * ((fr + rr) / gw - 0.5)   # +toward driverside/right

    return Vehicle(
        name=f"{name} (Zcg: {src})",
        gw_kg=gw,
        xcg_mm=xcg,
        ycg_mm=ycg,
        zcg_mm=z,
        wheelbase_mm=wb,
        track_mm=tr,
        rstat_mm=rstat_mm,
        front_axle_limit_kg=front_axle_limit_kg,
        rear_axle_limit_kg=rear_axle_limit_kg,
        gvw_limit_kg=gvw_limit_kg,
    )


# ---------------------------------------------------------------------------
# Use case 2b: four-axle (T1) wheel-load measurement
#
# The T1 is an 8x8 with four axles; the validated two-support-line engine
# treats axles 1+2 as the "front axle" and 3+4 as the "rear axle". This layer
# collapses eight measured left/right wheel-group loads into that two-group
# model and derives the same Vehicle the workbook uses, while retaining the
# per-axle and per-side totals for UI explanation.
#
#   front_group = axle1 + axle2 ;  rear_group = axle3 + axle4
#   GW  = sum of all eight loads
#   Xcg = wheelbase * rear_group / GW          (moment about the front group)
#   Ycg = track * (right_side / GW - 0.5)      (+toward driverside / right)
# ---------------------------------------------------------------------------

# T1 vendor grouped limits (mobility_profiles.T1_PROFILE); kept here so this
# module has no import cycle with the profile layer.
DEFAULT_T1_FRONT_GROUP_LIMIT_KG = 16000.0
DEFAULT_T1_REAR_GROUP_LIMIT_KG = 20000.0
DEFAULT_T1_GVW_LIMIT_KG = 36000.0


@dataclass(frozen=True)
class FourAxleWheelLoadSummary:
    """Derived Vehicle plus the per-axle / per-side breakdown that produced it."""
    vehicle: Vehicle
    axle_totals_kg: Tuple[float, float, float, float]
    front_group_left_kg: float
    front_group_right_kg: float
    rear_group_left_kg: float
    rear_group_right_kg: float
    front_group_kg: float
    rear_group_kg: float
    left_side_kg: float
    right_side_kg: float


def derive_4axle_wheel_load_summary(
    a1_left_kg: float,
    a1_right_kg: float,
    a2_left_kg: float,
    a2_right_kg: float,
    a3_left_kg: float,
    a3_right_kg: float,
    a4_left_kg: float,
    a4_right_kg: float,
    wheelbase_mm: float,
    track_mm: float,
    zcg_mm: float,
    zcg_source: str,
    name: str = "4-axle wheel-load derived",
    rstat_mm: float = DEFAULT_RSTAT_MM,
    front_group_limit_kg: float = DEFAULT_T1_FRONT_GROUP_LIMIT_KG,
    rear_group_limit_kg: float = DEFAULT_T1_REAR_GROUP_LIMIT_KG,
    gvw_limit_kg: float = DEFAULT_T1_GVW_LIMIT_KG,
) -> FourAxleWheelLoadSummary:
    """
    Collapse eight T1 wheel-group loads (kg) into the two-support-line Vehicle.

    Zcg cannot be derived from static wheel loads; the caller must supply a
    verified value with a non-empty `zcg_source` provenance label. Raises
    ValueError on any non-positive load/dimension or a missing source.
    """
    a1l = _require_positive(a1_left_kg, "axle1 left load")
    a1r = _require_positive(a1_right_kg, "axle1 right load")
    a2l = _require_positive(a2_left_kg, "axle2 left load")
    a2r = _require_positive(a2_right_kg, "axle2 right load")
    a3l = _require_positive(a3_left_kg, "axle3 left load")
    a3r = _require_positive(a3_right_kg, "axle3 right load")
    a4l = _require_positive(a4_left_kg, "axle4 left load")
    a4r = _require_positive(a4_right_kg, "axle4 right load")
    wb = _require_positive(wheelbase_mm, "wheelbase")
    tr = _require_positive(track_mm, "track")
    z = _require_positive(zcg_mm, "Zcg")
    src = _require_label(zcg_source, "Zcg source")

    front_left = a1l + a2l
    front_right = a1r + a2r
    rear_left = a3l + a4l
    rear_right = a3r + a4r
    front_group = front_left + front_right
    rear_group = rear_left + rear_right
    left_side = front_left + rear_left
    right_side = front_right + rear_right
    gw = front_group + rear_group

    xcg = wb * rear_group / gw
    ycg = tr * (right_side / gw - 0.5)   # +toward driverside/right

    vehicle = Vehicle(
        name=f"{name} (Zcg: {src})",
        gw_kg=gw, xcg_mm=xcg, ycg_mm=ycg, zcg_mm=z,
        wheelbase_mm=wb, track_mm=tr, rstat_mm=rstat_mm,
        front_axle_limit_kg=front_group_limit_kg,
        rear_axle_limit_kg=rear_group_limit_kg,
        gvw_limit_kg=gvw_limit_kg,
    )
    return FourAxleWheelLoadSummary(
        vehicle=vehicle,
        axle_totals_kg=(a1l + a1r, a2l + a2r, a3l + a3r, a4l + a4r),
        front_group_left_kg=front_left, front_group_right_kg=front_right,
        rear_group_left_kg=rear_left, rear_group_right_kg=rear_right,
        front_group_kg=front_group, rear_group_kg=rear_group,
        left_side_kg=left_side, right_side_kg=right_side,
    )


def vehicle_from_4axle_wheel_loads(**kwargs) -> Vehicle:
    """Convenience: the derived Vehicle only (see derive_4axle_wheel_load_summary)."""
    return derive_4axle_wheel_load_summary(**kwargs).vehicle


# ---------------------------------------------------------------------------
# Tilt-test Zcg derivation (four-test SAR method)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TiltTestResult:
    """One inclined-platform test: the inputs and the Zcg it implies."""
    angle_deg: float
    rear_load_kg: float
    zcg_mm: float


def zcg_from_tilt_tests(
    f_level_kg: float,
    gw_kg: float,
    wheelbase_mm: float,
    tests: Sequence[Tuple[float, float]],
    wheel_radius_mm: float = DEFAULT_RSTAT_MM,
) -> Tuple[List[TiltTestResult], float]:
    """
    Derive Zcg from inclined-platform (tilt) tests.

    Tilting the vehicle nose-up by theta shifts load onto the rear axle in
    proportion to the CG height above the wheel centres:

        Z_i = (F_i - F_level) * WB / (GW * tan(theta_i)) + R

    (divide by tan(theta) -- a steeper tilt needs LESS load shift for the
    same CG height). R adds back the wheel radius because the moment balance
    works about the axle centreline while Zcg is measured from the ground.

    Args:
        f_level_kg     : rear-axle load on level ground (RL + RR). Named
                         f_level (not FL) -- FL means front-left wheel load.
        gw_kg          : gross vehicle weight (kg).
        wheelbase_mm   : wheelbase (mm).
        tests          : sequence of (angle_deg, inclined_rear_load_kg).
        wheel_radius_mm: static wheel radius (mm), default 580.

    Returns (per-test TiltTestResult list in input order, average Zcg in mm).
    Raises ValueError on non-positive scalars, an empty test list, angles
    outside (0, 90) degrees, or non-positive rear loads.
    """
    f_level = _require_positive(f_level_kg, "f_level_kg (level rear-axle load)")
    gw = _require_positive(gw_kg, "GW")
    wb = _require_positive(wheelbase_mm, "wheelbase")
    r = _require_positive(wheel_radius_mm, "wheel radius")
    if not tests:
        raise ValueError("at least one tilt test (angle, rear load) is required")

    results: List[TiltTestResult] = []
    for i, (angle_deg, rear_load_kg) in enumerate(tests):
        tag = f"tilt test #{i + 1}"
        angle = float(angle_deg)
        if not (0.0 < angle < 90.0):
            raise ValueError(f"{tag}: angle must be between 0 and 90 degrees "
                             f"(exclusive), got {angle}")
        f_i = _require_positive(rear_load_kg, f"{tag}: inclined rear load")
        z = (f_i - f_level) * wb / (gw * math.tan(math.radians(angle))) + r
        results.append(TiltTestResult(angle_deg=angle_deg,
                                      rear_load_kg=rear_load_kg,
                                      zcg_mm=z))

    avg = sum(t.zcg_mm for t in results) / len(results)
    return results, avg


# ---------------------------------------------------------------------------
# ISO twist-lock plane datum conversion
# ---------------------------------------------------------------------------

def iso_x_to_axle_x(x_iso_mm: float) -> float:
    """Component X from the front ISO twist-lock plane -> X from the front axle."""
    return float(x_iso_mm) + FRONT_AXLE_TO_ISO_PLANE_MM


def axle_x_to_iso_x(x_axle_mm: float) -> float:
    """X from the front axle -> X from the front ISO twist-lock plane."""
    return float(x_axle_mm) - FRONT_AXLE_TO_ISO_PLANE_MM


# ---------------------------------------------------------------------------
# Use case 4: advanced certified CG entry
# ---------------------------------------------------------------------------

def vehicle_from_certified_cg(
    gw_kg: float,
    xcg_mm: float,
    ycg_mm: float,
    zcg_mm: float,
    wheelbase_mm: float,
    track_mm: float,
    source: str,
    name: str = "Certified CG",
    rstat_mm: float = DEFAULT_RSTAT_MM,
    front_axle_limit_kg: float = DEFAULT_FRONT_AXLE_LIMIT_KG,
    rear_axle_limit_kg: float = DEFAULT_REAR_AXLE_LIMIT_KG,
    gvw_limit_kg: float = DEFAULT_GVW_LIMIT_KG,
) -> Vehicle:
    """
    Build a Vehicle from directly supplied GW/CG values (advanced path).

    A non-empty `source` reference label is mandatory so results stay
    traceable. Ycg may be negative (kerbside of centreline); GW, Zcg and
    dimensions must be positive. Xcg is validated as positive but NOT clamped
    to the wheelbase -- use check_cg_plausibility() for soft warnings.
    """
    gw = _require_positive(gw_kg, "GW")
    x = _require_positive(xcg_mm, "Xcg")
    z = _require_positive(zcg_mm, "Zcg")
    wb = _require_positive(wheelbase_mm, "wheelbase")
    tr = _require_positive(track_mm, "track")
    src = _require_label(source, "CG source/reference")
    y = float(ycg_mm)

    return Vehicle(
        name=f"{name} ({src})",
        gw_kg=gw,
        xcg_mm=x,
        ycg_mm=y,
        zcg_mm=z,
        wheelbase_mm=wb,
        track_mm=tr,
        rstat_mm=rstat_mm,
        front_axle_limit_kg=front_axle_limit_kg,
        rear_axle_limit_kg=rear_axle_limit_kg,
        gvw_limit_kg=gvw_limit_kg,
    )


# ---------------------------------------------------------------------------
# Use case 3: design / modification study
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MassChange:
    """
    One component change applied to a baseline vehicle.

    action      : "add" | "remove" | "relocate"
    description : free text, e.g. "Winch", "Spare wheel relocation"
    mass_kg     : component mass, must be positive
    old_xyz_mm  : (X, Y, Z) of the component on the BASELINE vehicle.
                  Required for "remove" and "relocate".
    new_xyz_mm  : (X, Y, Z) of the component AFTER the change.
                  Required for "add" and "relocate".

    Coordinates use the vehicle datum: X from front axle, Y right-positive
    from centreline, Z from ground. Component Z must be positive; X and Y
    are unrestricted (a towbar load can sit behind the rear axle).
    """
    action: str
    description: str
    mass_kg: float
    old_xyz_mm: Optional[Tuple[float, float, float]] = None
    new_xyz_mm: Optional[Tuple[float, float, float]] = None


def _validate_change(ch: MassChange, idx: int) -> None:
    tag = f"change #{idx + 1} ({ch.description or 'unnamed'})"
    if ch.action not in _ACTIONS:
        raise ValueError(f"{tag}: unknown action {ch.action!r}, "
                         f"expected one of {_ACTIONS}")
    _require_positive(ch.mass_kg, f"{tag}: mass")
    if ch.action in ("remove", "relocate"):
        if ch.old_xyz_mm is None or len(ch.old_xyz_mm) != 3:
            raise ValueError(f"{tag}: action '{ch.action}' requires "
                             f"old_xyz_mm=(X, Y, Z)")
        _require_positive(ch.old_xyz_mm[2], f"{tag}: old Z")
    if ch.action in ("add", "relocate"):
        if ch.new_xyz_mm is None or len(ch.new_xyz_mm) != 3:
            raise ValueError(f"{tag}: action '{ch.action}' requires "
                             f"new_xyz_mm=(X, Y, Z)")
        _require_positive(ch.new_xyz_mm[2], f"{tag}: new Z")


def apply_mass_changes(base: Vehicle,
                       changes: Sequence[MassChange]) -> Vehicle:
    """
    Apply component add / remove / relocate changes to a baseline Vehicle
    via moment summation about the vehicle datum.

      add      : GW += m ; moments += m * new_position
      remove   : GW -= m ; moments -= m * old_position
      relocate : GW unchanged ; moments += m * (new - old)

    Returns a NEW Vehicle (baseline is never mutated). An empty change list
    returns an exact copy of the baseline. Raises ValueError on invalid
    changes or a non-positive final mass. Limits, dimensions and rstat are
    inherited from the baseline (vendor limits do not change with payload).
    """
    if not changes:
        return replace(base)

    m_total = base.gw_kg
    mx = base.gw_kg * base.xcg_mm
    my = base.gw_kg * base.ycg_mm
    mz = base.gw_kg * base.zcg_mm

    for i, ch in enumerate(changes):
        _validate_change(ch, i)
        m = float(ch.mass_kg)
        if ch.action == "add":
            x, y, z = ch.new_xyz_mm
            m_total += m
            mx += m * x
            my += m * y
            mz += m * z
        elif ch.action == "remove":
            x, y, z = ch.old_xyz_mm
            m_total -= m
            mx -= m * x
            my -= m * y
            mz -= m * z
        else:  # relocate
            ox, oy, oz = ch.old_xyz_mm
            nx, ny, nz = ch.new_xyz_mm
            mx += m * (nx - ox)
            my += m * (ny - oy)
            mz += m * (nz - oz)

    if m_total <= 0:
        raise ValueError(f"final vehicle mass is non-positive "
                         f"({m_total:.1f} kg) -- removals exceed baseline")

    new_zcg = mz / m_total
    if new_zcg <= 0:
        raise ValueError(f"final Zcg is non-positive ({new_zcg:.1f} mm) -- "
                         f"check component Z coordinates")

    return replace(
        base,
        name=f"{base.name} + {len(changes)} change(s)",
        gw_kg=m_total,
        xcg_mm=mx / m_total,
        ycg_mm=my / m_total,
        zcg_mm=new_zcg,
    )


def baseline_delta(base: Vehicle, modified: Vehicle) -> dict:
    """Deltas (modified - base) for the four scenario-summary metrics."""
    return {
        "gw_kg": modified.gw_kg - base.gw_kg,
        "xcg_mm": modified.xcg_mm - base.xcg_mm,
        "ycg_mm": modified.ycg_mm - base.ycg_mm,
        "zcg_mm": modified.zcg_mm - base.zcg_mm,
    }


# ---------------------------------------------------------------------------
# Soft plausibility checks (warn, never reject)
# ---------------------------------------------------------------------------

def check_cg_plausibility(v: Vehicle) -> list:
    """
    Return a list of plain-ASCII warning strings for unusual-but-possible
    CG positions. Empty list = nothing notable. Callers (UI) should display
    these as warnings, not errors.
    """
    warnings = []
    if not (0.0 < v.xcg_mm < v.wheelbase_mm):
        warnings.append(
            f"[WARN] Xcg = {v.xcg_mm:.1f} mm lies outside the wheelbase "
            f"(0 to {v.wheelbase_mm:.0f} mm) -- one axle would carry the "
            f"entire load or lift off")
    if abs(v.ycg_mm) > v.track_mm / 4:
        warnings.append(
            f"[WARN] |Ycg| = {abs(v.ycg_mm):.1f} mm exceeds track/4 "
            f"({v.track_mm / 4:.0f} mm) -- heavily asymmetric load")
    if v.zcg_mm > v.track_mm:
        warnings.append(
            f"[WARN] Zcg = {v.zcg_mm:.1f} mm exceeds the track width "
            f"({v.track_mm:.0f} mm) -- lateral stability will be very poor")
    if v.zcg_mm < v.rstat_mm:
        warnings.append(
            f"[WARN] Zcg = {v.zcg_mm:.1f} mm is below the static wheel "
            f"radius ({v.rstat_mm:.0f} mm) -- unusually low; verify datum "
            f"is ground, not chassis")
    return warnings
