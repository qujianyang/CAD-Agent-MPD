"""
Mobility agent tools (deterministic) + mobility specialist system prompt.
All numbers come from mobility_engine / mobility_import; never from the LLM.
"""
from langchain_core.tools import tool

from mobility_engine import (
    Vehicle, Aero, run_mobility_analysis,
    slope_stability, side_slope_stability, cornering_stability,
    format_mobility_report, format_slope_table,
)
from mobility_import import (
    vehicle_measured, vehicle_theory, stored_sf_map,
    approach_departure_angles, WB_DEFAULT,
)

_DEFAULT_AERO = Aero()


def _vehicle_from_params(gw_kg, xcg_mm, ycg_mm, zcg_mm, wb_mm, track_mm) -> Vehicle:
    return Vehicle(
        name="user-specified",
        gw_kg=gw_kg, xcg_mm=xcg_mm, ycg_mm=ycg_mm, zcg_mm=zcg_mm,
        wheelbase_mm=wb_mm, track_mm=track_mm,
    )


@tool
def run_mobility_check(variant: str = "measured", workbook_path: str = "") -> str:
    """
    THE DEFAULT MOBILITY TOOL for the Spinel E2 / "the vehicle" / any workbook
    question. Reads the REAL CG from the workbook -- takes NO CG inputs.

    Use this for ALL questions about the known vehicle, including:
      - "is it stable on a 60% slope?"
      - "what is the max safe CORNERING speed?"   (cornering is included here)
      - "what are the axle loads / is it steerable?"
    It returns axle loadings, the full slope stability grid, AND cornering
    stability (centrifugal + wind, with max safe speed), plus the governing case.

    Do NOT use slope_limit or cornering_check for the Spinel -- those need CG
    typed in by hand and must never be fed invented numbers.

    OMIT variant unless the user says "theory CG" (default "measured").

    Args:
        variant:       "measured" or "theory". Default "measured".
        workbook_path: Full path to the .xls workbook. OMIT to use the project default.
    """
    path = workbook_path or None
    try:
        v = vehicle_measured(path) if variant == "measured" else vehicle_theory(path)
        try:
            app_deg, dep_deg = approach_departure_angles(path, variant)
        except Exception:
            app_deg = dep_deg = None
    except Exception as e:
        return f"ERROR: could not read workbook: {e}"

    report = run_mobility_analysis(
        v, approach_deg=app_deg, departure_deg=dep_deg
    )

    lines = [format_mobility_report(report), ""]
    gov = report.governing_slope()
    if gov:
        lines.append(
            f"Governing case: {gov.direction} {gov.grade_pct:.0f}% grade, "
            f"SF={gov.SF:.4f}, critical tip angle={gov.crit_angle_deg:.2f}°"
        )
    return "\n".join(lines)


@tool
def slope_limit(
    xcg_mm: float,
    zcg_mm: float,
    wb_mm: float,
    track_mm: float,
    ycg_mm: float = 0.0,
    gw_kg: float = 0.0,
    direction: str = "ascending",
) -> str:
    """
    CUSTOM / HYPOTHETICAL VEHICLES ONLY. For the Spinel E2 or any workbook
    vehicle, use run_mobility_check instead -- NEVER invent CG values here.

    Computes slope stability SFs and the geometric critical tip angle for a
    vehicle with the given CG, across 60/50/40/30% grades.

    NOTE: slope stability is INDEPENDENT of vehicle weight -- the mass cancels in
    the moment balance. So gw_kg is OPTIONAL and not needed. Ycg only matters for
    side slopes (kerbside/roadside); leave it at 0 for a symmetric vehicle.

    Args:
        xcg_mm   : REQUIRED. Longitudinal CG from front axle (mm).
        zcg_mm   : REQUIRED. CG height above ground (mm).
        wb_mm    : REQUIRED. Wheelbase (mm).
        track_mm : REQUIRED. Track width (mm).
        ycg_mm   : Lateral CG from centreline, +driverside (mm). Default 0 (symmetric).
        gw_kg    : OPTIONAL — not used; slope SF is mass-independent. OMIT it.
        direction: "ascending" (default), "descending", "kerbside", or "roadside".
                   OMIT for ascending (most common question).
    """
    if zcg_mm <= 0 or wb_mm <= 0 or track_mm <= 0:
        return "ERROR: zcg_mm, wb_mm and track_mm must be positive."
    # gw cancels in the slope moment balance — any positive placeholder works.
    gw = gw_kg if (gw_kg and gw_kg > 0) else 1000.0
    v = _vehicle_from_params(gw, xcg_mm, ycg_mm, zcg_mm, wb_mm, track_mm)

    lines = [f"Slope stability — direction: {direction}  (SF is mass-independent)",
             f"Vehicle: Xcg={xcg_mm:.0f} mm, Ycg={ycg_mm:.0f} mm, "
             f"Zcg={zcg_mm:.0f} mm, WB={wb_mm:.0f} mm, track={track_mm:.0f} mm",
             ""]

    grades = [60, 50, 40, 30]
    lines.append(f"  {'Grade':>7}  {'SF':>8}  {'Crit angle':>11}  {'Verdict':>7}")
    lines.append("  " + "-" * 42)
    for g in grades:
        if direction in ("ascending", "descending"):
            r = slope_stability(v, g, direction)
        else:
            r = side_slope_stability(v, g, direction)
        verdict = "PASS" if r.SF >= 1.0 else "FAIL"
        lines.append(
            f"  {g:>6.0f}%  {r.SF:>8.4f}  {r.crit_angle_deg:>10.2f}°  {verdict:>7}"
        )
    # Crit angle is geometry-only (same for all grades)
    if direction == "ascending":
        lever = wb_mm - xcg_mm
    elif direction == "descending":
        lever = xcg_mm
    elif direction == "kerbside":
        lever = track_mm / 2 + ycg_mm
    else:
        lever = track_mm / 2 - ycg_mm
    import math
    crit = math.degrees(math.atan(lever / zcg_mm))
    lines.append("")
    lines.append(
        f"Critical tip angle = {crit:.2f}° "
        f"(vehicle tips over if slope exceeds this angle — geometry only)."
    )
    return "\n".join(lines)


