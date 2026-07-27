# Installation Considerations

**Chunk:** `shock_mount/installation_considerations`
**Grounding:** HYBRID — the clearance gate is grounded in code; general load
guidance is confirmed by the VMC Tech Notes; CB1390 construction and interface
options are confirmed by SRC-CAT-01; installation torque and project-specific
orientation still require supplier confirmation.
**Source:** `catalog.py`, `physics_engine.py`, The VMC Group "Wire Rope
Isolators" Tech Notes, and SRC-CAT-01 `Socitec - CB1390.pdf`.

---

Installation checks that remain the **engineer's** responsibility — the tool
sizes the isolator against shock and clearance, but does not certify the full
installation.

## Grounded (code) — clearance gate

The tool already enforces a per-axis clearance gate: the effective deflection
limit is `min(mount rated travel, clearance to neighbouring structure)`
(`travel_limit_gate.md`). A mount within its own travel is rejected if it would
collide with adjacent equipment.

Axis→case mapping: Z→Comp-Bottom, Y→Comp-Wall, X&Z→Roll-Wall, X&Y→Roll-Bottom.

## From the VMC Tech Notes (source-confirmed)

- **Do not use the tension direction for primary shock attenuation.** Tensile
  loading dominates in the cable and produces a *stiffening* curve — the opposite
  of the intended snubbing/softening behaviour.
- **Consult the principal- and cross-axis load-deflection curves** before
  committing a part; the static-load placement on the curve changes the effective
  spring rate, available travel, and cross-axis stability.
- **Leave real sway / rattle space.** Theoretical selection must be reconsidered
  against real-world equipment sway space and the isolator's physical size and
  stability (beyond the computed `ΔD`).
- **Frequency separation for vibration:** keep a **3:1 or 4:1** ratio between the
  input frequency to be attenuated and the suspension natural frequency to avoid
  amplification near resonance. (Isolation begins above √2 × the resonant
  frequency.)
- **Payload geometry and CG** matter for **induced rocking** — a high or offset
  CG couples translation into rotation (the tool only warns on high CG).

## From the Socitec CB1390 catalogue

- The standard CB1390 uses stainless-steel cable, aluminium-alloy retainer bars
  with SurTec finish, zinc-plated alloy-steel screws, and stainless-steel
  inserts. Galvanized-cable and all-stainless options exist.
- The complete suffix defines both bar interfaces. Available combinations use
  8.4 mm through holes, 90-degree countersunk holes, or M8 inserts.
- The model envelope varies substantially with size. Confirm height, width,
  mass, hole pattern, and fastener engagement using
  `socitec_cb1390_construction.md`.
- The catalogue temperature and corrosion statements are vendor claims, not a
  substitute for project environmental approval.

## Installation guidance the tool does NOT check

- Project-specific mount orientation and local loading mode.
- Fastener grade, installation torque, thread engagement, and interface-plate
  strength.
- Minimum sway space beyond computed `ΔD`.
- Snubbing or travel stops for over-travel events.
- Environmental suitability of the ordered material and finish.
- Real load sharing when CG or structural flexibility breaks the model's
  symmetry assumption.

## Engineer's residual responsibilities

- Verify real per-mount static load matches the model's distribution
  (`load_distribution.md`) given the actual CG.
- Confirm physical envelope fits (mount `H×W` from the catalog chunks).
- Confirm clearance figures fed to the tool are the true installed gaps.
- Confirm the actual physical arrangement; rack gang count alone is not enough
  (`installation_acceptance_workflow.md`).
