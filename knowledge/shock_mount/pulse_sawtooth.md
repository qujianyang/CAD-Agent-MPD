# Pulse Shape: Terminal-Peak Sawtooth (Triangular)

**Chunk:** `shock_mount/pulse_sawtooth`
**Source (method):** **The VMC Group — "Wire Rope Isolators" Tech Notes** (velocity-step method, "Triangular" pulse).
**Source (code):** `physics_engine.py` (`_PULSE_COEFF["sawtooth"] = 0.5`).
**Grounding:** validated-in-repo AND source-confirmed. (The *choice* of sawtooth as the project default is still `project_shock_requirements.md`.)

---

The sawtooth (terminal-peak) pulse is the tool's **default** shock profile. In
the VMC Tech Notes energy method it is the **"Triangular"** pulse.

## Grounded and source-confirmed

The velocity change integrates to half the peak for a triangular / terminal-peak
sawtooth pulse:

```
V = (g/2) · Ao · to        (coeff = 0.5)
```

- A terminal-peak sawtooth rises linearly to `Ao` then drops instantly; its
  area (velocity change) is `½·Ao·to` — identical to the Tech Notes "Triangular"
  form. The code key `"sawtooth"` implements exactly this.
- For the 20 G / 11 ms default: `V = 1.0791 m/s` (`impulse_velocity.md`).

## Contrast with half-sine

`pulse_half_sine.md` covers the alternative. In the same energy method a
half-sine imparts `(2/π)·g·Ao·to ≈ 0.637·g·Ao·to` — **~27 % more** velocity than
a sawtooth for the same `Ao`/`to`. The code models both with these coefficients.

## Standard basis (verified 2026-07-14)

MIL-STD-810H Method 516.8 uses the **terminal-peak sawtooth** as the classical
default pulse for Procedure I - Functional Test: Table 516.8-IV / Figure
516.8-3 (method page 516.8-23) gives the default peak/duration pairs, including
the project's 20 G / 11 ms via Note 3 (`project_shock_requirements.md`).
Paragraph 4.6.2 cautions that classical pulses require tailoring justification
and must be applied in both positive and negative directions. That is why the
project default pulse is a sawtooth rather than the half-sine the VMC Tech
Notes describe as more common in general industry specifications.

**Retrieval distractor to preserve:** sawtooth/triangular vs. half-sine —
different coefficients, different velocity for the same `Ao`/`to`.
