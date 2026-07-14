# CB1400 Series Catalog

**Chunk:** `shock_mount/cb1400_catalog`
**Source (K / travel):** Aeroflex **"HELICAL"** master catalog (`helical.pdf`, p.15) — Shock Average K, Vibration Average K, Max Rated Dynamic Travel. Corroborated by **The VMC Group** datasheet *"Model CB1400 Series Wire Rope Isolator"*, **Rev. 5**.
**Source (Max Static F):** **Socitec** "'helical' performances" catalog (`Helical_English.pdf`, p.30, dated 2005).
**Grounding:** validated-in-repo AND confirmed against BOTH supplied sources (all values match `catalog.py` exactly).

---

CB1400 is a standard-construction **Helical Series** wire-rope isolator on
**1/2"** wire rope. Primary series for standard 19" racks. Included in AUTO
selection.

## Identity (from the datasheet title block)

| Field         | Value                                                     |
|---------------|-----------------------------------------------------------|
| Series        | CB1400                                                     |
| Product line  | Helical Series wire rope isolator                         |
| Manufacturer  | **The VMC Group** (HQ Bloomingdale, NJ; Houston, TX)      |
| Heritage      | Aeroflex pioneered the wire-rope isolator; acquired by VMC Group in 2005 |
| Datasheet     | Model CB1400 Series Wire Rope Isolator, **Rev. 5**       |
| Wire rope     | 1/2"                                                       |
| Size range    | -10 through -60                                            |
| Coils         | 8 coils standard (blank in part number)                   |
| Dimensions    | Nominal, inches, reference only (ANSI Y14.5)             |

Part-number scheme: `CB [ ] 1400 [ ] -SIZE [ ] -C2` (mounting-hole / coil-count
/ wire-rope options). Wire rope: Series 302 stainless standard. Operating
temperature range -40 °F to +700 °F.

## Full datasheet values (confirmed against `catalog.py`)

Columns per the datasheet: Shock Average K and Vibration Average K (both lb/in),
Max Rated Dynamic Travel (in). `1 lb/in = 175.1268 N/m`, `1 in = 25.4 mm`.

| Part      | Shock K comp | Shock K shear | Vib K comp | Vib K shear | Travel comp (in) | Travel shear (in) |
|-----------|--------------|---------------|------------|-------------|------------------|-------------------|
| CB1400-10 | 3515         | 1801          | 8550       | 1785        | 1.10             | 1.10              |
| CB1400-12 | 3145         | 1531          | 7500       | 1750        | 1.20             | 1.20              |
| CB1400-15 | 2650         | 1080          | 6525       | 1475        | 1.40             | 1.60              |
| CB1400-17 | 2090         | 865           | 5000       | 1075        | 1.60             | 1.80              |
| CB1400-20 | 1365         | 740           | 3650       | 740         | 2.00             | 2.00              |
| CB1400-25 | 1135         | 580           | 2950       | 650         | 2.20             | 2.20              |
| CB1400-30 | 905          | 420           | 2250       | 560         | 2.40             | 2.40              |
| CB1400-40 | 665          | 320           | 1700       | 425         | 2.80             | 2.80              |
| CB1400-50 | 500          | 260           | 1250       | 380         | 3.20             | 3.20              |
| CB1400-60 | 265          | 145           | 525        | 165         | 4.00             | 3.60              |

All Shock K, Shear K, and travel values **match `catalog.py` exactly**. The
engine uses `k_comp` (COMPRESSION) and `k_shear` (SHEAR/ROLL); Vibration K feeds
only the separate road-vibration check.

## Third load mode on the datasheet (unused by the engine)

Each part also lists a **"45 DEG. C/R"** (45-degree compression/roll) mode with
its own K and larger travel (e.g. CB1400-15: 1435 lb/in shock, 4350 vib,
2.40 in travel). The four-case physics uses only COMPRESSION and SHEAR/ROLL, so
45-deg values are recorded here for completeness but are not selected on.

## Max Static F — from the Socitec catalog (confirmed)

The VMC/Aeroflex K-and-travel datasheets do **not** publish Max Static F (VMC
"does not list load ratings for individual wire rope isolators"). Those ratings
come from the **Socitec** "'helical' performances" catalog, p.30, which lists
three load modes. The static gate uses **Compression** (bottom mounts carry the
weight); shear is informational and is ≈ half.

| Mode (Socitec p.30)          | -12 | -15 | -17 | -20 | -30 | -40 | -50 | -60 |
|------------------------------|-----|-----|-----|-----|-----|-----|-----|-----|
| Max Static F, Compression [daN] | 496 | 416 | 396 | 301 | 261 | 237 | 206 | 162 |
| Max Static F, Shear/Roll [daN]  | 248 | 208 | 198 | 151 | 130 | 119 | 103 |  81 |

All match `catalog.py` (`max_static_comp_daN` / `max_static_shear_daN`) exactly.
Socitec also lists a "45° C/R" static mode and Max Shock F at deflection (the
load-deflection points). Socitec's CB1400 list starts at **-12** and has **no
-25** — which is exactly why `catalog.py` marks **CB1400-10 and -25 as unrated**
(`None`). Socitec additionally lists a **-70** (156 daN comp) not in `catalog.py`.

## Findings for the maintainer (do not silently change the oracle)

- Aeroflex/VMC datasheets **publish Vibration K for CB1400-10 / -12 / -25**,
  which `catalog.py` stores as `None` for -10/-25 (VMC Rev. 5 also gives -12).
  Could be filled if desired.
- CB1400-10 / -25 have no Max Static F because Socitec does not list them — keep
  them warning-only in the static gate.

CB1400 vs CB61400 remains a deliberate retrieval distractor
(`cb61400_optional_scope.md`).
