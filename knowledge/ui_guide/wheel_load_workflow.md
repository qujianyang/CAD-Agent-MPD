# Wheel-Load Measurement Workflow

Use the **Wheel-load measurement** vehicle source when you have weighbridge or wheel-scale
readings and want to derive the vehicle state from them.

## What it derives, and what it cannot

From the four wheel readings the tab derives gross weight, longitudinal CG (Xcg), and
lateral CG (Ycg) using a moment balance (the same method as SAR Appendix B).

**It cannot derive Zcg (CG height).** Static wheel loads contain no height information, so
Zcg must be entered separately from a verified source.

## Steps

1. Enter the four wheel loads (the weighbridge readings for each wheel).
2. Enter a verified **Zcg** value in the "Zcg" field. The help text notes it must come from
   a tilt test, a CAD model, or a certified report — it is not derivable here.
3. Choose where that Zcg came from in the **"Zcg source"** dropdown. The options are:
   - **tilt test**
   - **CAD model**
   - **certified report**
   This source is recorded in the provenance line for traceability.
4. The Spinel vendor axle and GVW limits apply by default; expand the limits section only if
   you need to override them.

## After deriving

Once the vehicle is derived, "Run Analysis" becomes enabled. If you have entered the four
wheel loads but the vehicle is still not built, check that Zcg is filled in — it is required.
