# CB1500 Series Catalog

**Chunk:** `shock_mount/cb1500_catalog`
**Source (K / travel):** Aeroflex **"HELICAL"** master catalog (`helical.pdf`, p.16). Corroborated by **The VMC Group** datasheet *"Model CB1500 Series Wire Rope Isolator"*, **Rev. 6**.
**Source (Max Static F):** **Socitec** "'helical' performances" catalog (`Helical_English.pdf`, p.32, dated 2005).
**Grounding:** validated-in-repo AND confirmed against BOTH supplied sources (loaded values match `catalog.py` exactly).

---

CB1500 is a standard-construction **Helical Series** wire-rope isolator on
**5/8"** wire rope — the heavier series above CB1400. Included in AUTO selection.

## Identity (from the datasheet title block)

| Field         | Value                                                     |
|---------------|-----------------------------------------------------------|
| Series        | CB1500                                                     |
| Product line  | Helical Series wire rope isolator                         |
| Manufacturer  | **The VMC Group** (HQ Bloomingdale, NJ; Houston, TX)      |
| Datasheet     | Model CB1500 Series Wire Rope Isolator, **Rev. 6**       |
| Wire rope     | 5/8"                                                       |
| Size range    | -10 through -70                                            |
| Coils         | 8 coils standard (blank in part number)                   |

Wire rope: Series 302 stainless standard. Operating temperature -40 °F to +700 °F.

## Full datasheet values (11 variants)

Columns: Shock Average K and Vibration Average K (lb/in), Max Rated Dynamic
Travel (in).

| Part      | Shock K comp | Shock K shear | Vib K comp | Vib K shear | Travel comp (in) | Travel shear (in) |
|-----------|--------------|---------------|------------|-------------|------------------|-------------------|
| CB1500-10 | 6200         | 3360          | 13800      | 4350        | 1.20             | 1.20              |
| CB1500-12 | 5375         | 2735          | 12625      | 2950        | 1.20             | 1.20              |
| CB1500-15 | 3655         | 1870          | 8095       | 2100        | 1.40             | 1.40              |
| CB1500-17 | 3200         | 1550          | 7200       | 1850        | 1.40             | 1.40              |
| CB1500-20 | 2585         | 1250          | 5525       | 1350        | 1.80             | 1.80              |
| CB1500-25 | 1850         | 1000          | 4100       | 1150        | 2.20             | 2.20              |
| CB1500-30 | 1610         | 800           | 3425       | 1060        | 2.20             | 2.20              |
| CB1500-40 | 1155         | 560           | 2450       | 750         | 2.40             | 2.40              |
| CB1500-50 | 795          | 410           | 1700       | 550         | 3.20             | 3.20              |
| CB1500-60 | 700          | 380           | 1240       | 390         | 3.40             | 3.40              |
| CB1500-70 | 650          | 330           | 1140       | 350         | 3.70 (comp) / 4.00 (shear) | — |

`catalog.py` currently carries **6 of these 11** variants (-12, -15, -20, -30,
-40, -50); every value for those six **matches the datasheet exactly**. The
engine uses `k_comp` (COMPRESSION) and `k_shear` (SHEAR/ROLL).

## Third load mode on the datasheet (unused)

Each part also lists a **"45 DEG. C/R"** mode (e.g. CB1500-15: 2265 lb/in shock,
5525 vib, 2.20 in travel). Not used by the four-case physics.

## Max Static F — from the Socitec catalog (confirmed)

Per Socitec p.32 (Compression = comp static; Shear/Roll = shear static, ≈ half):

| Mode (Socitec p.32)          | -12 | -15 | -17 | -20 | -30 | -40 | -50 | -60 |
|------------------------------|-----|-----|-----|-----|-----|-----|-----|-----|
| Max Static F, Compression [daN] | 846 | 731 | 640 | 518 | 421 | 367 | 323 | 312 |
| Max Static F, Shear/Roll [daN]  | 423 | 366 | 320 | 259 | 210 | 183 | 162 | 156 |

The six variants in `catalog.py` (-12, -15, -20, -30, -40, -50) match exactly.

## Findings for the maintainer

- The Aeroflex/VMC catalogs support **more variants** than `catalog.py` loads
  (VMC: -10, -17, -25, -60, -70). Socitec gives Max Static F for -17 (640) and
  -60 (312) too; -10, -25, -70 have no Socitec static rating. Do not expand the
  selectable set silently.
