# Transmitted Acceleration (GT)

**Chunk:** `shock_mount/transmitted_acceleration`
**Source (method):** **The VMC Group — "Wire Rope Isolators" Tech Notes** (`f_ns = (Gt·61.4)/V`, i.e. `Gt = 2π·fn·V/g`).
**Source (code):** `physics_engine.py` (`_transmitted_g`, `DirectionResult.GT_ok`); worked value validated against `Shock Isolator_850kg_4 Bayed 35U.xls`.
**Grounding:** validated-in-repo AND source-confirmed

---

The **transmitted acceleration** `GT` is the peak acceleration the isolated
equipment actually experiences after the mount attenuates the input pulse. It is
the quantity compared against the equipment's fragility limit.

## Formula

```
GT = (2π · fn · V) / g          [G]
```

- `fn` — mounted natural frequency for the case (`natural_frequency.md`)
- `V`  — pulse velocity change (`impulse_velocity.md`)
- `g`  — 9.81 m/s²

## Monotonicity (why softer isolates better)

```
fn = (1/2π)·√(k/m)   →   GT = (2π·fn·V)/g   =   V·√(k/m)/g
```

`GT` rises monotonically with `k`. A **softer** spring lowers `fn`, which lowers
`GT` — the basis of the `best_isolation` objective. The trade-off is larger
deflection (`dynamic_deflection.md`).

## Same relation in the VMC Tech Notes

The Tech Notes express the shock natural frequency as `f_ns = (Gt · 61.4) / V`,
which rearranges to `Gt = f_ns · V / 61.4`. With imperial `g = 386.4 in/s²`,
`61.4 ≈ g / 2π`, so `Gt = 2π · fn · V / g` — identical to the engine's formula.
`Gt` is the equipment's tolerable peak (its "fragility"); it is the **output**,
distinct from the pulse **input** `Ao`.

## Pass criterion

```
PASS (this case)  ⇔  GT < GT_limit          (strict inequality in code)
```

`GT_limit` defaults to 10 G in the tool. Its origin (equipment/customer limit
vs. standard) is documented in `transmitted_g_limit.md`.

## Worked value (CB1400-15, Z-axis Comp-Bottom)

```
GT = (2π · 9.109 · 1.0791) / 9.81 = 6.296 G   (< 10 G → OK)
```

Matches the reference Excel to 4 decimal places.
