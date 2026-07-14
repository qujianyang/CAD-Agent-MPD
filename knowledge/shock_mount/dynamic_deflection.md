# Dynamic Deflection (ΔD)

**Chunk:** `shock_mount/dynamic_deflection`
**Source (method):** **The VMC Group — "Wire Rope Isolators" Tech Notes** (`D_d = V²/(386·Gt)`, `f_ns = V/(2π·D_d)`).
**Source (code):** `physics_engine.py` (`_dynamic_deflection_mm`, `DirectionResult.delta_ok`); worked value validated against `Shock Isolator_850kg_4 Bayed 35U.xls`.
**Grounding:** validated-in-repo AND source-confirmed

---

The **dynamic deflection** `ΔD` is the peak travel of the isolator during the
shock event. It must stay within the isolator's rated travel (and any
installation clearance) or the mount bottoms out / collides.

## Formula

```
ΔD = V / (2π · fn)        [m]   →  × 1000 for mm
```

- `V`  — pulse velocity change (`impulse_velocity.md`)
- `fn` — mounted natural frequency for the case (`natural_frequency.md`)

`ΔD` is inversely related to `fn`: a **softer** spring (lower `fn`) gives lower
`GT` but **larger** `ΔD`. This is the direct tension against
`transmitted_acceleration.md` and the reason for the `max_clearance` objective.

The VMC Tech Notes give the equivalent dynamic-displacement form
`D_d = V² / (386 · Gt)` (imperial, inches; `386 ≈ g`) together with
`f_ns = V / (2π · D_d)` — algebraically the same as `ΔD = V / (2π·fn)`.

## Pass criterion

```
PASS (this case)  ⇔  ΔD < effective travel limit      (strict inequality)
```

The effective travel limit is the **tighter** of the mount's own rated travel
and the mapped installation clearance:

```
limit = min( d_max , clearance_for_this_axis )
```

- Cases 1–2 (compression) use `d_max_comp`.
- Cases 3–4 (shear/roll) use `d_max_shear`.

See `travel_limit_gate.md` for the full gate and axis→clearance mapping.

## Worked value (CB1400-15, Z-axis Comp-Bottom)

```
ΔD = 1.0791 / (2π · 9.109) × 1000 = 18.85 mm
d_max_comp = 1.4 in = 35.56 mm   →  18.85 < 35.56  → OK
```

Matches the reference Excel to 4 decimal places.
