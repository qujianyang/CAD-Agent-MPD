"""
Mobility physics engine.
Source: Spinel-E2 Measured CG in FIT_13-5-2026_Turning Radius R_Final 1.xls
Verified against stored SF cells on both 'E2 Measured Mobility Analysis' and
'E2 Theory Mobility Analysis' sheets (see validate_mobility_excel.py).

Five analysis modules (all reproducing the Excel workbook):
  1. Axle loadings        -- front/rear/lateral from CG position
  2. Steerability         -- front axle >= 25% GW (bodybuilder guideline)
  3. Longitudinal slope   -- ascending / descending, moment balance
  4. Side slope           -- kerbside / roadside, moment balance
  5. Cornering            -- centrifugal + wind moment vs lateral resist
     + approach/departure angle suitability (geometric, no stability calc)

SF formula (all modules):
  SF = stabilising_moment / overturning_moment
  = (mg * cos(theta) * lever_m) / (mg * sin(theta) * Z_m)

Moment convention:
  - Longitudinal ascending: tipping about REAR axle (downhill); lever = WB - Xcg
  - Longitudinal descending: tipping about FRONT axle;            lever = Xcg
  - Lateral kerbside:       tipping about LEFT axle;              lever = track/2 + Ycg
  - Lateral roadside:       tipping about RIGHT axle;             lever = track/2 - Ycg
  (Ycg positive toward driverside / right)
"""

import math
from dataclasses import dataclass, field
from typing import Optional

G = 9.81  # m/s²


@dataclass
class Vehicle:
    name: str
    gw_kg: float
    xcg_mm: float           # longitudinal CG from FRONT axle (mm)
    ycg_mm: float           # lateral CG from vehicle centreline, +driverside (mm)
    zcg_mm: float           # CG height above ground (mm)
    wheelbase_mm: float
    track_mm: float
    rstat_mm: float = 580.0
    front_axle_limit_kg: float = 8000.0
    rear_axle_limit_kg: float = 10600.0
    gvw_limit_kg: float = 18600.0


@dataclass
class Aero:
    air_density: float = 1.18      # kg/m³
    cd: float = 1.0
    front_area_m2: float = 9.0     # MPFA front (for wind on longitudinal face)
    side_area_m2: float = 35.52    # MPFA side  (for cornering wind)
    wind_height_m: float = 2.05    # height at which wind force acts (m)


@dataclass
class AxleResult:
    front_kg: float
    rear_kg: float
    front_pct: float            # front axle as % of GW
    driverside_kg: float
    kerbside_kg: float
    front_ok: bool
    rear_ok: bool
    gvw_ok: bool
    steer_ok: bool              # front_pct >= min_front_pct

    @property
    def all_ok(self) -> bool:
        return self.front_ok and self.rear_ok and self.gvw_ok and self.steer_ok


@dataclass
class SlopeResult:
    grade_pct: float
    direction: str              # "ascending" | "descending" | "kerbside" | "roadside"
    theta_deg: float
    lever_mm: float
    stab_Nm: float
    over_Nm: float
    SF: float
    crit_angle_deg: float       # tip-over angle from CG geometry (independent of slope)

    @property
    def passed(self, target: float = 1.0) -> bool:
        return self.SF >= target


@dataclass
class CornerResult:
    speed_kmh: float
    radius_m: float
    wind_kmh: float
    Fc_N: float
    over_fc_Nm: float
    Fw_N: float
    over_wind_Nm: float
    over_total_Nm: float
    resist_Nm: float
    yprime_mm: float            # critical lateral lever (smaller side)
    SF: float
    max_safe_speed_kmh: float   # speed at which SF drops to 1.0

    @property
    def passed(self, target: float = 1.0) -> bool:
        return self.SF >= target


