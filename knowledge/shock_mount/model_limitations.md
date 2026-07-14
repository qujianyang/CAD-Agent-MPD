# Model Limitations

**Chunk:** `shock_mount/model_limitations`
**Source:** `physics_engine.py` (`IMPULSE_VALIDITY_RATIO`, warnings), `catalog.py`, and scope notes in `mil_std_basis.md` (vibration is a separate analysis).
**Grounding:** validated-in-repo (behaviour). Standard-scope wording → cross-check `standard_scope.md`.

---

The model in `model_assumptions.md` is valid within bounds. Known limitations:

1. **Impulse approximation has a validity window.** The velocity-impulse form
   holds only while `fn·to ≤ 0.25`. Beyond it, `GT`/`ΔD` are unreliable; the
   engine **flags** the case (warning) rather than failing it. Reference cases
   sit at `fn·to ≈ 0.07–0.12`.

2. **No random-vibration fatigue.** This tool performs the **shock** analysis
   only. Road/transport random-vibration fatigue (the MIL-STD-810 vibration
   method, "Category 4 off-road" spectra) is a **separate** analysis this tool
   does not perform. A separate road-vibration resonance check exists but uses a
   different ("Vibration Average") stiffness column.

3. **Linear stiffness only (averaged rate).** The VMC Tech Notes warn the
   published spring rates are **averages**, and that *where the static load sits
   on the third-order load-deflection curve* modifies the effective spring rate,
   the available dynamic travel, and cross-axis stability. The single "Shock
   Average K" cannot capture this. Verify near-limit parts against the vendor's
   principal- and cross-axis load-deflection curves.

   Note also: VMC "does not list load ratings for individual wire rope
   isolators." Any Max Static F used by the static gate comes from a separate
   document, not these datasheets (`static_load_gate.md`).

4. **No fatigue / permanent-set life.** A part loaded near its travel limit for
   many mission cycles may degrade; the model gives a single-event pass/fail, not
   a life estimate.

5. **No cross-axis coupling.** Cases are evaluated independently; simultaneous
   multi-axis input and rotational/rocking coupling are not modelled.

6. **CG not in the load split.** Load distribution assumes the Excel convention;
   a high or offset CG changes real per-mount loads. The tool only emits a
   high-CG warning (CG > 60 % of height), it does not re-distribute load.

7. **Catalogue-bounded.** Selection only considers transcribed CB-series parts
   (plus user-supplied custom isolators via the custom-isolator path). Parts
   without a published static rating warn rather than fail.

When any limitation is material to a decision, surface it — do not present a
pass as unconditional.
