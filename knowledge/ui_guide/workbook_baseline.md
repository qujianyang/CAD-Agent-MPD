# Workbook Baseline Mode

Use the **Workbook baseline** vehicle source to analyse the validated, unmodified Spinel E2.
This is the normal workflow.

## What it does

It reads the centre of gravity (CG), gross weight, and geometry from the Spinel E2 workbook,
so you never type physical numbers by hand. After loading, the tab shows the derived weight
and CG with a provenance line so you can confirm the source.

## The workbook path

The "Workbook path" field points to the Spinel E2 measured-CG workbook. You can override it
with the `MOBILITY_XLS` environment variable. Most users leave it at the project default.

## Measured vs theory CG

The "CG variant" radio chooses which CG the workbook supplies:

- **Measured** — CG from physical tilt tests on the real vehicle. Use this for as-built
  assessments and to reproduce the published safety factors.
- **Theory** — CG from the component mass budget (a design-stage estimate). Use this when
  comparing against the design intent rather than the built vehicle.

If you are unsure, choose **Measured** — it reflects the real vehicle.

## After loading

Once the workbook vehicle is loaded, the "Run Analysis" button becomes enabled. Set your
grades, cornering speed/radius, and OEM margins, then run the analysis. For the actual
safety-factor numbers, use "Run Analysis" or ask the engineering "Ask the mobility
assistant" panel, for example: "Is the measured Spinel stable on a 60% slope?"
