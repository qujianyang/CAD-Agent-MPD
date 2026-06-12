# Quick Selector — Overview and Workflow

The Quick Selector tab selects wire-rope shock isolators from typed-in weights. Use it when
SolidWorks isn't running or you are working from spec sheets. This page explains how to
drive the tab; it does not perform calculations — the "Select Best Isolator" button and the
"💬 Ask the shock-isolation assistant" panel do that.

## The two modes

The "Mode" radio at the top chooses the workflow:

- **Auto (recommend best part)** — you describe the system; the tool evaluates the whole
  catalog and recommends the best part that passes all four load cases. Use the "Catalog
  filter" to restrict the series searched.
- **Manual (verify a specific part)** — you pick one part number in "Select part to verify"
  and the tool checks whether it passes for your system. Use this to confirm a part you
  already have in mind.

## The workflow

1. Enter the **weights** — "Equipment weight [kg]" (the payload) and "Rack / chassis
   weight [kg]" (the frame). The caption shows the total system mass M.
2. Set the **mount configuration** — "n_bottom (bottom mounts)" and "n_wall (wall mounts)".
3. Set the **shock environment** — pulse amplitude, duration, GT limit and pulse profile
   (see "Shock environment and clearances").
4. Optionally set **installation clearances** and the **selection objective** (Auto mode).
5. Click **"🎯 Select Best Isolator"** (Auto) or **"📊 Run Analysis"** (Manual).

## Quick Selector vs CAD + Shock tab

If your equipment exists as a SolidWorks assembly, the **CAD + Shock** tab can extract the
mass and geometry automatically instead of typing weights — see "CAD + Shock workflow".

## Two assistants, different jobs

- **🧭 Shock Selector UI Guide** (this assistant) — explains how to operate the tab.
- **💬 Ask the shock-isolation assistant** — the engineering agent that runs the validated
  physics and answers with real numbers (e.g. "select an isolator for a 1500 kg rack,
  6 bottom + 4 wall").
