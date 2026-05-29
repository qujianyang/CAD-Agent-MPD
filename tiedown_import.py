"""
Import the MCDLL Tie-Down Provision 'Workings' sheet into Item objects.
Reads sigma/area straight from the sheet cells (cols 10/11/12) for exact replication.

NOTE: the reference workbook is sensitive defence data and is NOT committed.
Keep it local; override the path with the TIEDOWN_XLSX env var if needed.
"""
import os
import pandas as pd

from tiedown_engine import Item, MountFace, FastenerSpec

WORKINGS_SHEET = "Tie-Down Provision Workings"
WB_DEFAULT = os.environ.get(
    "TIEDOWN_XLSX",
    r"C:\Users\qujia\Downloads\MCDLL Tie-Down Provision_20-8-2023.xlsx",
)
FIRST_ROW, LAST_ROW = 9, 67   # 0-based row indices for items 1..59 (inclusive)
_G = 9.81

# 0-based column indices (verified against the workbook)
C_NAME, C_WEIGHT, C_LONG = 2, 3, 4
C_AREA, C_SIGMA_T, C_SIGMA_S = 10, 11, 12
C_CLASS, C_SIZE = 8, 9
C_QTY_LONG, C_QTY_VERT, C_QTY_LAT, C_QTY_TOTAL = 15, 16, 17, 18


def _num(x) -> float:
    return 0.0 if pd.isna(x) else float(x)


def _infer_kind(size_label: str) -> str:
    s = (size_label or "").strip().lower()
    if s.startswith("m") or s.startswith("1/4"):
        return "BOLT"
    if "camlock" in s:
        return "CAMLOCK"
    if "ratchet" in s:
        return "RATCHET"
    if "spring latch" in s:
        return "SPRING_LATCH"
    if "locking pin" in s:
        return "LOCKING_PIN"
    if "dring" in s or "d-ring" in s:
        return "DRING"
    if "strap" in s:
        return "STRAP"
    return "BOLT"


def item_from_row(df, r):
    """Build one Item from sheet row r, or None if the row has no weight."""
    w = df.iat[r, C_WEIGHT]
    if pd.isna(w):
        return None
    area = _num(df.iat[r, C_AREA])
    st = _num(df.iat[r, C_SIGMA_T])
    ss = _num(df.iat[r, C_SIGMA_S])
    ql, qv, qla = _num(df.iat[r, C_QTY_LONG]), _num(df.iat[r, C_QTY_VERT]), _num(df.iat[r, C_QTY_LAT])
    qty = int(_num(df.iat[r, C_QTY_TOTAL]))
    face = MountFace.WALL_X if ql > 0 else (MountFace.FLOOR_Z if qv > 0 else MountFace.WALL_Y)
    size_label = "" if pd.isna(df.iat[r, C_SIZE]) else str(df.iat[r, C_SIZE])
    cls_label = "" if pd.isna(df.iat[r, C_CLASS]) else str(df.iat[r, C_CLASS])
    name = str(df.iat[r, C_NAME]) if pd.notna(df.iat[r, C_NAME]) else f"item_row{r}"
    fastener = FastenerSpec(f"{cls_label} {size_label}".strip(), _infer_kind(size_label), st, ss, area)
    # item-49 quirk: design force based on a different kg than the weight cell
    design_kg = df.iat[r, C_LONG] / (4.0 * _G)
    override = round(design_kg, 6) if abs(design_kg - float(w)) > 1e-6 else None
    return Item(name=name, weight_kg=float(w), mount_face=face, fastener=fastener,
                qty=qty, design_override_kg=override)


def import_workbook(path: str = WB_DEFAULT, sheet: str = WORKINGS_SHEET) -> list:
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    items = []
    for r in range(FIRST_ROW, LAST_ROW + 1):
        it = item_from_row(df, r)
        if it is not None:
            items.append(it)
    return items
