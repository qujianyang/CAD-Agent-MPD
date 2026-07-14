from evaluation.benchmark.generate_final_shock_draft import _config_key, build_cases


def test_final_shock_draft_has_controlled_composition_and_system_gold():
    cases = build_cases()

    assert len(cases) == 170
    assert len({case["case_id"] for case in cases}) == 170
    assert len({case["question"] for case in cases}) == 170
    # Boundary status is computed after objective assignment; the 80 numeric
    # cases (not the duplicated categories) must carry >= 40 boundary configs.
    assert sum(case["boundary_band"] for case in cases[:80]) >= 40
    assert sum(case["category"] == "reference" for case in cases) == 30
    assert sum(case["category"] == "missing_input" for case in cases) == 20
    # v0.2: four adversarial families of five cases each.
    adversarial = [case for case in cases if case["category"].startswith("adversarial_")]
    assert len(adversarial) == 20
    assert {case["category"] for case in adversarial} == {
        "adversarial_missing_mass",
        "adversarial_assumed_mass",
        "adversarial_conflicting_mass",
        "adversarial_invalid_value",
    }
    # v0.2: selection FAIL (no catalogue part passes) must be represented.
    assert sum(
        case["category"] == "selection" and case["gold"]["verdict"] == "FAIL"
        for case in cases
    ) >= 5
    # v0.2: no configuration may be reused across tool-calling categories.
    tool_configs = [
        _config_key(case["provided_inputs"])
        for case in cases
        if case["category"] in {"selection", "verification", "unit_conversion", "multi_tool"}
    ]
    assert len(tool_configs) == len(set(tool_configs))
    for case in cases:
        by_system = case["gold"]["tool_calls_by_system"]
        assert set(by_system) == {"B", "C", "D"}
        assert by_system["B"] == []
    assert all(
        "mass_kg" not in case["provided_inputs"]
        for case in cases
        if case["category"] == "unit_conversion"
    )
    # Reference gold chunk IDs must exist in the frozen corpus.
    from pathlib import Path

    for case in cases:
        for chunk_id in case["gold"]["required_chunk_ids"]:
            assert (Path("knowledge") / f"{chunk_id}.md").exists(), chunk_id
