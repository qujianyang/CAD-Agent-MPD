"""Run: .\\mpd\\Scripts\\python.exe test_tiedown_tools.py  (deterministic; reads the workbook)"""
from tiedown_tools import (
    run_tiedown_check, recommend_fasteners, get_fastener_data, check_workbook_item,
)


def test_run_tiedown_check_generator():
    out = run_tiedown_check.invoke({
        "weight_kg": 1269.0, "mount_face": "floor",
        "fastener": "8.8", "fastener_size": "M12", "qty": 10,
    })
    assert "4.9" in out                 # long-axis SF ~4.9
    assert "Tensile" in out and "Shear" in out
    assert "PASS" in out


def test_run_tiedown_check_bad_face():
    out = run_tiedown_check.invoke({
        "weight_kg": 10.0, "mount_face": "nonsense",
        "fastener": "8.8", "fastener_size": "M6", "qty": 4,
    })
    assert out.startswith("ERROR")


def test_recommend_fasteners_prefers_bolt():
    out = recommend_fasteners.invoke({
        "weight_kg": 1269.0, "mount_face": "floor", "target_SF": 1.0,
    })
    assert "M10" in out                 # smallest valid bolt at SF 1.0
    assert "RECOMMENDED" in out


def test_recommend_fasteners_specific_fastener_qty():
    # td-size eval case shape: "how many M12 8.8 bolts ... at SF 2?"
    out = recommend_fasteners.invoke({
        "weight_kg": 1269.0, "mount_face": "floor",
        "fastener": "8.8 M12", "target_SF": 2.0,
    })
    assert "x5" in out                  # closed-form min qty = 5
    assert "2.45" in out                # achieved min SF at qty 5
    assert "REQUIRED" in out


def test_recommend_fasteners_unknown_fastener():
    out = recommend_fasteners.invoke({
        "weight_kg": 100.0, "mount_face": "floor", "fastener": "unobtainium",
    })
    assert out.startswith("ERROR")


def test_get_fastener_data_bolt():
    out = get_fastener_data.invoke({"fastener": "8.8 M10"}).replace(",", "")
    assert "33466" in out               # tensile yield force N
    assert "16733" in out               # shear yield force N


def test_get_fastener_data_strap():
    out = get_fastener_data.invoke({"fastener": "camlock"}).replace(",", "")
    assert "2500" in out                # rated load of the 1" camlock strap


def test_get_fastener_data_class_defaults_to_88_with_note():
    out = get_fastener_data.invoke({"fastener": "M10"})
    assert "NOTE" in out and "8.8" in out


def test_get_fastener_data_catalog_summary():
    out = get_fastener_data.invoke({})
    assert "8.8" in out and "M12" in out and "Camlock" in out


def test_check_workbook_item_single_match_detail():
    out = check_workbook_item.invoke({"item_name": "water jerry"})
    assert "1.06" in out                # weakest workbook item
    assert "FAIL" in out                # below the default 1.5 design factor


def test_check_workbook_item_multi_match_lists_all():
    out = check_workbook_item.invoke({"item_name": "generator"})
    assert "4.9" in out                 # the 1269 kg generator, M12 x10
    assert out.lower().count("generator") >= 2   # ladder item matches too


def test_check_workbook_item_summary():
    out = check_workbook_item.invoke({})
    assert "59" in out                  # all workbook items analysed
    assert "Water Jerry" in out         # below-target list names the worst item


def test_check_workbook_item_unknown_name():
    out = check_workbook_item.invoke({"item_name": "flux capacitor"})
    assert out.startswith("ERROR")


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
