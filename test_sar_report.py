"""
Tests for the SAR appendix (.docx) generator.
Run: .\\mpd\\Scripts\\python.exe test_sar_report.py

Verifies the generated document reproduces the PUBLISHED SAR safety factors
(2.21 / 2.73 / 2.20 / 2.11 / 3.12) and contains the expected B/C/D/E structure.
"""
from mobility_engine import Vehicle, Aero
from mobility_import import (
    MeasurementData, WheelReading, TiltTest,
)
from sar_report import generate_sar_appendices


_V = Vehicle(
    name="Spinel E2 (Measured CG)",
    gw_kg=17850.0, xcg_mm=2655.4621848739494, ycg_mm=20.470588235294144,
    zcg_mm=1617.8285033663278, wheelbase_mm=4800.0, track_mm=2088.0,
)

_M = MeasurementData(
    wheels=[
        WheelReading("Front Left (FL)", 4000, 4000, 4000),
        WheelReading("Front Right (FR)", 4000, 3950, 3975),
        WheelReading("Rear Left (RL)", 4750, 4750, 4750),
        WheelReading("Rear Right (RR)", 5100, 5150, 5125),
    ],
    gw_kg=17850, front_axle_kg=7975, rear_axle_kg=9875,
    driver_kg=9100, kerb_kg=8750, front_diff_pct=0.313, rear_diff_pct=3.797,
    tilt_tests=[
        TiltTest(1, 10.2, 580, 10550, 1588.8),
        TiltTest(2, 12.3, 580, 10700, 1597.5),
        TiltTest(3, 8.2, 580, 10450, 1653.0),
        TiltTest(4, 6.2, 580, 10300, 1632.0),
    ],
    avg_z_mm=1617.8,
)


def _all_text(doc):
    parts = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                parts.append(c.text)
    return "\n".join(parts)


def test_has_four_appendices():
    doc = generate_sar_appendices(_V, _M)
    txt = _all_text(doc)
    assert "Appendix B" in txt
    assert "Appendix C" in txt
    assert "Appendix D" in txt
    assert "Appendix E" in txt


def test_appendix_b_wheel_loads():
    doc = generate_sar_appendices(_V, _M)
    txt = _all_text(doc)
    assert "Front Left (FL)" in txt
    assert "7975" in txt and "9875" in txt   # axle loads
    assert "2655.5" in txt                   # Xcg
    assert "1617.8" in txt                   # Zcg


def test_published_slope_sfs():
    doc = generate_sar_appendices(_V, _M)
    txt = _all_text(doc)
    # The exact published SAR values
    assert "2.21" in txt   # asc 60
    assert "2.73" in txt   # desc 60
    assert "2.20" in txt   # kerb 30
    assert "2.11" in txt   # road 30


def test_published_cornering_sf():
    doc = generate_sar_appendices(_V, _M)
    txt = _all_text(doc)
    assert "3.12" in txt          # cornering SF
    assert "1.5" in txt           # OEM recommended threshold


def test_table_captions():
    doc = generate_sar_appendices(_V, _M)
    txt = _all_text(doc)
    for cap in ["Table B-1", "Table B-2", "Table C-1", "Table C-2",
                "Table D-1", "Table D-2", "Table E-1"]:
        assert cap in txt, cap


def test_saves_file(tmp_path=None):
    import tempfile, os
    d = tempfile.mkdtemp()
    out = os.path.join(d, "out.docx")
    generate_sar_appendices(_V, _M, out_path=out)
    assert os.path.exists(out) and os.path.getsize(out) > 5000


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
