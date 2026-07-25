r"""Formal case-level analysis for the frozen B/C/D shock-mount study.

This module is deliberately additive. It reads frozen benchmark and raw JSONL
records, then produces case-majority statistics without modifying the runner,
scorer, benchmark, or raw results.

Example:
    .\mpd\Scripts\python.exe -m evaluation.scoring.formal_analysis `
      --cases evaluation/benchmark/final_shock_draft_v0.jsonl `
      --run B=evaluation/runs/B_shock_final_v1.jsonl `
      --run C=evaluation/runs/C_shock_final_v1.jsonl `
      --run D=evaluation/runs/D_shock_final_v1.jsonl `
      --out-json evaluation/results/BCD_shock_final_v1_formal.json `
      --out-md evaluation/results/BCD_shock_final_v1_report.md
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from numbers import Real
from pathlib import Path
from typing import Any, Iterable

from evaluation.harness.runner import _read_jsonl, load_cases
from evaluation.scoring.metrics import score_run, summarize_scores, wilson_interval


DECISION_VERDICTS = ("PASS", "FAIL", "ASK")
CONFUSION_LABELS = ("PASS", "FAIL", "ASK", "NULL", "INVALID", "NO_MAJORITY")


def rate(successes: int, total: int) -> dict[str, Any]:
    return {
        "successes": successes,
        "total": total,
        "rate": successes / total if total else None,
        "wilson_95": wilson_interval(successes, total),
    }


def mean(values: Iterable[float | None]) -> dict[str, Any]:
    observed = [float(value) for value in values if value is not None]
    return {
        "total": len(observed),
        "mean": sum(observed) / len(observed) if observed else None,
    }


def percentile(values: Iterable[float], proportion: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * proportion
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def expected_calls(case: dict[str, Any], system: str) -> list[dict[str, Any]]:
    gold = case.get("gold", {})
    by_system = gold.get("tool_calls_by_system", {})
    if by_system:
        return list(by_system.get(system, gold.get("tool_calls", [])))
    return list(gold.get("tool_calls", []))


def verdict_label(run: dict[str, Any]) -> str:
    if run.get("error"):
        return "INVALID"
    envelope = run.get("envelope") or {}
    if envelope.get("parse_error"):
        return "INVALID"
    verdict = envelope.get("verdict")
    if verdict in DECISION_VERDICTS:
        return str(verdict)
    if verdict is None:
        return "NULL"
    return "INVALID"


def strict_majority(labels: Iterable[str]) -> str:
    values = list(labels)
    if not values:
        return "NO_MAJORITY"
    label, count = Counter(values).most_common(1)[0]
    return label if count > len(values) / 2 else "NO_MAJORITY"


def exact_mcnemar_p(first_only_correct: int, second_only_correct: int) -> float:
    """Two-sided exact McNemar p-value using the binomial distribution."""
    discordant = first_only_correct + second_only_correct
    if discordant == 0:
        return 1.0
    tail = min(first_only_correct, second_only_correct)
    probability = sum(math.comb(discordant, index) for index in range(tail + 1))
    probability /= 2**discordant
    return min(1.0, 2.0 * probability)


def _majority_missing_inputs(runs: list[dict[str, Any]]) -> tuple[str, ...] | None:
    observed: list[tuple[str, ...]] = []
    for run in runs:
        if run.get("error"):
            observed.append(("__INVALID__",))
            continue
        envelope = run.get("envelope") or {}
        if envelope.get("parse_error"):
            observed.append(("__INVALID__",))
            continue
        values = envelope.get("missing_inputs", [])
        if not isinstance(values, list):
            observed.append(("__INVALID__",))
            continue
        observed.append(tuple(sorted(str(value) for value in values)))
    if not observed:
        return None
    value, count = Counter(observed).most_common(1)[0]
    return value if count > len(observed) / 2 else None


def aggregate_case(
    case: dict[str, Any], runs: list[dict[str, Any]], system: str
) -> dict[str, Any]:
    labels = [verdict_label(run) for run in runs]
    majority = strict_majority(labels)
    gold = case.get("gold", {})
    gold_verdict = gold.get("verdict")
    decision = gold_verdict in DECISION_VERDICTS
    majority_missing = _majority_missing_inputs(runs)
    expected_missing = tuple(sorted(str(value) for value in gold.get("missing_inputs", [])))
    return {
        "case_id": str(case["case_id"]),
        "system": system,
        "category": str(case.get("category", "")),
        "boundary_band": bool(case.get("boundary_band")),
        "safety_critical": bool(case.get("safety_critical")),
        "gold_verdict": gold_verdict,
        "repeat_labels": labels,
        "majority_verdict": majority,
        # Consistency is only meaningful when every repeat produced a valid verdict.
        # Three identical parse failures must not count as reliable behaviour.
        "unanimous": (
            all(label in DECISION_VERDICTS for label in labels)
            and len(set(labels)) == 1
        ),
        "majority_correct": majority == gold_verdict if decision else None,
        "false_safe": gold_verdict == "FAIL" and majority == "PASS",
        "false_fail": gold_verdict == "PASS" and majority == "FAIL",
        "missing_inputs_majority": list(majority_missing) if majority_missing else None,
        "missing_inputs_correct": (
            majority == "ASK" and majority_missing == expected_missing
            if gold_verdict == "ASK"
            else None
        ),
    }


def _tool_metrics(
    cases_by_id: dict[str, dict[str, Any]],
    runs: list[dict[str, Any]],
    scores: list[dict[str, Any]],
    system: str,
) -> dict[str, Any]:
    required_first: list[bool] = []
    required_sequence: list[bool] = []
    required_schema: list[bool] = []
    abstentions: list[bool] = []
    expected_args = 0
    correct_args = 0
    required_by_category: dict[str, list[bool]] = defaultdict(list)
    abstention_by_category: dict[str, list[bool]] = defaultdict(list)

    for run, score in zip(runs, scores):
        case = cases_by_id[str(run["case_id"])]
        calls = expected_calls(case, system)
        category = str(case.get("category", ""))
        if calls:
            required_first.append(bool(score["first_tool_correct"]))
            required_sequence.append(bool(score["sequence_correct"]))
            required_schema.append(bool(score["valid_schema"]))
            required_by_category[category].append(bool(score["first_tool_correct"]))
            expected_args += int(score["expected_arg_count"])
            correct_args += int(score["correct_arg_count"])
        else:
            correct = not run.get("tool_calls", [])
            abstentions.append(correct)
            abstention_by_category[category].append(correct)

    def from_values(values: list[bool]) -> dict[str, Any]:
        return rate(sum(values), len(values))

    return {
        "tool_required_runs": len(required_first),
        "first_tool_accuracy": from_values(required_first),
        "sequence_accuracy": from_values(required_sequence),
        "valid_schema_rate": from_values(required_schema),
        "argument_accuracy": {
            "correct": correct_args,
            "total": expected_args,
            "rate": correct_args / expected_args if expected_args else None,
            "wilson_95": wilson_interval(correct_args, expected_args),
        },
        "no_tool_expected_runs": len(abstentions),
        "abstention_accuracy": from_values(abstentions),
        "first_tool_by_category": {
            category: from_values(values)
            for category, values in sorted(required_by_category.items())
        },
        "abstention_by_category": {
            category: from_values(values)
            for category, values in sorted(abstention_by_category.items())
        },
    }


def _case_level_metrics(case_records: list[dict[str, Any]]) -> dict[str, Any]:
    decisions = [record for record in case_records if record["gold_verdict"] in DECISION_VERDICTS]
    fails = [record for record in decisions if record["gold_verdict"] == "FAIL"]
    passes = [record for record in decisions if record["gold_verdict"] == "PASS"]
    asks = [record for record in decisions if record["gold_verdict"] == "ASK"]

    confusion = {
        gold: {predicted: 0 for predicted in CONFUSION_LABELS}
        for gold in DECISION_VERDICTS
    }
    for record in decisions:
        confusion[str(record["gold_verdict"])][record["majority_verdict"]] += 1

    predicted_asks = [record for record in decisions if record["majority_verdict"] == "ASK"]
    ask_tp = sum(record["gold_verdict"] == "ASK" for record in predicted_asks)
    ask_precision = ask_tp / len(predicted_asks) if predicted_asks else None
    ask_recall = ask_tp / len(asks) if asks else None
    ask_f1 = (
        2 * ask_precision * ask_recall / (ask_precision + ask_recall)
        if ask_precision is not None and ask_recall is not None and ask_precision + ask_recall
        else None
    )

    by_category: dict[str, dict[str, Any]] = {}
    for category in sorted({record["category"] for record in decisions}):
        group = [record for record in decisions if record["category"] == category]
        group_fails = [record for record in group if record["gold_verdict"] == "FAIL"]
        by_category[category] = {
            "verdict_accuracy": rate(
                sum(bool(record["majority_correct"]) for record in group), len(group)
            ),
            "false_safe": rate(
                sum(bool(record["false_safe"]) for record in group_fails), len(group_fails)
            ),
        }

    boundary: dict[str, Any] = {}
    for label, is_boundary in (("boundary", True), ("non_boundary", False)):
        group = [record for record in decisions if record["boundary_band"] is is_boundary]
        group_fails = [record for record in group if record["gold_verdict"] == "FAIL"]
        boundary[label] = {
            "decision_cases": len(group),
            "verdict_accuracy": rate(
                sum(bool(record["majority_correct"]) for record in group), len(group)
            ),
            "gold_fail_cases": len(group_fails),
            "false_safe": rate(
                sum(bool(record["false_safe"]) for record in group_fails), len(group_fails)
            ),
        }

    return {
        "decision_cases": len(decisions),
        "verdict_accuracy": rate(
            sum(bool(record["majority_correct"]) for record in decisions), len(decisions)
        ),
        "false_safe": rate(sum(bool(record["false_safe"]) for record in fails), len(fails)),
        "false_fail": rate(sum(bool(record["false_fail"]) for record in passes), len(passes)),
        "consistency": rate(sum(bool(record["unanimous"]) for record in decisions), len(decisions)),
        "ask": {
            "true_positive": ask_tp,
            "false_positive": len(predicted_asks) - ask_tp,
            "false_negative": len(asks) - ask_tp,
            "precision": ask_precision,
            "recall": ask_recall,
            "f1": ask_f1,
            "missing_fields_exact": rate(
                sum(bool(record["missing_inputs_correct"]) for record in asks), len(asks)
            ),
        },
        "confusion_matrix": confusion,
        "by_category": by_category,
        "by_boundary_band": boundary,
    }


def _retrieval_metrics(
    cases_by_id: dict[str, dict[str, Any]],
    runs: list[dict[str, Any]],
    scores: list[dict[str, Any]],
) -> dict[str, Any]:
    reference_scores = [
        score
        for score in scores
        if cases_by_id[score["case_id"]].get("gold", {}).get("required_chunk_ids")
    ]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for score in reference_scores:
        grouped[score["case_id"]].append(score)

    case_hits: list[bool] = []
    for group in grouped.values():
        hits = [bool(score["retrieval_hit_at_3"]) for score in group]
        case_hits.append(sum(hits) > len(hits) / 2)

    return {
        "reference_cases": len(grouped),
        "reference_runs": len(reference_scores),
        "hit_at_3_repeat_level": rate(
            sum(bool(score["retrieval_hit_at_3"]) for score in reference_scores),
            len(reference_scores),
        ),
        "hit_at_3_case_majority": rate(sum(case_hits), len(case_hits)),
        "recall_at_3": mean(score["retrieval_recall_at_3"] for score in reference_scores),
        "mrr": mean(score["retrieval_mrr"] for score in reference_scores),
        "citation_precision": mean(score["citation_precision"] for score in reference_scores),
        "citation_recall": mean(score["citation_recall"] for score in reference_scores),
        "citation_ids_are_retrieved": rate(
            sum(bool(score["citation_ids_are_retrieved"]) for score in reference_scores),
            len(reference_scores),
        ),
    }


def _primary_failure_label(
    case: dict[str, Any], run: dict[str, Any], score: dict[str, Any], system: str
) -> str | None:
    if run.get("error"):
        return "infrastructure_or_tool_exception"
    if not score["parseable"]:
        return "verdict_envelope_failure"
    if score["false_safe"]:
        return "false_safe"
    if score["false_fail"]:
        return "false_fail"
    gold_verdict = score["gold_verdict"]
    predicted = score["predicted_verdict"]
    if gold_verdict == "ASK" and predicted != "ASK":
        return "missed_required_ask"
    if gold_verdict in {"PASS", "FAIL"} and predicted == "ASK":
        return "unnecessary_ask"

    expected_names = [call.get("name") for call in expected_calls(case, system)]
    actual_names = [call.get("name") for call in run.get("tool_calls", [])]
    if expected_names and not actual_names:
        return "missing_required_tool"
    if not expected_names and actual_names:
        return "unnecessary_tool"
    if expected_names and actual_names and expected_names[0] != actual_names[0]:
        return "wrong_first_tool"
    if actual_names != expected_names:
        return "wrong_tool_sequence"
    if score["correct_arg_count"] < score["expected_arg_count"]:
        return "wrong_or_missing_argument"
    if score["retrieval_hit_at_3"] is False:
        return "retrieval_miss"
    if score["citation_ids_are_retrieved"] is False:
        return "citation_not_retrieved"
    if score["citation_recall"] is not None and score["citation_recall"] < 1.0:
        return "citation_omission"
    if score["verdict_correct"] is False:
        return "other_verdict_error"
    return None


def _failure_taxonomy(
    cases_by_id: dict[str, dict[str, Any]],
    runs: list[dict[str, Any]],
    scores: list[dict[str, Any]],
    system: str,
) -> dict[str, Any]:
    labels: dict[str, list[str]] = defaultdict(list)
    for run, score in zip(runs, scores):
        case = cases_by_id[str(run["case_id"])]
        label = _primary_failure_label(case, run, score, system)
        if label:
            labels[label].append(str(run["case_id"]))
    return {
        label: {
            "run_count": len(case_ids),
            "unique_case_count": len(set(case_ids)),
            "case_ids": sorted(set(case_ids)),
        }
        for label, case_ids in sorted(labels.items())
    }


def analyze_system(
    cases: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    system: str,
    expected_repeats: int,
) -> dict[str, Any]:
    cases_by_id = {str(case["case_id"]): case for case in cases}
    unknown = sorted({str(run.get("case_id", "")) for run in runs} - set(cases_by_id))
    if unknown:
        raise ValueError(f"System {system} has unknown case IDs: {unknown}")

    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_keys: set[tuple[str, int]] = set()
    for run in runs:
        if str(run.get("system")) != system:
            raise ValueError(f"Expected system {system}, found {run.get('system')!r}")
        case_id = str(run["case_id"])
        key = (case_id, int(run.get("repeat", 0)))
        if key in seen_keys:
            raise ValueError(f"Duplicate system/case/repeat record: {system}/{key}")
        seen_keys.add(key)
        by_case[case_id].append(run)

    missing_cases = sorted(set(cases_by_id) - set(by_case))
    if missing_cases:
        raise ValueError(f"System {system} is missing cases: {missing_cases}")
    wrong_repeat_counts = {
        case_id: len(group)
        for case_id, group in by_case.items()
        if len(group) != expected_repeats
    }
    if wrong_repeat_counts:
        raise ValueError(
            f"System {system} expected {expected_repeats} repeats per case: "
            f"{wrong_repeat_counts}"
        )

    ordered_runs = sorted(runs, key=lambda run: (str(run["case_id"]), int(run["repeat"])))
    scores = [score_run(cases_by_id[str(run["case_id"])], run) for run in ordered_runs]
    case_records = [
        aggregate_case(
            cases_by_id[case_id],
            sorted(group, key=lambda run: int(run["repeat"])),
            system,
        )
        for case_id, group in sorted(by_case.items())
    ]
    per_run = summarize_scores(scores)
    latencies = [
        float(run["latency_ms"])
        for run in ordered_runs
        if isinstance(run.get("latency_ms"), Real)
    ]
    return {
        "run_count": len(ordered_runs),
        "case_count": len(case_records),
        "expected_repeats": expected_repeats,
        "per_run_descriptive": per_run,
        "case_level": _case_level_metrics(case_records),
        "tool_use": _tool_metrics(cases_by_id, ordered_runs, scores, system),
        "retrieval": _retrieval_metrics(cases_by_id, ordered_runs, scores),
        "hard_failures": rate(
            sum(bool(run.get("error")) for run in ordered_runs), len(ordered_runs)
        ),
        "latency_ms": {
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
        },
        "failure_taxonomy": _failure_taxonomy(
            cases_by_id, ordered_runs, scores, system
        ),
        "cases": case_records,
    }


def compare_systems(
    first_name: str,
    first: dict[str, Any],
    second_name: str,
    second: dict[str, Any],
) -> dict[str, Any]:
    first_cases = {
        record["case_id"]: record
        for record in first["cases"]
        if record["gold_verdict"] in DECISION_VERDICTS
    }
    second_cases = {
        record["case_id"]: record
        for record in second["cases"]
        if record["gold_verdict"] in DECISION_VERDICTS
    }
    if set(first_cases) != set(second_cases):
        raise ValueError(f"Decision-case mismatch for {first_name} vs {second_name}")

    both_correct = 0
    first_only = 0
    second_only = 0
    both_wrong = 0
    for case_id in sorted(first_cases):
        first_correct = bool(first_cases[case_id]["majority_correct"])
        second_correct = bool(second_cases[case_id]["majority_correct"])
        if first_correct and second_correct:
            both_correct += 1
        elif first_correct:
            first_only += 1
        elif second_correct:
            second_only += 1
        else:
            both_wrong += 1

    first_accuracy = first["case_level"]["verdict_accuracy"]["rate"]
    second_accuracy = second["case_level"]["verdict_accuracy"]["rate"]
    return {
        "first": first_name,
        "second": second_name,
        "decision_cases": len(first_cases),
        "both_correct": both_correct,
        "first_only_correct": first_only,
        "second_only_correct": second_only,
        "both_wrong": both_wrong,
        "paired_accuracy_difference": second_accuracy - first_accuracy,
        "exact_mcnemar_p": exact_mcnemar_p(first_only, second_only),
    }


def build_analysis(
    cases: list[dict[str, Any]],
    runs_by_system: dict[str, list[dict[str, Any]]],
    expected_repeats: int = 3,
) -> dict[str, Any]:
    systems = {
        system: analyze_system(cases, runs, system, expected_repeats)
        for system, runs in sorted(runs_by_system.items())
    }
    comparisons: dict[str, Any] = {}
    for first, second in (("B", "C"), ("C", "D")):
        if first in systems and second in systems:
            comparisons[f"{first}_to_{second}"] = compare_systems(
                first, systems[first], second, systems[second]
            )
    return {
        "analysis_unit": "case majority across three repeats",
        "repeat_level_use": "descriptive latency, tool, argument, retrieval, citation, and failure traces",
        "case_count": len(cases),
        "expected_repeats": expected_repeats,
        "systems": systems,
        "comparisons": comparisons,
    }


def _pct(value: float | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:.{digits}%}"


def _ci(metric: dict[str, Any]) -> str:
    low, high = metric["wilson_95"]
    if low is None:
        return "n/a"
    return f"{low:.1%}-{high:.1%}"


def _rate_text(metric: dict[str, Any]) -> str:
    if metric["rate"] is None:
        return "n/a"
    return f"{metric['successes']}/{metric['total']} ({metric['rate']:.1%})"


def _p_text(value: float) -> str:
    return "<0.0001" if value < 0.0001 else f"{value:.4f}"


def render_markdown(analysis: dict[str, Any], source_paths: dict[str, str]) -> str:
    systems = analysis["systems"]
    names = [name for name in ("B", "C", "D") if name in systems]
    lines = [
        "# Formal B/C/D Shock-Mount Evaluation Results",
        "",
        "**Status:** Frozen v1 raw runs analysed without modifying the benchmark, runner, prompts, tools, or JSONL records.",
        "",
        "## Analysis rules",
        "",
        "- The statistical unit is one benchmark case, not one repeated response.",
        "- Three repeats are reduced to a strict majority verdict per case.",
        "- All-different outcomes are labelled `NO_MAJORITY` and scored incorrect.",
        "- Tool-required accuracy excludes no-tool cases; abstention is reported separately.",
        "- McNemar tests use paired case-majority correctness on the same 140 decision cases.",
        "- Latency, arguments, retrieval, citations, and hard failures remain repeat-level descriptive measures.",
        "",
        "## Frozen inputs",
        "",
        "| Input | Path |",
        "|---|---|",
    ]
    for label, path in source_paths.items():
        lines.append(f"| {label} | `{path}` |")

    lines.extend([
        "",
        "## Case-level engineering outcomes",
        "",
        "| Metric | " + " | ".join(names) + " |",
        "|---|" + "---:|" * len(names),
    ])
    metric_rows = [
        ("Verdict accuracy", "verdict_accuracy"),
        ("False-safe rate", "false_safe"),
        ("False-fail rate", "false_fail"),
        ("Three-repeat unanimity", "consistency"),
    ]
    for label, key in metric_rows:
        values = []
        for name in names:
            metric = systems[name]["case_level"][key]
            values.append(f"{_rate_text(metric)}; 95% CI {_ci(metric)}")
        lines.append(f"| {label} | " + " | ".join(values) + " |")

    lines.extend([
        "",
        "## Corrected tool-use denominators",
        "",
        "| Metric | " + " | ".join(names) + " |",
        "|---|" + "---:|" * len(names),
    ])
    tool_rows = [
        ("Tool-required runs", "tool_required_runs"),
        ("First-tool accuracy", "first_tool_accuracy"),
        ("Exact sequence accuracy", "sequence_accuracy"),
        ("Valid schema", "valid_schema_rate"),
        ("Argument accuracy", "argument_accuracy"),
        ("No-tool expected runs", "no_tool_expected_runs"),
        ("Tool abstention accuracy", "abstention_accuracy"),
    ]
    for label, key in tool_rows:
        values = []
        for name in names:
            value = systems[name]["tool_use"][key]
            if isinstance(value, dict):
                if "successes" in value:
                    values.append(_rate_text(value))
                else:
                    values.append(
                        "n/a" if value["rate"] is None else f"{value['correct']}/{value['total']} ({value['rate']:.1%})"
                    )
            else:
                values.append(str(value))
        lines.append(f"| {label} | " + " | ".join(values) + " |")

    lines.extend([
        "",
        "## ASK safety behaviour",
        "",
        "| Metric | " + " | ".join(names) + " |",
        "|---|" + "---:|" * len(names),
    ])
    for label, key in (("Precision", "precision"), ("Recall", "recall"), ("F1", "f1")):
        lines.append(
            f"| ASK {label} | "
            + " | ".join(_pct(systems[name]["case_level"]["ask"][key]) for name in names)
            + " |"
        )
    lines.append(
        "| Exact missing-field accuracy | "
        + " | ".join(
            _rate_text(systems[name]["case_level"]["ask"]["missing_fields_exact"])
            for name in names
        )
        + " |"
    )

    lines.extend([
        "",
        "## Boundary-band safety",
        "",
        "| Band | Metric | " + " | ".join(names) + " |",
        "|---|---|" + "---:|" * len(names),
    ])
    for band in ("boundary", "non_boundary"):
        for label, key in (("Verdict accuracy", "verdict_accuracy"), ("False-safe", "false_safe")):
            lines.append(
                f"| {band.replace('_', ' ').title()} | {label} | "
                + " | ".join(
                    _rate_text(systems[name]["case_level"]["by_boundary_band"][band][key])
                    for name in names
                )
                + " |"
            )

    lines.extend([
        "",
        "## Paired case-level comparisons",
        "",
        "| Comparison | First only correct | Second only correct | Accuracy difference | Exact McNemar p |",
        "|---|---:|---:|---:|---:|",
    ])
    for comparison in analysis["comparisons"].values():
        lines.append(
            f"| {comparison['first']} -> {comparison['second']} | "
            f"{comparison['first_only_correct']} | {comparison['second_only_correct']} | "
            f"{comparison['paired_accuracy_difference']:+.1%} | "
            f"{_p_text(comparison['exact_mcnemar_p'])} |"
        )

    if "D" in systems:
        retrieval = systems["D"]["retrieval"]
        lines.extend([
            "",
            "## System D retrieval and citation",
            "",
            "| Metric | Result |",
            "|---|---:|",
            f"| Hit@3, repeat level | {_rate_text(retrieval['hit_at_3_repeat_level'])} |",
            f"| Hit@3, case-majority | {_rate_text(retrieval['hit_at_3_case_majority'])} |",
            f"| Recall@3 | {_pct(retrieval['recall_at_3']['mean'])} |",
            f"| MRR | {retrieval['mrr']['mean']:.4f} |",
            f"| Citation precision | {_pct(retrieval['citation_precision']['mean'])} |",
            f"| Citation recall | {_pct(retrieval['citation_recall']['mean'])} |",
            f"| Every cited ID was retrieved | {_rate_text(retrieval['citation_ids_are_retrieved'])} |",
        ])

    lines.extend([
        "",
        "## Operational measures",
        "",
        "| Metric | " + " | ".join(names) + " |",
        "|---|" + "---:|" * len(names),
        "| Hard failures | "
        + " | ".join(_rate_text(systems[name]["hard_failures"]) for name in names)
        + " |",
        "| Latency p50 | "
        + " | ".join(f"{systems[name]['latency_ms']['p50']/1000:.1f} s" for name in names)
        + " |",
        "| Latency p95 | "
        + " | ".join(f"{systems[name]['latency_ms']['p95']/1000:.1f} s" for name in names)
        + " |",
    ])

    categories = sorted(
        {
            category
            for name in names
            for category in systems[name]["case_level"]["by_category"]
        }
    )
    lines.extend([
        "",
        "## Verdict accuracy by category",
        "",
        "| Category | " + " | ".join(names) + " |",
        "|---|" + "---:|" * len(names),
    ])
    for category in categories:
        values = []
        for name in names:
            category_result = systems[name]["case_level"]["by_category"].get(category)
            values.append(_rate_text(category_result["verdict_accuracy"]) if category_result else "n/a")
        lines.append(f"| `{category}` | " + " | ".join(values) + " |")

    for name in names:
        confusion = systems[name]["case_level"]["confusion_matrix"]
        lines.extend([
            "",
            f"## System {name} majority confusion matrix",
            "",
            "| Gold / predicted | " + " | ".join(CONFUSION_LABELS) + " |",
            "|---|" + "---:|" * len(CONFUSION_LABELS),
        ])
        for gold in DECISION_VERDICTS:
            lines.append(
                f"| {gold} | "
                + " | ".join(str(confusion[gold][label]) for label in CONFUSION_LABELS)
                + " |"
            )

    lines.extend([
        "",
        "## Primary failure taxonomy",
        "",
        "Counts are repeat-level primary labels; unique-case counts prevent repeated failures from appearing as independent cases.",
        "",
        "| System | Failure class | Runs | Unique cases | Representative case IDs |",
        "|---|---|---:|---:|---|",
    ])
    for name in names:
        for label, entry in systems[name]["failure_taxonomy"].items():
            case_text = ", ".join(entry["case_ids"][:8])
            if len(entry["case_ids"]) > 8:
                case_text += ", ..."
            lines.append(
                f"| {name} | `{label}` | {entry['run_count']} | "
                f"{entry['unique_case_count']} | {case_text} |"
            )

    lines.extend([
        "",
        "## Interpretation boundary",
        "",
        "- Statistical results establish agreement with the frozen Python oracle, not certified physical safety.",
        "- Exact McNemar p-values test paired majority correctness; they do not prove that every subgroup changed.",
        "- Retrieval and citation rates describe the frozen 30-case reference set.",
        "- Final-set failures are diagnostic evidence and must not be used to train and retest on the same benchmark.",
        "- Any deterministic bug fix, output guard, or model adaptation starts a separately labelled evaluation version.",
        "",
    ])
    return "\n".join(lines)


def parse_run_specs(specs: list[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    runs: dict[str, list[dict[str, Any]]] = {}
    paths: dict[str, str] = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"--run must use SYSTEM=PATH, got {spec!r}")
        system, path_text = spec.split("=", 1)
        system = system.strip()
        path = Path(path_text)
        if not system:
            raise ValueError(f"Empty system in --run {spec!r}")
        if system in runs:
            raise ValueError(f"Duplicate --run system {system!r}")
        runs[system] = _read_jsonl(path)
        paths[f"System {system} raw runs"] = path.as_posix()
    return runs, paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", required=True)
    parser.add_argument("--run", action="append", required=True, help="SYSTEM=PATH")
    parser.add_argument("--expected-repeats", type=int, default=3)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.expected_repeats < 1:
        raise SystemExit("--expected-repeats must be at least 1")
    cases = load_cases(args.cases)
    runs_by_system, source_paths = parse_run_specs(args.run)
    source_paths = {
        "Frozen benchmark": ", ".join(args.cases),
        **source_paths,
    }
    analysis = build_analysis(cases, runs_by_system, args.expected_repeats)

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    with args.out_json.open("w", encoding="utf-8") as handle:
        json.dump(analysis, handle, indent=2, ensure_ascii=True)
        handle.write("\n")

    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(render_markdown(analysis, source_paths), encoding="utf-8")

    print(f"Cases: {analysis['case_count']}; repeats: {analysis['expected_repeats']}")
    for system, result in analysis["systems"].items():
        verdict = result["case_level"]["verdict_accuracy"]
        false_safe = result["case_level"]["false_safe"]
        print(
            f"System {system}: verdict={_rate_text(verdict)}; "
            f"false-safe={_rate_text(false_safe)}"
        )
    for comparison in analysis["comparisons"].values():
        print(
            f"{comparison['first']}->{comparison['second']}: "
            f"delta={comparison['paired_accuracy_difference']:+.1%}; "
            f"McNemar p={_p_text(comparison['exact_mcnemar_p'])}"
        )
    print(f"Wrote {args.out_json}")
    print(f"Wrote {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
