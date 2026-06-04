# Mobility Standard and Test Requirements

## Required Slope Capability

The Spinel E2 is assessed against the GSMB (Ground System Mobility Benchmark)
test-track requirements:

| Test | Requirement | Spinel E2 Result |
|---|---|---|
| Longitudinal slope | 60% grade (30.96°) | PASS (SF 2.21) |
| Lateral slope | 30% grade (16.70°) | PASS (SF 2.11) |
| Approaching angle | 60% grade equivalent | 63.5% — SUITABLE |
| Departure angle | 60% grade equivalent | 60.1% — SUITABLE |
| Minimum turning radius | 11 m | Input to cornering analysis |
| Cornering at 15 km/h | SF ≥ 1.0 | PASS (SF 3.12) |

## Safety Factor Threshold

No explicit mil-standard minimum SF is mandated for mobility (unlike tie-down
MIL-STD-209K SF ≥ 1.0 = no yield). In the SAR context:
- **SF ≥ 1.0** = vehicle will not tip under that condition (hard minimum)
- The large margins (SF 2.1–3.3) provide confidence against CG measurement
  uncertainty, payload shifts, and dynamic effects not captured by the static model

## Assessed Variants

Two CG variants are analysed:
- **Measured CG**: derived from physical wheel-load measurements (tilting tests)
  — more conservative as it accounts for actual loading and construction tolerances
- **Theory CG**: derived from the component mass budget (CAD/calculated values)
  — used as a design reference

Both variants pass all requirements. Measured CG governs (heavier, higher Zcg).

## Source Reference

Workbook: `Spinel -E2 Measured CG in FIT_13-5-2026_Turning Radius R_Final 1.xls`
Sheets: `E2 Measured Mobility Analysis`, `E2 Theory Mobility Analysis`
Engine validation: 22/22 stored SFs reproduced within 1.2% (Excel angle rounding).
