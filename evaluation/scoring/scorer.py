r"""Score raw evaluation JSONL records without an LLM judge.

Example:
    .\mpd\Scripts\python.exe -m evaluation.scoring.scorer `
      --cases evaluation/benchmark/dev.jsonl `
      --runs evaluation/runs/qwen35_9b_dev.jsonl `
      --out evaluation/results/qwen35_9b_dev_scored.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.harness.runner import _read_jsonl, load_cases
from evaluation.scoring.metrics import score_run, summarize_scores


def score_records(
    cases: list[dict[str, Any]], runs: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases_by_id = {str(case["case_id"]): case for case in cases}
    scored: list[dict[str, Any]] = []
    for run in runs:
        case_id = str(run.get("case_id", ""))
        if case_id not in cases_by_id:
            raise KeyError(f"Run references unknown case_id {case_id!r}")
        scored.append(score_run(cases_by_id[case_id], run))
    return scored, summarize_scores(scored)


def _format_rate(metric: dict[str, Any]) -> str:
    if metric["rate"] is None:
        return "n/a"
    return f"{metric['successes']}/{metric['total']} ({metric['rate']:.1%})"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", required=True)
    parser.add_argument("--runs", nargs="+", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cases = load_cases(args.cases)
    runs: list[dict[str, Any]] = []
    for path in args.runs:
        runs.extend(_read_jsonl(path))
    scored, summary = score_records(cases, runs)

    print(f"Runs: {summary['runs']}")
    print(f"Verdict accuracy: {_format_rate(summary['verdict_accuracy'])}")
    print(f"False-safe: {_format_rate(summary['false_safe'])}")
    print(f"First-tool accuracy: {_format_rate(summary['first_tool_accuracy'])}")
    argument = summary["argument_accuracy"]
    argument_text = "n/a" if argument["rate"] is None else f"{argument['rate']:.1%}"
    print(f"Argument accuracy: {argument_text}")
    print(f"Parseable envelope: {_format_rate(summary['parseable_envelope'])}")
    print(f"Retrieval Hit@3 (D reference cases): {_format_rate(summary['retrieval_hit_at_3'])}")
    retrieval_mrr = summary["retrieval_mrr"]
    citation_recall = summary["citation_recall"]
    print(
        "Retrieval MRR (D reference cases): "
        + ("n/a" if retrieval_mrr["mean"] is None else f"{retrieval_mrr['mean']:.4f}")
    )
    print(
        "Citation recall (D reference cases): "
        + ("n/a" if citation_recall["mean"] is None else f"{citation_recall['mean']:.1%}")
    )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"summary": summary, "runs": scored}
        with args.out.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True)
            handle.write("\n")
        print(f"Wrote scored results to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
