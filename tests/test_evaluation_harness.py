"""Offline tests for the deterministic local-LLM evaluation harness."""

import json

from evaluation.harness.runner import completed_keys, load_cases, run_case
from evaluation.harness.systems import (
    SYSTEMS,
    SystemConfig,
    activated_system,
    build_evaluation_agent,
    get_system,
)
from evaluation.harness.verdict import parse_verdict_envelope
from evaluation.benchmark.generate_dev_pilot import build_cases
from evaluation.models.create_eval_models import EVAL_MODELS, PARAMETERS, _parse_parameters
from evaluation.scoring.metrics import score_run, summarize_scores, values_match
from evaluation.scoring.scorer import score_records


def _case(case_id="case_1", verdict="PASS", tool_calls=None, missing_inputs=None):
    return {
        "case_id": case_id,
        "domain": "shock_mount",
        "question": "fixture question",
        "gold": {
            "verdict": verdict,
            "tool_calls": tool_calls or [],
            "missing_inputs": missing_inputs or [],
            "required_chunk_ids": [],
        },
    }


def _run(case_id="case_1", verdict="PASS", tool_calls=None, repeat=1, error=None):
    return {
        "case_id": case_id,
        "system": "fixture",
        "repeat": repeat,
        "tool_calls": tool_calls or [],
        "envelope": {
            "verdict": verdict,
            "governing_check": None,
            "key_numbers": {},
            "units": {},
            "missing_inputs": [],
            "citations": [],
            "parse_error": None,
        },
        "latency_ms": 100.0,
        "error": error,
    }


def test_verdict_parser_handles_prose_fence_and_nested_objects():
    text = """Result follows.
```json
{
  "verdict": "pass",
  "governing_check": "Comp-Bottom",
  "key_numbers": {"GT": {"value": 6.2}},
  "units": {"GT": "G"},
  "missing_inputs": []
}
```
"""
    parsed = parse_verdict_envelope(text)
    assert parsed["verdict"] == "PASS"
    assert parsed["governing_check"] == "Comp-Bottom"
    assert parsed["key_numbers"]["GT"]["value"] == 6.2
    assert parsed["parse_error"] is None


def test_system_specific_tool_expectations_and_rag_metrics():
    case = _case(verdict=None, tool_calls=[])
    case["gold"]["tool_calls_by_system"] = {
        "B": [],
        "C": [{"name": "select_isolator", "args": {}, "tolerances": {}}],
        "D": [{"name": "lookup_knowledge", "args": {}, "tolerances": {}}],
    }
    case["gold"]["required_chunk_ids"] = ["shock_mount/selection_workflow"]
    run = _run(
        verdict=None,
        tool_calls=[{"name": "lookup_knowledge", "args": {}, "error": False}],
    )
    run["system"] = "D"
    run["retrieved_chunk_ids"] = ["shock_mount/selection_workflow"]
    run["envelope"]["citations"] = ["shock_mount/selection_workflow"]

    score = score_run(case, run)

    assert score["first_tool_correct"] is True
    assert score["sequence_correct"] is True
    assert score["retrieval_hit_at_3"] is True
    assert score["retrieval_recall_at_3"] == 1.0
    assert score["retrieval_mrr"] == 1.0
    assert score["citation_precision"] == 1.0
    assert score["citation_recall"] == 1.0
    assert score["citation_ids_are_retrieved"] is True


def test_verdict_parser_uses_last_verdict_object_and_aliases_missing_fields():
    text = (
        '{"verdict":"FAIL"}\n'
        'Final: {"verdict":"ASK","missing_fields":["mass_kg"]}'
    )
    parsed = parse_verdict_envelope(text)
    assert parsed["verdict"] == "ASK"
    assert parsed["missing_inputs"] == ["mass_kg"]


def test_verdict_parser_records_failure_instead_of_guessing():
    parsed = parse_verdict_envelope("The isolator probably passes.")
    assert parsed["verdict"] is None
    assert "No JSON object" in parsed["parse_error"]


def test_verdict_parser_accepts_null_for_information_only_question():
    parsed = parse_verdict_envelope(
        '{"verdict":null,"key_numbers":{},"units":{},"missing_inputs":[]}'
    )
    assert parsed["verdict"] is None
    assert parsed["parse_error"] is None


def test_numeric_argument_tolerance():
    tolerance = {"relative": 0.01, "absolute": 0.0}
    assert values_match(100.5, 100.0, tolerance)
    assert not values_match(102.0, 100.0, tolerance)
    assert not values_match("100", 100.0, tolerance)


