"""Run: .\\mpd\\Scripts\\python.exe test_tiedown_report.py"""
from tiedown_engine import FastenerSpec, Item, MountFace, run_tiedown_analysis
from tiedown_report import generate_appendix_g


def _demo_report(target=1.5):
    m12 = FastenerSpec("8.8 M12", "BOLT", 640.0, 320.0, 76.247)
    camlock = FastenerSpec('Camlock Strap (1")', "CAMLOCK", 2500.0, 2500.0, 1.0)
    items = [
        Item("Generator", 1269.0, MountFace.FLOOR_Z, m12, 10),
        Item("Water Jerry Cans", 60.0, MountFace.FLOOR_Z, camlock, 1),
    ]
    return run_tiedown_analysis(items, target_SF=target)


def test_heading_and_standard():
    t = generate_appendix_g(_demo_report())
    assert "Appendix G" in t
    assert "MIL-STD-209K" in t
    assert "tie-down" in t.lower()


def test_states_design_loads():
    t = generate_appendix_g(_demo_report())
    assert "4G" in t and "2G" in t and "1.5G" in t
    assert "9.81" in t


def test_includes_table_numbers():
    t = generate_appendix_g(_demo_report())
    assert "Generator" in t
    assert "4.900" in t            # generator long SF from the table
    assert "SF Long" in t          # table header


def test_conclusion_flags_failing_item():
    t = generate_appendix_g(_demo_report(target=1.5))   # water cans SF 1.06 < 1.5
    assert "Water Jerry Cans" in t
    assert "1.062" in t or "1.06" in t
    assert "FAIL" in t.upper() or "do not" in t.lower() or "below" in t.lower()


def test_all_pass_conclusion():
    t = generate_appendix_g(_demo_report(target=1.0))   # everything passes at 1.0
    assert "satisfactor" in t.lower() or "all" in t.lower()


def test_target_sf_appears():
    t = generate_appendix_g(_demo_report(target=1.5))
    assert "1.5" in t


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