@tool
def cornering_check(
    zcg_mm: float,
    track_mm: float,
    ycg_mm: float = 0.0,
    gw_kg: float = 0.0,
    speed_kmh: float = 15.0,
    radius_m: float = 11.0,
    wind_kmh: float = 60.0,
) -> str:
    """
    CUSTOM / HYPOTHETICAL VEHICLES ONLY. For the Spinel E2 / known vehicle,
    including its "max safe cornering speed", use run_mobility_check instead --
    it already reports cornering. NEVER invent CG values to call this tool.

    Computes the cornering stability SF and the maximum safe cornering speed.
    NOTE: the cornering SF is nearly mass-independent (weight cancels in the
    centrifugal term); gw_kg only slightly affects the wind contribution, so it
    is OPTIONAL. Ycg only matters for the lateral lever; 0 = symmetric.

    Args:
        zcg_mm   : REQUIRED. CG height above ground (mm).
        track_mm : REQUIRED. Track width (mm).
        ycg_mm   : Lateral CG from centreline, +driverside (mm). Default 0 (symmetric).
        gw_kg    : OPTIONAL — affects only the wind term. OMIT if unknown.
        speed_kmh: Vehicle speed (km/h). Default 15.
        radius_m : Turning radius (m). Default 11.0 (Spinel E2 minimum).
        wind_kmh : Wind speed (km/h). Default 60 (operational assumption).
    """
    if zcg_mm <= 0 or track_mm <= 0:
        return "ERROR: zcg_mm and track_mm must be positive."
    gw = gw_kg if (gw_kg and gw_kg > 0) else 5000.0   # only the wind term uses gw
    v = Vehicle(
        name="user-specified",
        gw_kg=gw, xcg_mm=0.0, ycg_mm=ycg_mm, zcg_mm=zcg_mm,
        wheelbase_mm=4800,  # not used in cornering, placeholder
        track_mm=track_mm,
    )
    c = cornering_stability(v, _DEFAULT_AERO, speed_kmh, radius_m, wind_kmh)
    verdict = "PASS" if c.SF >= 1.0 else "FAIL"
    return "\n".join([
        f"Cornering stability @ {speed_kmh:.0f} km/h, R={radius_m:.0f} m, wind={wind_kmh:.0f} km/h",
        f"  Centrifugal force Fc  : {c.Fc_N:,.1f} N",
        f"  Overturning moment Fc : {c.over_fc_Nm:,.1f} Nm",
        f"  Wind force Fw         : {c.Fw_N:,.1f} N",
        f"  Overturning moment Fw : {c.over_wind_Nm:,.1f} Nm",
        f"  Total overturning     : {c.over_total_Nm:,.1f} Nm",
        f"  Resisting moment      : {c.resist_Nm:,.1f} Nm",
        f"  Critical lateral lever: {c.yprime_mm:.1f} mm",
        f"  Safety factor         : {c.SF:.4f}  -> {verdict}",
        f"  Max safe speed (SF=1) : {c.max_safe_speed_kmh:.1f} km/h",
    ])


