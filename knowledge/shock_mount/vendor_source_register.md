# Vendor Evidence Source Register

**Chunk:** `shock_mount/vendor_source_register`
**Grounding:** supplied source documents reviewed on 2026-07-26

---

Use this register to distinguish catalogue data, simulation predictions,
internal practice notes, and physical test evidence. These evidence types are
not interchangeable.

| Source ID | Supplied file | Evidence type | Permitted use |
|---|---|---|---|
| SRC-RPT-01 | `Shock_Mount_Report.docx` | Internal working report | Describes the reported company workflow, installation examples, and road-trial acceptance process. It is not a vendor specification or qualification report. |
| SRC-CAT-01 | `Socitec - CB1390.pdf` | Vendor catalogue, dated 24 Aug 2021 | CB1390 materials, dimensions, interfaces, and reference performance values. The catalogue says performance characteristics are for reference and may increase under specific conditions. |
| SRC-SIM-01 | `A101549__320kg_6xCB1390-30_4_bot&2_stab.pdf` | Vendor nonlinear SDOF calculation | Prediction for one 320 kg arrangement using six physical CB1390-30 mounts. |
| SRC-SIM-02 | `A101549__609.86kg_8xCB1390-20_6_bot&2_stab.pdf` | Vendor nonlinear SDOF calculation | Prediction for one 609.86 kg arrangement using eight physical CB1390-20 mounts. |
| SRC-SIM-03 | `A101319_115KG_4xHH14-30-03XXX.pdf` | Vendor simulation report | Prediction for 115 kg on four HH14-30 three-loop mounts. |
| SRC-SIM-04 | `A101319_135KG_4xHH14-30-03XXX.pdf` | Vendor simulation report | Prediction for 135 kg on four HH14-30 three-loop mounts. |
| SRC-SIM-05 | `A101753_850KG_10XCB1400-15XXX_6bot-4stab.pdf` | Vendor simulation report | Prediction for 850 kg on ten CB1400-15 mounts, including shock and random-vibration results. |
| SRC-SIM-06 | `A101753_1050KG_10XCB1400-15XXX_6bot-4stab.pdf` | Vendor simulation report | Prediction for 1050 kg on the same ten-mount arrangement. |
| SRC-CURVE-01 | `Stiffness dynamic-A101549.docx` | Vendor dynamic load-deflection plots | Image-only nonlinear force-deflection curves for CB1390-20 and CB1390-30. |

## Evidence rules

1. A vendor simulation or calculation sheet is not a physical test report.
2. A predicted shock response below a limit is not proof of random-vibration
   endurance, installation integrity, or road-trial acceptance.
3. Catalogue values are reference data unless the supplier confirms them for
   the exact model, interface, orientation, load, and environment.
4. No physical laboratory qualification report was included in this supplied
   document set.
5. Customer and contact names from the supplied documents are intentionally
   omitted from this knowledge base.
