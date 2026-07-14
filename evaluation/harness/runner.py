r"""Resume-safe command-line runner for local-LLM benchmark cases.

Example:
    .\mpd\Scripts\python.exe -m evaluation.harness.runner `
      --system qwen35_9b `
      --cases evaluation/benchmark/dev.jsonl `
      --repeats 3 `
      --out evaluation/runs/qwen35_9b_dev.jsonl
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
import re
import time
from typing import Any, Iterable

from dotenv import load_dotenv

from evaluation.harness.systems import (
    SYSTEMS,
    activated_system,
    build_evaluation_agent,
    get_system,
)
from evaluation.harness.verdict import parse_verdict_envelope


_CHUNK_ID_RE = re.compile(r"---\s*\[\d+\]\s+([^\s(]+)")
_ENVELOPE_REMINDER = """

Evaluation requirement: Your final response is invalid unless it ends with the
JSON verdict envelope specified by the system prompt. Include it even when you
ask for missing input or answer an information-only question. Use verdict null
only when no engineering safety decision applies.
"""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}:{line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Expected a JSON object in {path}:{line_number}")
            records.append(value)
    return records


def expand_case_paths(patterns: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = [Path(item) for item in glob.glob(pattern)]
        if not matches and Path(pattern).is_file():
            matches = [Path(pattern)]
        if not matches:
            raise FileNotFoundError(f"No case files matched {pattern!r}")
        paths.extend(sorted(matches))
    return paths


def load_cases(patterns: Iterable[str]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path in expand_case_paths(patterns):
        for case in _read_jsonl(path):
            for required in ("case_id", "domain", "question"):
                if not case.get(required):
                    raise ValueError(f"{path}: case is missing required field {required!r}")
            case_id = str(case["case_id"])
            if case_id in seen_ids:
                raise ValueError(f"Duplicate case_id {case_id!r}")
            seen_ids.add(case_id)
            cases.append(case)
    return cases


def completed_keys(path: Path) -> set[tuple[str, str, int]]:
    if not path.exists():
        return set()
    keys: set[tuple[str, str, int]] = set()
    for record in _read_jsonl(path):
        try:
            keys.add((
                str(record["case_id"]),
                str(record["system"]),
                int(record["repeat"]),
            ))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Malformed existing run record in {path}: {record}") from exc
    return keys


def _is_tool_error(content: str) -> bool:
    prefix = content.strip()[:120].lower()
    return prefix.startswith("error") or "error invoking tool" in prefix


def _extract_chunk_ids(content: str) -> list[str]:
    return list(dict.fromkeys(_CHUNK_ID_RE.findall(content)))


def run_case(agent: object, case: dict[str, Any], system_id: str, repeat: int) -> dict:
    start = time.perf_counter()
    tool_calls: list[dict[str, Any]] = []
    calls_by_id: dict[str, dict[str, Any]] = {}
    retrieved_chunk_ids: list[str] = []
    final_text = ""

    question_sent = f"{str(case['question']).rstrip()}\n{_ENVELOPE_REMINDER}"
    for event in agent.stream(question_sent, chat_history=None):
        event_type = event.get("type")
        now_ms = round((time.perf_counter() - start) * 1000, 3)
        if event_type == "tool_call":
            call = {
                "name": str(event.get("name", "?")),
                "args": event.get("args", {}),
                "id": str(event.get("id", "")),
                "result_text": None,
                "error": None,
                "t_call_ms": now_ms,
                "t_result_ms": None,
            }
            tool_calls.append(call)
            if call["id"]:
                calls_by_id[call["id"]] = call
        elif event_type == "tool_result":
            content = str(event.get("content", ""))
            call_id = str(event.get("id", ""))
            call = calls_by_id.get(call_id)
            if call is None:
                # Some backends omit IDs. Associate with the latest unmatched
                # call of the same name so the raw trace remains useful.
                name = str(event.get("name", "?"))
                call = next(
                    (
                        item for item in reversed(tool_calls)
                        if item["name"] == name and item["result_text"] is None
                    ),
                    None,
                )
            if call is not None:
                call["result_text"] = content
                call["error"] = _is_tool_error(content)
                call["t_result_ms"] = now_ms
            if str(event.get("name")) == "lookup_knowledge":
                retrieved_chunk_ids.extend(_extract_chunk_ids(content))
        elif event_type == "final":
            final_text = str(event.get("content", ""))

    latency_ms = round((time.perf_counter() - start) * 1000, 3)
    return {
        "case_id": str(case["case_id"]),
        "system": system_id,
        "repeat": repeat,
        "domain": str(case["domain"]),
        "question_sent": question_sent,
        "tool_calls": tool_calls,
        "retrieved_chunk_ids": list(dict.fromkeys(retrieved_chunk_ids)),
        "final_text": final_text,
        "envelope": parse_verdict_envelope(final_text),
        "latency_ms": latency_ms,
        "tokens": {"input": None, "output": None},
        "error": None,
    }


def _error_record(
    case: dict[str, Any], system_id: str, repeat: int, exc: Exception, latency_ms: float
) -> dict:
    return {
        "case_id": str(case["case_id"]),
        "system": system_id,
        "repeat": repeat,
        "domain": str(case["domain"]),
        "question_sent": f"{str(case['question']).rstrip()}\n{_ENVELOPE_REMINDER}",
        "tool_calls": [],
        "retrieved_chunk_ids": [],
        "final_text": "",
        "envelope": parse_verdict_envelope(""),
        "latency_ms": round(latency_ms, 3),
        "tokens": {"input": None, "output": None},
        "error": f"{type(exc).__name__}: {exc}",
    }


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")))
        handle.write("\n")
        handle.flush()


def _run_with_retry(
    agent: object,
    case: dict[str, Any],
    system_id: str,
    repeat: int,
    max_retries: int,
) -> dict:
    started = time.perf_counter()
    for attempt in range(max_retries + 1):
        try:
            return run_case(agent, case, system_id, repeat)
        except Exception as exc:
            retryable = "429" in str(exc)
            if retryable and attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            elapsed_ms = (time.perf_counter() - started) * 1000
            return _error_record(case, system_id, repeat, exc, elapsed_ms)
    raise AssertionError("unreachable")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", choices=sorted(SYSTEMS), required=True)
    parser.add_argument("--cases", nargs="+", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--warmup",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="run one unscored small-talk turn before timed cases (default: true)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")
    if args.max_retries < 0:
        raise SystemExit("--max-retries cannot be negative")

    load_dotenv(override=False)
    config = get_system(args.system)
    cases = load_cases(args.cases)
    if args.case_ids:
        requested = set(args.case_ids)
        available = {str(case["case_id"]) for case in cases}
        unknown = requested - available
        if unknown:
            raise SystemExit(f"Unknown --case-id value(s): {', '.join(sorted(unknown))}")
        cases = [case for case in cases if str(case["case_id"]) in requested]
    if args.limit is not None:
        cases = cases[: args.limit]

    total = len(cases) * args.repeats
    done = completed_keys(args.out)
    pending = sum(
        (str(case["case_id"]), config.id, repeat) not in done
        for case in cases
        for repeat in range(1, args.repeats + 1)
    )
    print(f"System: {config.id} ({config.model})")
    print(f"Cases: {len(cases)}; repeats: {args.repeats}; total: {total}")
    print(f"Already complete: {total - pending}; pending: {pending}")
    if args.dry_run:
        return 0

    agents: dict[str, object] = {}
    completed_now = 0
    with activated_system(config):
        for domain in sorted({str(case["domain"]) for case in cases}):
            agents[domain] = build_evaluation_agent(config, domain)
        if args.warmup and pending:
            print("Warming model with one unscored turn...")
            for domain, agent in agents.items():
                for _event in agent.stream("Hello.", chat_history=None):
                    pass
                print(f"[OK] warmup domain={domain}")
        for case in cases:
            domain = str(case["domain"])
            for repeat in range(1, args.repeats + 1):
                key = (str(case["case_id"]), config.id, repeat)
                if key in done:
                    continue
                record = _run_with_retry(
                    agents[domain], case, config.id, repeat, args.max_retries
                )
                record["system_config"] = config.public_record()
                append_jsonl(args.out, record)
                completed_now += 1
                status = "ERROR" if record["error"] else "OK"
                print(
                    f"[{status}] {case['case_id']} repeat={repeat} "
                    f"tools={len(record['tool_calls'])} latency_ms={record['latency_ms']:.1f}"
                )
                if args.delay > 0 and completed_now < pending:
                    time.sleep(args.delay)

    print(f"Wrote {completed_now} new record(s) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