def test_hand_computed_scoring_fixture():
    expected_call = {
        "name": "select_isolator",
        "args": {"mass_kg": 850, "n_bottom": 4},
        "tolerances": {},
    }
    actual_call = {
        "name": "select_isolator",
        "args": {"mass_kg": 850, "n_bottom": 4},
        "error": False,
    }
    fail_case = _case("fail_1", "FAIL", [expected_call])
    false_safe_run = _run("fail_1", "PASS", [actual_call])
    ask_case = _case("ask_1", "ASK", [], ["mass_kg"])
    ask_run = _run("ask_1", "ASK", [])
    ask_run["envelope"]["missing_inputs"] = ["mass_kg"]

    scores, summary = score_records(
        [fail_case, ask_case], [false_safe_run, ask_run]
    )

    assert scores[0]["false_safe"] is True
    assert scores[0]["first_tool_correct"] is True
    assert scores[1]["missing_input_correct"] is True
    assert summary["verdict_accuracy"]["successes"] == 1
    assert summary["verdict_accuracy"]["total"] == 2
    assert summary["false_safe"]["successes"] == 1
    assert summary["false_safe"]["total"] == 1
    assert summary["argument_accuracy"]["correct"] == 2
    assert summary["argument_accuracy"]["total"] == 2


def test_consistency_requires_repeated_valid_matching_verdicts():
    case = _case()
    scores = [
        score_run(case, _run(repeat=1)),
        score_run(case, _run(repeat=2)),
        score_run(case, _run(verdict="FAIL", repeat=3)),
    ]
    summary = summarize_scores(scores)
    assert summary["consistency"]["total"] == 1
    assert summary["consistency"]["successes"] == 0


def test_information_only_case_is_excluded_from_verdict_accuracy():
    case = _case(verdict=None, tool_calls=[{"name": "get_isolator_data", "args": {}}])
    run = _run(verdict=None, tool_calls=[{"name": "get_isolator_data", "args": {}, "error": False}])
    score = score_run(case, run)
    summary = summarize_scores([score])
    assert score["parseable"] is True
    assert score["verdict_correct"] is None
    assert summary["verdict_accuracy"]["total"] == 0
    assert summary["parseable_envelope"]["successes"] == 1


def test_case_loading_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "cases.jsonl"
    case = _case()
    path.write_text(
        json.dumps(case) + "\n" + json.dumps(case) + "\n", encoding="utf-8"
    )
    try:
        load_cases([str(path)])
    except ValueError as exc:
        assert "Duplicate case_id" in str(exc)
    else:
        raise AssertionError("duplicate case IDs should be rejected")


def test_resume_keys_are_read_from_existing_jsonl(tmp_path):
    path = tmp_path / "runs.jsonl"
    path.write_text(
        json.dumps({"case_id": "a", "system": "s", "repeat": 2}) + "\n",
        encoding="utf-8",
    )
    assert completed_keys(path) == {("a", "s", 2)}


def test_run_case_captures_tool_trace_and_verdict():
    class FakeAgent:
        def stream(self, question, chat_history=None):
            assert question.startswith("fixture question")
            assert "JSON verdict envelope" in question
            assert chat_history is None
            yield {
                "type": "tool_call",
                "name": "select_isolator",
                "args": {"mass_kg": 850},
                "id": "call-1",
            }
            yield {
                "type": "tool_result",
                "name": "select_isolator",
                "content": "Part CB1400-15 PASS",
                "id": "call-1",
            }
            yield {
                "type": "final",
                "content": '{"verdict":"PASS","missing_inputs":[]}',
            }

    record = run_case(FakeAgent(), _case(), "fixture", 1)
    assert record["tool_calls"][0]["name"] == "select_isolator"
    assert record["tool_calls"][0]["args"] == {"mass_kg": 850}
    assert record["tool_calls"][0]["result_text"] == "Part CB1400-15 PASS"
    assert record["tool_calls"][0]["error"] is False
    assert record["envelope"]["verdict"] == "PASS"
    assert "Evaluation requirement" in record["question_sent"]


def test_evaluation_agent_removes_rag_tool(monkeypatch):
    import agent

    class NamedTool:
        def __init__(self, name):
            self.name = name

    captured = {}

    class FakeDomainAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(
        agent.DOMAINS,
        "fixture_domain",
        {
            "prompt": "fixture prompt",
            "tools": [NamedTool("select_isolator"), NamedTool("lookup_knowledge")],
        },
    )
    monkeypatch.setattr(agent, "DomainAgent", FakeDomainAgent)
    config = SystemConfig(
        id="fixture", provider="ollama", model="fixture", tools=True, rag=False
    )
    build_evaluation_agent(config, "fixture_domain")

    assert [tool.name for tool in captured["tools"]] == ["select_isolator"]
    assert captured["domain"] == "fixture_domain"
    assert "RAG is disabled" in captured["system_prompt"]
    assert "EVALUATION OUTPUT CONTRACT" in captured["system_prompt"]
    assert "Never write \"null\" as a\nstring" in captured["system_prompt"]


