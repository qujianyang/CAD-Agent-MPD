# Vendor Case Evidence for CB1400-15 Rack Arrangements

**Chunk:** `shock_mount/vendor_cb1400_cases`
**Sources:** SRC-SIM-05 and SRC-SIM-06
**Grounding:** vendor simulation results, not physical qualification tests

---

The supplied rack simulations use the same nominal envelope and arrangement:
1685 mm high, 2240 mm wide, 800 mm deep, with six bottom and four stabilizer
CB1400-15 isolators. Each isolator is modelled with eight loops. The input is a
20 g, 11 ms sawtooth shock represented by 1.08 m/s initial velocity, with a
requested transmitted limit of 10 g.

| Result | 850 kg case | 1050 kg case |
|---|---:|---:|
| Gravity Z deflection | 0.613 mm | 0.771 mm |
| Modal X/Y/Z | 10.42 / 6.98 / 11.68 Hz | 9.37 / 6.28 / 10.42 Hz |
| Max absolute displacement X/Y/Z | 15.89 / 20.79 / 15.22 mm | 17.91 / 22.99 / 17.40 mm |
| Max absolute acceleration X/Y/Z | 7.05 / 5.96 / 7.17 g | 6.70 / 5.51 / 6.73 g |

The tabulated shock predictions remain below 10 g in all three axes for these
two simulated cases. This is evidence of the supplier's predicted response for
the stated inputs, not proof that an installed rack passed a physical shock
test.

The mass comparison again shows the expected trade-off: the heavier case has
lower modal frequencies and larger predicted displacement. It does not show a
simple monotonic increase in acceleration because the isolator response is
nonlinear and axis-dependent.

Both reports separately state that the configurations do not meet the required
40-minute random-vibration duration. See
`shock_mount/shock_vibration_separation`.
