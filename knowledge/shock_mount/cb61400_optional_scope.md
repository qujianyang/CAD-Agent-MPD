# CB61400 Optional Scope

**Chunk:** `shock_mount/cb61400_optional_scope`
**Source:** `helical.pdf`, PDF page 5 (printed page 15), for Shock Average K,
Vibration Average K, and rated dynamic travel. `catalog.py` supplies the
application scope and selection behaviour.
**Grounding:** stiffness and travel are catalogue-verified against the supplied
legacy Aeroflex brochure. Static capacity is not verified by the supplied
sources.

CB61400 is a 6-strand Helical isolator on 1/2 inch wire rope. It has the same
physical envelope as CB1400 but is softer. It is deliberately excluded from
automatic selection because its large deflections are often unsuitable for a
standard rack and no confirmed static-load rating is available.

## Selection scope

`AUTO_SELECT_CATALOGS = CB1400 + CB1500 + CB1700`. CB61400 is included only
when the engineer explicitly requests `series="ALL"` or `series="CB61400"`.

## Catalogue-verified values

| Part | K comp [lb/in] | K shear [lb/in] | Travel comp [in] | Travel shear [in] |
|---|---:|---:|---:|---:|
| CB61400-15 | 1990 | 810 | 1.40 | 1.60 |
| CB61400-17 | 1570 | 650 | 1.60 | 1.80 |
| CB61400-20 | 1025 | 555 | 2.00 | 2.00 |
| CB61400-30 | 680 | 315 | 2.40 | 2.40 |
| CB61400-40 | 500 | 240 | 2.80 | 2.80 |
| CB61400-50 | 375 | 195 | 3.20 | 3.20 |
| CB61400-60 | 200 | 110 | 4.00 | 3.60 |

No confirmed Max Static F is available from the supplied sources. The static
gate must therefore warn rather than verify. Do not expand automatic selection
to this series without a current vendor revision and confirmed static rating.