def test_core_bcd_systems_change_only_tools_and_rag():
    core = [SYSTEMS[system_id] for system_id in ("B", "C", "D")]

    assert {config.model for config in core} == {"cad-eval-qwen35-9b:8k"}
    assert {config.provider for config in core} == {"ollama"}
    assert {config.context_length for config in core} == {8192}
    assert {config.temperature for config in core} == {0.0}
    assert {config.max_tokens for config in core} == {2048}
    assert {config.seed for config in core} == {42}
    assert {config.embedding_provider for config in core} == {"ollama"}
    assert {config.embedding_model for config in core} == {"bge-m3"}
    assert {config.knowledge_store_path for config in core} == {
        "artifacts/embedding_candidates/bge_m3.json"
    }
    assert {config.knowledge_max_chars_per_hit for config in core} == {1400}
    assert [(config.tools, config.rag) for config in core] == [
        (False, False),
        (True, False),
        (True, True),
    ]


def test_evaluation_agent_tool_free_baseline_bypasses_tool_guard(monkeypatch):
    import agent

    captured = {}

    class FakeDomainAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(
        agent.DOMAINS,
        "fixture_domain",
        {"prompt": "fixture prompt", "tools": [object()]},
    )
    monkeypatch.setattr(agent, "DomainAgent", FakeDomainAgent)
    config = SystemConfig(
        id="fixture", provider="ollama", model="fixture", tools=False, rag=False
    )
    build_evaluation_agent(config, "fixture_domain")

    assert captured["tools"] == []
    assert captured["domain"] == "evaluation_no_tools_fixture_domain"
    assert "No external tools are available" in captured["system_prompt"]
    assert "RAG is disabled" in captured["system_prompt"]
    assert "EVALUATION OUTPUT CONTRACT" in captured["system_prompt"]


def test_system_environment_restores_existing_values(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "before")
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    config = get_system("qwen35_9b")
    with activated_system(config):
        import os

        assert os.environ["LLM_PROVIDER"] == "ollama"
        assert os.environ["OLLAMA_MODEL"] == "cad-eval-qwen35-9b:8k"
        assert os.environ["LLM_TEMPERATURE"] == "0.0"
        assert os.environ["LLM_MAX_TOKENS"] == "2048"
        assert os.environ["LLM_SEED"] == "42"
        assert os.environ["LLM_REASONING_EFFORT"] == "none"
        assert os.environ["LLM_TOP_P"] == "0.95"
        assert os.environ["LLM_PRESENCE_PENALTY"] == "0.0"
        assert os.environ["EMBEDDING_PROVIDER"] == "ollama"
        assert os.environ["OLLAMA_EMBEDDING_MODEL"] == "bge-m3"
        assert os.environ["OLLAMA_EMBEDDING_BASE_URL"] == "http://127.0.0.1:11434"
        assert os.environ["KNOWLEDGE_STORE_PATH"] == "artifacts/embedding_candidates/bge_m3.json"
        assert os.environ["KNOWLEDGE_MAX_CHARS_PER_HIT"] == "1400"
    import os

    assert os.environ["LLM_PROVIDER"] == "before"
    assert "OLLAMA_MODEL" not in os.environ
    assert "EMBEDDING_PROVIDER" not in os.environ


def test_development_pilot_is_oracle_generated_and_well_formed():
    cases = build_cases()
    assert len(cases) == 10
    assert len({case["case_id"] for case in cases}) == 10
    assert {case["gold"]["verdict"] for case in cases} >= {"PASS", "FAIL", "ASK", None}
    assert any(len(case["gold"]["tool_calls"]) == 2 for case in cases)
    assert any(case["gold"]["missing_inputs"] == ["mass_kg"] for case in cases)
    static_fail = next(
        case for case in cases if case["case_id"] == "shock_dev_006_verify_static_fail"
    )
    assert static_fail["gold"]["verdict"] == "FAIL"
    assert static_fail["oracle"]["details"]["static_ok"] is False


def test_eval_model_aliases_share_frozen_context_parameters():
    assert len(EVAL_MODELS) == 3
    assert PARAMETERS == {
        "num_ctx": 8192,
        "temperature": 0.0,
        "seed": 42,
        "num_predict": 2048,
        "top_k": 20,
        "top_p": 0.95,
        "repeat_penalty": 1.0,
    }
    assert {model.base for model in EVAL_MODELS} == {
        "qwen3:14b",
        "qwen3.5:9b",
        "gemma4:12b",
    }


def test_ollama_parameter_parser_handles_aligned_columns():
    parsed = _parse_parameters(
        "seed                           42\n"
        "temperature                    0\n"
        "num_ctx                        8192\n"
    )
    assert parsed == {"seed": "42", "temperature": "0", "num_ctx": "8192"}
