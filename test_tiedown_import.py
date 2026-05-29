"""Run: .\\mpd\\Scripts\\python.exe test_tiedown_import.py  (reads the local reference workbook)"""
from tiedown_import import import_workbook, WB_DEFAULT


def test_import_count():
    items = import_workbook(WB_DEFAULT)
    assert len(items) == 59, len(items)


def test_import_item1():
    it = import_workbook(WB_DEFAULT)[0]
    assert "Air-Con" in it.name
    assert abs(it.weight_kg - 14.0) < 1e-9
    assert it.mount_face.value == "WALL_X"
    assert it.qty == 6
    assert abs(it.fastener.tensile_force_N - 11452.16) < 1e-3


def test_import_item49_override():
    it = import_workbook(WB_DEFAULT)[48]   # item 49, row index 48
    assert abs(it.weight_kg - 59.0) < 1e-9
    assert it.design_override_kg is not None
    assert abs(it.design_kg - 60.0) < 1e-3


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
            failed += 1; print(f"[ERROR] {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run()