@dataclass
class ApproachResult:
    approach_angle_deg: float
    departure_angle_deg: float
    required_grade_pct: float
    approach_grade_pct: float   # tan(angle) * 100
    departure_grade_pct: float
    approach_ok: bool
    departure_ok: bool

    @property
    def all_ok(self) -> bool:
        return self.approach_ok and self.departure_ok


@dataclass
class MobilityReport:
    vehicle: Vehicle
    axle: AxleResult
    slope_results: list         # list[SlopeResult]
    corner: Optional[CornerResult] = None
    approach: Optional[ApproachResult] = None
    target_SF: float = 1.0

    @property
    def all_passed(self) -> bool:
        slope_ok = all(r.SF >= self.target_SF for r in self.slope_results)
        corner_ok = self.corner is None or self.corner.SF >= self.target_SF
        return self.axle.all_ok and slope_ok and corner_ok

    def governing_slope(self) -> Optional[SlopeResult]:
        return min(self.slope_results, key=lambda r: r.SF) if self.slope_results else None

    def critical_cases(self, target: Optional[float] = None) -> list:
        t = target if target is not None else self.target_SF
        return [r for r in self.slope_results if r.SF < t]


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------

def axle_loads(v: Vehicle, min_front_pct: float = 25.0) -> AxleResult:
    """
    Longitudinal: front = GW * (WB - Xcg) / WB  (moment about rear axle).
    Lateral: driverside = GW * (track/2 + Ycg) / track  (moment about kerbside axle).
    """
    front_kg = v.gw_kg * (v.wheelbase_mm - v.xcg_mm) / v.wheelbase_mm
    rear_kg = v.gw_kg - front_kg
    front_pct = front_kg / v.gw_kg * 100
    driverside_kg = v.gw_kg * (v.track_mm / 2 + v.ycg_mm) / v.track_mm
    kerbside_kg = v.gw_kg - driverside_kg
    return AxleResult(
        front_kg=front_kg,
        rear_kg=rear_kg,
        front_pct=front_pct,
        driverside_kg=driverside_kg,
        kerbside_kg=kerbside_kg,
        front_ok=front_kg <= v.front_axle_limit_kg,
        rear_ok=rear_kg <= v.rear_axle_limit_kg,
        gvw_ok=v.gw_kg <= v.gvw_limit_kg,
        steer_ok=front_pct >= min_front_pct,
    )


def _trig(theta: float, trig_dp: Optional[int]):
    """cos/sin of theta, optionally rounded to trig_dp decimals to mirror a
    hand/spreadsheet calculation (the SAR uses 3-dp trig constants)."""
    c, s = math.cos(theta), math.sin(theta)
    if trig_dp is not None:
        c, s = round(c, trig_dp), round(s, trig_dp)
    return c, s


def slope_stability(v: Vehicle, grade_pct: float, direction: str,
                    angle_deg: Optional[float] = None,
                    trig_dp: Optional[int] = None) -> SlopeResult:
    """
    Longitudinal slope stability.
    direction: "ascending" (tips toward rear) or "descending" (tips toward front).
    angle_deg: optional slope angle override. If given, used instead of
               atan(grade_pct/100) -- matches the SAR which computes with the
               rounded printed angle (e.g. 31 deg for a 60% grade).
    trig_dp:   optional rounding of cos/sin to N decimals (SAR uses 3) so the
               output reproduces the published safety factors exactly.
    """
    theta = math.radians(angle_deg) if angle_deg is not None else math.atan(grade_pct / 100)
    if direction == "ascending":
        lever_mm = v.wheelbase_mm - v.xcg_mm   # rear axle to CG
    else:
        lever_mm = v.xcg_mm                     # front axle to CG
    cos_t, sin_t = _trig(theta, trig_dp)
    stab = G * v.gw_kg * cos_t * lever_mm / 1000
    over = G * v.gw_kg * sin_t * v.zcg_mm / 1000
    SF = stab / over
    crit_angle_deg = math.degrees(math.atan(lever_mm / v.zcg_mm))
    return SlopeResult(grade_pct, direction, math.degrees(theta),
                       lever_mm, stab, over, SF, crit_angle_deg)


