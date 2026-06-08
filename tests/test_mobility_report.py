"""Run: .\\mpd\\Scripts\\python.exe test_mobility_report.py"""
from mobility_engine import Vehicle, run_mobility_analysis
from mobility_report import generate_mobility_chapter

_V = Vehicle(
    name="Spinel E2 (Measured CG)",
    gw_kg=17850.0, xcg_mm=2655.46, ycg_mm=20.47, zcg_mm=1617.83,
    wheelbase_mm=4800.0, track_mm=2088.0,
)


def _demo(target=1.0):
    return run_mobility_analysis(_V, approach_deg=32.4, departure_deg=31.0, target_SF=target)


def test_heading():
    t = generate_mobility_chapter(_demo())
    assert "Appendix H" in t
    assert "Mobility" in t


def test_vehicle_params_present():
    t = generate_mobility_chapter(_demo())
    assert "17,850" in t   # GW
    assert "2655.5" in t or "2655.4" in t    # Xcg
    assert "4800" in t     # WB


def test_axle_table():
    t = generate_mobility_chapter(_demo())
    assert "7,975" in t or "7975" in t   # front axle load
    assert "9,875" in t or "9875" in t   # rear axle load
    assert "OK" in t


def test_slope_table_grades():
    t = generate_mobility_chapter(_demo())
    assert "60%" in t and "50%" in t
    assert "30%" in t and "25%" in t


def test_sf_values_present():
    t = generate_mobility_chapter(_demo())
    assert "2.2" in t    # ascending 60% SF prefix


def test_cornering_section():
    t = generate_mobility_chapter(_demo())
    assert "Cornering" in t
    assert "28,172" in t or "28172" in t   # Fc
    assert "3.116" in t


def test_all_pass_assessment():
    t = generate_mobility_chapter(_demo(target=1.0))
    assert "satisfactory" in t.lower()


def test_fail_assessment_names_case():
    t = generate_mobility_chapter(_demo(target=5.0))  # nothing can pass SF=5
    assert "do NOT meet" in t or "not meet" in t.lower()


def test_approach_departure_table():
    t = generate_mobility_chapter(_demo())
    assert "Approach" in t or "approach" in t.lower()
    assert "32.4" in t
    assert "Suitable" in t


def test_standard_cited():
    t = generate_mobility_chapter(_demo(), standard="MIL-STD-1300")
    assert "MIL-STD-1300" in t


def _run():
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"[PASS] {fn.__name__}")
        except AssertionError as e:
            failed += 1; print(f"[FAIL] {fn.__name__}: {e}")
        except Exception as e:
            failed += 1; print(f"[ERROR] {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run()
