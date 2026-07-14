# Model Assumptions

**Chunk:** `shock_mount/model_assumptions`
**Source:** `physics_engine.py` (formula set, load distribution, impulse-velocity method); method basis in **The VMC Group — "Wire Rope Isolators" Tech Notes**.
**Grounding:** validated-in-repo AND method source-confirmed

---

The tool's shock analysis rests on a specific, deliberately simple model. State
these when defending a result; they define where the numbers are trustworthy.

1. **Single-degree-of-freedom (SDOF) per case.** Each load case is one
   spring–mass system: `fn = (1/2π)√(k/m)`. No multi-mode or coupled dynamics.

2. **Impulse / velocity-conserved pulse.** The pulse is treated as an ideal
   impulse characterised by its velocity change `V = coeff·g·Ao·to`. Damage
   potential is taken to track `V`, not peak G alone (`impulse_velocity.md`).

3. **Linear stiffness via an averaged spring rate.** `k_comp` and `k_shear` are
   constant, taken from the datasheet **"Shock Average K"**. Per the VMC Tech
   Notes, a wire-rope isolator has a **third-order ("softening") load-deflection
   curve**, so the vendor publishes two averages: the **Vibration Average K**
   (tangent slope near zero, small amplitude) and the **Shock Average K**
   (overall end-to-end slope over the shock excursion). The shock analysis uses
   the shock average; the road-vibration check uses the vibration average. The
   single average cannot capture the full nonlinear curve.

   The Tech Notes also state wire rope provides **~15–20 % of critical damping**;
   the tool's shock method is undamped (conservative for peak transmission), and
   the separate road-vibration check applies a damping ratio explicitly.

4. **Fixed load distribution.** Per-isolator mass follows the Excel convention
   (`load_distribution.md`): `M/n_bottom` vertical; `M/(n·2)` for the three
   lateral/shear cases. CG offset and footprint asymmetry are **not** folded
   into the load split (CG is used only for a separate high-CG warning).

5. **Static load on bottom mounts only.** Gravity is carried by bottom mounts in
   compression; wall mounts are statically unloaded (`static_load_gate.md`).

6. **Four cases span three axes.** Comp-Bottom (Z), Comp-Wall (Y),
   Roll-Wall (X,Z), Roll-Bottom (X,Y) together cover X/Y/Z
   (`four_load_cases.md`).

7. **Rigid mounted body.** The protected assembly is treated as a rigid mass;
   internal flexibility of the rack/equipment is not modelled.

8. **Sawtooth default pulse.** `coeff = 0.5`. A half-sine option uses
   `coeff = 2/π` on the same Ao/to (`pulse_half_sine.md`).

Limits that follow from these assumptions are in `model_limitations.md`.
