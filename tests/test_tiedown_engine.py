"""Standalone checks for tiedown_engine. Run: .\\mpd\\Scripts\\python.exe test_tiedown_engine.py"""
from tiedown_engine import DesignLoads, MountFace, FastenerSpec, Item


def test_fastener_forces():
    m6 = FastenerSpec("8.8 M6", "BOLT", 640.0, 320.0, 17.894)
    assert abs(m6.tensile_force_N - 11452.16) < 1e-6
    assert abs(m6.shear_force_N - 5726.08) < 1e-6
    assert abs(m6.yield_force_N("Tensile") - 11452.16) < 1e-6
    assert abs(m6.yield_force_N("Shear") - 5726.08) < 1e-6


def test_mount_face_force_types():
    assert MountFace.WALL_X.force_type("long") == "Tensile"
    assert MountFace.WALL_X.force_type("vert") == "Shear"
    assert MountFace.WALL_X.force_type("lat") == "Shear"
    assert MountFace.FLOOR_Z.force_type("vert") == "Tensile"
    assert MountFace.FLOOR_Z.force_type("long") == "Shear"
    assert MountFace.WALL_Y.force_type("lat") == "Tensile"
    assert MountFace.WALL_Y.force_type("long") == "Shear"


def test_design_loads_defaults():
    L = DesignLoads()
    assert (L.g, L.long_G, L.vert_G, L.lat_G) == (9.81, 4.0, 2.0, 1.5)


def test_item_design_kg_override():
    f = FastenerSpec("x", "BOLT", 640.0, 320.0, 17.894)
    assert Item("a", 59.0, MountFace.FLOOR_Z, f, 2, design_override_kg=60.0).design_kg == 60.0
    assert Item("b", 14.0, MountFace.WALL_X, f, 6).design_kg == 14.0


def test_generator_anchor():
    from tiedown_engine import analyze_item
    m12 = FastenerSpec("8.8 M12", "BOLT", 640.0, 320.0, 76.247)
    gen = Item("Generator", 1269.0, MountFace.FLOOR_Z, m12, 10)
    res = analyze_item(gen)
    by = {a.axis: a for a in res.axes}
    assert abs(by["long"].SF - 4.9) < 1e-2, by["long"].SF
    assert abs(by["vert"].SF - 19.599) < 1e-2, by["vert"].SF
    assert abs(by["lat"].SF - 13.066) < 1e-2, by["lat"].SF
    assert by["long"].force_type == "Shear"
    assert by["vert"].force_type == "Tensile"
    assert abs(res.min_SF - 4.9) < 1e-2


def test_water_jerry_can_marginal():
    from tiedown_engine import analyze_item
    camlock = FastenerSpec('Camlock Strap (1")', "CAMLOCK", 2500.0, 2500.0, 1.0)
    res = analyze_item(Item("Water Jerry Cans", 60.0, MountFace.FLOOR_Z, camlock, 1))
    assert abs(res.min_SF - 1.062) < 1e-2, res.min_SF
    assert res.limiting_axis.axis == "long"


def test_report_and_critical_items():
    from tiedown_engine import run_tiedown_analysis, format_report
    f8 = FastenerSpec("8.8 M6", "BOLT", 640.0, 320.0, 17.894)
    camlock = FastenerSpec('Camlock Strap (1")', "CAMLOCK", 2500.0, 2500.0, 1.0)
    items = [
        Item("Bolted box", 14.0, MountFace.WALL_X, f8, 6),
        Item("Water Jerry Cans", 60.0, MountFace.FLOOR_Z, camlock, 1),
    ]
    rep = run_tiedown_analysis(items, target_SF=2.0)
    assert not rep.all_passed                       # water cans min_SF 1.06 < 2.0
    crit = rep.critical_items()
    assert len(crit) == 1 and crit[0].item.name == "Water Jerry Cans"
    assert "TIE-DOWN PROVISION ANALYSIS" in format_report(rep)


def test_qty_zero_raises():
    from tiedown_engine import analyze_item
    f = FastenerSpec("8.8 M6", "BOLT", 640.0, 320.0, 17.894)
    try:
        analyze_item(Item("zero qty", 10.0, MountFace.WALL_X, f, 0))
        assert False, "expected ValueError for qty=0"
    except ValueError:
        pass


def test_wall_y_lateral_tensile():
    from tiedown_engine import analyze_item
    camlock = FastenerSpec('Camlock Strap (1")', "CAMLOCK", 2500.0, 2500.0, 1.0)
    res = analyze_item(Item("Side panel", 15.0, MountFace.WALL_Y, camlock, 4))
    by = {a.axis: a for a in res.axes}
    assert by["lat"].force_type == "Tensile"
    assert by["long"].force_type == "Shear" and by["vert"].force_type == "Shear"


def test_format_item_detail():
    from tiedown_engine import analyze_item, format_item_detail
    m12 = FastenerSpec("8.8 M12", "BOLT", 640.0, 320.0, 76.247)
    res = analyze_item(Item("Generator", 1269.0, MountFace.FLOOR_Z, m12, 10))
    txt = format_item_detail(res)
    assert "Generator" in txt
    assert "Tensile" in txt and "Shear" in txt
    assert "long" in txt and "vert" in txt and "lat" in txt
    assert "4.9" in txt                  # long-axis SF ~4.9
    assert "M12" in txt and "10" in txt   # fastener label + qty


def test_format_full_report_table():
    from tiedown_engine import run_tiedown_analysis, format_full_report_table
    m12 = FastenerSpec("8.8 M12", "BOLT", 640.0, 320.0, 76.247)
    camlock = FastenerSpec('Camlock Strap (1")', "CAMLOCK", 2500.0, 2500.0, 1.0)
    items = [
        Item("Generator", 1269.0, MountFace.FLOOR_Z, m12, 10),
        Item("Water Jerry Cans", 60.0, MountFace.FLOOR_Z, camlock, 1),
    ]
    rep = run_tiedown_analysis(items, target_SF=2.0)
    t = format_full_report_table(rep)
    # header columns present
    assert "SF Long" in t and "SF Vert" in t and "SF Lat" in t and "Min SF" in t
    # anchor values reproduced
    assert "4.900" in t    # generator long SF
    assert "19.599" in t   # generator vert SF
    assert "13.066" in t   # generator lat SF
    assert "1.062" in t    # water jerry cans min SF
    # verdict column
    assert "PASS" in t and "FAIL" in t
    # overall summary mentions the failing item
    assert "Water Jerry Cans" in t


def _run():
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"[PASS] {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"[FAIL] {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"[ERROR] {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run()
