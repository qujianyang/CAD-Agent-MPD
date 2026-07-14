"""Pure deterministic metrics for local-LLM evaluation."""

from __future__ import annotations

from collections import defaultdict
import math
from numbers import Real
from typing import Any, Iterable


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float | None]:
    if total <= 0:
        return [None, None]
    p = successes / total
    denominator = 1 + (z * z / total)
    center = (p + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt((p * (1 - p) / total) + (z * z / (4 * total * total)))
        / denominator
    )
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _rate(values: Iterable[bool | None]) -> dict[str, Any]:
    observed = [value for value in values if value is not None]
    successes = sum(bool(value) for value in observed)
    total = len(observed)
    return {
        "successes": successes,
        "total": total,
        "rate": successes / total if total else None,
        "wilson_95": wilson_interval(successes, total),
    }


def _mean(values: Iterable[float | None]) -> dict[str, Any]:
    observed = [float(value) for value in values if value is not None]
    return {
        "total": len(observed),
        "mean": sum(observed) / len(observed) if observed else None,
    }


def _percentile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * proportion
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def values_match(actual: Any, expected: Any, tolerance: dict[str, Any] | None = None) -> bool:
    tolerance = tolerance or {}
    if isinstance(expected, Real) and not isinstance(expected, bool):
        if not isinstance(actual, Real) or isinstance(actual, bool):
            return False
        absolute = float(tolerance.get("absolute", 0.0))
        relative = float(tolerance.get("relative", 0.0))
        allowed = max(absolute, abs(float(expected)) * relative)
        return abs(float(actual) - float(expected)) <= allowed
    return actual == expected


