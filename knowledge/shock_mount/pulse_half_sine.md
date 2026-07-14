# Pulse Shape: Half-Sine

**Chunk:** `shock_mount/pulse_half_sine`
**Source (method):** The VMC Group "Wire Rope Isolators" Tech Notes
(velocity-step method, half-sine).
**Source (standard):** MIL-STD-810H Method 516.8, method page 516.8-12,
classical pulse and equal-velocity substitution guidance.
**Source (code):** `physics_engine.py` (`_PULSE_COEFF["half_sine"] = 2/pi`).

Half-sine is the tool's alternative pulse profile. Two distinct half-sine uses
must not be conflated.

## Idea 1: the code's half-sine

The VMC Tech Notes velocity-step for a half-sine pulse is:

```
V = (2g/pi) * Ao * to
```

This is `_PULSE_COEFF["half_sine"] = 2/pi`. At the same peak acceleration and
duration, it gives about 27 percent more velocity change than a sawtooth. This
is the calculation performed when the user explicitly selects `half_sine`.

## Idea 2: standard equal-velocity substitution

Method 516.8 permits classical-pulse substitution when the substituted pulse is
scaled to provide equivalent velocity change and the substitution is documented
and approved. A half-sine may therefore be lower in peak amplitude than a
sawtooth while producing the same velocity change. This is an equivalent test
specification, not the same calculation as Idea 1.

The exact relationship is in **Table 516.8-IV, Note 1** (method page 516.8-23,
verified 2026-07-14): for materiel that is shock mounted or weighs more than
136 kg (300 lbs), an 11 ms half-sine of equivalent velocity may be employed,
with:

```
Am(half-sine) = (pi/4) * Am(sawtooth)
```

The project's racks meet both conditions (shock-mounted, > 136 kg), so a
15.7 G / 11 ms half-sine is the velocity-equivalent of the default 20 G / 11 ms
sawtooth.

## Why the distinction matters

- Code half-sine: same `Ao` and `to`, therefore more severe velocity input than
  a same-amplitude sawtooth.
- Standard substitution: reduced amplitude, selected to match velocity change.

Always state which meaning is intended. Do not silently change a user-supplied
pulse shape or amplitude.
