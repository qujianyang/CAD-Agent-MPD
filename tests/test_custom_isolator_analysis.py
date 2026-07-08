import pytest

from custom_isolator import CustomIsolatorInput, DirectionInput, StiffnessInput, ValidationError
from custom_isolator_analysis import analyze_custom_isolator
from physics_engine import ShockEnv


ENV = ShockEnv(Ao_G=20.0, to_s=0.011, GT_limit_G=10.0)


def _vmc_cb1400_15():
    return CustomIsolatorInput(
        vendor="VMC",
        part_no="CB1400-15",
        compression=DirectionInput(
            stiffness=StiffnessInput.direct_k(2650, "lb/in"),
            max_dynamic_travel=1.40,
            travel_unit="in",
        ),
        shear=DirectionInput(
            stiffness=StiffnessInput.direct_k(1080, "lb/in"),
            max_dynamic_travel=1.60,
            travel_unit="in",
        ),
        max_static_comp=416,
        max_static_comp_unit="daN",
        source="Helical CB1400 datasheet",
    )


def _vibratec_a070146_061():
    return CustomIsolatorInput(
        vendor="Vibratec",
        part_no="A070146-061",
        compression=DirectionInput(
            stiffness=StiffnessInput.rated_load_frequency(30, "kg", 10),
            max_dynamic_travel=32,
            travel_unit="mm",
        ),
        shear=DirectionInput(
            stiffness=StiffnessInput.rated_load_frequency(6, "kg", 10),
            max_dynamic_travel=37,
            travel_unit="mm",
        ),
        max_static_comp=34,
        max_static_comp_unit="kg",
        source="Vibratec WRI-A07 datasheet row",
    )


def _socitec_cb1400_15():
    return CustomIsolatorInput(
        vendor="Socitec",
        part_no="CB1400-15",
        compression=DirectionInput(
            stiffness=StiffnessInput.force_deflection(1253, "daN", 37, "mm"),
            max_dynamic_travel=37,
            travel_unit="mm",
        ),
        shear=DirectionInput(
            stiffness=StiffnessInput.force_deflection(1100, "daN", 35, "mm"),
            max_dynamic_travel=35,
            travel_unit="mm",
        ),
        max_static_comp=417,
        max_static_comp_unit="daN",
        source="Socitec CB1400 PDF",
    )


def test_analyzes_validated_custom_vmc_part_with_existing_four_case_engine():
    result = analyze_custom_isolator(
        _vmc_cb1400_15(),
        mass_kg=850.0,
        n_bottom=6,
        n_wall=4,
        shock_env=ENV,
    )

    assert result.normalized.spec.name == "VMC CB1400-15"
    assert result.validation_level == "validated"
    assert result.static_load_daN == pytest.approx((850.0 / 6) * 9.81 / 10)
    assert result.static_rating_daN == pytest.approx(416)
    assert result.static_ok is True
    assert result.report.all_passed is True
    assert result.passed is True
    assert result.verdict == "PASS"
    assert [d.label for d in result.report.directions] == [
        "Comp - Bottom (Z-axis, vertical)",
        "Comp - Wall (Y-axis, lateral)",
        "Roll - Wall (X,Z-axis, shear)",
        "Roll - Bottom (X,Y-axis, shear)",
    ]


def test_custom_vibratec_analysis_fails_static_gate_and_keeps_screening_warning():
    result = analyze_custom_isolator(
        _vibratec_a070146_061(),
        mass_kg=850.0,
        n_bottom=6,
        n_wall=4,
        shock_env=ENV,
    )

    assert result.validation_level == "screening_only"
    assert result.static_load_daN == pytest.approx((850.0 / 6) * 9.81 / 10)
    assert result.static_rating_daN == pytest.approx(34 * 0.981)
    assert result.static_ok is False
    assert result.passed is False
    assert result.verdict == "FAIL"
    assert any("vibration frequency" in warning for warning in result.warnings)
    assert any("static" in warning.lower() and "exceed" in warning.lower() for warning in result.warnings)


def test_custom_socitec_analysis_runs_as_screening_shock_load_deflection_data():
    result = analyze_custom_isolator(
        _socitec_cb1400_15(),
        mass_kg=850.0,
        n_bottom=6,
        n_wall=4,
        shock_env=ENV,
    )

    assert result.normalized.stiffness_source_comp == "derived_from_shock_load_deflection"
    assert result.normalized.stiffness_source_shear == "derived_from_shock_load_deflection"
    assert result.validation_level == "screening_only"
    assert len(result.report.directions) == 4
    assert any("shock load-deflection" in warning for warning in result.warnings)


def test_custom_analysis_rejects_missing_shear_before_running_physics():
    raw = CustomIsolatorInput(
        vendor="Vibratec",
        part_no="A070146-061",
        compression=DirectionInput(
            stiffness=StiffnessInput.rated_load_frequency(30, "kg", 10),
            max_dynamic_travel=32,
            travel_unit="mm",
        ),
        shear=None,
    )

    with pytest.raises(ValidationError, match="shear"):
        analyze_custom_isolator(raw, mass_kg=850.0, shock_env=ENV)


def test_custom_analysis_rejects_bad_mount_counts():
    with pytest.raises(ValidationError, match="n_bottom"):
        analyze_custom_isolator(_vmc_cb1400_15(), mass_kg=850.0, n_bottom=0, shock_env=ENV)

    with pytest.raises(ValidationError, match="mass_kg"):
        analyze_custom_isolator(_vmc_cb1400_15(), mass_kg=0, shock_env=ENV)
