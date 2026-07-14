"""Offline checks for the model/interface freeze manifest."""

from evaluation.freeze_model_interface import build_manifest


def test_manifest_captures_identical_core_model_settings():
    manifest = build_manifest(
        "http://localhost:11434/v1",
        verify_ollama=False,
    )

    core = manifest["core_systems"]
    assert {record["model"] for record in core.values()} == {
        "cad-eval-qwen35-9b:8k"
    }
    assert [(core[key]["tools"], core[key]["rag"]) for key in "BCD"] == [
        (False, False),
        (True, False),
        (True, True),
    ]
    assert manifest["ollama"] == {"verification": "skipped"}
    assert len(manifest["manifest_content_sha256"]) == 64


def test_manifest_captures_engineering_domains_and_tool_schemas():
    manifest = build_manifest(
        "http://localhost:11434/v1",
        verify_ollama=False,
    )

    assert set(manifest["domains"]) == {"shock_mount", "tiedown", "mobility"}
    for domain in manifest["domains"].values():
        assert len(domain["prompt_sha256"]) == 64
        assert len(domain["tool_schema_sha256"]) == 64
        assert domain["tools"]
        assert all(tool["name"] for tool in domain["tools"])
