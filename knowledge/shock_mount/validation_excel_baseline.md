# Validation Baseline (Excel Reference)

**Chunk:** `shock_mount/validation_excel_baseline`
**Source:** `Shock Isolator_850kg_4 Bayed 35U.xls` vs `physics_engine.py` `__main__` smoke test and `tests/` regressions.
**Grounding:** validated-in-repo (the numbers below are the accepted baseline). Workbook provenance (author / date / revision) → confirm when the workbook is supplied.

---

The physics engine reproduces a hand-validated spreadsheet. This chunk records
the accepted baseline so RAG can explain **where the tool's correctness claim
comes from** — while the Python engine, not RAG, remains the numerical oracle.

## Reference case

| Parameter        | Value                         |
|------------------|-------------------------------|
| Workbook         | `Shock Isolator_850kg_4 Bayed 35U.xls` |
| Isolator         | CB1400-15                     |
| System mass `M`  | 850 kg                        |
| Mounts           | 6 bottom + 4 wall             |
| Shock profile    | 20 G, 11 ms, sawtooth         |
| GT limit         | 10 G                          |

## Accepted numbers (Comp-Bottom / Z-axis)

| Quantity | Value      | Source cell / sheet             |
|----------|------------|---------------------------------|
| m        | 141.67 kg  | `850kg,Stooth,Comp,Bottom`      |
| V        | 1.0791 m/s | velocity change                 |
| fn       | 9.109 Hz   | natural frequency               |
| GT       | 6.296 G    | transmitted G (< 10 G)          |
| ΔD       | 18.85 mm   | dynamic deflection (< 35.56 mm) |

Python matches these to **4 decimal places**. The four-case per-isolator masses
(141.67 / 106.25 / 106.25 / 70.83 kg) match the Excel `m =` cells exactly
(`load_distribution.md`).

## Provenance to confirm

The engineering values are accepted and validated in-repo. The following
workbook metadata is **not yet confirmed** and should be filled from the
supplied file:

- `[SOURCE NEEDED: workbook author / owning group]`
- `[SOURCE NEEDED: workbook date / revision]`
- `[SOURCE NEEDED: any documented tolerance for Excel↔Python agreement]`

## Known PASS / FAIL anchors

- **PASS anchor:** CB1400-15 @ 850 kg, 6+4 (above).
- **FAIL anchors:** to be curated from oracle runs for the benchmark (e.g. a
  mass high enough to breach the static gate, or a clearance tight enough to
  fail `travel_limit_gate.md`). Record chosen anchors here once frozen.
