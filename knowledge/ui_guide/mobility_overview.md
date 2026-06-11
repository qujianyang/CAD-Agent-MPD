# Mobility Tab — Overview and Workflow

The Mobility tab assesses vehicle stability (slopes, cornering, axle loads) for the
Spinel E2 platform and modified variants. This page explains how to drive the tab. It does
not perform calculations — the engineering "Ask the mobility assistant" panel and the
"Run Analysis" button do that.

## The four-step workflow

1. **Build a vehicle scenario** — choose a "Vehicle source" and load/derive/build the
   vehicle. Until this is done, "Run Analysis" stays disabled.
2. **Review the CG source** — the tab shows the derived weight, centre of gravity, and a
   provenance line (method + source) so you can confirm where the numbers came from.
3. **Set analysis conditions** — longitudinal/lateral grades, cornering speed/radius, and
   the OEM recommended margins used for the verdict.
4. **Run Analysis** — produces axle loads, the slope-stability grid, cornering, and a
   verdict against structural and OEM limits.

## The "Vehicle source" modes

The "Vehicle source" radio at the top of the tab selects how the vehicle CG is obtained:

- **Workbook baseline** — the validated Spinel E2 CG read from the measured/theory
  workbook. This is the normal workflow. See "Workbook baseline".
- **Wheel-load measurement** — derive weight and horizontal CG from four weighbridge
  readings. Zcg (CG height) must be entered separately. See "Wheel-load workflow".
- **Design / modification study** — start from a workbook baseline, then add, remove, or
  relocate components. See "Modification workflow".
- **Advanced: certified CG entry** — type a certified gross weight and CG directly, with a
  mandatory source reference. See "Certified CG entry".

## Which mode should I choose?

- Assessing the real, unmodified Spinel E2 → **Workbook baseline**.
- You have weighbridge / wheel-scale readings → **Wheel-load measurement**.
- You are adding or moving equipment on the vehicle → **Design / modification study**.
- You have a certified CG from a report and want to enter it directly → **Advanced:
  certified CG entry**.

## Two assistants, different jobs

- **🧭 Mobility UI Guide** (this assistant) — explains how to operate the tab. It never
  computes safety factors.
- **💬 Ask the mobility assistant** (the in-tab panel) — the engineering agent that runs the
  validated physics tools and returns safety factors, slope limits, and cornering results.
