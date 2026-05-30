# Tie-Down Design Loads (Transport Inertia)

**Source of truth:** `MCDLL Tie-Down Provision_20-8-2023.xlsx` ("Matrix 2 MCD(S) Tie-down Transportation Mode").
External standard (MIL-STD-209 / Def Stan / DSTA) to be confirmed with supervisor.

Each secured item must withstand inertial loads in three axes, applied as multiples of its weight:

| Axis | Direction | Design factor | Physical cause |
|---|---|---|---|
| Longitudinal (X) | fore / aft | 4 G | braking / acceleration |
| Vertical (Z) | up / down | 2 G | road bumps |
| Lateral (Y) | side | 1.5 G | cornering |

Design force per axis: `F_axis = weight_kg * G_axis * g`, with g = 9.81 m/s^2.
Example: a 14 kg item -> longitudinal 549.36 N, vertical 274.68 N, lateral 206.01 N.
