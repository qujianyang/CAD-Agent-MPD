"""
Profile-based mobility analysis runner.

Keeps mobility_engine.py family-agnostic: this thin layer applies a
VehicleProfile's exact assumptions (the SAR rounded-angle / 3-dp-trig
convention via slope_kwargs_for, the profile aero and default turning radius)
so the workbook safety factors reproduce exactly, without any special-casing
inside the validated engine.

run_profile_mobility_analysis() returns the same mobility_engine.MobilityReport
that run_mobility_analysis() does, so every downstream consumer (formatters,
SAR generator, UI) is unchanged -- only the angle/trig/aero inputs differ per
vehicle family.

Verified: the T1 measured vehicle reproduces the workbook SFs
(asc60 2.4074, desc60 2.5838, kerb30 1.9775, road30 2.0272, corner 3.6015)
and the theory vehicle its own set (2.2875 / 2.7037 / 2.0217 / 1.9830 / 3.6073).
"""
from typing import Optional

from mobility_engine import (
    Vehicle, MobilityReport, axle_loads,
    slope_stability, side_slope_stability, cornering_stability,
)
from mobility_profiles import VehicleProfile, slope_kwargs_for


def run_profile_mobility_analysis(
    vehicle: Vehicle,
    profile: VehicleProfile,
    grades_long: tuple = (60, 50),
    grades_side: tuple = (30, 25),
    speed_kmh: float = 15.0,
    radius_m: Optional[float] = None,
    wind_kmh: float = 60.0,
    target_SF: float = 1.0,
) -> MobilityReport:
    """
    Run the standard mobility suite applying `profile`'s SAR conventions.

    Longitudinal and lateral slopes use the profile's rounded-angle / trig-dp
    map (slope_kwargs_for); grades absent from the map fall back to exact
    atan(). Cornering uses the profile aero and, unless overridden, the
    profile's default turning radius.
    """
    axle = axle_loads(vehicle)

    slopes = []
    for grade in grades_long:
        for direction in ("ascending", "descending"):
            slopes.append(slope_stability(
                vehicle, grade, direction,
                **slope_kwargs_for(profile, direction, grade)))
    for grade in grades_side:
        for direction in ("kerbside", "roadside"):
            slopes.append(side_slope_stability(
                vehicle, grade, direction,
                **slope_kwargs_for(profile, direction, grade)))

    corner = cornering_stability(
        vehicle, profile.aero, speed_kmh=speed_kmh,
        radius_m=profile.default_radius_m if radius_m is None else radius_m,
        wind_kmh=wind_kmh)

    return MobilityReport(vehicle, axle, slopes, corner, None, target_SF)


def format_profile_axle_context(profile: VehicleProfile, wheel_summary=None) -> str:
    """
    Human-readable note on how a multi-axle profile maps onto the engine's two
    support lines (for the UI / SAR). Pass a FourAxleWheelLoadSummary as
    `wheel_summary` to append the measured per-axle totals.
    """
    lines = [f"Support model: {profile.display_name} ({profile.support_model})"]
    if profile.support_model == "four_axle_grouped":
        groups = {g.name: g for g in profile.groups}
        for g in profile.groups:
            members = ", ".join(g.axle_names)
            lines.append(f"  {g.name}: {members}  (limit {g.limit_kg:,.0f} kg)")
        lines.append("  -> engine treats each group as one support line "
                     "(front group = 'front axle', rear group = 'rear axle').")
    else:
        lines.append("  Two-axle vehicle: engine axles map directly.")

    if wheel_summary is not None:
        a1, a2, a3, a4 = wheel_summary.axle_totals_kg
        lines += [
            "Measured axle totals (kg):",
            f"  Axle 1 {a1:,.0f} | Axle 2 {a2:,.0f} | Axle 3 {a3:,.0f} | Axle 4 {a4:,.0f}",
            f"  Front group {wheel_summary.front_group_kg:,.0f} | "
            f"Rear group {wheel_summary.rear_group_kg:,.0f}",
        ]
    return "\n".join(lines)


if __name__ == "__main__":
    from mobility_profiles import T1_PROFILE
    v = T1_PROFILE.make_vehicle("T1 measured", 26175.0,
                                2717.765042979943, -13.037249283667734, 1750.3799217829044)
    rep = run_profile_mobility_analysis(v, T1_PROFILE)
    by = {(r.grade_pct, r.direction): r for r in rep.slope_results}
    print(format_profile_axle_context(T1_PROFILE))
    print(f"front={rep.axle.front_kg:.1f} rear={rep.axle.rear_kg:.1f}")
    print(f"asc60={by[(60,'ascending')].SF:.6f}  desc60={by[(60,'descending')].SF:.6f}")
    print(f"kerb30={by[(30,'kerbside')].SF:.6f}  road30={by[(30,'roadside')].SF:.6f}")
    print(f"corner={rep.corner.SF:.6f}")
    assert abs(by[(60, "ascending")].SF - 2.4073834454365226) < 1e-9
    assert abs(rep.corner.SF - 3.601540982344649) < 1e-9
    print("[OK] T1 measured reproduces workbook SFs")
