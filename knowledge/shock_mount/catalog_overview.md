# CB-Series Wire Rope Isolator Catalog Overview

VMC Group helical wire rope isolators currently supported in the selection
engine. Numeric values are transcribed from VMC catalog `706-C` and the
individual `Model CBxxxx Helical wire rope isolator` datasheets.

For exact K and dmax values per part, see `catalog.py` in the codebase.

---

## When to use which series

| Series  | Rope dia | Typical use         | Suitable load range | Envelope     |
|---------|----------|---------------------|---------------------|--------------|
| CB1400  | 1/2"     | Standard 19" racks  | ~200 - 1000 kg      | 3" - 7" wide |
| CB1500  | 5/8"     | Heavy 19" racks     | ~500 - 1800 kg      | 4" - 7" wide |
| CB1800  | 1"       | Shelter / chassis   | ~1000 - 3000 kg     | 6" - 9" wide |

Mass ranges are rough guides; always run the selector against the 4 load
cases — a part is suitable only when all 4 pass.

---

## CB1400 family (10 variants)

Source: datasheet REV:5

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

The `-15` suffix is the most common pick for ~850 kg rack systems and is the
default in the reference Excel.

---

## CB1500 family (6 variants)

Source: datasheet REV:6 / VMC catalog 706-C

| Part      | K_comp [lb/in] | K_shear [lb/in] | dmax_comp [in] | dmax_shear [in] |
|-----------|----------------|-----------------|----------------|-----------------|
| CB1500-12 | 5375           | 2735            | 1.20           | 1.20            |
| CB1500-15 | 3655           | 1870            | 1.40           | 1.40            |
| CB1500-20 | 2585           | 1250            | 1.80           | 1.80            |
| CB1500-30 | 1610           |  800            | 2.20           | 2.20            |
| CB1500-40 | 1155           |  560            | 2.40           | 2.40            |
| CB1500-50 |  795           |  410            | 3.20           | 3.20            |

---

## CB1800 family (5 variants)

Source: datasheet REV:7 / VMC catalog 706-C

| Part      | K_comp [lb/in] | K_shear [lb/in] | dmax_comp [in] | dmax_shear [in] |
|-----------|----------------|-----------------|----------------|-----------------|
| CB1800-15 | 12100          | 6220            | 2.00           | 2.00            |
| CB1800-17 |  9300          | 4470            | 2.40           | 2.40            |
| CB1800-20 |  5910          | 2840            | 2.80           | 2.80            |
| CB1800-30 |  3080          | 1440            | 3.60           | 3.60            |
| CB1800-40 |  2050          |  870            | 4.00           | 4.00            |

---

## Unit conversions used in selection

- 1 lb/in = 175.1268 N/m
- 1 in   = 25.4 mm

So K_comp for CB1400-15: 2650 lb/in × 175.1268 = **464,086 N/m**
And dmax_comp: 1.4 in × 25.4 = **35.56 mm**

These conversions are applied automatically inside `CatalogEntry.to_isolator_spec()`.
