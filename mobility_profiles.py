"""
Vehicle-family profiles for the mobility workflow.

A VehicleProfile bundles everything that varies BETWEEN vehicle families so the
generic physics in mobility_engine.py stays family-agnostic:
  - geometry (wheelbase, track) and grouped axle / GVW limits
  - the axle layout and support-group reduction (T1 is 4-axle -> 2 groups)
  - aero assumptions and minimum turning radius
  - the SAR angle/trig replication convention (rounded 31/16.7 deg, 3-dp trig)
  - OEM safety-factor margins and the ISO twist-lock datum offset (amendments
    from the T1 source audit -- these are variant-specific and must not be
    hard-coded)

make_vehicle() maps the grouped limits onto the existing Vehicle dataclass
(front group -> front_axle_limit, rear group -> rear_axle_limit), so the
validated two-support-line engine runs unchanged: for T1 it treats axles 1+2
as the "front axle" and 3+4 as the "rear axle".

Datum (matches mobility_engine.Vehicle): X longitudinal from the front support
line, Y right-positive from centreline, Z from ground.
"""
from dataclasses import dataclass, field
from typing import Mapping, Optional

from mobility_engine import Vehicle, Aero


@dataclass(frozen=True)
class Axle:
    name: str
    x_mm: float          # position from the front support-group centre
    limit_kg: float


@dataclass(frozen=True)
class AxleGroup:
    name: str
    axle_names: tuple
    x_mm: float          # group-centre position (support line)
    limit_kg: float


@dataclass(frozen=True)
class VehicleProfile:
    key: str
    display_name: str
    support_model: str                       # "two_axle" | "four_axle_grouped"
    wheelbase_mm: float                       # effective (group-centre to group-centre)
    track_mm: float
    front_group_limit_kg: float
    rear_group_limit_kg: float
    gvw_limit_kg: float
    aero: Aero
    default_radius_m: float
    axles: tuple
    groups: tuple
    longitudinal_angle_deg: Mapping           # grade_pct -> rounded SAR angle
    side_angle_deg: Mapping
    trig_dp: Optional[int] = 3
    # --- audit amendments (variant-specific, previously hard-coded) ---
    iso_plane_offset_mm: float = 0.0          # front support line -> front ISO plane
    oem_margin_long: float = 1.5              # OEM recommended slope SF (SAR-stated)
    oem_margin_lat: float = 1.5
    oem_margin_corner: float = 1.5
    zcg_source_default: str = ""              # provenance note for Zcg

    def make_vehicle(self, name: str, gw_kg: float, xcg_mm: float,
                     ycg_mm: float, zcg_mm: float) -> Vehicle:
        """Build a mobility_engine.Vehicle, mapping grouped limits onto the
        engine's front/rear axle-limit fields."""
        return Vehicle(
            name=name,
            gw_kg=gw_kg, xcg_mm=xcg_mm, ycg_mm=ycg_mm, zcg_mm=zcg_mm,
            wheelbase_mm=self.wheelbase_mm, track_mm=self.track_mm,
            front_axle_limit_kg=self.front_group_limit_kg,
            rear_axle_limit_kg=self.rear_group_limit_kg,
            gvw_limit_kg=self.gvw_limit_kg,
        )


def slope_kwargs_for(profile: VehicleProfile, direction: str, grade_pct: float) -> dict:
    """
    Slope-call kwargs (angle_deg, trig_dp) for a profile + direction + grade.
    Longitudinal directions use the profile's longitudinal_angle_deg map;
    lateral (kerbside/roadside) use side_angle_deg. A grade absent from the map
    yields angle_deg=None so the engine uses exact atan(grade/100).
    """
    if direction in ("ascending", "descending"):
        amap = profile.longitudinal_angle_deg
    elif direction in ("kerbside", "roadside"):
        amap = profile.side_angle_deg
    else:
        raise ValueError(f"unknown slope direction {direction!r}")
    return {"angle_deg": amap.get(float(grade_pct)), "trig_dp": profile.trig_dp}


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

