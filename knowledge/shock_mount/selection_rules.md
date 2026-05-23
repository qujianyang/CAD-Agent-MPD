# Isolator Selection Rules

How to pick the correct CB-series wire rope isolator for a rack / cabinet.

---

## Pass condition

An isolator part is **valid** for the design when it passes ALL 4 load cases
(see `load_cases.md`):

```
For each case i in [Comp-Bottom, Comp-Wall, Roll-Wall, Roll-Bottom]:
    GT_i  <  GT_limit       (typically 10 G)
    ΔD_i  <  dmax           (compression or shear travel from datasheet)
```

If any one of the 4 cases fails, the part is **not** acceptable for that load.

---

## Recommended part = softest valid part

Among all valid candidates, prefer the one with the **lowest K_compression**.

### Why softest wins

The transmitted G is a monotonically increasing function of `fn`, which is a
monotonically increasing function of `K`:

```
fn = (1/2π) · √(K/m)        # K ↑  →  fn ↑
GT = (2π · fn · V) / g      # fn ↑ →  GT ↑
```

So softer K → lower GT → better isolation. Use the softest part that still
keeps `ΔD` within the isolator's rated travel.

---

## When NO part passes

Options, in order of preference:

1. **Increase the mount count** (`n_bottom` and/or `n_wall`). This lowers
   mass-per-isolator, lowers `fn`, lowers `GT`.
2. **Relax `GT_limit`** if the protected equipment can actually tolerate higher
   G (check the equipment spec, don't guess).
3. **Re-evaluate the shock profile** — confirm `Ao` and `to` with the project
   shock test spec; over-conservative inputs lead to over-built designs.
4. **Move up a series** — CB1500 (5/8" rope) or CB1800 (1" rope) have higher
   capacity but bigger envelope.

---

## When MORE THAN ONE part passes

The selector returns the softest. The engineer may override with a stiffer
part if:

- **Deflection clearance is tight** — softer K → larger `ΔD`. If the rack only
  has 20 mm of clearance to surrounding structure, you must use a part whose
  `ΔD` at this load is < 20 mm.
- **Permanent set / fatigue** — for vehicle environments with many shock
  cycles per mission, a part loaded near its travel limit may degrade faster.
- **Standardisation** — if the project already uses CB1400-15 across other
  bays, using it again simplifies BOM and qualification.

---

## Typical mount configurations

| Rack size           | Typical n_bottom | Typical n_wall | Notes                       |
|---------------------|------------------|----------------|-----------------------------|
| Single 19" cabinet  | 4                | 4              | 4 corners + 4 wall          |
| 4-bay 35U rack      | 6                | 4              | Reference Excel case        |
| Heavy shelter rack  | 8                | 6              | For > 1500 kg systems       |

---

## Workflow summary

1. Get **mass M** (live CAD extraction or user input)
2. Confirm **n_bottom and n_wall** with the engineer (default 6 + 4)
3. Confirm **shock profile** (default 20G / 11ms saw-tooth, 10G limit)
4. Run selection — pick softest valid part across CB1400/1500/1800
5. **Sanity check** worst-case GT ratio and ΔD ratio against project margins
