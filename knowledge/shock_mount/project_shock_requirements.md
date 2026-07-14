# Project Shock Requirements (20 G / 11 ms / 10 G)

**Chunk:** `shock_mount/project_shock_requirements`
**Source (pulse):** MIL-STD-810H, Method 516.8, Table 516.8-IV with Notes 1-3
(method page 516.8-23) and paragraph 4.6.2 (method page 516.8-22), verified
against the project copy of `MIL-STD-810H.pdf` on 2026-07-14.
**Source (transmitted limit):** equipment/customer fragility requirement —
document still to be supplied.
**Source (code defaults):** `physics_engine.py` (`ShockEnv`).

---

This chunk states where each default shock input comes from, and separates
standard-derived values from internal or customer design requirements.

## Tool defaults and their origins

| Input                | Default  | Origin                                                        |
|----------------------|----------|---------------------------------------------------------------|
| Shock magnitude `Ao` | 20 G     | MIL-STD-810H Table 516.8-IV **Note 3** (see below)            |
| Pulse duration `to`  | 11 ms    | MIL-STD-810H Table 516.8-IV (TD = 11 ms for all categories)   |
| Pulse shape          | terminal-peak sawtooth | MIL-STD-810H Table 516.8-IV / Figure 516.8-3 (Procedure I classical-pulse default) |
| Transmitted-G limit  | 10 G     | **Equipment/customer fragility limit — NOT from MIL-STD-810** |

## The 20 G basis (verified)

Table 516.8-IV, *"Terminal peak sawtooth default test parameters for
Procedures I - Functional Test"*, gives reference peak value and duration
`Am (G-Pk) & TD (ms)`:

| Materiel category              | Am   | TD    |
|--------------------------------|------|-------|
| Flight Vehicle Materiel        | 20 G | 11 ms |
| Weapon Launch / Captive Carry  | 30 G | 11 ms |
| Ground Materiel                | 40 G | 11 ms |

Ground materiel defaults to **40 G**, but **Note 3** states: *"For materiel
mounted only in trucks and semi-trailers, use a 20G peak value."* The project's
racks are vehicle-mounted (truck/shelter) materiel, so 20 G applies. The 11 ms
duration is the table's TD for every category.

**Note 1** (relevant because these racks are shock-mounted and well over
136 kg): an 11 ms half-sine of equivalent velocity may be employed, with
`Am(half-sine) = (pi/4) * Am(sawtooth)` — see `pulse_half_sine.md`.

## Caveats from the standard (para 4.6.2, method page 516.8-22)

- Classical pulses (e.g. terminal-peak sawtooth) are *"in general ...
  unacceptable unless it can be demonstrated during tailoring that the field
  shock environment time trace approximates such a form"*; they are permissible
  when other testing resources are exhausted.
- Classical-pulse testing must be performed *"in both a positive and negative
  direction"*.
- Tailoring from measured field data is preferred over table defaults
  (`mil_std_516_8_scope_tailoring.md`, `mil_std_516_8_transport_defaults.md`).

So the 20 G / 11 ms sawtooth is a **documented default for design sizing**, not
proof of test compliance — see `standard_scope.md` for the calculation-vs-test
boundary.

## The 10 G transmitted limit is NOT from the standard

Table 516.8-IV defines **input** pulses only; Method 516.8 sets no
transmitted-acceleration acceptance value. The 10 G limit is the protected
equipment's fragility requirement (customer/equipment side).
`[SOURCE NEEDED: the customer or equipment document that fixes the 10 G
transmitted limit — see transmitted_g_limit.md.]`

## Remaining open items

- Acceptance criteria wording from the project/customer shock specification.
- Whether the project spec independently restates the 20 G / 11 ms values or
  simply invokes the standard.

Cross-refs: `pulse_sawtooth.md`, `pulse_half_sine.md`, `transmitted_g_limit.md`,
`standard_scope.md`, `mil_std_516_8_functional_transport.md`.
