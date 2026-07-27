# Data Required for a Supplier Isolator Enquiry

**Chunk:** `shock_mount/supplier_data_requirements`
**Sources:** fields used in SRC-SIM-01 through SRC-SIM-06, interface data from
SRC-CAT-01, and workflow from SRC-RPT-01
**Grounding:** derived from the supplied enquiry and simulation evidence

---

A supplier enquiry should separate known project inputs, preliminary project
calculations, and outputs that the supplier must confirm.

## Project inputs to provide

- total sprung mass and tolerance;
- rack height, width, depth, and CG location;
- exact physical count and position of bottom and stabilizer mounts;
- axis convention and the expected compression, shear, or roll direction at
  each mount;
- available displacement and sway clearance in both directions on each axis;
- interface geometry, hole pattern, fastener size, bracket arrangement, and
  environmental constraints;
- shock pulse shape, peak acceleration, duration, and velocity change;
- allowable transmitted acceleration or equipment fragility limit;
- random-vibration PSD/category, axes, exposure duration, and duty cycle;
- whether equipment must operate during transport or only after the event.

## Preliminary data to label clearly

- project-selected candidate and objective;
- per-mount static loads;
- average stiffness source and units;
- four-case transmitted acceleration and displacement;
- governing static, acceleration, or travel check;
- all assumptions, warnings, and missing inputs.

## Supplier outputs to request

- complete part number, loop count, material/finish, and both bar interfaces;
- nonlinear static and dynamic load-deflection curves by relevant axis;
- modelling configuration, orientation, damping, and effective-count
  assumptions;
- predicted static deflection and modal frequencies;
- minimum and maximum displacement and acceleration in X, Y, and Z;
- random-vibration resonance, RMS acceleration, PSD response, and explicit
  duration compliance;
- installation torque, fastener engagement, bracket, clearance, and snubbing
  requirements;
- a clear statement of whether each output is a catalogue value, simulation
  prediction, or physical test result.

Do not call the pack complete while mass, mount arrangement, shock definition,
transmitted limit, or clearance is unknown. Mark those fields `TO BE
CONFIRMED`.
