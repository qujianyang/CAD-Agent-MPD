# The 4 Load Cases (Mass-per-Isolator Distribution)

A wire rope isolator must be evaluated against **four independent load cases**.
The isolator passes only if ALL four cases pass `GT < GT_limit` AND `ΔD < dmax`.

**Source of truth:** the four calculation sheets in
`Shock Isolator_850kg_4 Bayed 35U.xls` — one sheet per case.

---

## Notation

- `M` = total system mass [kg]
- `n_bottom` = number of bottom-mounted isolators
- `n_wall`   = number of wall-mounted isolators
- `m`        = mass per isolator for the given case [kg]

---

## The 4 cases

| # | Excel sheet                       | Direction | Mount  | Stiffness used | Mass per isolator      | Travel limit  |
|---|-----------------------------------|-----------|--------|----------------|------------------------|---------------|
| 1 | `850kg,Stooth,Comp,Bottom`        | Z         | Bottom | K_compression  | `m = M / n_bottom`     | dmax_comp     |
| 2 | `850kg,Stooth,Comp,Wall`          | Y         | Wall   | K_compression  | `m = M / n_wall / 2`   | dmax_comp     |
| 3 | `850kg,Stooth,Roll,Wall`          | X, Z      | Wall   | K_shear/roll   | `m = M / n_wall / 2`   | dmax_shear    |
| 4 | `850kg,Stooth,Rollshear,Bottom`   | X, Y      | Bottom | K_shear/roll   | `m = M / n_bottom / 2` | dmax_shear    |

---

## Why the `/2` for lateral cases?

Vertical (Z, case 1) has **no `/2`** because gravity is unidirectional — every
bottom mount carries weight equally and simultaneously.

The three lateral cases (Y, X-Z, X-Y) have a `/2` load-sharing factor because
two opposing sides of the structure both resist a lateral shock:

- **Comp-Wall (Y)**: 2 wall mounts on left + 2 on right share the lateral load
- **Roll-Wall (X,Z)**: same wall mounts, but in shear/roll direction
- **Roll-Bottom (X,Y)**: 2 rows of bottom mounts share the shear load

This `/2` is **the convention used in the validated Excel template**. Do not
omit it; doing so changes mass-per-isolator by 2× and gives wrong GT/ΔD.

---

## Worked Example — M = 850 kg, n_bottom = 6, n_wall = 4

| Case | Formula     | Calculation | m per isolator |
|------|-------------|-------------|----------------|
| 1. Comp-Bottom (Z)   | M / n_bottom         | 850 / 6        | **141.67 kg** |
| 2. Comp-Wall (Y)     | M / n_wall / 2       | 850 / 4 / 2    | **106.25 kg** |
| 3. Roll-Wall (X,Z)   | M / n_wall / 2       | 850 / 4 / 2    | **106.25 kg** |
| 4. Roll-Bottom (X,Y) | M / n_bottom / 2     | 850 / 6 / 2    |  **70.83 kg** |

These match the Excel `m =` cells exactly.

---

## Which K to use

| Case | K from datasheet      | Notes                                       |
|------|-----------------------|---------------------------------------------|
| 1, 2 | `K_compression`       | Axial compression of the wire rope         |
| 3, 4 | `K_shear/roll`        | Lateral / shear deflection mode             |

For CB1400-15 (datasheet REV:5):
- K_comp  = 2650 lb/in = 464,086 N/m
- K_shear = 1080 lb/in = 189,137 N/m
- dmax_comp  = 1.4 in = 35.56 mm
- dmax_shear = 1.6 in = 40.64 mm
