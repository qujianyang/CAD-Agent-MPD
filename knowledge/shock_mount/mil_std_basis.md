# MIL-STD-810H Basis for the Shock Profile (Defensibility)

**Purpose:** Records the MIL-STD-810H authority behind the shock inputs used in
isolator selection — the 20G / 11 ms terminal-peak sawtooth, the multi-axis
evaluation, and the use of velocity change as the governing quantity. Cite this
page when a design review asks *why* these inputs were chosen.

**Source of truth:** MIL-STD-810H, Method 516.8 (Shock) and Method 514.8
(Vibration), transcribed from the official PDF.

The physics formulas live in `formulas.md`; this page is the *justification /
citation* layer, not the calculation.

---

## Why 20G / 11 ms terminal-peak sawtooth

Method 516.8, **Table 516.8-IV** (terminal-peak sawtooth default parameters,
Procedure I — Functional Shock) gives the default peak (Am) and duration (TD):

| Materiel type                  | Peak (Am) | Duration (TD) |
|--------------------------------|-----------|---------------|
| Flight Vehicle Materiel        | 20 G      | 11 ms         |
| Weapon Launch / Captive Carry  | 30 G      | 11 ms         |
| Ground Materiel                | 40 G      | 11 ms         |

**Why 20G applies here:** Table 516.8-IV **Note 3** states *"For materiel
mounted only in trucks and semi-trailers, use a 20G peak value."* So although
general ground materiel defaults to 40G, **transport-mounted shelter racks use
20G** — the value used in this project.

**Note 1 (heavy / shock-mounted materiel):** *"For material that is shock
mounted or weighing more than 136 kg (300 lbs), an 11 ms half-sine pulse of such
amplitude that yields an equivalent velocity to the default terminal peak
sawtooth may be employed. Equivalent Velocity Relationship:
Am(half-sine) = (π/4) · Am(sawtooth)."* These racks are both shock-mounted (on
the wire-rope isolators) and well over 136 kg, so a half-sine equivalent is
permissible. The sawtooth is kept as default; the half-sine equivalent would be
(π/4) × 20G = 15.7G / 11 ms, delivering the same velocity change.

---

## Why velocity change (V) is the governing quantity

The selection physics treats V as the conserved property of the pulse
(V = 1/2 · g · Ao · to = 1.0791 m/s for 20G / 11 ms). Two clauses support this:

1. **Method 516.8, para 2.3.2.3:** *"Shock pulse substitution... requires
   adjustment in the amplitude such that the velocity of the substituted shock
   pulse is equivalent to the original specification."* Velocity is preserved
   across pulse-shape substitution.
2. **Method 516.8, para 4.6.4 (Fragility, Procedure III):** *"materiel stress is
   directly related to materiel velocity... and, in particular, to change in
   materiel velocity denoted as ΔV."* Damage potential tracks ΔV.

This is why isolators are sized against V, not peak G alone.

---

## Why four load cases across three axes

**Method 516.8, para 2.3.3:** *"subject the test item to a sufficient number of
suitable shocks... in both directions along each of three orthogonal axes."*
The four-case evaluation — Comp-Bottom (Z), Comp-Wall (Y), Roll-Wall (XZ),
Roll-Bottom (XY) — covers the three orthogonal axes the standard requires.

---

## The "Category 4 off-road" reference (terminology)

The shock input is paired with a vibration environment. **Method 516.8,
Table 516.8-VII, Note 1** (Transportation Shock) states the transportation shock
*"must always be carried out together with ground transportation vibration
testing as specified in Method 514.8, Category 4 and/or Category 20."* This is
why project documents cite **Method 514.8 Category 4 (off-road wheeled
vehicle)** alongside the saw-tooth shock — the standard pairs them.

For precise citation, keep the two methods distinct:
- The **20G / 11 ms saw-tooth pulse** is from **Method 516.8** (Shock).
- The **"Category 4 off-road"** label is from **Method 514.8** (Vibration).

The isolator sizing performed by this tool is the *shock* analysis (516.8). The
514.8 Category 4 vibration spectra (ASD g²/Hz break-points, ~2.24 G-rms
vertical) are a separate random-vibration fatigue analysis that this tool does
**not** perform.

---

## Reference shock magnitudes (context only)

Other Method 516.8 severities, for when a reviewer asks about alternatives:

| Scenario | Peak | Duration | Source |
|---|---|---|---|
| Functional, truck/trailer mounted (this project) | 20 G | 11 ms | Table 516.8-IV, Note 3 |
| Functional, general ground materiel | 40 G | 11 ms | Table 516.8-IV |
| Functional, flight vehicle | 20 G | 11 ms | Table 516.8-IV |
| Transportation, on-road (5000 km) | 5.1 / 6.4 / 7.6 G | 11 ms | Table 516.8-VII |
| Transportation, off-road (1000 km) | 10.2 / 12.8 / 15.2 G | 5 ms | Table 516.8-VII |
| Crash hazard, ground equipment | 75 G (SRS) | — | Table 516.8-III |

The project's selection uses the 20G / 11 ms functional value per Table
516.8-IV, Note 3.
