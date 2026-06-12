# Shock Environment, Clearances and Selection Objective

## Shock environment inputs

- **"Shock Ao [G]"** (default 20) — the peak input acceleration of the shock pulse.
- **"Pulse to [ms]"** (default 11) — the pulse duration.
- **"GT limit [G]"** (default 10) — the maximum transmitted acceleration the equipment may
  see. A part passes only if its transmitted G stays below this in every load case.
- **"Pulse profile"** — the pulse shape:
  - **"Saw-Tooth (terminal-peak)"** — the standard test pulse (default).
  - **"Half-Sine (~27% harsher)"** — carries more velocity change for the same Ao and
    duration, so the same part sees roughly 27% harsher loading. Pick this only if your
    requirement specifies a half-sine pulse.

Leave the defaults unless your shock specification says otherwise — they reflect the
project's standard 20 G / 11 ms terminal-peak saw-tooth environment.

## Installation clearance

"Clearance X [mm]", "Clearance Y [mm]", "Clearance Z [mm]" — the free gap to neighbouring
equipment or the rack wall in each axis (Z = vertical, X/Y = lateral).

- **0 means no limit** — only the mount's own rated travel constrains deflection.
- A non-zero value adds a hard constraint: the dynamic deflection must stay below the gap,
  otherwise the equipment strikes its neighbour. Parts that exceed it are rejected.

## Selection objective (Auto mode only)

Chooses how to rank parts that already pass everything:

- **"Balanced (furthest from any limit)"** — most margin overall (default).
- **"Best isolation (softest, lowest G)"** — minimises transmitted G; deflects more.
- **"Max clearance (stiffest, least travel)"** — minimises deflection; transmits more G.

Note the help text on the control: clearance is a hard pass/fail gate in every mode — the
objective only chooses BETWEEN parts that already pass all 4 cases.
