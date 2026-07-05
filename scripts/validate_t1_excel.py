"""
Proof harness: the full T-1 mobility chain vs the T-1 workbook.
Run:  .\\mpd\\Scripts\\python.exe scripts\\validate_t1_excel.py

Reproduces, from the imported CG alone (importer -> T1 profile -> validated
engine, no engine changes), every stored figure on the two analysis sheets and
the reverse-CG sheet, and diffs each to 1e-9:

  per variant (Measured, Theory):
    axle front / rear                         P11 / P12            (2)
    slope SF asc/desc 60, asc/desc 50         AA17/AA40/AA65/AA88  (4)
    slope SF kerb/road 30, kerb/road 25       AK17/AK40/AK65/AK88  (4)
    cornering SF                              BH77                 (1)
  shelter component table                     count 75 / sum 10492.9 (2)
  reverse-CG payload  mass/X/Y/Z   'Re-engrg Laden Shelter Weight' G18/D19/D27/D12 (4)

Expected: 28/28 pass.

Twist-lock strength is proved separately by validate_t1_twistlock.py (12/12).
Path override: T1_MOBILITY_XLSX environment variable.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings("ignore")
import openpyxl

import mobility_import_t1 as t1
from mobility_profiles import T1_PROFILE
from mobility_profile_analysis import run_profile_mobility_analysis

TOL = 1e-9

# Analysis-sheet stored SF cells (same layout on measured + theory sheets),
# keyed by (grade_pct, direction) so they map straight onto engine results.
_SF_CELLS = {
    (60, "ascending"):  "AA17",
    (50, "ascending"):  "AA65",
    (60, "descending"): "AA40",
    (50, "descending"): "AA88",
    (30, "kerbside"):   "AK17",
    (25, "kerbside"):   "AK65",
    (30, "roadside"):   "AK40",
    (25, "roadside"):   "AK88",
}
_CORNER_CELL = "BH77"
_SF_SHEET = {"measured": "M.Stability Assess (Measured)",
             "theory":   "M.Stability Assessment (Theory)"}

# Reverse-CG payload cells on 'Re-engrg Laden Shelter Weight'
_REENG_SHEET = "Re-engrg Laden Shelter Weight"
_PAYLOAD_CELLS = {"mass": "G18", "x": "D19", "y": "D27", "z": "D12"}


class Tally:
    def __init__(self):
        self.p = self.n = 0

    def check(self, label, engine, stored):
        self.n += 1
        ok = abs(engine - stored) <= TOL * max(1.0, abs(stored))
        if ok:
            self.p += 1
        flag = "ok  " if ok else "FAIL"
        print(f"  [{flag}] {label:<26} engine={engine:>18.10f}  stored={stored:>18.10f}")
        return ok


def main() -> int:
    path = t1.workbook_path()
    if path is None:
        print(f"[SKIP] T1 workbook not found; set {t1.WB_ENV}")
        return 0
    wb = openpyxl.load_workbook(path, data_only=True)
    tally = Tally()

    for variant, vfn in (("measured", t1.vehicle_measured_t1),
                         ("theory",   t1.vehicle_theory_t1)):
        v = vfn(path)
        rep = run_profile_mobility_analysis(v, T1_PROFILE,
                                            grades_long=(60, 50), grades_side=(30, 25))
        sheet = wb[_SF_SHEET[variant]]
        print(f"=== {variant.upper()} (GW {v.gw_kg:.1f}, Xcg {v.xcg_mm:.3f}) ===")

        # axle group loads
        axle = t1.stored_axle_map_t1(path, variant)
        tally.check(f"{variant} axle front", rep.axle.front_kg, float(axle["front_kg"]))
        tally.check(f"{variant} axle rear", rep.axle.rear_kg, float(axle["rear_kg"]))

        # slope SFs
        by = {(r.grade_pct, r.direction): r for r in rep.slope_results}
        for (grade, direction), cell in _SF_CELLS.items():
            eng = by[(grade, direction)].SF
            tally.check(f"{variant} {direction} {grade}%", eng, float(sheet[cell].value))

        # cornering SF
        tally.check(f"{variant} cornering", rep.corner.SF, float(sheet[_CORNER_CELL].value))
        print()

    # shelter component table
    print("=== SHELTER COMPONENTS ===")
    comps = t1.shelter_components_t1(path)
    tally.check("component count", float(len(comps)), 75.0)
    tally.check("component mass sum", sum(c.total_mass_kg for c in comps), 10492.9)
    print()

    # reverse-CG payload vs the workbook's own stored derivation
    print("=== REVERSE-CG PAYLOAD ===")
    pl = t1.payload_cg_from_measured_t1(path)
    rs = wb[_REENG_SHEET]
    tally.check("payload mass", pl.mass_kg, float(rs[_PAYLOAD_CELLS["mass"]].value))
    tally.check("payload X", pl.x_mm, float(rs[_PAYLOAD_CELLS["x"]].value))
    tally.check("payload Y", pl.y_mm, float(rs[_PAYLOAD_CELLS["y"]].value))
    tally.check("payload Z", pl.z_mm, float(rs[_PAYLOAD_CELLS["z"]].value))
    print()

    print(f"TOTAL: {tally.p}/{tally.n} pass")
    return 0 if tally.p == tally.n else 1


if __name__ == "__main__":
    sys.exit(main())
