# Road-Vibration Check (After Shock Selection)

**Chunk:** `shock_mount/road_vibration_check`
**Source:** `vibration_engine.py` and `catalog.py` (`k_vib_comp_lbin` /
`k_vib_shear_lbin`); Vibration Average K column from the Aeroflex/VMC
datasheets; method validated against the company's SPF_Vibration workbook;
vendor case evidence in SRC-SIM-05 and SRC-SIM-06.
**Grounding:** validated-in-repo

---

Shock selection can prefer a soft mount, which pushes the mounted natural
frequency down toward the truck's suspension band. This separate check catches
parts that pass every shock gate but would ride their own resonance during
road transport.

## Why it exists

The chassis vibration PSD (heavy-duty truck, vertical) peaks at roughly
**3.6-4.3 Hz**. A mount whose *vibration* natural frequency lands in that band
amplifies the input for the whole journey (Q approx 1/(2*zeta) approx 4 at
zeta = 0.12), even though it passes the shock cases.

## Use the Vibration Average K, not the shock K

Wire rope is stiffer at small amplitudes. The datasheets publish a second
stiffness column, **Vibration Average K**, typically 2-3x the Shock Average K
(e.g. CB1400-15: 6525 lb/in vibration vs 2650 lb/in shock). Using the shock K
here would underestimate the vibration natural frequency by roughly 40 %.
Values live in `catalog.py` (`k_vib_comp_lbin` / `k_vib_shear_lbin`); the VMC
Tech Notes define vibration K as the tangent slope near zero on the
load-deflection curve (`model_assumptions.md`).

## Method

```
fn_vib   = (1/2pi) * sqrt(K_vib / m) * sqrt(1 - zeta^2)     (damped, zeta = 0.12)
PSD_out(f) = T(f)^2 * PSD_in(f)                             (damped transmissibility)
g_rms    = sqrt(area under PSD_out)
```

A part is **flagged** when its `fn_vib` sits on a dominant band of the input
PSD. Fix: pick a stiffer part (higher `fn_vib`, off the peak) or verify the
duty cycle with the vendor.

## Validation

Method and numbers validated against the company's SPF_Vibration workbook
(g_rms 3.94 -> 1.52 for its reference system).

## Boundary

This is a screening check inside the selection workflow
(`selection_workflow.md`), not the full MIL-STD-810 Method 514.8
random-vibration fatigue analysis — that remains out of scope
(`model_limitations.md`, `standard_scope.md`).

The supplied vendor evidence demonstrates why this boundary matters. The
850 kg and 1050 kg CB1400-15 simulations both predicted shock accelerations
below the requested 10 g limit, but both explicitly stated that the
configuration did not meet the required 40-minute random-vibration duration.
See `shock_vibration_separation.md` for the reported resonance, RMS, and PSD
values.
