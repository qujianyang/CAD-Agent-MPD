"""
Validate that tiedown_engine reproduces the workbook's safety factors.
Run: .\\mpd\\Scripts\\python.exe validate_tiedown_excel.py
Exit 0 = all 177 SFs match to < 1e-6; exit 1 = mismatch.
"""
import sys
import pandas as pd

from tiedown_import import item_from_row, WORKINGS_SHEET, WB_DEFAULT, FIRST_ROW, LAST_ROW
from tiedown_engine import analyze_item

C_SF = (43, 44, 45)   # sheet SF columns: long, vert, lat


def main(path: str = WB_DEFAULT) -> bool:
    df = pd.read_excel(path, sheet_name=WORKINGS_SHEET, header=None)
    items = 0
    compared = 0
    max_diff = 0.0
    worst = None
    for r in range(FIRST_ROW, LAST_ROW + 1):
        it = item_from_row(df, r)
        if it is None:
            continue
        items += 1
        res = analyze_item(it)
        for a, col in zip(res.axes, C_SF):
            sheet_sf = float(df.iat[r, col])
            compared += 1
            d = abs(a.SF - sheet_sf)
            if d > max_diff:
                max_diff = d
                worst = (r, a.axis, round(a.SF, 6), sheet_sf)
    ok = (items == 59 and compared == 177 and max_diff < 1e-6)
    print(f"items compared   : {items}")
    print(f"SFs compared     : {compared}")
    print(f"max abs diff     : {max_diff:.3e}")
    print(f"worst case       : {worst}")
    print("[PASS] engine reproduces all 177 safety factors to < 1e-6"
          if ok else "[FAIL] mismatch -- investigate the worst case above")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
