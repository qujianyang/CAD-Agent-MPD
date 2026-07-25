from evaluation.scoring.formal_analysis import (
    aggregate_case,
    build_analysis,
    exact_mcnemar_p,
    strict_majority,
    verdict_label,
)


def _case(case_id, verdict, calls_by_system=None, category="fixture", boundary=False):
    calls_by_system = calls_by_system or {"B": [], "C": [], "D": []}
    return {
        "case_id": case_id,
        "category": category,
        "boundary_band": boundary,
        "safety_critical": verdict is not None,
        "gold": {
            "verdict": verdict,
            "tool_calls": calls_by_system.get("D", []),
            "tool_calls_by_system": calls_by_system,
            "missing_inputs": ["mass_kg"] if verdict == "ASK" else [],
            "required_chunk_ids": [],
        },
    }


def _run(case_id, system, repeat, verdict, calls=None, missing=None, error=None):
    return {
        "case_id": case_id,
        "system": system,
        "repeat": repeat,
        "tool_calls": calls or [],
        "retrieved_chunk_ids": [],
        "envelope": {
            "verdict": verdict,
            "missing_inputs": missing or [],
            "citations": [],
            "parse_error": None,
        },
        "latency_ms": 100.0 + repeat,
        "error": error,
    }


def test_verdict_labels_and_strict_majority():
    assert verdict_label(_run("x", "C", 1, "PASS")) == "PASS"
    assert verdict_label(_run("x", "C", 1, None)) == "NULL"
    assert verdict_label(_run("x", "C", 1, "PASS", error="boom")) == "INVALID"
    assert strict_majority(["PASS", "PASS", "FAIL"]) == "PASS"
    assert strict_majority(["PASS", "FAIL", "ASK"]) == "NO_MAJORITY"


def test_aggregate_case_uses_majority_and_missing_field_majority():
    case = _case("ask", "ASK")
    runs = [
        _run("ask", "C", 1, "ASK", missing=["mass_kg"]),
        _run("ask", "C", 2, "ASK", missing=["mass_kg"]),
        _run("ask", "C", 3, "PASS"),
    ]
    result = aggregate_case(case, runs, "C")
    assert result["majority_verdict"] == "ASK"
    assert result["majority_correct"] is True
    assert result["missing_inputs_correct"] is True
    assert result["unanimous"] is False


def test_aggregate_case_does_not_count_repeated_invalid_outputs_as_consistent():
    case = _case("invalid", "PASS")
    runs = [
        _run("invalid", "C", 1, None),
        _run("invalid", "C", 2, None),
        _run("invalid", "C", 3, None),
    ]
    for run in runs:
        run["error"] = "fixture parse failure"

    result = aggregate_case(case, runs, "C")

    assert result["majority_verdict"] == "INVALID"
    assert result["unanimous"] is False


def test_exact_mcnemar_known_values():
    assert exact_mcnemar_p(0, 0) == 1.0
    assert exact_mcnemar_p(10, 0) == 0.001953125
    assert exact_mcnemar_p(3, 3) == 1.0


def test_build_analysis_separates_required_tools_from_abstention():
    tool_call = {"name": "select_isolator", "args": {"mass_kg": 850}, "tolerances": {}}
    cases = [
        _case("tool", "PASS", {"B": [], "C": [tool_call], "D": [tool_call]}),
        _case("ask", "ASK"),
    ]
    runs = {
        "C": [
            _run(
                "tool",
                "C",
                repeat,
                "PASS",
                calls=[{"name": "select_isolator", "args": {"mass_kg": 850}, "error": False}],
            )
            for repeat in (1, 2, 3)
        ]
        + [
            _run("ask", "C", repeat, "ASK", missing=["mass_kg"])
            for repeat in (1, 2, 3)
        ]
    }
    result = build_analysis(cases, runs)["systems"]["C"]
    assert result["tool_use"]["tool_required_runs"] == 3
    assert result["tool_use"]["first_tool_accuracy"]["rate"] == 1.0
    assert result["tool_use"]["no_tool_expected_runs"] == 3
    assert result["tool_use"]["abstention_accuracy"]["rate"] == 1.0
    assert result["case_level"]["ask"]["precision"] == 1.0
    assert result["case_level"]["ask"]["recall"] == 1.0


def test_paired_comparison_uses_cases_not_repeats():
    cases = [_case("one", "PASS"), _case("two", "FAIL")]
    b_runs = []
    c_runs = []
    for repeat in (1, 2, 3):
        b_runs.append(_run("one", "B", repeat, "ASK"))
        b_runs.append(_run("two", "B", repeat, "FAIL"))
        c_runs.append(_run("one", "C", repeat, "PASS"))
        c_runs.append(_run("two", "C", repeat, "ASK"))
    analysis = build_analysis(cases, {"B": b_runs, "C": c_runs})
    comparison = analysis["comparisons"]["B_to_C"]
    assert comparison["decision_cases"] == 2
    assert comparison["first_only_correct"] == 1
    assert comparison["second_only_correct"] == 1
    assert comparison["exact_mcnemar_p"] == 1.0