def score_run(case: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    gold = case.get("gold", {})
    expected_verdict = gold.get("verdict")
    envelope = run.get("envelope") or {}
    predicted_verdict = envelope.get("verdict")
    parseable = predicted_verdict in {"PASS", "FAIL", "ASK", None} and not envelope.get(
        "parse_error"
    )
    verdict_scorable = expected_verdict in {"PASS", "FAIL", "ASK"}

    calls_by_system = gold.get("tool_calls_by_system", {})
    if calls_by_system:
        expected_calls = calls_by_system.get(str(run.get("system", "")), gold.get("tool_calls", []))
    else:
        expected_calls = gold.get("tool_calls", [])
    actual_calls = run.get("tool_calls", [])
    expected_names = [call.get("name") for call in expected_calls]
    actual_names = [call.get("name") for call in actual_calls]

    if expected_names:
        first_tool_correct: bool | None = bool(actual_names) and (
            actual_names[0] == expected_names[0]
        )
    else:
        first_tool_correct = not actual_names
    sequence_correct = actual_names == expected_names

    expected_arg_count = 0
    correct_arg_count = 0
    extra_arg_count = 0
    for index, expected_call in enumerate(expected_calls):
        expected_args = expected_call.get("args", {})
        tolerances = expected_call.get("tolerances", {})
        expected_arg_count += len(expected_args)
        actual_args: dict[str, Any] = {}
        if index < len(actual_calls) and actual_calls[index].get("name") == expected_call.get("name"):
            candidate_args = actual_calls[index].get("args", {})
            if isinstance(candidate_args, dict):
                actual_args = candidate_args
        for name, expected_value in expected_args.items():
            if name in actual_args and values_match(
                actual_args[name], expected_value, tolerances.get(name)
            ):
                correct_arg_count += 1
        extra_arg_count += len(set(actual_args) - set(expected_args))

    expected_missing = set(gold.get("missing_inputs", []))
    actual_missing = set(envelope.get("missing_inputs", []))
    missing_input_correct: bool | None = None
    if expected_verdict == "ASK":
        missing_input_correct = predicted_verdict == "ASK" and actual_missing == expected_missing

    tool_error_count = sum(call.get("error") is True for call in actual_calls)
    expected_call_count = len(expected_calls)
    valid_schema: bool | None
    if expected_call_count:
        valid_schema = (
            len(actual_calls) >= expected_call_count
            and tool_error_count == 0
            and all(isinstance(call.get("args"), dict) for call in actual_calls)
        )
    else:
        valid_schema = not actual_calls

    required_chunk_ids = set(gold.get("required_chunk_ids", []))
    retrieved_chunk_ids = list(dict.fromkeys(run.get("retrieved_chunk_ids", [])))
    citations = list(dict.fromkeys(envelope.get("citations", [])))
    rag_scorable = bool(required_chunk_ids) and str(run.get("system", "")) == "D"
    retrieved_hits = set(retrieved_chunk_ids) & required_chunk_ids
    citation_hits = set(citations) & required_chunk_ids
    reciprocal_rank: float | None = None
    if rag_scorable:
        for rank, chunk_id in enumerate(retrieved_chunk_ids, 1):
            if chunk_id in required_chunk_ids:
                reciprocal_rank = 1.0 / rank
                break
        if reciprocal_rank is None:
            reciprocal_rank = 0.0

    return {
        "case_id": str(case["case_id"]),
        "system": str(run.get("system", "")),
        "repeat": int(run.get("repeat", 0)),
        "gold_verdict": expected_verdict,
        "predicted_verdict": predicted_verdict,
        "parseable": parseable,
        "verdict_correct": (
            parseable and predicted_verdict == expected_verdict
            if verdict_scorable
            else None
        ),
        "false_safe": expected_verdict == "FAIL" and predicted_verdict == "PASS",
        "false_fail": expected_verdict == "PASS" and predicted_verdict == "FAIL",
        "first_tool_correct": first_tool_correct,
        "sequence_correct": sequence_correct,
        "expected_arg_count": expected_arg_count,
        "correct_arg_count": correct_arg_count,
        "extra_arg_count": extra_arg_count,
        "argument_accuracy": (
            correct_arg_count / expected_arg_count if expected_arg_count else None
        ),
        "valid_schema": valid_schema,
        "missing_input_correct": missing_input_correct,
        "tool_error_count": tool_error_count,
        "retrieval_hit_at_3": bool(retrieved_hits) if rag_scorable else None,
        "retrieval_recall_at_3": (
            len(retrieved_hits) / len(required_chunk_ids) if rag_scorable else None
        ),
        "retrieval_mrr": reciprocal_rank,
        "citation_precision": (
            len(citation_hits) / len(citations) if rag_scorable and citations else 0.0
            if rag_scorable
            else None
        ),
        "citation_recall": (
            len(citation_hits) / len(required_chunk_ids) if rag_scorable else None
        ),
        "citation_ids_are_retrieved": (
            bool(citations) and set(citations).issubset(set(retrieved_chunk_ids))
            if rag_scorable
            else None
        ),
        "latency_ms": run.get("latency_ms"),
        "hard_failure": bool(run.get("error")),
    }


def summarize_scores(scores: list[dict[str, Any]]) -> dict[str, Any]:
    expected_args = sum(score["expected_arg_count"] for score in scores)
    correct_args = sum(score["correct_arg_count"] for score in scores)
    latencies = [
        float(score["latency_ms"])
        for score in scores
        if isinstance(score.get("latency_ms"), Real)
    ]

    false_safe_values = [
        score["false_safe"] if score["gold_verdict"] == "FAIL" else None
        for score in scores
    ]
    # False-safe is an error rate, so expose both the error count/rate and its CI.
    false_safe_rate = _rate(false_safe_values)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for score in scores:
        grouped[(score["system"], score["case_id"])].append(score)
    consistency_values: list[bool] = []
    for group in grouped.values():
        if len(group) < 2:
            continue
        if group[0]["gold_verdict"] not in {"PASS", "FAIL", "ASK"}:
            continue
        verdicts = [item["predicted_verdict"] for item in group]
        consistency_values.append(
            all(verdict in {"PASS", "FAIL", "ASK"} for verdict in verdicts)
            and len(set(verdicts)) == 1
        )

    return {
        "runs": len(scores),
        "verdict_accuracy": _rate(score["verdict_correct"] for score in scores),
        "false_safe": false_safe_rate,
        "false_fail": _rate(
            score["false_fail"] if score["gold_verdict"] == "PASS" else None
            for score in scores
        ),
        "parseable_envelope": _rate(score["parseable"] for score in scores),
        "first_tool_accuracy": _rate(score["first_tool_correct"] for score in scores),
        "tool_sequence_accuracy": _rate(score["sequence_correct"] for score in scores),
        "valid_schema": _rate(score["valid_schema"] for score in scores),
        "missing_input_accuracy": _rate(
            score["missing_input_correct"] for score in scores
        ),
        "retrieval_hit_at_3": _rate(score["retrieval_hit_at_3"] for score in scores),
        "retrieval_recall_at_3": _mean(score["retrieval_recall_at_3"] for score in scores),
        "retrieval_mrr": _mean(score["retrieval_mrr"] for score in scores),
        "citation_precision": _mean(score["citation_precision"] for score in scores),
        "citation_recall": _mean(score["citation_recall"] for score in scores),
        "citation_ids_are_retrieved": _rate(
            score["citation_ids_are_retrieved"] for score in scores
        ),
        "argument_accuracy": {
            "correct": correct_args,
            "total": expected_args,
            "rate": correct_args / expected_args if expected_args else None,
            "wilson_95": wilson_interval(correct_args, expected_args),
        },
        "consistency": _rate(consistency_values),
        "hard_failure": _rate(score["hard_failure"] for score in scores),
        "latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
        },
    }
