# Reading the Shock Selection Results

## The recommendation line

Auto mode reports e.g. **"Recommended: CB1400-30 (Series CB1400, worst GT = 45% of limit)"**.
"Worst GT" is the highest transmitted acceleration across the four load cases, shown as a
percentage of your GT limit — lower means more margin.

Four metrics follow:

- **K_comp / K_shear** — the part's compression and shear stiffness (lb/in, catalog values).
- **Size** — the part's height and width in inches (installation envelope).
- **Worst dD ratio** — the largest dynamic deflection across cases as a percentage of its
  allowable (rated travel, or your clearance if that is tighter).

## The "4 Load Cases (all must pass)" table

One row per case (bottom-compression, wall-compression, roll cases). Columns:

- **Case** — which mount group and load direction is being checked.
- **m [kg]** — the mass carried per isolator in that case.
- **fn [Hz]** — natural frequency of the mounted system in that case.
- **GT [G]** vs **GT limit** — transmitted acceleration against your limit.
- **dD [mm]** vs **dD limit [mm]** — dynamic deflection against its allowable.
- **Binding** — the constraint closest to failing in that case. If it reads
  "deflection (clearance)", the neighbouring-equipment gap — not the mount's own rated
  travel — is the limiting factor; increasing the clearance input or choosing a stiffer
  objective changes the outcome.
- **PASS** — whether the case passes. All four must pass for the part to be valid.

## The expanders

- **"📊 Full multi-series matrix"** — every candidate part across the searched series with
  its pass/fail status, so you can see what was rejected and why.
- **"🔬 Full physics report"** — the complete calculation trace (velocity change, fn, GT,
  dD per direction) for the recommended part.

For the actual numbers on a different configuration, ask the "💬 Ask the shock-isolation
assistant" panel, e.g. "What is the heaviest mass a CB1400-30 can support?"
