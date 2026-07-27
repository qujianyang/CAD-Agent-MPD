# Shock Passing Does Not Prove Random-Vibration Compliance

**Chunk:** `shock_mount/shock_vibration_separation`
**Sources:** SRC-SIM-05 and SRC-SIM-06
**Grounding:** explicit vendor simulation statements

---

Shock and random vibration are separate requirements. A configuration may
predict transmitted shock below 10 g and still fail a duration-based
random-vibration requirement.

The supplied CB1400-15 vendor simulations illustrate this directly:

| Mass | Shock prediction | Vendor random-vibration statement |
|---:|---|---|
| 850 kg | Maximum absolute tabulated acceleration is 7.17 g | Does not meet the required 40-minute MIL-STD-810H 514.8C-VII Category 4 duration |
| 1050 kg | Maximum absolute tabulated acceleration is 6.73 g | Does not meet the required 40-minute MIL-STD-810H 514.8C-VII Category 4 duration |

The reported random results were:

| Mass | Axis | Resonance | RMS acceleration | Maximum PSD |
|---:|---|---:|---:|---:|
| 850 kg | X | 12.00 Hz | 1.74 g | 0.492 g^2/Hz |
| 850 kg | Y | 7.41 Hz | 3.37 g | 10.3 g^2/Hz |
| 850 kg | Z | 12.71 Hz | 3.40 g | 2.69 g^2/Hz |
| 1050 kg | X | 10.70 Hz | 1.71 g | 0.548 g^2/Hz |
| 1050 kg | Y | 6.36 Hz | 2.63 g | 6.45 g^2/Hz |
| 1050 kg | Z | 11.33 Hz | 3.27 g | 2.86 g^2/Hz |

## Assistant rule

Never answer `the installation is qualified` from a shock result alone. Report
shock status and vibration status separately. If random-vibration duty,
duration, PSD, or operating state is missing, ask for it or state that
vibration compliance is undetermined.
