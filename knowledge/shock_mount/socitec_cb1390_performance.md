# Socitec CB1390 Reference Performance

**Chunk:** `shock_mount/socitec_cb1390_performance`
**Source:** SRC-CAT-01, `Socitec - CB1390.pdf`, page 2
**Grounding:** vendor catalogue; nonlinear reference performance

---

The CB1390 catalogue publishes force at a corresponding deflection rather than
one universal linear spring rate. The values below are the modes relevant to
the supplied CB1390-20 and CB1390-30 cases.

| Model and mode | Max static F at d | Max shock F at d | Max vibration input 2a | Uncoupled resonant f |
|---|---|---|---:|---:|
| CB1390-20 compression | 282 daN at 6.8 mm | 846 daN at 36 mm | 4.1 mm | 6.0 Hz |
| CB1390-20 compression/roll 45 deg | 211 daN at 9.6 mm | 547 daN at 55 mm | 6.1 mm | 5.2 Hz |
| CB1390-20 shear/roll | 141 daN at 9.6 mm | 674 daN at 32 mm | 3.6 mm | 6.5 Hz |
| CB1390-30 compression | 198 daN at 7.3 mm | 596 daN at 39 mm | 4.4 mm | 6.2 Hz |
| CB1390-30 compression/roll 45 deg | 149 daN at 11.7 mm | 399 daN at 59 mm | 6.5 mm | 5.2 Hz |
| CB1390-30 shear/roll | 99.4 daN at 10.4 mm | 573 daN at 42 mm | 4.6 mm | 5.9 Hz |

`2a` is the catalogue's maximum peak-to-peak sinusoidal vibration input under
the stated maximum static loading. It is not the same quantity as one-sided
shock travel.

## Interpretation boundary

- Do not divide `Max shock F` by `d` and call the result an exact stiffness
  across the whole motion. That ratio is only an average load-deflection
  estimate for preliminary screening.
- Compression, 45-degree compression/roll, tension, and shear/roll are
  different nonlinear curves.
- SRC-CURVE-01 confirms that the CB1390-20 and CB1390-30 dynamic curves are
  nonlinear and asymmetric about zero displacement.
- The catalogue states that performance characteristics are for reference,
  may increase under specific conditions, and should be confirmed with the
  supplier.
