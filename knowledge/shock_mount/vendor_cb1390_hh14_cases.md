# Vendor Case Evidence for CB1390 and HH14

**Chunk:** `shock_mount/vendor_cb1390_hh14_cases`
**Sources:** SRC-SIM-01 through SRC-SIM-04
**Grounding:** vendor nonlinear simulation and calculation results, not tests

---

These cases show that physical mount count, load orientation, mass, and axis
all affect the predicted response. They are examples, not universal presets.

## CB1390 arrangement cases

| Case | Physical arrangement | Vendor model field | Static deflection | Reported random-response frequencies X/Y/Z |
|---|---|---:|---:|---|
| 320 kg, CB1390-30 | 4 bottom + 2 stabilizers | 4.66 | -1.4 mm | 18.1 / 7.4 / 10.5 Hz |
| 609.86 kg, CB1390-20 | 6 bottom + 2 stabilizers | 6.66 | -1.2 mm | 19.5 / 8.1 / 11.3 Hz |

Both calculation sheets use a 20 g, 11 ms sawtooth requirement represented by
about 1.1 m/s initial velocity. Their shock responses are plotted separately in
X, Y, and Z and are visibly different by axis.

The vendor fields `4.66` and `6.66` are effective configuration values in the
nonlinear SDOF sheets. They are not the physical number of isolators and must
not be entered as `n_bottom` or `n_wall` in the project physics engine.

## HH14 mass comparison

Both HH14 cases use four HH14-30 three-loop mounts in compression.

| Mass | Gravity deflection | Modal X/Y/Z | Max absolute shock displacement X/Y/Z | Max absolute shock acceleration X/Y/Z |
|---:|---:|---|---|---|
| 115 kg | 1.134 mm | 4.24 / 4.24 / 8.63 Hz | 34.14 / 34.13 / 21.09 mm | 3.63 / 3.63 / 4.90 g |
| 135 kg | 1.587 mm | 3.91 / 3.91 / 7.83 Hz | 36.85 / 36.85 / 23.78 mm | 3.42 / 3.42 / 4.59 g |

For the same mount arrangement, increasing the supported mass lowered the
reported modal frequencies and increased the required displacement. Peak
acceleration did not increase monotonically because the vendor model is
nonlinear.
