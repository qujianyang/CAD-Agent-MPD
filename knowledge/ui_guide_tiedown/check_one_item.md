# Check One Item (Section 1)

Verifies whether one item's tie-down passes a target safety factor.

## Inputs

- **"Item weight [kg]"** — the secured item's weight.
- **"Mounting surface"** — which face the item is fastened to. Three choices:
  - **"Front or rear wall"**
  - **"Floor or ceiling"**
  - **"Left or right wall"**

  The surface decides which axis loads the fastener in TENSION (pull-out) versus SHEAR
  (sliding). Opposing faces are equivalent — front = rear, floor = ceiling, left = right —
  because the design loads are direction-independent; only the surface's normal axis
  matters. (Hover the "?" on the control for the same explanation.)
- **"Fastener kind"** — **Bolt** (pick "Property class", default 8.8, and "Bolt size",
  default M8) or **Strap / Latch** (pick a named strap/latch from the list).
- **"Fasteners (qty)"** — how many fasteners share the load.
- **"Target safety factor"** — the item passes if the minimum SF across the three axes is
  at or above this. The MIL-STD-209K design factor is 1.5; the default 1.0 is the bare
  structural minimum.

Click **"Check tie-down"**.

## Reading the result

- **PASS** (green) or **FAIL** (red), with "min SF = ..." and the **limiting axis** — the
  axis (longitudinal / vertical / lateral) with the lowest safety factor. Fixes should
  target that axis.
- The per-axis table shows: **Design force [N]** (the MIL-STD load on that axis),
  **Force type** (Tensile or Shear — set by your mounting surface), **Per fastener [N]**
  (design force divided across the quantity), **Yield [N]** (the fastener's capacity in
  that force type) and the resulting **Safety factor**.
- The caption beneath repeats the fastener's tensile and shear capacities per fastener.

If it fails, either increase the quantity, choose a stronger fastener, or use Section 2 to
size the restraint automatically.
