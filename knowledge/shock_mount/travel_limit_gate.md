# Travel Limit Gate (and Clearance)

**Chunk:** `shock_mount/travel_limit_gate`
**Source:** `physics_engine.py` (`run_analysis` limit mapping, `DirectionResult.delta_ok`), `catalog.py` (`select_isolator` clearance gate).
**Grounding:** validated-in-repo

---

For each of the four load cases the dynamic deflection `ΔD` must stay within an
**effective travel limit**. This gate is independent of the `GT` gate: a part
can keep transmitted G below the limit and still fail on travel.

## The check

```
PASS (this case)  ⇔  ΔD < effective_limit          (strict inequality)
effective_limit = min( d_max_for_case , clearance_for_axis )
```

The effective limit is the **tighter** of two things:

1. The mount's own **rated dynamic travel** from the datasheet.
2. The **installation clearance** to neighbouring structure/equipment on the
   relevant axis.

A mount within its own rated travel is still rejected if it would collide with
adjacent gear.

## Which travel limit per case

| Case          | Datasheet limit | Clearance mapping        |
|---------------|-----------------|--------------------------|
| Comp - Bottom (Z)  | `d_max_comp`  | `clr_z`                  |
| Comp - Wall (Y)    | `d_max_comp`  | `clr_y`                  |
| Roll - Wall (X,Z)  | `d_max_shear` | `min(clr_x, clr_z)`      |
| Roll - Bottom (X,Y)| `d_max_shear` | `min(clr_x, clr_y)`      |

Clearance defaults to "unlimited" (a large sentinel) when the engineer leaves it
blank, so an unspecified clearance reproduces pure travel-limited behaviour.

## Rated travel is series/part specific

`d_max_comp` and `d_max_shear` differ by part number and are transcribed (in
inches → mm at 25.4 mm/in) in the series catalog chunks. Example CB1400-15:
`d_max_comp = 1.4 in = 35.56 mm`, `d_max_shear = 1.6 in = 40.64 mm`.

## Interaction with the softest-part rule

A softer spring lowers `GT` but **raises** `ΔD`, so this gate is what stops the
selector from going arbitrarily soft. See `dynamic_deflection.md` and
`max_clearance_objective.md`.
