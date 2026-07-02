"""
Proof harness: shock physics engine vs the reference workbook.
Run:  .\\mpd\\Scripts\\python.exe scripts\\validate_shock_excel.py

Reads the four direction sheets of 'Shock Isolator_850kg_4 Bayed 35U.xls',
recomputes V / fn / GT / dD from each sheet's OWN inputs (g, Ao, to, m, k)
via physics_engine, and diffs against the stored cell values:
    E27 = V [m/s], E30 = fn [Hz], E34 = GT [g], E38 = dD [mm]
Expected: 16/16 to machine precision (identical formulas).

Workbook path override: SHOCK_XLS environment variable.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xlrd

from physics_engine import (
    _velocity_change, _natural_freq, _transmitted_g, _dynamic_deflection_mm,
)

WB_DEFAULT = r"C:\Users\qujia\Downloads\Shock_Mount\Shock Isolator_850kg_4 Bayed 35U.xls"

SHEETS = [
    "850kg,Stooth,Comp,Bottom",
    "850kg,Stooth,Comp,Wall",
    "850kg,Stooth,Roll,Wall",
    "850kg,Stooth,Rollshear,Bottom",
]

# (row, col) 0-indexed cell refs, identical layout on all four sheets
CELLS_IN = {
    "g":  (4, 4),   # E5
    "Ao": (5, 4),   # E6
    "to": (6, 4),   # E7
    "m":  (8, 4),   # E9   mass per isolator
    "k":  (10, 4),  # E11  stiffness for this direction
}
CELLS_OUT = {
    "V":  (26, 4),  # E27  [m/s]
    "fn": (29, 4),  # E30  [Hz]
    "GT": (33, 4),  # E34  [g]
    "dD": (37, 4),  # E38  [mm]
}

TOL = 1e-9


def validate_sheet(sheet) -> list:
    """Return [(label, engine, stored, diff, ok), ...] for one direction sheet."""
    g  = sheet.cell_value(*CELLS_IN["g"])
    Ao = sheet.cell_value(*CELLS_IN["Ao"])
    to = sheet.cell_value(*CELLS_IN["to"])
    m  = sheet.cell_value(*CELLS_IN["m"])
    k  = sheet.cell_value(*CELLS_IN["k"])

    V  = _velocity_change(g, Ao, to, "sawtooth")
    fn = _natural_freq(k, m)
    GT = _transmitted_g(fn, V, g)
    dD = _dynamic_deflection_mm(V, fn)

    engine = {"V": V, "fn": fn, "GT": GT, "dD": dD}
    rows = []
    for label, rc in CELLS_OUT.items():
        stored = sheet.cell_value(*rc)
        diff = abs(engine[label] - stored)
        rows.append((label, engine[label], stored, diff, diff <= TOL * max(1.0, abs(stored))))
    return rows


def main() -> int:
    path = os.environ.get("SHOCK_XLS") or WB_DEFAULT
    try:
        wb = xlrd.open_workbook(path)
    except Exception as e:
        print(f"[ERROR] cannot open workbook: {e}")
        return 2

    n_pass = n_total = 0
    for name in SHEETS:
        sheet = wb.sheet_by_name(name)
        rows = validate_sheet(sheet)
        ok_count = sum(1 for *_, ok in rows if ok)
        n_pass += ok_count
        n_total += len(rows)
        print(f"=== {name} — {ok_count}/{len(rows)} ===")
        print(f"  {'qty':<4} {'engine':>20} {'stored':>20} {'diff':>12}")
        for label, eng, stored, diff, ok in rows:
            flag = "OK" if ok else "FAIL"
            print(f"  {label:<4} {eng:>20.12f} {stored:>20.12f} {diff:>12.2e}  {flag}")
        print()

    print(f"TOTAL: {n_pass}/{n_total} pass")
    return 0 if n_pass == n_total else 1


if __name__ == "__main__":
    sys.exit(main())
