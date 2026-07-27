from pathlib import Path

from setup_knowledge import collect_chunks


def test_shock_topic_filter_collects_only_shock_chunks(tmp_path: Path):
    (tmp_path / "shock_mount").mkdir()
    (tmp_path / "mobility").mkdir()
    (tmp_path / "shock_mount" / "basis.md").write_text("# Shock basis", encoding="utf-8")
    (tmp_path / "mobility" / "guide.md").write_text("# Mobility guide", encoding="utf-8")

    chunks = collect_chunks(tmp_path, topic="shock_mount")

    assert [chunk["id"] for chunk in chunks] == ["shock_mount/basis"]
    assert chunks[0]["title"] == "Shock basis"


def test_vendor_evidence_chunks_keep_source_boundaries():
    knowledge_dir = Path(__file__).parents[1] / "knowledge"
    chunks = {
        chunk["id"]: chunk
        for chunk in collect_chunks(knowledge_dir, topic="shock_mount")
    }

    expected_ids = {
        "shock_mount/vendor_source_register",
        "shock_mount/socitec_cb1390_construction",
        "shock_mount/socitec_cb1390_performance",
        "shock_mount/vendor_cb1390_hh14_cases",
        "shock_mount/vendor_cb1400_cases",
        "shock_mount/vendor_nonlinear_model_boundary",
        "shock_mount/vendor_effective_configuration_count",
        "shock_mount/installation_acceptance_workflow",
        "shock_mount/shock_vibration_separation",
        "shock_mount/supplier_data_requirements",
    }
    assert expected_ids <= chunks.keys()

    source_register = chunks["shock_mount/vendor_source_register"]["content"]
    assert "not a physical test report" in source_register
    assert "No physical laboratory qualification report" in source_register

    installation = chunks[
        "shock_mount/installation_acceptance_workflow"
    ]["content"]
    assert "must not infer mount count" in installation

    vibration = chunks[
        "shock_mount/shock_vibration_separation"
    ]["content"]
    assert "Does Not Prove Random-Vibration Compliance" in vibration
    assert "40-minute" in vibration

    effective_count = chunks[
        "shock_mount/vendor_effective_configuration_count"
    ]["content"]
    assert "Never enter `4.66` or `6.66`" in effective_count
