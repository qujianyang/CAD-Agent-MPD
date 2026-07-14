# The Four Load Cases

**Chunk:** `shock_mount/four_load_cases`
**Source:** `physics_engine.py` (`run_analysis` direction list) and `catalog.py` (`select_isolator`); one case per sheet in `Shock Isolator_850kg_4 Bayed 35U.xls`.
**Grounding:** validated-in-repo

---

Every candidate isolator is evaluated against **four independent load cases**,
one per calculation sheet in the reference Excel. A part is acceptable only if
**all four** pass their `GT` and `ΔD` gates (and the static gate — see
`governing_check.md`).

## The four cases

| # | Case label (code)           | Axis | Mount  | Stiffness used | Mass per isolator     | Travel limit  |
|---|-----------------------------|------|--------|----------------|-----------------------|---------------|
| 1 | Comp - Bottom (Z-axis)      | Z    | Bottom | `k_comp`       | `M / n_bottom`        | `d_max_comp`  |
| 2 | Comp - Wall (Y-axis)        | Y    | Wall   | `k_comp`       | `M / n_wall / 2`      | `d_max_comp`  |
| 3 | Roll - Wall (X,Z-axis)      | X, Z | Wall   | `k_shear/roll` | `M / n_wall / 2`      | `d_max_shear` |
| 4 | Roll - Bottom (X,Y-axis)    | X, Y | Bottom | `k_shear/roll` | `M / n_bottom / 2`    | `d_max_shear` |

- Cases 1–2 load the wire rope in **compression**, using `k_comp` and the
  compression travel limit.
- Cases 3–4 load it in **shear/roll**, using `k_shear` and the shear travel
  limit.
- The four cases together span all three orthogonal axes (X, Y, Z).

## All-pass rule

```
part valid ⇔ (GT_i < GT_limit AND ΔD_i < travel_limit_i) for every case i
            AND static gate passes
```

A single failing case disqualifies the part for that load. Which case fails
first (the "governing" case) is defined in `governing_check.md`.

## Per-case physics

Each case runs the same pipeline with its own `k` and `m`:
`impulse_velocity.md` → `natural_frequency.md` →
`transmitted_acceleration.md` + `dynamic_deflection.md`.

## Reference (CB1400-15, 850 kg, 6 bottom + 4 wall)

| Case          | m [kg] | k [lb/in] | GT [G] | ΔD [mm] |
|---------------|--------|-----------|--------|---------|
| Comp - Bottom | 141.67 | 2650 comp | 6.296  | 18.85   |
| Comp - Wall   | 106.25 | 2650 comp | (per Excel) | (per Excel) |
| Roll - Wall   | 106.25 | 1080 shear| (per Excel) | (per Excel) |
| Roll - Bottom | 70.83  | 1080 shear| (per Excel) | (per Excel) |

The Comp-Bottom row is the fully validated 4-dp baseline
(`validation_excel_baseline.md`).