def side_slope_stability(v: Vehicle, grade_pct: float, side: str,
                         angle_deg: Optional[float] = None,
                         trig_dp: Optional[int] = None) -> SlopeResult:
    """
    Lateral (side) slope stability.
    side: "kerbside" (tips left, pivot = left axle) or "roadside" (tips right).
    angle_deg: optional angle override (SAR uses 16.7 deg for a 30% grade).
    trig_dp:   optional cos/sin rounding (SAR uses 3) for exact replication.
    """
    theta = math.radians(angle_deg) if angle_deg is not None else math.atan(grade_pct / 100)
    if side == "kerbside":
        lever_mm = v.track_mm / 2 + v.ycg_mm   # kerbside axle to CG (+Ycg adds)
    else:
        lever_mm = v.track_mm / 2 - v.ycg_mm   # roadside axle to CG
    cos_t, sin_t = _trig(theta, trig_dp)
    stab = G * v.gw_kg * cos_t * lever_mm / 1000
    over = G * v.gw_kg * sin_t * v.zcg_mm / 1000
    SF = stab / over
    crit_angle_deg = math.degrees(math.atan(lever_mm / v.zcg_mm))
    return SlopeResult(grade_pct, side, math.degrees(theta),
                       lever_mm, stab, over, SF, crit_angle_deg)


def cornering_stability(v: Vehicle, aero: Aero, speed_kmh: float,
                        radius_m: float, wind_kmh: float = 0.0) -> CornerResult:
    """
    Cornering stability (left turn assumed — less stable when Ycg > 0 driverside).
    Fc = S²/R × GW  (centrifugal, N).
    Wind acts on side area at aero.wind_height_m.
    Critical lateral lever = min(track/2 ± Ycg) = track/2 - |Ycg| for typical bias.
    SF = (GW × g × yprime_m) / (Fc × Zcg_m + Fw × wind_height_m).
    """
    S = speed_kmh / 3.6
    Fc = S ** 2 / radius_m * v.gw_kg
    over_fc = Fc * v.zcg_mm / 1000

    Vw = wind_kmh / 3.6
    Fw = 0.5 * aero.air_density * aero.cd * Vw ** 2 * aero.side_area_m2
    over_wind = Fw * aero.wind_height_m

    over_total = over_fc + over_wind

    # Use the smaller lateral lever (critical side; sheet confirms left turn is less stable)
    yprime_mm = min(v.track_mm / 2 + v.ycg_mm, v.track_mm / 2 - v.ycg_mm)
    yprime_m = yprime_mm / 1000
    resist = v.gw_kg * G * yprime_m

    SF = resist / over_total if over_total > 0 else float("inf")

    # Max safe speed at SF = 1: Fc_crit = (resist - over_wind) / Zcg_m
    resist_margin = resist - over_wind
    if resist_margin > 0:
        Fc_crit = resist_margin / (v.zcg_mm / 1000)
        S_max = math.sqrt(max(0.0, Fc_crit * radius_m / v.gw_kg))
        max_speed_kmh = S_max * 3.6
    else:
        max_speed_kmh = 0.0

    return CornerResult(
        speed_kmh=speed_kmh, radius_m=radius_m, wind_kmh=wind_kmh,
        Fc_N=Fc, over_fc_Nm=over_fc,
        Fw_N=Fw, over_wind_Nm=over_wind,
        over_total_Nm=over_total,
        resist_Nm=resist, yprime_mm=yprime_mm,
        SF=SF, max_safe_speed_kmh=max_speed_kmh,
    )


