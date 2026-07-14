# Pulse Velocity Change (Impulse Velocity)

**Chunk:** `shock_mount/impulse_velocity`
**Source (method):** **The VMC Group — "Wire Rope Isolators" Tech Notes**, energy/velocity-step method (extracted 2026-07-13).
**Source (code):** `physics_engine.py` (`_velocity_change`, `_PULSE_COEFF`, `IMPULSE_VALIDITY_RATIO`); worked value validated against `Shock Isolator_850kg_4 Bayed 35U.xls`.
**Grounding:** validated-in-repo AND source-confirmed.

---

The selection physics uses the VMC Tech Notes **energy method**: a shock pulse is
reduced to an equivalent **velocity step** `V`, and the isolator is sized against
that velocity change rather than peak G alone. `V` is the conserved property of
the pulse.

## Velocity-step formulas (VMC Tech Notes)

```
V = coeff · g · Ao · to        [in/sec, with g = 386.4 in/s²]
```

| Pulse shape                        | Formula            | coeff   | Code key     |
|------------------------------------|--------------------|---------|--------------|
| Half sine                          | `V = (2g/π)·Ao·to` | 2/π ≈ 0.637 | `"half_sine"` |
| Triangular (= terminal-peak sawtooth) | `V = (g/2)·Ao·to` | 0.5   | `"sawtooth"` |
| Square                             | `V = g·Ao·to`      | 1.0     | (not in code)|

Other velocity-step inputs the Tech Notes list (not used by this tool):
- Inelastic vertical flat drop: `V = √(2·g·h)`
- Mil-S-901 medium/heavy weight test: `V = 120 in/sec`
- Mil-S-901 light weight test: `V = 150 in/sec`

**Variable definitions (VMC Tech Notes):**
`V` = equivalent velocity step [in/sec]; `g` = 386.4 in/s²; `Ao` = peak
acceleration of the pulse [G]; `to` = pulse duration [s]; `h` = drop height [in].

> The tool works in SI (`g = 9.81 m/s²`, `V` in m/s); the coefficient is the same
> pure number. The code's `"sawtooth"` key **is** the Tech Notes *Triangular*
> pulse — a terminal-peak sawtooth is a triangular pulse, both integrating to
> `½·Ao·to`.

## Worked value (project default: 20 G, 11 ms sawtooth/triangular)

```
V = 0.5 · 9.81 · 20 · 0.011 = 1.0791 m/s
```

Drives every downstream quantity (`natural_frequency.md`,
`transmitted_acceleration.md`, `dynamic_deflection.md`).

## Validity of the impulse approximation

Valid only while the pulse is short next to the mount's natural period:

```
fn · to  ≤  0.25        (IMPULSE_VALIDITY_RATIO)
```

Outside this the computed `GT`/`ΔD` are unreliable; the engine **flags** the case
rather than failing it. Reference cases sit at `fn·to = 0.07–0.12`.

> The pulse *values* (20 G / 11 ms) are project defaults whose origin is tracked
> in `project_shock_requirements.md`. The Tech Notes give the *method and
> coefficients*, not those values (their own example is 30 G / 11 ms half-sine).
