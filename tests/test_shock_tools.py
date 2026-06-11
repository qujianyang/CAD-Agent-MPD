"""Run: .\\mpd\\Scripts\\python.exe tests\\test_shock_tools.py  (offline; catalog + engine only)"""
from agent import run_shock_analysis, select_isolator, get_isolator_data


def test_run_shock_analysis_sawtooth_anchor():
    out = run_shock_analysis.invoke({"mass_kg": 850.0, "part_no": "CB1400-15"})
    assert "6.296" in out               # Excel validation: GT comp-bottom
    assert "18.85" in out               # Excel validation: dD comp-bottom
    assert "sawtooth" in out


def test_run_shock_analysis_half_sine_harsher():
    out = run_shock_analysis.invoke({
        "mass_kg": 850.0, "part_no": "CB1400-15", "pulse_shape": "half-sine",
    })
    assert "8.016" in out               # GT scales by (2/pi)/0.5 ~ 1.273
    assert "24.01" in out
    assert "half_sine" in out


def test_run_shock_analysis_bad_pulse_clamped():
    out = run_shock_analysis.invoke({
        "mass_kg": 850.0, "part_no": "CB1400-15", "pulse_shape": "triangle",
    })
    assert "NOTE" in out                # substitution surfaced to the LLM
    assert "6.296" in out               # fell back to sawtooth physics


def test_select_isolator_objective_max_clearance():
    out = select_isolator.invoke({"mass_kg": 850.0, "objective": "max_clearance"})
    assert "RECOMMENDED: CB1700-20" in out   # stiffest valid -> biggest margin


def test_select_isolator_bad_objective_clamped():
    out = select_isolator.invoke({"mass_kg": 850.0, "objective": "fastest"})
    assert "NOTE" in out
    assert "RECOMMENDED: CB61400-60" in out  # fell back to best_isolation


def test_get_isolator_data_part():
    out = get_isolator_data.invoke({"part_no": "CB1400-15"}).replace(",", "")
    assert "2650" in out                # K_comp lb/in
    assert "464086" in out              # K_comp N/m (deterministic conversion)
    assert "35.56" in out               # dmax_comp mm


def test_get_isolator_data_series():
    out = get_isolator_data.invoke({"series": "CB1500"})
    for p in ("CB1500-12", "CB1500-15", "CB1500-20",
              "CB1500-30", "CB1500-40", "CB1500-50"):
        assert p in out


def test_get_isolator_data_overview():
    out = get_isolator_data.invoke({})
    for s in ("CB61400", "CB1400", "CB1500", "CB1700"):
        assert s in out


def test_get_isolator_data_unknown_part():
    out = get_isolator_data.invoke({"part_no": "CB9999-1"})
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