def approach_departure_check(approach_deg: float, departure_deg: float,
                              required_grade_pct: float = 60.0) -> ApproachResult:
    """
    Geometric suitability: vehicle's approach/departure angles vs required grade.
    approach_grade_pct = tan(approach_deg) × 100  (the slope the angle equals).
    """
    app_grade = math.tan(math.radians(approach_deg)) * 100
    dep_grade = math.tan(math.radians(departure_deg)) * 100
    return ApproachResult(
        approach_angle_deg=approach_deg,
        departure_angle_deg=departure_deg,
        required_grade_pct=required_grade_pct,
        approach_grade_pct=app_grade,
        departure_grade_pct=dep_grade,
        approach_ok=app_grade >= required_grade_pct,
        departure_ok=dep_grade >= required_grade_pct,
    )


def run_mobility_analysis(
    v: Vehicle,
    aero: Optional[Aero] = None,
    grades_long: tuple = (60, 50),      # longitudinal grades to analyse (%)
    grades_side: tuple = (30, 25),      # lateral grades to analyse (%)
    speed_kmh: float = 15.0,
    radius_m: float = 11.0,
    wind_kmh: float = 60.0,
    approach_deg: Optional[float] = None,
    departure_deg: Optional[float] = None,
    required_grade_pct: float = 60.0,
    target_SF: float = 1.0,
) -> MobilityReport:
    aero = aero or Aero()
    axle = axle_loads(v)
    slopes = []
    for g in grades_long:
        slopes.append(slope_stability(v, g, "ascending"))
        slopes.append(slope_stability(v, g, "descending"))
    for g in grades_side:
        slopes.append(side_slope_stability(v, g, "kerbside"))
        slopes.append(side_slope_stability(v, g, "roadside"))
    corner = cornering_stability(v, aero, speed_kmh, radius_m, wind_kmh)
    approach = None
    if approach_deg is not None and departure_deg is not None:
        approach = approach_departure_check(approach_deg, departure_deg, required_grade_pct)
    return MobilityReport(v, axle, slopes, corner, approach, target_SF)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_mobility_report(report: MobilityReport) -> str:
    v = report.vehicle
    ax = report.axle
    lines = [
        "=" * 70,
        "MOBILITY ANALYSIS",
        f"  Vehicle  : {v.name}",
        f"  GW       : {v.gw_kg:,.0f} kg",
        f"  CG (Xcg/Ycg/Zcg): {v.xcg_mm:.1f} / {v.ycg_mm:.1f} / {v.zcg_mm:.1f} mm",
        f"  WB / Track: {v.wheelbase_mm:.0f} / {v.track_mm:.0f} mm",
        "=" * 70,
        "AXLE LOADINGS",
        f"  Front : {ax.front_kg:,.1f} kg  ({ax.front_pct:.2f}%)  {'OK' if ax.front_ok else 'OVER'}",
        f"  Rear  : {ax.rear_kg:,.1f} kg  {'OK' if ax.rear_ok else 'OVER'}",
        f"  GVW   : {v.gw_kg:,.0f} kg  {'OK' if ax.gvw_ok else 'OVER'}",
        f"  Steer : {ax.front_pct:.2f}% front  {'OK' if ax.steer_ok else 'FAIL (< 25%)'}",
        "-" * 70,
        "SLOPE STABILITY",
        f"  {'Grade':>8}  {'Direction':<12}  {'theta':>7}  {'Lever mm':>9}  {'SF':>8}  {'Crit deg':>9}  {'Verdict':>7}",
    ]
    for r in report.slope_results:
        verdict = "PASS" if r.SF >= report.target_SF else "FAIL"
        lines.append(
            f"  {r.grade_pct:>7.0f}%  {r.direction:<12}  {r.theta_deg:>6.2f}°  "
            f"{r.lever_mm:>9.1f}  {r.SF:>8.4f}  {r.crit_angle_deg:>8.2f}°  {verdict:>7}"
        )
    if report.corner:
        c = report.corner
        verdict = "PASS" if c.SF >= report.target_SF else "FAIL"
        lines += [
            "-" * 70,
            "CORNERING",
            f"  Speed {c.speed_kmh:.0f} km/h, R={c.radius_m:.0f} m, Wind {c.wind_kmh:.0f} km/h",
            f"  Fc={c.Fc_N:,.1f} N  over_fc={c.over_fc_Nm:,.1f} Nm",
            f"  Fw={c.Fw_N:,.1f} N  over_wind={c.over_wind_Nm:,.1f} Nm",
            f"  Resist={c.resist_Nm:,.1f} Nm  SF={c.SF:.4f}  {verdict}",
            f"  Max safe speed = {c.max_safe_speed_kmh:.1f} km/h (at SF=1)",
        ]
    gov = report.governing_slope()
    crit_cases = report.critical_cases()
    lines += [
        "=" * 70,
        "OVERALL: " + (
            f"ALL PASS (governing: {gov.direction} {gov.grade_pct:.0f}%, SF={gov.SF:.4f})"
            if report.all_passed else
            f"{len(crit_cases)} case(s) below target SF {report.target_SF}"
        ),
        "=" * 70,
    ]
    return "\n".join(lines)


