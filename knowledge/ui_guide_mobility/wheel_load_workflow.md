# Wheel-Load Measurement Workflow

Use the **Wheel-load measurement** vehicle source when you have weighbridge or wheel-scale
readings and want to derive the vehicle state from them.

## What it derives, and what it cannot

From the four wheel readings the tab derives gross weight, longitudinal CG (Xcg), and
lateral CG (Ycg) using a moment balance (the same method as SAR Appendix B).

**Static wheel loads alone cannot give Zcg (CG height).** Zcg comes from inclined-platform
**tilt tests** (the built-in calculator) or from a separately verified value.

## Steps

1. Enter the four level wheel loads (the weighbridge readings for each wheel), plus
   wheelbase and track.
2. Pick a **"Zcg method"**:
   - **Derive from tilt tests** (default) — enter the tilt-test readings (next section).
   - **Enter verified value** — type a pre-verified Zcg and pick its source in the
     **"Zcg source"** dropdown (**tilt test** / **CAD model** / **certified report**).
     The source is recorded in the provenance line for traceability.
3. The Spinel vendor axle and GVW limits apply by default; expand the limits section only if
   you need to override them.
4. Press **"Derive vehicle from wheel loads"**. The button stays disabled until a valid
   Zcg exists (tilt tests complete, or a verified value entered).

## Tilt-test ZCG calculator

Each inclined-platform test gives one Zcg estimate:

    Zi = (Fi − F_level) × WB / (GW × tan θi) + R

- **F_level** is the level rear-axle load (RL + RR) — taken automatically from the level
  wheel loads entered above, together with GW and the wheelbase WB.
- **Wheel radius R (mm)** defaults to 580 mm (Spinel E2 static radius). The tilt moment
  balance works about the axle centreline; R converts the result to height above ground.
- The table takes one row per test: **Angle (deg)** and **Inclined rear load (kg)**. It is
  prefilled with the four E2 test readings (10.2° / 10,550 kg, 12.3° / 10,700 kg,
  8.2° / 10,450 kg, 6.2° / 10,300 kg); add or remove rows for your own campaign.
- The per-test Z values are shown live, and the **average Zcg** (green banner) is what the
  derived vehicle uses, with source "tilt test".

The complete flow: four level wheel loads → GW / Xcg / Ycg → tilt-test readings → one Zcg
per test → average Zcg → complete measured vehicle.

## After deriving

Once the vehicle is derived, "Run Analysis" becomes enabled. If the derive button is
disabled, check the Zcg method section — the tilt table needs at least one complete row,
or the verified-value field must be filled in.
