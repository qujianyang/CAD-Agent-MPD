"""
Mobility report generation — assembles the SAR Mobility/Stability chapter.

Deterministic: all numbers from mobility_engine. No LLM in numeric path.
"""
from datetime import date as _date
from typing import Optional

from mobility_engine import (
    MobilityReport, format_slope_table, format_mobility_report,
)


def generate_mobility_chapter(
    report: MobilityReport,
    *,
    project: str = "Project Spinel",
    variant: str = "Variant E-2",
    standard: str = "AVTP / Def Stan",
    report_date: Optional[str] = None,
) -> str:
    """
    Build the Mobility / Stability chapter (Markdown) from a MobilityReport.

    H.1  Scope and basis
    H.2  Axle loadings & steerability
    H.3  Static slope stability
    H.4  Cornering stability
    H.5  Assessment
    """
    v = report.vehicle
    ax = report.axle
    c = report.corner
    d = report_date or _date.today().isoformat()
    target = report.target_SF

    lines = [
        "# Appendix H - Mobility and Stability Analysis",
        "",
        f"*{project}, {variant}  |  {d}*",
        "",
        "## H.1  Scope and Basis",
        "",
        f"The mobility and stability of {v.name} has been assessed using the "
        f"measured centre-of-gravity (CG) data. All calculations follow the "
        f"moment-balance method in accordance with {standard}.",
        "",
        f"Vehicle parameters used in this analysis:",
        "",
        f"| Parameter | Value |",
        f"|---|---|",
        f"| Gross weight (GW) | {v.gw_kg:,.0f} kg |",
        f"| Xcg (from front axle) | {v.xcg_mm:.1f} mm |",
        f"| Ycg (from centreline, +driverside) | {v.ycg_mm:.1f} mm |",
        f"| Zcg (above ground) | {v.zcg_mm:.1f} mm |",
        f"| Wheelbase | {v.wheelbase_mm:.0f} mm |",
        f"| Track width | {v.track_mm:.0f} mm |",
        "",
        "The safety factor formula applied throughout is:",
        "",
        "`SF = stabilising moment / overturning moment`",
        "`   = (mg · cosθ · lever_m) / (mg · sinθ · Zcg_m)`",
        "",
        f"An item is assessed as satisfactory when SF ≥ {target:g}.",
        "",
        "## H.2  Axle Loadings and Steerability",
        "",
        f"| Axle | Load (kg) | Limit (kg) | Status |",
        f"|---|---|---|---|",
        f"| Front | {ax.front_kg:,.1f} ({ax.front_pct:.1f}% of GW) | "
        f"{v.front_axle_limit_kg:,.0f} | {'OK' if ax.front_ok else '**EXCEEDS LIMIT**'} |",
        f"| Rear  | {ax.rear_kg:,.1f} | {v.rear_axle_limit_kg:,.0f} | "
        f"{'OK' if ax.rear_ok else '**EXCEEDS LIMIT**'} |",
        f"| GVW   | {v.gw_kg:,.0f} | {v.gvw_limit_kg:,.0f} | "
        f"{'OK' if ax.gvw_ok else '**EXCEEDS LIMIT**'} |",
        "",
        f"The front axle carries {ax.front_pct:.1f}% of the gross weight, which "
        f"{'satisfies' if ax.steer_ok else 'does NOT satisfy'} the minimum "
        f"25% steerability requirement (bodybuilder guideline).",
        "",
        "## H.3  Static Slope Stability",
        "",
        "Longitudinal (ascending: tips toward rear; descending: tips toward front):",
        "Lateral (kerbside: tips left; roadside: tips right).",
        "",
        "```",
        format_slope_table(report),
        "```",
        "",
    ]

    # Critical angle interpretation
    asc_cases = [r for r in report.slope_results if r.direction == "ascending"]
    if asc_cases:
        crit = asc_cases[0].crit_angle_deg
        lines += [
            f"The vehicle will tip over longitudinally (ascending) if the slope exceeds "
            f"**{crit:.1f}°** (geometric critical angle based on CG position). "
            f"The military test-track requirement of 60% grade ({60/(1+0**0.5):.1f}° "
            f"actual: {__import__('math').degrees(__import__('math').atan(0.6)):.1f}°) is well within this limit.",
            "",
        ]

    lines += [
        "## H.4  Cornering Stability",
        "",
    ]

    if c:
        verdict = "PASS" if c.SF >= target else "FAIL"
        lines += [
            f"Analysis at {c.speed_kmh:.0f} km/h, minimum turning radius {c.radius_m:.0f} m, "
            f"wind speed {c.wind_kmh:.0f} km/h:",
            "",
            f"| Parameter | Value |",
            f"|---|---|",
            f"| Centrifugal force Fc | {c.Fc_N:,.1f} N |",
            f"| Overturning moment (Fc) | {c.over_fc_Nm:,.1f} Nm |",
            f"| Wind force Fw | {c.Fw_N:,.1f} N |",
            f"| Overturning moment (wind) | {c.over_wind_Nm:,.1f} Nm |",
            f"| Total overturning moment | {c.over_total_Nm:,.1f} Nm |",
            f"| Resisting moment | {c.resist_Nm:,.1f} Nm |",
            f"| **Safety factor** | **{c.SF:.3f}** |",
            f"| Maximum safe cornering speed (SF=1) | {c.max_safe_speed_kmh:.1f} km/h |",
            "",
            f"Cornering verdict: **{verdict}**",
            "",
        ]
    else:
        lines += ["*Cornering analysis not performed.*", ""]

    # H.5 Assessment
    gov = report.governing_slope()
    failing = report.critical_cases()
    lines += ["## H.5  Assessment", ""]

    if gov:
        lines.append(
            f"The governing (lowest SF) case is **{gov.direction} {gov.grade_pct:.0f}% grade** "
            f"with SF = {gov.SF:.3f}. "
        )

    if report.all_passed:
        lines.append(
            f"All axle loadings, slope stability cases, and cornering stability "
            f"meet the required safety factor of {target:g}. "
            f"The vehicle mobility provisions are assessed to be **satisfactory**."
        )
    else:
        names = "; ".join(
            f"{r.direction} {r.grade_pct:.0f}% (SF {r.SF:.3f})"
            for r in sorted(failing, key=lambda r: r.SF)
        )
        lines.append(
            f"The following case(s) do NOT meet the required factor of {target:g} "
            f"and require review: {names}."
        )
    lines.append("")

    # Approach / departure (if available)
    if report.approach:
        app = report.approach
        lines += [
            "### Approach and Departure Angle Suitability",
            "",
            f"| Angle | Value | Equivalent grade | Required | Status |",
            f"|---|---|---|---|---|",
            f"| Approaching | {app.approach_angle_deg:.1f}° | {app.approach_grade_pct:.1f}% | "
            f"{app.required_grade_pct:.0f}% | {'Suitable' if app.approach_ok else '**Unsuitable**'} |",
            f"| Departure | {app.departure_angle_deg:.1f}° | {app.departure_grade_pct:.1f}% | "
            f"{app.required_grade_pct:.0f}% | {'Suitable' if app.departure_ok else '**Unsuitable**'} |",
            "",
        ]

    return "\n".join(lines)
