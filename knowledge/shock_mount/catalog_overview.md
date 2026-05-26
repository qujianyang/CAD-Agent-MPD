# CB-Series Wire Rope Isolator Catalog Overview

Helical (Aeroflex) wire rope isolators supported in the selection engine.
All values transcribed from the official Helical datasheet PDF supplied by supervisor.
Supervisor's stated range: **C1260 to CB1700**.

For exact K and dmax values per part, see `catalog.py` in the codebase.

---

## When to use which series

| Series  | Rope dia | Construction  | Typical use           | Suitable load range | Envelope      |
|---------|----------|---------------|-----------------------|---------------------|---------------|
| CB61400 | 1/2"     | 6-strand hel. | Lighter racks, softer | ~150 - 800 kg       | 4" - 7" wide  |
| CB1400  | 1/2"     | Standard      | Standard 19" racks    | ~200 - 1000 kg      | 3" - 7" wide  |
| CB1500  | 5/8"     | Standard      | Heavy 19" racks       | ~500 - 1800 kg      | 4" - 7" wide  |
| CB1700  | 7/8"     | Standard      | Shelter / chassis     | ~800 - 3000 kg      | 6" - 9" wide  |

CB61400 and CB1400 have the same physical dimensions; CB61400 is ~25% softer.
Mass ranges are rough guides — always run the selector against all 4 load cases.

---

## CB61400 family (7 variants) — 6-strand helical, 1/2" wire

Source: Helical CB6 1400 Series datasheet

| Part        | K_comp [lb/in] | K_shear [lb/in] | dmax_comp [in] | dmax_shear [in] |
|-------------|----------------|-----------------|----------------|-----------------|
| CB61400-15  | 1990           |  810            | 1.40           | 1.60            |
| CB61400-17  | 1570           |  650            | 1.60           | 1.80            |
| CB61400-20  | 1025           |  555            | 2.00           | 2.00            |
| CB61400-30  |  680           |  315            | 2.40           | 2.40            |
| CB61400-40  |  500           |  240            | 2.80           | 2.80            |
| CB61400-50  |  375           |  195            | 3.20           | 3.20            |
| CB61400-60  |  200           |  110            | 4.00           | 3.60            |

---

## CB1400 family (10 variants) — 1/2" wire

Source: Helical CB 1400 Series datasheet REV:5
Note: -10, -12, -25 variants from REV:5 only; Helical PDF shows -15 through -60.

| Part      | K_comp [lb/in] | K_shear [lb/in] | dmax_comp [in] | dmax_shear [in] |
|-----------|----------------|-----------------|----------------|-----------------|
| CB1400-10 | 3515           | 1801            | 1.10           | 1.10            |
| CB1400-12 | 3145           | 1531            | 1.20           | 1.20            |
| CB1400-15 | 2650           | 1080            | 1.40           | 1.60            |
| CB1400-17 | 2090           |  865            | 1.60           | 1.80            |
| CB1400-20 | 1365           |  740            | 2.00           | 2.00            |
| CB1400-25 | 1135           |  580            | 2.20           | 2.20            |
| CB1400-30 |  905           |  420            | 2.40           | 2.40            |
| CB1400-40 |  665           |  320            | 2.80           | 2.80            |
| CB1400-50 |  500           |  260            | 3.20           | 3.20            |
| CB1400-60 |  265           |  145            | 4.00           | 3.60            |

CB1400-15 is the most common pick for ~850 kg rack systems (reference Excel validation case).

---

## CB1500 family (6 variants) — 5/8" wire

Source: Helical CB 1500 Series datasheet

| Part      | K_comp [lb/in] | K_shear [lb/in] | dmax_comp [in] | dmax_shear [in] |
|-----------|----------------|-----------------|----------------|-----------------|
| CB1500-12 | 5375           | 2735            | 1.20           | 1.20            |
| CB1500-15 | 3655           | 1870            | 1.40           | 1.40            |
| CB1500-20 | 2585           | 1250            | 1.80           | 1.80            |
| CB1500-30 | 1610           |  800            | 2.20           | 2.20            |
| CB1500-40 | 1155           |  560            | 2.40           | 2.40            |
| CB1500-50 |  795           |  410            | 3.20           | 3.20            |

---

## CB1700 family (5 variants) — 7/8" wire

Source: Helical CB 1700 Series datasheet p.16
Replaces CB1800 which does not appear in the official Helical catalog.

| Part      | K_comp [lb/in] | K_shear [lb/in] | dmax_comp [in] | dmax_shear [in] |
|-----------|----------------|-----------------|----------------|-----------------|
| CB1700-15 | 7565           | 3890            | 2.00           | 2.00            |
| CB1700-17 | 5815           | 2795            | 2.40           | 2.40            |
| CB1700-20 | 3695           | 1775            | 2.80           | 2.80            |
| CB1700-30 | 1925           |  900            | 3.60           | 3.60            |
| CB1700-40 | 1285           |  545            | 4.00           | 4.00            |

---

## Unit conversions used in selection

- 1 lb/in = 175.1268 N/m
- 1 in   = 25.4 mm

So K_comp for CB1400-15: 2650 lb/in × 175.1268 = **464,086 N/m**
And dmax_comp: 1.4 in × 25.4 = **35.56 mm**

These conversions are applied automatically inside `CatalogEntry.to_isolator_spec()`.
