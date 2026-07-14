# Mounted Natural Frequency

**Chunk:** `shock_mount/natural_frequency`
**Source (method):** **The VMC Group — "Wire Rope Isolators" Tech Notes** (classical `fn = (1/2π)√(K/m)`; `K_shock = (2π·fn)²·m`).
**Source (code):** `physics_engine.py` (`_natural_freq`); worked value validated against `Shock Isolator_850kg_4 Bayed 35U.xls`.
**Grounding:** validated-in-repo AND source-confirmed

---

Each load case models the mounted mass on its isolators as a single-degree-of-
freedom spring–mass system. Its undamped natural frequency is:

## Formula

```
fn = (1 / 2π) · √(k / m)        [Hz]
```

| Symbol | Meaning                                   | Unit |
|--------|-------------------------------------------|------|
| k      | Isolator stiffness for the case           | N/m  |
| m      | Mass carried per isolator for the case    | kg   |

- `k` is the **compression** stiffness for the vertical/lateral compression
  cases and the **shear/roll** stiffness for the two shear cases
  (see `four_load_cases.md`).
- `m` is the per-isolator mass from `load_distribution.md`, not the total system
  mass.

## Why fn is the pivot quantity

`fn` increases monotonically with `k` and decreases with `m`. Both the
transmitted acceleration and the dynamic deflection are functions of `fn`, so
`fn` is the single quantity that couples "which spring" to "how well it
isolates" (see `transmitted_acceleration.md`, `dynamic_deflection.md`).

## Tech Notes note on units

The VMC Tech Notes state the classical relation `fn = (1/2π)√(K/m)` where **`m`
is mass in `lb-sec²/inch`, not weight**, and give the inverse `K_shock =
(2π·fn)²·m`. The engine works in SI (`K` in N/m, `m` in kg), which is the same
relation in consistent units. The Tech Notes also warn that published spring
rates are *average* — actual stiffness depends where the static load sits on the
third-order load-deflection curve (`model_limitations.md`).

## Worked value (CB1400-15, Z-axis Comp-Bottom, 850 kg / 6 bottom)

```
m = 850 / 6 = 141.67 kg
k_comp = 2650 lb/in = 464 086 N/m
fn = (1 / 2π) · √(464086 / 141.67) = 9.109 Hz
```

Matches the reference Excel `850kg,Stooth,Comp,Bottom` sheet.
