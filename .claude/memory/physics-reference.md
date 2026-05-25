# Physics Reference

This is the source of truth. All four numbers must match the Excel sheet to 4 decimal places. Excel file: `Shock Isolator_850kg_4 Bayed 35U.xls`.

## The four formulas

| Quantity | Formula | Units |
|---|---|---|
| Impact velocity V | `V = ½ · g · Ao · to` | m/s |
| Natural frequency fn | `fn = (1/2π) · √(K/m)` | Hz |
| Transmitted G | `GT = (2π · fn · V) / g` | g |
| Peak deflection ΔD | `ΔD = V / (2π · fn)` | m |

Where:
- `g = 9.81 m/s²`
- `Ao` = input pulse acceleration (g)
- `to` = pulse duration (s) — **never hardcode this to 0; see gotchas.md**
- `K` = spring stiffness per isolator (N/m)
- `m` = mass per isolator for that case (kg)

## The four load cases

| Case | Direction | Mass divisor | Notes |
|---|---|---|---|
| Comp-Bottom | Z (vertical) | `M / n` | **NO /2.** Full weight on bottom isolators. |
| Comp-Wall | X or Y | `M / n / 2` | /2 because lateral case shares load. |
| Roll-Wall | X or Y | `M / n / 2` | Lateral roll. |
| Roll-Bottom | Z (vertical) | `M / n / 2` | Vertical component of roll. |

The /2 rule was traced back to Excel formulas: `=E8/E21/2` for wall / roll cases, but `=M/n` (no /2) for Comp-Bottom. The user confirmed this asymmetry is **intentional** — don't "fix" it.

## Validation point

CB1400-15 at 850 kg, 6 isolators bottom + 4 wall:
- **GT = 6.296 G**
- **ΔD = 18.85 mm**

If your changes don't reproduce this exactly, you broke something.

## Selection rule (`catalog.py`)

**"Softest valid K"** — pick the smallest K from the candidate list that passes all 4 cases (GT under spec, ΔD under dmax). Softer = lower transmitted G = better isolation.

## High-CG warning

Uses `cg_z_base` (base-relative, derived from bbox shift) when present, falls back to raw `cg_z`. Triggers warning if CG height > 50% of bbox Z extent.

## Catalog families

| Family | K range | dmax |
|---|---|---|
| CB1400 | softest | small |
| CB1500 | mid | mid |
| CB1800 | stiffest | largest |

Exact K and dmax values live in `catalog.py` and `knowledge/shock_mount/catalog_overview.md`.
