# Load Distribution (Mass per Isolator)

**Chunk:** `shock_mount/load_distribution`
**Source:** `physics_engine.py` (`_loads_per_isolator`); formulas transcribed verbatim from `Shock Isolator_850kg_4 Bayed 35U.xls`.
**Grounding:** validated-in-repo

---

Before any physics runs, the total system mass `M` is split into the effective
mass carried **per isolator** for each of the four load cases. Every downstream
`fn`/`GT`/`ΔD` uses this per-isolator mass, never `M` directly.

## Inputs

| Symbol     | Meaning                          |
|------------|----------------------------------|
| `M`        | Total system mass [kg]           |
| `n_bottom` | Number of bottom-mounted isolators |
| `n_wall`   | Number of wall-mounted isolators   |

`n_bottom` and `n_wall` must both be `> 0` (the engine raises otherwise).

## The four per-isolator masses

| Case            | Direction | Formula            | Reason                                   |
|-----------------|-----------|--------------------|------------------------------------------|
| Comp - Bottom   | Z         | `M / n_bottom`     | Gravity is unidirectional; every bottom mount shares the weight equally and simultaneously. |
| Comp - Wall     | Y         | `M / n_wall / 2`   | Lateral shock: two opposing wall faces share the load (load-sharing factor 1/2). |
| Roll - Wall     | X, Z      | `M / n_wall / 2`   | Same load-sharing logic, shear stiffness. |
| Roll - Bottom   | X, Y      | `M / n_bottom / 2` | Same load-sharing logic, bottom mounts in shear. |

## The `/2` load-sharing factor

The vertical case has **no** `/2` because gravity loads all bottom mounts at
once. The three lateral/shear cases carry `/2` because a lateral shock is
resisted by two opposing rows/faces of mounts simultaneously. This `/2` is the
convention baked into the validated Excel template; omitting it doubles the
per-isolator mass and produces wrong `GT`/`ΔD`.

## Static load (separate from the four dynamic cases)

The gravity (pre-shock) static load per bottom mount is `M / n_bottom` — the
same as the Comp-Bottom dynamic mass — and feeds the static gate
(`static_load_gate.md`). Wall mounts are treated as statically unloaded.

## Worked example (M = 850 kg, n_bottom = 6, n_wall = 4)

| Case          | Calculation   | m per isolator |
|---------------|---------------|----------------|
| Comp - Bottom | 850 / 6       | **141.67 kg**  |
| Comp - Wall   | 850 / 4 / 2   | **106.25 kg**  |
| Roll - Wall   | 850 / 4 / 2   | **106.25 kg**  |
| Roll - Bottom | 850 / 6 / 2   | **70.83 kg**   |

These match the Excel `m =` cells exactly.
