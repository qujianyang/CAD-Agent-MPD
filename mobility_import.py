"""
Mobility workbook importer.
Source: Spinel-E2 Measured CG in FIT_13-5-2026_Turning Radius R_Final 1.xls

Reads the vehicle CG inputs and stored SF values from both CG variants:
  - "Measured" uses the 'E2 Measured CG' sheet for inputs,
                     and 'E2 Measured Mobility Analysis' for stored SFs.
  - "Theory"   uses CG summary row in 'E2 Theory Mobility Analysis'.

Override workbook path via MOBILITY_XLS environment variable.
"""

import os
import xlrd

from mobility_engine import Vehicle, Aero

WB_DEFAULT = r"C:\Users\qujia\Downloads\Spinel -E2 Measured CG in FIT_13-5-2026_Turning Radius R_Final 1.xls"

# ---------------------------------------------------------------------------
# Cell references — change here if the workbook layout ever shifts.
# All row/col are 0-indexed.  Col: A=0, B=1, ... Z=25, AA=26, etc.
# ---------------------------------------------------------------------------

# 'E2 Measured CG' input cells (col D = index 3)
_MEAS_CG = "E2 Measured CG"
_MC = {                     # (row, col)
    "WB":    (5,  3),       # D6
    "track": (6,  3),       # D7
    "Rstat": (7,  3),       # D8
    "GW":    (8,  3),       # D9
    "Xcg":   (9,  3),       # D10
    "Ycg":   (10, 3),       # D11
    "Zcg":   (11, 3),       # D12
}

# Axle limits live in 'E2 Measured Mobility Analysis' (same for both variants)
_ANAL_MEAS = "E2 Measured Mobility Analysis"
_ANAL_THEO = "E2 Theory Mobility Analysis"
_AX_LIMITS = {
    "front_limit": (13, 3),  # D14
    "rear_limit":  (14, 3),  # D15
    "gvw_limit":   (15, 3),  # D16
}

# Approach/departure angles (user-measured, same for both sheets)
_APPROACH = {
    "approach_deg": (49, 4),   # E50
    "departure_deg": (50, 4),  # E51
}

# Theory CG: row 6 of the Theory sheet (C6=GW, D6=Xcg, E6=Ycg, F6=Zcg)
_THEO_ROW = 5   # 0-indexed (row 6)
_THEO_COLS = {"GW": 2, "Xcg": 3, "Ycg": 4, "Zcg": 5}  # C, D, E, F

# ---------------------------------------------------------------------------
# Stored SF cells for validation (0-indexed row, col on the analysis sheet).
# SF labels match keys used in validate_mobility_excel.py.
# Column indices: AA=26, AJ=35, BH=59
# ---------------------------------------------------------------------------
_STORED_SF = {
    "asc_60":   (16, 26),   # AA17
    "kerb_30":  (16, 36),   # AK17  (not AJ — AJ holds '=')
    "desc_60":  (39, 26),   # AA40
    "road_30":  (39, 36),   # AK40
    "asc_50":   (64, 26),   # AA65
    "kerb_25":  (64, 36),   # AK65
    "desc_50":  (87, 26),   # AA88
    "road_25":  (87, 36),   # AK88
    "corner":   (76, 59),   # BH77
}

# Stored axle load cells (front P11, rear P12 → col P = 15)
_STORED_AXLE = {
    "front_kg": (10, 15),   # P11
    "rear_kg":  (11, 15),   # P12
}


def _open(path: str = None) -> xlrd.Book:
    p = path or os.environ.get("MOBILITY_XLS") or WB_DEFAULT
    return xlrd.open_workbook(p)


def vehicle_measured(path: str = None) -> Vehicle:
    """Read Measured-CG vehicle from 'E2 Measured CG' and analysis limit cells."""
    wb = _open(path)
    cg = wb.sheet_by_name(_MEAS_CG)
    an = wb.sheet_by_name(_ANAL_MEAS)

    def c(sheet, key, lookup): return sheet.cell_value(*lookup[key])

    return Vehicle(
        name="Spinel E2 (Measured CG)",
        gw_kg=c(cg, "GW", _MC),
        xcg_mm=c(cg, "Xcg", _MC),
        ycg_mm=c(cg, "Ycg", _MC),
        zcg_mm=c(cg, "Zcg", _MC),
        wheelbase_mm=c(cg, "WB", _MC),
        track_mm=c(cg, "track", _MC),
        rstat_mm=c(cg, "Rstat", _MC),
        front_axle_limit_kg=an.cell_value(*_AX_LIMITS["front_limit"]),
        rear_axle_limit_kg=an.cell_value(*_AX_LIMITS["rear_limit"]),
        gvw_limit_kg=an.cell_value(*_AX_LIMITS["gvw_limit"]),
    )


