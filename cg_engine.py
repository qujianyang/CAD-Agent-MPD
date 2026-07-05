"""
Small centre-of-gravity engine: mass-moment combination and payload reverse-CG.

Pure functions over immutable CGState value objects. No I/O, no physics beyond
first-moment balance:

    combined mass = sum(M_i)
    Xcg = sum(M_i * X_i) / sum(M_i)          (same for Y, Z)

    payload mass = GW_combined - CW_base
    X_payload = (GW*X_GW - CW*X_CW) / payload_mass    (same for Y, Z)

Used by the T1 workflow to (a) build a laden vehicle CG from a component
mass table (theory buildup) or from combined + base CG states, and (b)
back-solve the shelter/payload CG from the laden and unladen vehicle CGs
(the 'Re-engrg Laden Shelter Weight' sheet method). All coordinates use the
vehicle datum: X longitudinal, Y right-positive from centreline, Z from ground.
"""
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CGState:
    name: str
    mass_kg: float
    x_mm: float
    y_mm: float
    z_mm: float


def combined_cg(items: Sequence[CGState], name: str = "combined") -> CGState:
    """
    Mass-weighted CG of one or more component states (first-moment balance).
    Raises ValueError on an empty list or non-positive total mass.
    """
    if not items:
        raise ValueError("combined_cg requires at least one CGState")
    total = sum(i.mass_kg for i in items)
    if total <= 0:
        raise ValueError(f"combined mass must be positive, got {total}")
    mx = sum(i.mass_kg * i.x_mm for i in items)
    my = sum(i.mass_kg * i.y_mm for i in items)
    mz = sum(i.mass_kg * i.z_mm for i in items)
    return CGState(name, total, mx / total, my / total, mz / total)


def derive_payload_cg(
    combined: CGState,
    base: CGState,
    payload_name: str = "payload",
) -> CGState:
    """
    Back-solve the payload CG from a combined (laden) and a base (unladen)
    CG state: payload = combined - base (moment subtraction).
    Raises ValueError when the payload mass is not positive.
    """
    pm = combined.mass_kg - base.mass_kg
    if pm <= 0:
        raise ValueError(
            f"payload mass must be positive, got {pm} "
            f"(combined {combined.mass_kg} - base {base.mass_kg})"
        )
    x = (combined.mass_kg * combined.x_mm - base.mass_kg * base.x_mm) / pm
    y = (combined.mass_kg * combined.y_mm - base.mass_kg * base.y_mm) / pm
    z = (combined.mass_kg * combined.z_mm - base.mass_kg * base.z_mm) / pm
    return CGState(payload_name, pm, x, y, z)


if __name__ == "__main__":
    combined = CGState("Laden T1", 26175.0,
                       2717.765042979943, -13.037249283667734, 1750.3799217829044)
    base = CGState("Unladen N1", 16450.0,
                   1946.8085106382978, 15.957446808510667, 1117.0)
    pl = derive_payload_cg(combined, base)
    print(f"Payload: mass={pl.mass_kg:.1f} kg  X={pl.x_mm:.3f}  "
          f"Y={pl.y_mm:.3f}  Z={pl.z_mm:.3f} mm")
    assert abs(pl.z_mm - 2821.752642947817) < 1e-3
    print("[OK] payload Z matches T1 workbook (2821.75 mm)")
