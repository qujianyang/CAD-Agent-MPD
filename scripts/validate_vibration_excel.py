"""
Proof harness: vibration engine vs SPF_Vibration.xls.
Run:  .\\mpd\\Scripts\\python.exe scripts\\validate_vibration_excel.py

Using the workbook's own fn (D42) and damping factor (D43), recomputes:
  - the transmissibility column     (I6:I33)
  - the output PSD column           (J6:J33)
  - both PSD areas                  (D34, K34)
  - both g_rms values               (D35 = 3.9405, K35 = 1.5215)
and diffs against the stored cells. Expected: exact to 1e-9 (same formulas).

Workbook quirks handled:
  - Row 27 uses f = 340 Hz on the input side (col B) but f = 350 Hz on the
    output side (col G): each column is validated against its own frequencies.
  - The workbook's fn cell (27.106 Hz) is the DAMPED natural frequency:
    fd = fn*sqrt(1 - zeta^2) = 27.31 * 0.99277 = 27.11 (reconciliation printed).

Path override: SPF_XLS environment variable.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xlrd

from vibration_engine import transmissibility, grms_right_rect

WB_DEFAULT = r"C:\Users\qujia\Downloads\Shock_Mount\SPF_Vibration.xls"

ROWS = range(5, 33)     # 0-indexed rows 6..33 (28 PSD breakpoints)
TOL = 1e-9


def main() -> int:
    path = os.environ.get("SPF_XLS") or WB_DEFAULT
    try:
        sheet = xlrd.open_workbook(path).sheet_by_name("Sheet1")
    except Exception as e:
        print(f"[ERROR] cannot open workbook: {e}")
        return 2

    K = sheet.cell_value(40, 3)      # D41 stiffness [N/m]
    fn = sheet.cell_value(41, 3)     # D42 natural frequency used by the sheet
    zeta = sheet.cell_value(42, 3)   # D43 damping factor

    # fn reconciliation: the sheet's fn is the damped natural frequency of
    # K with m = 1 kg (Load row): fd = fn_undamped * sqrt(1 - zeta^2).
    fn_undamped = math.sqrt(K / 1.0) / (2 * math.pi)
    fd = fn_undamped * math.sqrt(1 - zeta ** 2)
    print(f"fn reconciliation: undamped {fn_undamped:.3f} Hz -> damped "
          f"{fd:.3f} Hz | sheet fn = {fn:.3f} Hz "
          f"(diff {abs(fd - fn):.4f} Hz)")
    print()

    n_pass = n_total = 0

    def check(label, engine, stored, tol=TOL):
        nonlocal n_pass, n_total
        n_total += 1
        diff = abs(engine - stored)
        ok = diff <= tol * max(1.0, abs(stored))
        n_pass += ok
        if not ok:
            print(f"  FAIL {label}: engine={engine!r} stored={stored!r} diff={diff:.2e}")
        return ok

    # --- transmissibility + output PSD, row by row (output-side freqs, col G)
    in_pts, out_pts = [], []
    for r in ROWS:
        f_in = sheet.cell_value(r, 1)       # col B (input side)
        p_in_b = sheet.cell_value(r, 2)     # col C
        f_out = sheet.cell_value(r, 6)      # col G (output side; row 27 differs)
        p_in_h = sheet.cell_value(r, 7)     # col H
        t_stored = sheet.cell_value(r, 8)   # col I
        p_out_stored = sheet.cell_value(r, 9)  # col J

        T = transmissibility(f_out, fn, zeta)
        check(f"T@{f_out:g}Hz", T, t_stored)
        check(f"PSDout@{f_out:g}Hz", T * T * p_in_h, p_out_stored)

        in_pts.append((f_in, p_in_b))
        out_pts.append((f_out, p_out_stored))

    # --- areas and g_rms (right-endpoint rectangles, each side's own freqs)
    area_in_stored = sheet.cell_value(33, 3)    # D34
    grms_in_stored = sheet.cell_value(34, 3)    # D35
    area_out_stored = sheet.cell_value(33, 10)  # K34
    grms_out_stored = sheet.cell_value(34, 10)  # K35

    check("area_in", grms_right_rect(in_pts) ** 2, area_in_stored)
    check("grms_in", grms_right_rect(in_pts), grms_in_stored)
    check("area_out", grms_right_rect(out_pts) ** 2, area_out_stored)
    check("grms_out", grms_right_rect(out_pts), grms_out_stored)

    print(f"TOTAL: {n_pass}/{n_total} pass "
          f"(g_rms {grms_in_stored:.4f} -> {grms_out_stored:.4f} reproduced)")
    return 0 if n_pass == n_total else 1


if __name__ == "__main__":
    sys.exit(main())