def vehicle_theory(path: str = None) -> Vehicle:
    """Read Theory-CG vehicle from the summary row in 'E2 Theory Mobility Analysis'."""
    wb = _open(path)
    an = wb.sheet_by_name(_ANAL_THEO)
    meas = wb.sheet_by_name(_ANAL_MEAS)   # limits live on Measured sheet (same values)

    row = _THEO_ROW
    return Vehicle(
        name="Spinel E2 (Theory CG)",
        gw_kg=an.cell_value(row, _THEO_COLS["GW"]),
        xcg_mm=an.cell_value(row, _THEO_COLS["Xcg"]),
        ycg_mm=an.cell_value(row, _THEO_COLS["Ycg"]),
        zcg_mm=an.cell_value(row, _THEO_COLS["Zcg"]),
        wheelbase_mm=meas.cell_value(9, 3),    # D10 on measured sheet (WB same for both)
        track_mm=meas.cell_value(10, 3),   # D11 on measured sheet (track same for both)
        rstat_mm=580.0,
        front_axle_limit_kg=meas.cell_value(*_AX_LIMITS["front_limit"]),
        rear_axle_limit_kg=meas.cell_value(*_AX_LIMITS["rear_limit"]),
        gvw_limit_kg=meas.cell_value(*_AX_LIMITS["gvw_limit"]),
    )


def stored_sf_map(path: str = None, variant: str = "measured") -> dict:
    """
    Return a dict {label: stored_SF} from the analysis sheet.
    variant: "measured" or "theory".
    """
    wb = _open(path)
    sheet_name = _ANAL_MEAS if variant == "measured" else _ANAL_THEO
    s = wb.sheet_by_name(sheet_name)
    return {k: s.cell_value(*rc) for k, rc in _STORED_SF.items()}


def stored_axle_map(path: str = None, variant: str = "measured") -> dict:
    """Return {label: stored_load_kg} for axle validation."""
    wb = _open(path)
    sheet_name = _ANAL_MEAS if variant == "measured" else _ANAL_THEO
    s = wb.sheet_by_name(sheet_name)
    return {k: s.cell_value(*rc) for k, rc in _STORED_AXLE.items()}


def approach_departure_angles(path: str = None, variant: str = "measured") -> tuple:
    """Return (approach_deg, departure_deg) from the analysis sheet."""
    wb = _open(path)
    sheet_name = _ANAL_MEAS if variant == "measured" else _ANAL_THEO
    s = wb.sheet_by_name(sheet_name)
    app = s.cell_value(*_APPROACH["approach_deg"])
    dep = s.cell_value(*_APPROACH["departure_deg"])
    return float(app), float(dep)


def import_workbook(path: str = None) -> dict:
    """
    Top-level import: returns both vehicles and their stored SF maps.
    Returns: {"measured": (Vehicle, sf_map, axle_map), "theory": (Vehicle, sf_map, axle_map)}
    """
    return {
        "measured": (vehicle_measured(path),
                     stored_sf_map(path, "measured"),
                     stored_axle_map(path, "measured")),
        "theory":   (vehicle_theory(path),
                     stored_sf_map(path, "theory"),
                     stored_axle_map(path, "theory")),
    }


if __name__ == "__main__":
    data = import_workbook()
    for variant, (v, sfs, axles) in data.items():
        print(f"\n=== {variant.upper()} CG ===")
        print(f"  GW={v.gw_kg:.1f} kg  Xcg={v.xcg_mm:.2f}  Ycg={v.ycg_mm:.3f}  Zcg={v.zcg_mm:.3f}")
        print(f"  Stored SFs: {sfs}")
        print(f"  Stored axle loads: {axles}")
