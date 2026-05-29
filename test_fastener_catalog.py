"""Run: .\\mpd\\Scripts\\python.exe test_fastener_catalog.py"""
from tiedown_engine import MountFace
from fastener_catalog import bolt, non_bolt, make_fastener


def test_bolt_8p8_m6():
    f = bolt("8.8", "M6")
    assert abs(f.area_mm2 - 17.894) < 1e-9
    assert f.sigma_t_MPa == 640 and f.sigma_s_MPa == 320
    assert abs(f.tensile_force_N - 11452.16) < 1e-6
    assert abs(f.shear_force_N - 5726.08) < 1e-6


def test_bolt_m12():
    f = bolt("8.8", "M12")
    assert abs(f.area_mm2 - 76.247) < 1e-9
    assert abs(f.shear_force_N - 24399.04) < 1e-6


def test_camlock_strap():
    f = non_bolt('Camlock Strap (1")')
    assert f.sigma_t_MPa == 2500 and f.sigma_s_MPa == 2500 and f.area_mm2 == 1.0
    assert f.kind == "CAMLOCK"


def test_spring_latch_full_precision():
    f = non_bolt("Spring Latch")
    assert abs(f.area_mm2 - 113.09733552923255) < 1e-9
    assert f.sigma_t_MPa == 165 and f.sigma_s_MPa == 82.5
    assert abs(f.tensile_force_N - 18661.06) < 1e-2   # matches sheet item 12


def test_make_fastener_dispatch():
    assert make_fastener("8.8", "M8").kind == "BOLT"
    assert make_fastener('Ratchet (1")').kind == "RATCHET"


def test_min_qty_generator():
    from fastener_catalog import min_qty_for_target
    q = min_qty_for_target(1269.0, MountFace.FLOOR_Z, bolt("8.8", "M12"), target_SF=1.0)
    assert q == 3, q   # long axis governs: 49795.56 / 24399.04 = 2.04 -> ceil 3


def test_size_fasteners_meets_target():
    from fastener_catalog import size_fasteners
    opts = size_fasteners(60.0, MountFace.FLOOR_Z, target_SF=2.0)
    assert len(opts) >= 1
    assert opts[0].min_SF >= 2.0          # top option actually meets the target
    assert opts[0].qty >= 1
    # options are sorted by fewest fasteners, then smallest area
    assert all(opts[i].qty <= opts[i + 1].qty for i in range(len(opts) - 1))


def _run():
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"[PASS] {fn.__name__}")
        except AssertionError as e:
            failed += 1; print(f"[FAIL] {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run()
