# Installation Considerations

**Chunk:** `shock_mount/installation_considerations`
**Grounding:** HYBRID — the clearance gate is grounded in code; some guidance now source-confirmed from the VMC Tech Notes; mounting hardware detail still AWAITING SOURCE.
**Source:** code = `catalog.py` / `physics_engine.py` (clearance gate); practice = **The VMC Group — "Wire Rope Isolators" Tech Notes**; mounting hardware = `[SOURCE NEEDED: VMC mounting instructions / ST Engineering practice].`

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

## [SOURCE NEEDED] Installation guidance the tool does NOT check

<!-- Fill from vendor mounting instructions and ST Engineering practice. -->
- Mounting orientation / recommended loading direction per series: `[FILL]`
- Fastener grade, torque, and interface plate requirements: `[FILL]`
- Minimum sway space / rattle space beyond computed ΔD: `[FILL]`
- Snubbing / travel stops for over-travel events: `[FILL]`
- Environmental limits (temperature, corrosion) affecting stiffness: `[FILL]`
- Symmetry / even load-sharing assumptions the load model relies on: `[FILL]`

## Engineer's residual responsibilities

- Verify real per-mount static load matches the model's distribution
  (`load_distribution.md`) given the actual CG.
- Confirm physical envelope fits (mount `H×W` from the catalog chunks).
- Confirm clearance figures fed to the tool are the true installed gaps.

## Provide

- Vendor mounting/installation instructions for the CB series.
- Any ST Engineering installation standard or checklist permitted for use.
