from pathlib import Path

from evaluation.harness.runner import load_cases


def test_rag_development_pilot_is_reference_only_and_uses_stable_chunk_ids():
    cases = load_cases([str(Path("evaluation/benchmark/rag_dev_pilot.jsonl"))])

    assert len(cases) == 4
    assert {case["gold"]["verdict"] for case in cases} == {None}
    assert all(case["gold"]["tool_calls"][0]["name"] == "lookup_knowledge" for case in cases)
    assert all(
        chunk_id.startswith("shock_mount/")
        for case in cases
        for chunk_id in case["gold"]["required_chunk_ids"]
    )
