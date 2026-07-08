import math

import pytest

from custom_isolator import (
    CustomIsolatorInput,
    DirectionInput,
    StiffnessInput,
    ValidationError,
    normalize_custom_isolator,
)


def test_normalizes_vmc_direct_shock_stiffness_to_isolator_spec():
    raw = CustomIsolatorInput(
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

    normalized = normalize_custom_isolator(raw)

    assert normalized.spec.name == "VMC CB1400-15"
    assert normalized.spec.k_comp_Nm == pytest.approx(2650 * 175.1268)
    assert normalized.spec.k_shear_Nm == pytest.approx(1080 * 175.1268)
    assert normalized.spec.d_max_comp_mm == pytest.approx(35.56)
    assert normalized.spec.d_max_shear_mm == pytest.approx(40.64)
    assert normalized.spec.max_static_comp_daN == pytest.approx(416)
    assert normalized.stiffness_source_comp == "published_shock_k"
    assert normalized.stiffness_source_shear == "published_shock_k"
    assert normalized.validation_level == "validated"
    assert normalized.warnings == ()


def test_derives_vibratec_stiffness_from_rated_load_and_frequency():
    raw = CustomIsolatorInput(
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

    normalized = normalize_custom_isolator(raw)

    assert normalized.spec.name == "Vibratec A070146-061"
    assert normalized.spec.k_comp_Nm == pytest.approx(30 * (2 * math.pi * 10) ** 2)
    assert normalized.spec.k_shear_Nm == pytest.approx(6 * (2 * math.pi * 10) ** 2)
    assert normalized.spec.d_max_comp_mm == pytest.approx(32)
    assert normalized.spec.d_max_shear_mm == pytest.approx(37)
    assert normalized.spec.max_static_comp_daN == pytest.approx(34 * 0.981)
    assert normalized.stiffness_source_comp == "derived_from_vibration_frequency"
    assert normalized.stiffness_source_shear == "derived_from_vibration_frequency"
    assert normalized.validation_level == "screening_only"
    assert any("vibration frequency" in warning for warning in normalized.warnings)


def test_derives_socitec_stiffness_from_shock_force_deflection_pair():
    raw = CustomIsolatorInput(
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

    normalized = normalize_custom_isolator(raw)

    assert normalized.spec.k_comp_Nm == pytest.approx((1253 * 10) / 0.037)
    assert normalized.spec.k_shear_Nm == pytest.approx((1100 * 10) / 0.035)
    assert normalized.stiffness_source_comp == "derived_from_shock_load_deflection"
    assert normalized.stiffness_source_shear == "derived_from_shock_load_deflection"
    assert normalized.validation_level == "screening_only"
    assert any("shock load-deflection" in warning for warning in normalized.warnings)


def test_rejects_missing_shear_data_before_physics_can_run():
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
        normalize_custom_isolator(raw)


def test_rejects_invalid_frequency_and_unknown_units():
    with pytest.raises(ValidationError, match="frequency_hz"):
        StiffnessInput.rated_load_frequency(30, "kg", 0)

    raw = CustomIsolatorInput(
        vendor="Vendor",
        part_no="Part",
        compression=DirectionInput(
            stiffness=StiffnessInput.direct_k(10, "banana"),
            max_dynamic_travel=10,
            travel_unit="mm",
        ),
        shear=DirectionInput(
            stiffness=StiffnessInput.direct_k(10, "N/mm"),
            max_dynamic_travel=10,
            travel_unit="mm",
        ),
    )

    with pytest.raises(ValidationError, match="stiffness unit"):
        normalize_custom_isolator(raw)
