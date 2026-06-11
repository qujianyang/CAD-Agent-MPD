"""
Mobility agent tools (deterministic) + mobility specialist system prompt.
All numbers come from mobility_engine / mobility_import; never from the LLM.
"""
from langchain_core.tools import tool

from mobility_engine import (
    Vehicle, Aero, run_mobility_analysis, axle_loads,
    slope_stability, side_slope_stability, cornering_stability,
    format_mobility_report, format_slope_table,
)
from mobility_import import (
    vehicle_measured, vehicle_theory, stored_sf_map,
    approach_departure_angles, WB_DEFAULT, shelter_cg,
)
from mobility_scenarios import (
    MassChange, apply_mass_changes, baseline_delta,
    vehicle_from_wheel_loads, check_cg_plausibility,
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

    Use this for STABILITY questions about the known vehicle, including:
      - "is it stable on a 60% slope?"
      - "what is the max safe CORNERING speed?"   (cornering is included here)
    It returns axle loadings, the full slope stability grid, AND cornering
    stability (centrifugal + wind, with max safe speed), plus the governing case.

    For pure DATA questions (GW / CG / axle loads / limits, no slope or
    cornering needed) use get_vehicle_baseline instead -- it is faster.

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


def _vehicle_lines(v: Vehicle) -> list:
    """Compact data block for one vehicle: identity, CG, geometry, axles vs limits."""
    ax = axle_loads(v)
    return [
        f"  GW        : {v.gw_kg:,.0f} kg   (GVW limit {v.gvw_limit_kg:,.0f} kg  "
        f"{'[OK]' if ax.gvw_ok else '[OVER]'})",
        f"  Xcg       : {v.xcg_mm:,.1f} mm from front axle",
        f"  Ycg       : {v.ycg_mm:,.1f} mm from centreline (+right)",
        f"  Zcg       : {v.zcg_mm:,.1f} mm above ground",
        f"  Wheelbase : {v.wheelbase_mm:,.0f} mm   Track: {v.track_mm:,.0f} mm",
        f"  Front axle: {ax.front_kg:,.1f} kg ({ax.front_pct:.2f}% of GW)  "
        f"limit {v.front_axle_limit_kg:,.0f} kg  {'[OK]' if ax.front_ok else '[OVER]'}",
        f"  Rear axle : {ax.rear_kg:,.1f} kg  "
        f"limit {v.rear_axle_limit_kg:,.0f} kg  {'[OK]' if ax.rear_ok else '[OVER]'}",
        f"  Steer     : front {ax.front_pct:.2f}% of GW (needs >= 25%)  "
        f"{'[OK]' if ax.steer_ok else '[FAIL]'}",
    ]


@tool
def get_vehicle_baseline(variant: str = "", workbook_path: str = "") -> str:
    """
    DATA LOOKUP for the known Spinel E2 / workbook vehicle. Use this for:
      - "what is the GW / Xcg / Ycg / Zcg / wheelbase / track of the E2?"
      - "what are the axle loads / axle limits / GVW limit?"
      - "what is the difference between the measured and theory CG?"

    Returns the vehicle data and axle loadings ONLY -- no slope or cornering
    results. For stability questions ("is it stable on a 60% slope?") use
    run_mobility_check instead.

    OMIT variant to get BOTH variants side by side (best for comparisons).

    Args:
        variant:       "measured" or "theory". OMIT for both.
        workbook_path: Full path to the .xls workbook. OMIT to use the project default.
    """
    path = workbook_path or None
    want = [variant] if variant in ("measured", "theory") else ["measured", "theory"]
    vehicles = {}
    for w in want:
        try:
            vehicles[w] = vehicle_measured(path) if w == "measured" else vehicle_theory(path)
        except Exception as e:
            return f"ERROR: could not read workbook ({w}): {e}"

    lines = ["=== SPINEL E2 BASELINE (workbook) ==="]
    for w, v in vehicles.items():
        lines.append(f"\n[{w.upper()} CG]  ({v.name})")
        lines.extend(_vehicle_lines(v))

    if len(vehicles) == 2:
        m, t = vehicles["measured"], vehicles["theory"]
        lines.append(
            f"\nDelta (theory - measured): GW {t.gw_kg - m.gw_kg:+,.0f} kg, "
            f"Xcg {t.xcg_mm - m.xcg_mm:+,.1f} mm, Ycg {t.ycg_mm - m.ycg_mm:+,.1f} mm, "
            f"Zcg {t.zcg_mm - m.zcg_mm:+,.1f} mm"
        )

    try:
        sc = shelter_cg(path)
        lines.append(
            f"\nShelter (payload) CG: weight {sc.weight_kg:,.0f} kg, "
            f"X {sc.xcg_mm:,.1f} / Y {sc.ycg_mm:,.1f} / Z {sc.zcg_mm:,.1f} mm"
        )
    except Exception:
        pass

    return "\n".join(lines)


@tool
def derive_cg_from_wheel_loads(
    fl_kg: float,
    fr_kg: float,
    rl_kg: float,
    rr_kg: float,
    zcg_mm: float = 0.0,
    zcg_source: str = "",
    wheelbase_mm: float = 0.0,
    track_mm: float = 0.0,
) -> str:
    """
    USE ONLY when the user gives FOUR wheel / weighbridge readings. Derives the
    gross weight, Xcg and Ycg via the SAR Appendix B moment balance:
      GW = FL+FR+RL+RR,  Xcg = WB*(RL+RR)/GW,  Ycg = Track*((FR+RR)/GW - 0.5)

    Zcg (CG height) CANNOT be derived from static wheel loads. OMIT zcg_mm
    unless the user supplies a VERIFIED value together with its source
    (tilt test / CAD model / certified report) -- never invent one.

    OMIT wheelbase_mm and track_mm to use the Spinel E2 geometry.

    Args:
        fl_kg, fr_kg, rl_kg, rr_kg: REQUIRED. The four wheel loads (kg).
        zcg_mm:       OPTIONAL verified CG height (mm). OMIT if the user gave none.
        zcg_source:   Where zcg_mm came from ("tilt test", "CAD model",
                      "certified report"). REQUIRED whenever zcg_mm is passed.
        wheelbase_mm: OMIT to use the Spinel E2 wheelbase.
        track_mm:     OMIT to use the Spinel E2 track.
    """
    for label, val in (("FL", fl_kg), ("FR", fr_kg), ("RL", rl_kg), ("RR", rr_kg)):
        if val is None or val <= 0:
            return f"ERROR: {label} wheel load must be positive (got {val})."

    assumed = []
    wb, tr = wheelbase_mm, track_mm
    if wb <= 0 or tr <= 0:
        try:
            ref = vehicle_measured()
            wb = wb if wb > 0 else ref.wheelbase_mm
            tr = tr if tr > 0 else ref.track_mm
            assumed.append("Spinel E2 geometry (wheelbase/track) assumed from workbook")
        except Exception:
            return ("ERROR: wheelbase and track not given and the Spinel workbook is "
                    "unavailable -- ask the user for wheelbase_mm and track_mm.")

    gw = fl_kg + fr_kg + rl_kg + rr_kg
    xcg = wb * (rl_kg + rr_kg) / gw
    ycg = tr * ((fr_kg + rr_kg) / gw - 0.5)
    front, rear = fl_kg + fr_kg, rl_kg + rr_kg

    lines = [
        "=== CG FROM WHEEL LOADS (SAR Appendix B moment balance) ===",
        f"  Inputs    : FL {fl_kg:,.0f} / FR {fr_kg:,.0f} / RL {rl_kg:,.0f} / "
        f"RR {rr_kg:,.0f} kg   WB {wb:,.0f} mm  Track {tr:,.0f} mm",
        f"  GW        : {gw:,.1f} kg",
        f"  Xcg       : {xcg:,.1f} mm from front axle",
        f"  Ycg       : {ycg:,.1f} mm from centreline (+right)",
        f"  Front axle: {front:,.1f} kg ({front / gw * 100:.2f}% of GW)   "
        f"Rear axle: {rear:,.1f} kg",
    ]
    if assumed:
        lines.append(f"  Note      : {'; '.join(assumed)} -- Spinel vendor axle/GVW "
                     "limits apply only if this is the E2.")

    if zcg_mm > 0 and not zcg_source.strip():
        return ("ERROR: a Zcg value was given without its source. ASK the user where "
                "the Zcg came from (tilt test / CAD model / certified report) before "
                "using it.")
    if zcg_mm > 0:
        try:
            v = vehicle_from_wheel_loads(
                fl_kg, fr_kg, rl_kg, rr_kg,
                wheelbase_mm=wb, track_mm=tr,
                zcg_mm=zcg_mm, zcg_source=zcg_source,
            )
        except ValueError as e:
            return f"ERROR: {e}"
        lines.append(f"  Zcg       : {v.zcg_mm:,.1f} mm above ground  (source: {zcg_source})")
        for w in check_cg_plausibility(v):
            lines.append(f"  WARNING   : {w}")
        lines.append("Vehicle state is complete -- a full slope/cornering analysis can "
                     "now be run on it.")
    else:
        lines.append(
            "Zcg NOT determined: static wheel loads contain no height information. "
            "A verified Zcg from a tilt test, CAD mass-properties model or certified "
            "report is required before any slope or cornering analysis."
        )
    return "\n".join(lines)


@tool
def evaluate_mass_change(
    action: str,
    mass_kg: float,
    x_mm: float = 0.0,
    y_mm: float = 0.0,
    z_mm: float = 0.0,
    new_x_mm: float = 0.0,
    new_y_mm: float = 0.0,
    new_z_mm: float = 0.0,
    description: str = "component",
    variant: str = "measured",
    workbook_path: str = "",
) -> str:
    """
    THE WHAT-IF TOOL: "if I add a 3200 kg shelter at X 4000 mm...", "move the
    generator 500 mm rearward", "remove the spare wheel". Applies ONE component
    change to the workbook baseline and returns the combined CG plus a
    baseline-vs-modified comparison (CG, axle loads vs limits, governing slope
    SF, cornering).

    Coordinate datum: X from FRONT AXLE (mm, +rearward), Y from centreline
    (+right), Z from GROUND (must be positive).

    Parameter mapping by action:
      action="add"      -> x/y/z = position of the ADDED component.
      action="remove"   -> x/y/z = position of the REMOVED component.
      action="relocate" -> x/y/z = OLD position, new_x/new_y/new_z = NEW
                           position (mass unchanged).

    ONE change per call -- every call starts from the workbook baseline; calls
    do NOT stack. For multi-change studies, direct the user to the Design /
    modification section of the Mobility tab.

    If the user did NOT give the component's mass or position, ASK them --
    NEVER guess or invent a position.

    OMIT variant unless the user says "theory" (default "measured").

    Args:
        action:      REQUIRED. "add", "remove" or "relocate".
        mass_kg:     REQUIRED. Component mass (kg), positive.
        x_mm, y_mm, z_mm: Component position (see mapping above).
        new_x_mm, new_y_mm, new_z_mm: New position, ONLY for "relocate".
        description: Short component name, e.g. "shelter", "winch".
        variant:     "measured" (default) or "theory".
        workbook_path: OMIT to use the project default workbook.
    """
    if action not in ("add", "remove", "relocate"):
        return f"ERROR: action must be 'add', 'remove' or 'relocate' (got {action!r})."
    if mass_kg is None or mass_kg <= 0:
        return ("ERROR: a positive component mass is required. ASK the user for the "
                "component's mass -- never guess it.")

    if action == "add":
        change = MassChange(action, description, mass_kg, new_xyz_mm=(x_mm, y_mm, z_mm))
    elif action == "remove":
        change = MassChange(action, description, mass_kg, old_xyz_mm=(x_mm, y_mm, z_mm))
    else:
        change = MassChange(action, description, mass_kg,
                            old_xyz_mm=(x_mm, y_mm, z_mm),
                            new_xyz_mm=(new_x_mm, new_y_mm, new_z_mm))

    path = workbook_path or None
    try:
        base = vehicle_measured(path) if variant == "measured" else vehicle_theory(path)
    except Exception as e:
        return f"ERROR: could not read workbook: {e}"

    try:
        mod = apply_mass_changes(base, [change])
    except ValueError as e:
        return (f"ERROR: invalid change -- {e}. If a coordinate is missing, ASK the "
                "user for it (datum: X from front axle, Y from centreline, Z from "
                "ground, Z must be positive).")

    rep_b = run_mobility_analysis(base)
    rep_m = run_mobility_analysis(mod)
    d = baseline_delta(base, mod)
    ab, am = rep_b.axle, rep_m.axle
    gb, gm = rep_b.governing_slope(), rep_m.governing_slope()

    pos = (f"X={x_mm:,.0f}, Y={y_mm:,.0f}, Z={z_mm:,.0f} mm"
           + (f" -> X={new_x_mm:,.0f}, Y={new_y_mm:,.0f}, Z={new_z_mm:,.0f} mm"
              if action == "relocate" else ""))
    def _st(ok):
        return "[OK]" if ok else "[OVER]"

    lines = [
        f"=== MASS CHANGE: {action} '{description}' {mass_kg:,.0f} kg at {pos} "
        f"(baseline: {variant}) ===",
        f"{'':<18}{'baseline':>14}{'modified':>14}{'change':>12}",
        f"{'GW (kg)':<18}{base.gw_kg:>14,.0f}{mod.gw_kg:>14,.0f}{d['gw_kg']:>+12,.0f}",
        f"{'Xcg (mm)':<18}{base.xcg_mm:>14,.1f}{mod.xcg_mm:>14,.1f}{d['xcg_mm']:>+12,.1f}",
        f"{'Ycg (mm)':<18}{base.ycg_mm:>14,.1f}{mod.ycg_mm:>14,.1f}{d['ycg_mm']:>+12,.1f}",
        f"{'Zcg (mm)':<18}{base.zcg_mm:>14,.1f}{mod.zcg_mm:>14,.1f}{d['zcg_mm']:>+12,.1f}",
        f"{'Front axle (kg)':<18}{ab.front_kg:>14,.1f}{am.front_kg:>14,.1f}"
        f"   {_st(am.front_ok)} (limit {base.front_axle_limit_kg:,.0f})",
        f"{'Rear axle (kg)':<18}{ab.rear_kg:>14,.1f}{am.rear_kg:>14,.1f}"
        f"   {_st(am.rear_ok)} (limit {base.rear_axle_limit_kg:,.0f})",
        f"{'GVW (kg)':<18}{base.gw_kg:>14,.0f}{mod.gw_kg:>14,.0f}"
        f"   {_st(am.gvw_ok)} (limit {base.gvw_limit_kg:,.0f})",
        f"{'Steer (front %)':<18}{ab.front_pct:>14,.2f}{am.front_pct:>14,.2f}"
        f"   {'[OK]' if am.steer_ok else '[FAIL]'} (needs >= 25%)",
        f"Governing slope : {gb.direction} {gb.grade_pct:.0f}% SF={gb.SF:.4f}  ->  "
        f"{gm.direction} {gm.grade_pct:.0f}% SF={gm.SF:.4f}",
    ]
    if rep_b.corner and rep_m.corner:
        lines.append(
            f"Cornering SF    : {rep_b.corner.SF:.4f} "
            f"(max safe {rep_b.corner.max_safe_speed_kmh:.1f} km/h)  ->  "
            f"{rep_m.corner.SF:.4f} (max safe {rep_m.corner.max_safe_speed_kmh:.1f} km/h)"
        )
    lines.append(
        "STRUCTURAL: " + ("all axle/GVW/steer limits OK" if am.all_ok else
                          "LIMIT EXCEEDED -- modified vehicle fails axle/GVW/steer "
                          "checks (see [OVER]/[FAIL] above)")
    )
    for w in check_cg_plausibility(mod):
        lines.append(f"WARNING: {w}")
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

CG IS MEASURED, NOT PREDICTED: a vehicle's Xcg is not a function of its weight.
If the user asks e.g. "for a 3,200 kg E2 what is the expected Xcg", clarify what
they mean: adding a 3,200 kg payload to the E2 (then ASK for the payload position
and use evaluate_mass_change) or a different vehicle entirely (then they must
supply its CG).

Tool guide -- route by QUESTION TYPE:
- get_vehicle_baseline : DATA LOOKUP for the known E2. "what is the GW / Xcg /
                         Zcg / axle loads / limits?", "measured vs theory
                         difference?". Fast; returns NO slope/cornering results.
- evaluate_mass_change : WHAT-IF. "if I add/remove/relocate X kg at position ...".
                         Computes the combined CG and compares baseline vs
                         modified. ONE change per call. If the component's mass
                         or POSITION is missing, ASK the user -- never guess a
                         position.
- derive_cg_from_wheel_loads : user gives FOUR wheel/weighbridge readings.
                         Returns GW/Xcg/Ycg; Zcg is NOT derivable from static
                         loads.
- run_mobility_check   : FULL stability assessment of the workbook vehicle
                         (slope grid + cornering + axles): "is it stable on a
                         60% slope?", "max safe cornering speed?".
- slope_limit          : slope SFs for a CUSTOM vehicle with user-GIVEN CG only.
- cornering_check      : one cornering case for a CUSTOM vehicle, user-GIVEN CG only.
- flag_unstable        : list workbook cases below a target SF.
- lookup_knowledge     : ALWAYS pass parent_topic="mobility". Use it to cite
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
    get_vehicle_baseline,
    evaluate_mass_change,
    derive_cg_from_wheel_loads,
    slope_limit,
    cornering_check,
    flag_unstable,
]

