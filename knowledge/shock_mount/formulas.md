# Shock Isolation Formulas (Saw-Tooth Pulse)

**Source of truth:** `Shock Isolator_850kg_4 Bayed 35U.xls` — verbatim transcription.

Used for sizing wire rope isolators (CB1400 / CB1500 / CB1800 series) against
the 20G / 11 ms saw-tooth shock profile (MIL-STD-810H Category 4 off-road).

---

## Inputs

| Symbol | Name                          | Typical value     | Unit  |
|--------|-------------------------------|-------------------|-------|
| g      | Gravitational acceleration    | 9.81              | m/s²  |
| Ao     | Shock magnitude               | 20                | G     |
| to     | Shock pulse duration          | 0.011 (= 11 ms)   | s     |
| M      | Total system mass             | (from CAD)        | kg    |
| m      | Mass of load per isolator     | depends on case   | kg    |
| k      | Isolator stiffness            | from datasheet    | N/m   |

---

## Formulas

### 1. Velocity Change (constant for a given pulse)

```
V = 1/2 · g · Ao · to
```
For 20G / 11ms saw-tooth: **V = 1.0791 m/s**

### 2. Natural Frequency

```
fn = (1 / 2π) · √(k / m)            [Hz]
```

### 3. Transmitted G

```
GT = (2π · fn · V) / g              [G]
```

### 4. Dynamic Deflection

```
ΔD = V / (2π · fn)                  [m]   →  multiply by 1000 for mm
```

---

## Pass Criteria

The isolator **passes** for a load case only when **both** are true:

1. `GT < GT_limit` — typically **10 G** (vendor fragility limit)
2. `ΔD < dmax` — isolator's max rated travel (from datasheet)

`GT_limit` is set by the equipment being protected (electronics, displays).
`dmax` differs for compression and shear, and differs by part number.

---

## Worked Example — CB1400-15, 850 kg, 6 bottom + 4 wall (Z-axis case)

- m = 850 / 6 = 141.67 kg
- k_comp = 2650 lb/in = 464,086 N/m
- V = 0.5 × 9.81 × 20 × 0.011 = **1.0791 m/s**
- fn = (1 / 2π) × √(464086 / 141.67) = **9.109 Hz**
- GT = (2π × 9.109 × 1.0791) / 9.81 = **6.296 G** (< 10 G OK)
- ΔD = 1.0791 / (2π × 9.109) × 1000 = **18.85 mm** (< 35.56 mm OK)

These exact values appear in the `850kg,Stooth,Comp,Bottom` sheet of the reference Excel.
