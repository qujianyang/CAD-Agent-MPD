# Static Load Gate

**Chunk:** `shock_mount/static_load_gate`
**Source:** `physics_engine.py` (`run_analysis` static block), `catalog.py` (`CatalogCandidate.static_ok`, `max_static_comp_daN`). Vendor ratings transcribed in `catalog.py`.
**Grounding:** validated-in-repo AND the daN ratings are confirmed against the **Socitec** "Helical" catalog (`Helical_English.pdf`, pp.30/32/36) — see note below.

---

Before any shock physics, the part must survive the **static gravity load** it
carries at rest. This is an independent gate: a part can pass all four dynamic
`GT`/`ΔD` cases and still fail here.

## The check

```
static_load_daN = (M / n_bottom) · g / 10            (1 daN = 10 N)
PASS (static)  ⇔  static_load_daN ≤ Max Static F (compression, daN)
```

- Only **bottom** mounts carry static weight in this model; wall mounts are
  treated as statically unloaded.
- The rating used is the vendor **Max Static F in compression**. Shear static
  ratings (half of compression) are informational only.

## Unrated parts warn, they do not auto-fail

Some parts have **no published static rating** (`max_static_comp_daN = None`):
the entire CB61400 series and CB1400-10 / CB1400-25. For these the tool emits a
warning with the computed static load and asks the engineer to verify against
vendor load-deflection data — it does **not** hard-fail them.

```
static_ok = True   if load ≤ rating
          = False  if load > rating       → part excluded
          = None   if rating not published → warn, stay selectable
```

## Vendor Max Static F (compression, daN)

Transcribed in `catalog.py`. `1 daN ≈ 1.02 kgf`.

| Model | CB1400 | CB1500 | CB1700 |
|-------|--------|--------|--------|
| -12   | 496    | 846    | —      |
| -15   | 416    | 731    | 1528   |
| -17   | 396    | 640    | 1176   |
| -20   | 301    | 518    | 1045   |
| -30   | 261    | 421    | 804    |
| -40   | 237    | 367    | 672    |
| -50   | 206    | 323    | —      |
| -60   | 162    | —      | —      |

**Where these ratings come from (confirmed).** The Aeroflex/VMC K-and-travel
datasheets publish **no Max Static F** (VMC "does not list load ratings for
individual wire rope isolators"). The Max Static F values in `catalog.py` come
from the **Socitec** "'helical' performances" catalog (`Helical_English.pdf`,
dated 2005): **CB1400 p.30, CB1500 p.32, CB1700 p.36**. On each page Socitec
lists Max Static F for three load modes; `catalog.py` uses:

- `max_static_comp_daN` ← Socitec **"Compression and Tension"** row.
- `max_static_shear_daN` ← Socitec **"Shear or Roll"** row (≈ half of compression).

Every value matches `catalog.py` exactly (e.g. CB1400 comp 496/416/396/301/261/
237/206/162; CB1700 comp 1528/1176/1045/804/672). Parts absent from the Socitec
list have no rating: **CB1400-10/-25** (Socitec starts at -12, no -25) and the
entire **CB61400** series — these stay warning-only in the gate.

> Socitec is a distinct European vendor of the equivalent "Helical" line, so the
> catalog blends sources: K/travel from Aeroflex/VMC, Max Static F from Socitec.
> Note this in the report rather than implying one single datasheet.

## Worked example

`M = 850 kg, n_bottom = 6`:
```
static_load = (850 / 6) · 9.81 / 10 = 139 daN
CB1400-15 rating = 416 daN  →  139 ≤ 416  → PASS
```

A heavier `M = 1500 kg` on 6 bottom mounts gives 245 daN/mount — over
CB1400-50's 206 daN (excluded) but within CB1400-30's 261 daN.