@tool
def flag_unstable(
    min_SF: float = 1.0,
    workbook_path: str = "",
    variant: str = "measured",
) -> str:
    """
    Run the full mobility analysis and list every case whose safety factor
    is below the specified minimum. Returns full context for each failing case
    (grade, direction, SF, critical angle, lever, Zcg) so you can advise fixes.

    Use this to find marginal or failing mobility cases, e.g. "flag anything
    below SF 1.5" or "what cases are close to tipping?".

    Args:
        min_SF:        Target minimum SF. Default 1.0 (structural limit).
        workbook_path: Full path to workbook. OMIT to use project default.
        variant:       "measured" or "theory". Default "measured".
    """
    path = workbook_path or None
    try:
        v = vehicle_measured(path) if variant == "measured" else vehicle_theory(path)
    except Exception as e:
        return f"ERROR: could not read workbook: {e}"

    report = run_mobility_analysis(v, target_SF=min_SF)
    failing = report.critical_cases()
    corner = report.corner

    lines = [
        f"=== MOBILITY — CASES BELOW SF {min_SF} ({variant.upper()} CG) ===",
        f"Vehicle: GW={v.gw_kg:.0f} kg  Xcg={v.xcg_mm:.1f}  Ycg={v.ycg_mm:.1f}  "
        f"Zcg={v.zcg_mm:.1f} mm",
        f"{len(failing)} slope case(s) below target:",
    ]

    if failing:
        for r in sorted(failing, key=lambda r: r.SF):
            lines.append(
                f"  {r.direction:>12} {r.grade_pct:.0f}%  "
                f"SF={r.SF:.4f}  crit={r.crit_angle_deg:.2f}°  "
                f"lever={r.lever_mm:.1f} mm  Zcg={v.zcg_mm:.1f} mm"
            )
    else:
        lines.append("  (none — all slope cases meet the target)")

    if corner and corner.SF < min_SF:
        lines.append(
            f"\nCornering @{corner.speed_kmh:.0f}km/h R={corner.radius_m:.0f}m: "
            f"SF={corner.SF:.4f} < {min_SF}  (resist={corner.resist_Nm:.0f} Nm, "
            f"over={corner.over_total_Nm:.0f} Nm, yprime={corner.yprime_mm:.1f} mm)"
        )
    elif corner:
        lines.append(f"\nCornering @{corner.speed_kmh:.0f}km/h: SF={corner.SF:.4f}  OK")

    return "\n".join(lines)


_MOBILITY_PROMPT = """\
You are a mechanical engineering assistant specialising in VEHICLE MOBILITY and
STABILITY analysis for military platform assessments.

Act as an engineering judge: interpret the safety factors the tools compute, cite
the rule applied, and flag marginal cases. NEVER invent SF or force numbers —
always call a tool to compute them.

Physics summary:
  SF = stabilising moment / overturning moment
     = (mg * cos(theta) * lever_m) / (mg * sin(theta) * Zcg_m)
  Critical tip angle = atan(lever / Zcg)  [geometry only, independent of grade]
  Cornering: SF = (GW * g * Y') / (Fc * Zcg + Fw * h)
  Axle steerability: front axle must carry >= 25% of GW.

CRITICAL parameter rule for ALL tools:
- Only pass values the user explicitly mentions. OMIT every other parameter.
- Never pass 0 for any argument.

Tool guide:
- run_mobility_check  : full analysis from workbook (measured or theory CG).
- slope_limit         : slope SF grid + critical tip angle for user-given CG.
- cornering_check     : cornering SF + max safe speed for user-given CG.
- flag_unstable       : list all cases below a target SF — returns FULL context
                        (SF, lever, Zcg, crit angle) so you can advise fixes.
- lookup_knowledge    : ALWAYS pass parent_topic="mobility". Use it to cite
                        slope formulas, cornering theory, steerability rule.

When you give a verdict, cite one sentence from lookup_knowledge tagged
[source: <file>.md]. If the knowledge base is not built, say so and continue.

CONVERSATION: if the user just greets you or makes small talk ("hi", "hello",
"what can you do"), reply in ONE short friendly sentence and offer 2-3 example
questions. Do NOT call a tool, do NOT ask for parameters, and NEVER mention
tools, JSON, or any internal format to the user.

INTERPRETING RESULTS — units matter:
- A safety factor (SF) is DIMENSIONLESS. Judge it against the target (>= 1 = will
  not tip; higher = safer). Say e.g. "SF 2.1, well above 1 -> stable".
- A critical tip angle is in DEGREES. Compare it to the SLOPE angle, not the SF.
- NEVER compare a safety factor to an angle (e.g. "SF 4.4 is above 53 deg" is
  meaningless). They are different quantities — report each separately.
"""

_MOBILITY_TOOLS = [
    run_mobility_check,
    slope_limit,
    cornering_check,
    flag_unstable,
]