def format_slope_table(report: MobilityReport) -> str:
    """Compact grade-vs-SF grid for pasting into SAR."""
    by = {(r.grade_pct, r.direction): r for r in report.slope_results}
    grades_long = sorted({r.grade_pct for r in report.slope_results
                          if r.direction in ("ascending", "descending")}, reverse=True)
    grades_side = sorted({r.grade_pct for r in report.slope_results
                          if r.direction in ("kerbside", "roadside")}, reverse=True)
    lines = [
        f"{'Grade':>7}  {'Asc SF':>8}  {'Asc crit':>9}  {'Desc SF':>8}  {'Desc crit':>10}",
        "-" * 50,
    ]
    for g in grades_long:
        asc = by.get((g, "ascending"))
        desc = by.get((g, "descending"))
        lines.append(
            f"{g:>6.0f}%  {asc.SF:>8.4f}  {asc.crit_angle_deg:>8.2f}°  "
            f"{desc.SF:>8.4f}  {desc.crit_angle_deg:>9.2f}°"
        )
    lines += [
        "",
        f"{'Grade':>7}  {'Kerb SF':>8}  {'Kerb crit':>10}  {'Road SF':>8}  {'Road crit':>10}",
        "-" * 50,
    ]
    for g in grades_side:
        k = by.get((g, "kerbside"))
        r = by.get((g, "roadside"))
        lines.append(
            f"{g:>6.0f}%  {k.SF:>8.4f}  {k.crit_angle_deg:>9.2f}°  "
            f"{r.SF:>8.4f}  {r.crit_angle_deg:>9.2f}°"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Demo / smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    spinel = Vehicle(
        name="Spinel E2 (Measured CG)",
        gw_kg=17850, xcg_mm=2655.4622, ycg_mm=20.4706, zcg_mm=1617.8285,
        wheelbase_mm=4800, track_mm=2088,
    )
    report = run_mobility_analysis(
        spinel,
        approach_deg=32.4, departure_deg=31.0, required_grade_pct=60.0,
    )
    print(format_mobility_report(report))
    print()
    print(format_slope_table(report))
    # spot-checks
    by = {(r.grade_pct, r.direction): r for r in report.slope_results}
    assert abs(by[(60, "ascending")].SF - 2.2058) < 1e-2, by[(60, "ascending")].SF
    assert abs(by[(60, "descending")].SF - 2.7314) < 1e-2, by[(60, "descending")].SF
    assert abs(by[(30, "kerbside")].SF - 2.1963) < 1e-2, by[(30, "kerbside")].SF
    assert abs(by[(30, "roadside")].SF - 2.1118) < 1e-2, by[(30, "roadside")].SF
    assert abs(report.axle.front_kg - 7975.0) < 0.1
    assert abs(report.corner.SF - 3.1164) < 1e-2
    print("\n[OK] All spot-checks passed")