E2_PROFILE = VehicleProfile(
    key="e2",
    display_name="Spinel E-2",
    support_model="two_axle",
    wheelbase_mm=4800.0,
    track_mm=2088.0,
    front_group_limit_kg=8000.0,
    rear_group_limit_kg=10600.0,
    gvw_limit_kg=18600.0,
    aero=Aero(side_area_m2=35.52, wind_height_m=2.05),
    default_radius_m=11.0,
    axles=(
        Axle("Front axle", 0.0, 8000.0),
        Axle("Rear axle", 4800.0, 10600.0),
    ),
    groups=(
        AxleGroup("Front", ("Front axle",), 0.0, 8000.0),
        AxleGroup("Rear", ("Rear axle",), 4800.0, 10600.0),
    ),
    longitudinal_angle_deg={60.0: 31.0},
    side_angle_deg={30.0: 16.7},
    trig_dp=3,
    iso_plane_offset_mm=1450.0,
    # E2 workflow OEM margins (preserve existing mobility_scenarios behaviour)
    oem_margin_long=2.0, oem_margin_lat=2.2, oem_margin_corner=2.2,
    zcg_source_default="measured by vehicle tilt test",
)

T1_PROFILE = VehicleProfile(
    key="t1",
    display_name="Spinel T-1",
    support_model="four_axle_grouped",
    wheelbase_mm=5250.0,
    track_mm=2100.0,
    front_group_limit_kg=16000.0,
    rear_group_limit_kg=20000.0,
    gvw_limit_kg=36000.0,
    aero=Aero(side_area_m2=47.3634, wind_height_m=2.205),
    default_radius_m=14.0,
    axles=(
        Axle("Axle 1", -875.0, 8000.0),
        Axle("Axle 2", 875.0, 8000.0),
        Axle("Axle 3", 4525.0, 10000.0),
        Axle("Axle 4", 5975.0, 10000.0),
    ),
    groups=(
        AxleGroup("Front group", ("Axle 1", "Axle 2"), 0.0, 16000.0),
        AxleGroup("Rear group", ("Axle 3", "Axle 4"), 5250.0, 20000.0),
    ),
    # SAR rounded slope angles (verified vs stored SFs to 1e-9): 60% -> 31 deg,
    # side 30% -> 16.7, side 25% -> 14.0. Longitudinal 50% is left to exact
    # atan (the workbook does not round it), so it is intentionally absent.
    longitudinal_angle_deg={60.0: 31.0},
    side_angle_deg={30.0: 16.7, 25.0: 14.0},
    trig_dp=3,
    iso_plane_offset_mm=2400.0,   # AFE N1 spec: front axle -> front ISO plane
    # T1 SAR states OEM recommended slope SF = 1.5 for all directions
    oem_margin_long=1.5, oem_margin_lat=1.5, oem_margin_corner=1.5,
    zcg_source_default="CAD model (theoretical -- no tilt test for T1)",
)

PROFILES = {p.key: p for p in (E2_PROFILE, T1_PROFILE)}


def get_profile(key: str) -> VehicleProfile:
    try:
        return PROFILES[key]
    except KeyError:
        raise KeyError(f"unknown vehicle profile {key!r}; have {sorted(PROFILES)}")


if __name__ == "__main__":
    from mobility_engine import run_mobility_analysis
    v = T1_PROFILE.make_vehicle("T1 laden", 26175.0,
                                2717.765042979943, -13.037249283667734, 1750.3799217829044)
    rep = run_mobility_analysis(v)
    print(f"T1 front group = {rep.axle.front_kg:.1f} kg (want 12625)")
    print(f"T1 rear group  = {rep.axle.rear_kg:.1f} kg (want 13550)")
    assert abs(rep.axle.front_kg - 12625.0) < 0.5
    print("[OK] T1 profile reproduces workbook axle loads")