# User-facing capability registry for the mobility assistant. Curated for end users
# (capability -> purpose -> example), NOT extracted from tool docstrings (those are
# LLM-routing instructions). The "tool" field is the internal tool name, surfaced in
# small text for transparency and checked by a drift test so this guide can't fall out
# of sync with _MOBILITY_TOOLS. "lookup_knowledge" is a shared retriever the mobility
# prompt scopes to parent_topic="mobility"; it's documented here but not in _MOBILITY_TOOLS.
MOBILITY_CAPABILITIES = [
    {"capability": "Workbook mobility analysis",
     "purpose": "Analyse measured or theoretical Spinel CG — axle loads, slopes, cornering",
     "example": "Is the measured Spinel stable on a 60% slope?",
     "tool": "run_mobility_check"},
    {"capability": "Vehicle data lookup",
     "purpose": "GW, CG, geometry, axle loads and limits for the measured or theory E2",
     "example": "What is the measured Xcg of the Spinel E2?",
     "tool": "get_vehicle_baseline"},
    {"capability": "What-if mass change",
     "purpose": "Add / remove / relocate a component and compare CG, axle loads and stability vs baseline",
     "example": "If I add a 3,200 kg shelter at X 4,000 mm, Z 2,500 mm, does the rear axle still hold?",
     "tool": "evaluate_mass_change"},
    {"capability": "CG from wheel loads",
     "purpose": "Derive GW, Xcg and Ycg from four weighbridge readings",
     "example": "Wheel loads are FL 4000, FR 3975, RL 4750, RR 5125 kg — where is the CG?",
     "tool": "derive_cg_from_wheel_loads"},
    {"capability": "Margin screening",
     "purpose": "Find workbook cases below a selected SF",
     "example": "Which mobility cases are below SF 2.2?",
     "tool": "flag_unstable"},
    {"capability": "Custom slope analysis",
     "purpose": "Slope SF and tipping angle from a known CG and geometry",
     "example": "For Xcg 2600 mm and Zcg 1700 mm, what is the ascending slope limit?",
     "tool": "slope_limit"},
    {"capability": "Custom cornering analysis",
     "purpose": "Cornering SF and maximum safe speed",
     "example": "Check cornering at 20 km/h with an 11 m radius.",
     "tool": "cornering_check"},
    {"capability": "Engineering references",
     "purpose": "Explain formulas and mobility requirements",
     "example": "How is ascending slope safety factor calculated?",
     "tool": "lookup_knowledge"},
]
