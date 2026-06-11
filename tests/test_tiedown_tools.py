"""Run: .\\mpd\\Scripts\\python.exe test_tiedown_tools.py  (deterministic; reads the workbook)"""
from tiedown_tools import run_tiedown_check, recommend_fasteners


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
