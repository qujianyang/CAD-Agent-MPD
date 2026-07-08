"""Run: .\\mpd\\Scripts\\python.exe tests\\test_shock_tools.py  (offline; catalog + engine only)"""
from agent import (
    analyze_custom_isolator,
    run_shock_analysis,
    select_isolator,
    get_isolator_data,
)


def test_run_shock_analysis_sawtooth_anchor():
    out = run_shock_analysis.invoke({"mass_kg": 850.0, "part_no": "CB1400-15"})
    assert "6.296" in out               # Excel validation: GT comp-bottom
    assert "18.85" in out               # Excel validation: dD comp-bottom
    assert "sawtooth" in out


def test_run_shock_analysis_to_ms_no_warning():
    # to_ms=11 must reproduce the default 11 ms Excel anchor with NO substitution NOTE.
    out = run_shock_analysis.invoke({
        "mass_kg": 850.0, "part_no": "CB1400-15", "to_ms": 11.0,
    })
    assert "6.296" in out               # identical to the default-duration anchor
    assert "18.85" in out
    assert "NOTE" not in out            # clean pass-through, nothing substituted


def test_run_shock_analysis_to_ms_changes_result():
    # A different ms value must change the physics (proves to_ms is wired, not ignored).
    out = run_shock_analysis.invoke({
        "mass_kg": 850.0, "part_no": "CB1400-15", "to_ms": 22.0,
    })
    assert "6.296" not in out           # 22 ms != the 11 ms anchor


def test_select_isolator_to_ms_no_warning():
    out = select_isolator.invoke({"mass_kg": 850.0, "to_ms": 11.0})
    assert "NOTE" not in out            # no invalid-parameter substitution
    assert "RECOMMENDED:" in out        # a valid part was selected


def test_select_isolator_default_uses_max_clearance():
    out = select_isolator.invoke({"mass_kg": 850.0})
    assert "RECOMMENDED: CB1700-20" in out   # default is stiffest valid -> least movement


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
    assert "RECOMMENDED: CB1700-20" in out   # fell back to max_clearance (AUTO default)
    assert "CB61400" not in out              # default excludes the 6-strand series


def test_select_isolator_balanced_objective_removed():
    out = select_isolator.invoke({"mass_kg": 850.0, "objective": "balanced"})
    assert "NOTE" in out
    assert "RECOMMENDED: CB1700-20" in out


def test_select_isolator_default_excludes_cb61400():
    # Default series="AUTO" must never surface a CB61400 part (opt-in only).
    out = select_isolator.invoke({"mass_kg": 850.0})
    assert "RECOMMENDED:" in out
    assert "CB61400" not in out


def test_select_isolator_all_series_includes_cb61400():
    # Explicit opt-in still reaches the softer 6-strand series (no data lost).
    out = select_isolator.invoke({"mass_kg": 850.0, "series": "ALL"})
    assert "CB61400-60" in out


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


def test_analyze_custom_isolator_vibratec_style_data_surfaces_screening_warning():
    out = analyze_custom_isolator.invoke({
        "mass_kg": 850.0,
        "vendor": "Vibratec",
        "part_no": "A070146-061",
        "comp_stiffness_mode": "rated_load_frequency",
        "comp_value": 30.0,
        "comp_unit": "kg",
        "comp_frequency_hz": 10.0,
        "comp_max_dynamic_travel": 32.0,
        "comp_travel_unit": "mm",
        "shear_stiffness_mode": "rated_load_frequency",
        "shear_value": 6.0,
        "shear_unit": "kg",
        "shear_frequency_hz": 10.0,
        "shear_max_dynamic_travel": 37.0,
        "shear_travel_unit": "mm",
        "max_static_comp": 34.0,
        "max_static_comp_unit": "kg",
    })

    assert "=== CUSTOM ISOLATOR ANALYSIS ===" in out
    assert "Part: Vibratec A070146-061" in out
    assert "Validation: screening_only" in out
    assert "derived_from_vibration_frequency" in out
    assert "Static load" in out
    assert "FAIL" in out
    assert "vibration frequency" in out


def test_analyze_custom_isolator_socitec_style_data_runs_four_cases():
    out = analyze_custom_isolator.invoke({
        "mass_kg": 850.0,
        "vendor": "Socitec",
        "part_no": "CB1400-15",
        "comp_stiffness_mode": "force_deflection",
        "comp_value": 1253.0,
        "comp_unit": "daN",
        "comp_deflection": 37.0,
        "comp_deflection_unit": "mm",
        "comp_max_dynamic_travel": 37.0,
        "comp_travel_unit": "mm",
        "shear_stiffness_mode": "force_deflection",
        "shear_value": 1100.0,
        "shear_unit": "daN",
        "shear_deflection": 35.0,
        "shear_deflection_unit": "mm",
        "shear_max_dynamic_travel": 35.0,
        "shear_travel_unit": "mm",
        "max_static_comp": 417.0,
        "max_static_comp_unit": "daN",
    })

    assert "Part: Socitec CB1400-15" in out
    assert "derived_from_shock_load_deflection" in out
    assert "Comp-Bottom" in out
    assert "Comp-Wall" in out
    assert "Roll-Wall" in out
    assert "Roll-Bottom" in out
    assert "shock load-deflection" in out


def test_analyze_custom_isolator_rejects_missing_shear_data():
    out = analyze_custom_isolator.invoke({
        "mass_kg": 850.0,
        "vendor": "Vibratec",
        "part_no": "A070146-061",
        "comp_stiffness_mode": "rated_load_frequency",
        "comp_value": 30.0,
        "comp_unit": "kg",
        "comp_frequency_hz": 10.0,
        "comp_max_dynamic_travel": 32.0,
        "comp_travel_unit": "mm",
        "shear_stiffness_mode": "",
        "shear_value": 0.0,
        "shear_unit": "",
        "shear_max_dynamic_travel": 0.0,
        "shear_travel_unit": "",
    })

    assert out.startswith("ERROR")
    assert "shear" in out.lower()


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
