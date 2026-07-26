import json

from catalog import AUTO_SELECT_CATALOGS, select_and_analyze
from custom_isolator import CustomIsolatorInput, DirectionInput, StiffnessInput
from custom_isolator_analysis import analyze_custom_isolator
from physics_engine import ShockEnv
from shock_analysis_context import (
    analysis_id_for_key,
    build_custom_snapshot,
    build_runtime_context,
    build_selection_snapshot,
)


ENV = ShockEnv(Ao_G=20.0, to_s=0.011, GT_limit_G=10.0)


def test_catalog_snapshot_captures_authoritative_result_and_alternatives():
    report, candidates = select_and_analyze(
        850.0,
        6,
        4,
        shock_env=ENV,
        catalog=AUTO_SELECT_CATALOGS,
    )

    snapshot = build_selection_snapshot(
        report,
        candidates,
        analysis_key=("auto", 850.0, 6, 4, 20.0, 0.011),
    )

    assert snapshot.analysis_id.startswith("S-")
    assert snapshot.verdict == "PASS"
    assert snapshot.selected_part
    assert snapshot.mass_kg == 850.0
    assert snapshot.bottom_mounts == 6
    assert snapshot.wall_mounts == 4
    assert len(snapshot.load_cases) == 4
    assert snapshot.governing_case
    assert snapshot.worst_transmitted_g > 0
    assert snapshot.worst_movement_mm > 0
    assert len(snapshot.alternatives) == 3


def test_analysis_id_is_stable_for_same_inputs_and_changes_with_inputs():
    key = ("auto", 850.0, 6, 4)
    assert analysis_id_for_key(key) == analysis_id_for_key(key)
    assert analysis_id_for_key(key) != analysis_id_for_key(("auto", 900.0, 6, 4))


def test_current_runtime_context_contains_json_but_stale_context_hides_results():
    report, candidates = select_and_analyze(
        850.0,
        6,
        4,
        shock_env=ENV,
        catalog=AUTO_SELECT_CATALOGS,
    )
    snapshot = build_selection_snapshot(
        report,
        candidates,
        analysis_key=("auto", 850.0, 6, 4),
    )

    current = build_runtime_context(snapshot, state="current")
    payload_text = current[current.index("{"):]
    payload = json.loads(payload_text)
    assert payload["analysis_id"] == snapshot.analysis_id
    assert payload["selected_part"] == snapshot.selected_part
    assert str(snapshot.worst_transmitted_g) in current

    stale = build_runtime_context(snapshot, state="stale")
    assert snapshot.analysis_id in stale
    assert snapshot.selected_part not in stale
    assert str(snapshot.worst_transmitted_g) not in stale
    assert "rerun" in stale.lower()


def test_custom_snapshot_keeps_validation_level_and_vendor_warnings():
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
    result = analyze_custom_isolator(
        raw,
        mass_kg=850.0,
        n_bottom=6,
        n_wall=4,
        shock_env=ENV,
    )

    snapshot = build_custom_snapshot(
        result,
        analysis_key=("custom", raw, 850.0, 6, 4),
    )

    assert snapshot.mode == "custom_vendor"
    assert snapshot.selected_part == "Vibratec A070146-061"
    assert snapshot.validation_level == "screening_only"
    assert snapshot.verdict == "FAIL"
    assert any("vibration frequency" in warning for warning in snapshot.warnings)
    assert len(snapshot.load_cases) == 4
