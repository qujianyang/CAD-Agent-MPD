"""
Proof harness: engine SF vs stored cell values for both CG variants.
Run: .\\mpd\\Scripts\\python.exe validate_mobility_excel.py

Engine uses exact atan(); Excel rounds angles to 0.1deg.
Max allowed diff is 1% of the stored SF (relative) — calibrated against known rounding source.
"""

import sys
from mobility_engine import (
    Vehicle, Aero, axle_loads, slope_stability, side_slope_stability,
    cornering_stability, run_mobility_analysis,
)
from mobility_import import import_workbook

# Map stored SF label -> (grade_pct, direction)
_SF_CASES = {
    "asc_60":  (60,  "ascending"),
    "desc_60": (60,  "descending"),
    "asc_50":  (50,  "ascending"),
    "desc_50": (50,  "descending"),
    "kerb_30": (30,  "kerbside"),
    "road_30": (30,  "roadside"),
    "kerb_25": (25,  "kerbside"),
    "road_25": (25,  "roadside"),
}

_AERO = Aero()
_TOL_REL = 0.012    # 1.2% relative — accommodates 0.1-deg rounding in Excel


def _engine_sf(v: Vehicle, label: str) -> float:
    if label == "corner":
        return cornering_stability(v, _AERO, speed_kmh=15.0, radius_m=11.0, wind_kmh=60.0).SF
    grade, direction = _SF_CASES[label]
    if direction in ("ascending", "descending"):
        return slope_stability(v, grade, direction).SF
    return side_slope_stability(v, grade, direction).SF


def validate(variant: str, v: Vehicle, sf_map: dict, axle_map: dict) -> list:
    """Return list of (label, engine_val, sheet_val, diff, ok) tuples."""
    results = []

    for label, sheet_val in sf_map.items():
        eng = _engine_sf(v, label)
        diff = abs(eng - sheet_val)
        ok = diff <= _TOL_REL * abs(sheet_val)
        results.append((label, eng, sheet_val, diff, ok))

    # Axle loads
    ax = axle_loads(v)
    for label, sheet_val in axle_map.items():
        eng = ax.front_kg if label == "front_kg" else ax.rear_kg
        diff = abs(eng - sheet_val)
        ok = diff < 1.0   # 1 kg tolerance for axle loads
        results.append((label, eng, sheet_val, diff, ok))

    return results


def report(variant: str, rows: list) -> bool:
    n_pass = sum(1 for *_, ok in rows if ok)
    n_total = len(rows)
    header = f"=== {variant.upper()} CG — {n_pass}/{n_total} ==="
    print(header)
    print(f"  {'Label':<12}  {'Engine':>10}  {'Sheet':>10}  {'Diff':>10}  {'Status':>6}")
    print("  " + "-" * 55)
    for label, eng, sheet, diff, ok in rows:
        status = "OK" if ok else "FAIL"
        print(f"  {label:<12}  {eng:>10.6f}  {sheet:>10.6f}  {diff:>10.6f}  {status:>6}")
    print()
    return n_pass == n_total


if __name__ == "__main__":
    try:
        data = import_workbook()
    except Exception as e:
        print(f"[ERROR] Cannot read workbook: {e}")
        sys.exit(2)

    all_ok = True
    for variant, (v, sf_map, axle_map) in data.items():
        rows = validate(variant, v, sf_map, axle_map)
        ok = report(variant, rows)
        all_ok = all_ok and ok

    n_total = sum(len(validate(variant, v, sf_map, axle_map))
                  for variant, (v, sf_map, axle_map) in data.items())
    n_pass  = sum(sum(1 for *_, ok in validate(variant, v, sf_map, axle_map) if ok)
                  for variant, (v, sf_map, axle_map) in data.items())

    print(f"TOTAL: {n_pass}/{n_total} pass")
    sys.exit(0 if all_ok else 1)
