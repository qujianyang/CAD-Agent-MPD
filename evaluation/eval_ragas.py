"""
RAGAS full-agent evaluation for the shock mount assistant.

Runs each query in evaluation/agent_qa.jsonl through ShockMountAgent.stream(),
captures all tool_result outputs as RAGAS contexts and the final AI message as
the answer, then scores with RAGAS metrics:
  - faithfulness         (answer grounded in contexts)
  - answer_relevancy     (answer addresses question)
  - context_precision    (contexts are useful)
  - context_recall       (ground truth facts findable in contexts)

Judge LLM: NVIDIA Llama 3.1 70B (same family as agent; document bias in report).
Embeddings (for relevancy / precision scoring): NVIDIA NV-Embed.

Run from project root:
    .\\mpd\\Scripts\\python.exe -m evaluation.eval_ragas [flags]

CLI flags:
    --limit N          Run only first N queries (dev iteration)
    --skip-solidworks  Skip queries with requires_solidworks=true
    --dry-run          Print resolved query list; no LLM calls
    --no-judge         Run agent only, save answers + contexts, skip RAGAS scoring
    --timeout SECONDS  Per-query agent timeout (default 60)
    --output-dir PATH  Where to save results (default evaluation/results)
"""
import argparse
import json
import os
import sys
import time
import traceback
import types
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# RAGAS 0.4.3 + langchain-community 0.4.x compatibility shim.
#
# ragas/llms/base.py does an eager `from langchain_community.chat_models.vertexai
# import ChatVertexAI` at import time. That module path no longer exists in
# langchain-community 0.4.x (ChatVertexAI moved to langchain-google-vertexai).
# We never use VertexAI here -- so inject a dummy module so the import succeeds.
# Must run BEFORE any `import ragas`.
# ---------------------------------------------------------------------------
if "langchain_community.chat_models.vertexai" not in sys.modules:
    _shim = types.ModuleType("langchain_community.chat_models.vertexai")
    class _DummyChatVertexAI:  # pragma: no cover - placeholder only
        pass
    _shim.ChatVertexAI = _DummyChatVertexAI
    sys.modules["langchain_community.chat_models.vertexai"] = _shim

from dotenv import load_dotenv

# Project imports (run from repo root so these resolve)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent import ShockMountAgent

QRELS_PATH  = Path(__file__).parent / "agent_qa.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_qrels(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"ERROR: qrels file not found: {path}")
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not rows:
        sys.exit("ERROR: no rows in qrels file")
    return rows


def _filter_rows(rows: list[dict], limit: int | None, skip_solidworks: bool) -> list[dict]:
    out = rows
    if skip_solidworks:
        out = [r for r in out if not r.get("requires_solidworks")]
    if limit is not None and limit > 0:
        out = out[:limit]
    return out


def _run_agent_once(agent: ShockMountAgent, query: str, timeout_s: int) -> dict:
    """Run agent.stream(query) with a timeout. Capture all events."""
    def _worker():
        events = []
        for ev in agent.stream(query):
            events.append(ev)
        return events

    started = time.time()
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_worker)
        try:
            events = fut.result(timeout=timeout_s)
            return {
                "events":   events,
                "elapsed":  round(time.time() - started, 2),
                "error":    None,
            }
        except FutTimeout:
            return {"events": [], "elapsed": timeout_s, "error": "timeout"}
        except Exception as e:
            return {"events": [], "elapsed": round(time.time() - started, 2),
                    "error": f"{type(e).__name__}: {str(e)[:200]}"}


def _summarize_events(events: list[dict]) -> dict:
    """Pull tool_calls, tool_results (contexts), and final answer from the stream."""
    tool_calls   = [e for e in events if e.get("type") == "tool_call"]
    tool_results = [e for e in events if e.get("type") == "tool_result"]
    finals       = [e for e in events if e.get("type") == "final"]
    final_answer = finals[-1]["content"] if finals else ""

    return {
        "tool_names":  [tc.get("name", "?") for tc in tool_calls],
        "tool_args":   [tc.get("args", {})  for tc in tool_calls],
        "contexts":    [tr.get("content", "") for tr in tool_results],
        "answer":      final_answer,
    }


def _compare_tools(actual: list[str], expected: list[str] | None) -> str | None:
    """Return a warning string if actual != expected (set), or None if OK."""
    if not expected:
        return None
    actual_set, expected_set = set(actual), set(expected)
    if actual_set == expected_set:
        return None
    missing = expected_set - actual_set
    extra   = actual_set - expected_set
    bits = []
    if missing:
        bits.append(f"missing {sorted(missing)}")
    if extra:
        bits.append(f"extra {sorted(extra)}")
    return "; ".join(bits)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="RAGAS full-agent eval for shock mount assistant")
    parser.add_argument("--limit",            type=int, default=None,    help="Run only first N queries")
    parser.add_argument("--skip-solidworks",  action="store_true",       help="Skip queries with requires_solidworks=true")
    parser.add_argument("--dry-run",          action="store_true",       help="Print resolved query list; no LLM calls")
    parser.add_argument("--no-judge",         action="store_true",       help="Run agent only; skip RAGAS scoring")
    parser.add_argument("--timeout",          type=int, default=120,     help="Per-query agent timeout (s)")
    parser.add_argument("--output-dir",       type=Path, default=RESULTS_DIR, help="Results output dir")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not api_key and not args.dry_run:
        sys.exit("ERROR: NVIDIA_API_KEY not set in .env")

    rows_all = _load_qrels(QRELS_PATH)
    rows     = _filter_rows(rows_all, args.limit, args.skip_solidworks)

    print(f"Loaded {len(rows_all)} queries from {QRELS_PATH.name}")
    if args.skip_solidworks:
        n_skipped = len(rows_all) - len(_filter_rows(rows_all, None, True))
        print(f"Skipping {n_skipped} requires_solidworks queries")
    if args.limit:
        print(f"Limit: running first {len(rows)} queries")

    # ---------- DRY RUN ----------
    if args.dry_run:
        print(f"\n=== DRY RUN ({len(rows)} queries) ===")
        for r in rows:
            etools = ",".join(r.get("expected_tools", [])) or "(none)"
            tag = " [SW]" if r.get("requires_solidworks") else ""
            print(f"  {r['qid']:>5} [{r['category']:<10}]{tag}  expected_tools={etools}")
            print(f"        {r['query'][:90]}")
        print(f"\nDry-run complete. No LLM calls were made.")
        return

    # ---------- INSTANTIATE AGENT ----------
    print(f"\nInstantiating ShockMountAgent...")
    agent = ShockMountAgent(api_key)

    # ---------- RUN AGENT PER QUERY ----------
    print(f"\n=== Running agent on {len(rows)} queries (timeout={args.timeout}s/query) ===")
    per_query = []
    t_start_all = time.time()

    for i, r in enumerate(rows, 1):
        print(f"\n[{i}/{len(rows)}] {r['qid']} [{r['category']}]  -- {r['query'][:60]!r}")
        result = _run_agent_once(agent, r["query"], timeout_s=args.timeout)

        if result["error"]:
            print(f"  ERROR ({result['elapsed']}s): {result['error']}")
            per_query.append({
                **r,
                "agent_error":  result["error"],
                "elapsed":      result["elapsed"],
                "tool_names":   [],
                "contexts":     [],
                "answer":       "",
                "tool_warning": None,
            })
            continue

        summary = _summarize_events(result["events"])
        warn    = _compare_tools(summary["tool_names"], r.get("expected_tools"))

        if warn:
            print(f"  TOOL-WARNING: {warn}")
        print(f"  Tools called ({len(summary['tool_names'])}): {summary['tool_names']}")
        print(f"  Contexts captured: {len(summary['contexts'])}  |  Answer length: {len(summary['answer'])} chars  |  elapsed {result['elapsed']}s")

        per_query.append({
            **r,
            "agent_error":  None,
            "elapsed":      result["elapsed"],
            "tool_names":   summary["tool_names"],
            "tool_args":    summary["tool_args"],
            "contexts":     summary["contexts"],
            "answer":       summary["answer"],
            "tool_warning": warn,
        })

    elapsed_total = round(time.time() - t_start_all, 1)
    print(f"\nAgent stage complete in {elapsed_total}s")

    # ---------- SAVE AGENT-STAGE OUTPUT (always) ----------
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp        = datetime.now().strftime("%Y%m%d_%H%M%S")
    agent_path   = args.output_dir / f"ragas_agent_{stamp}.json"
    agent_path.write_text(json.dumps({
        "config": {"limit": args.limit, "skip_solidworks": args.skip_solidworks,
                   "timeout_s": args.timeout, "n_queries": len(rows)},
        "agent_elapsed_total_s": elapsed_total,
        "per_query": per_query,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved agent output: {agent_path.relative_to(Path.cwd())}" if agent_path.is_relative_to(Path.cwd()) else f"Saved agent output: {agent_path}")

    if args.no_judge:
        print("\n--no-judge set; skipping RAGAS scoring.")
        return

    # ---------- RAGAS SCORING ----------
    print(f"\n=== RAGAS scoring ===")

    # Filter out errored queries (no answer to score)
    scoreable = [r for r in per_query if not r.get("agent_error") and r.get("answer")]
    n_drop    = len(per_query) - len(scoreable)
    if n_drop:
        print(f"  Excluding {n_drop} queries with agent errors / no answer")
    if not scoreable:
        sys.exit("ERROR: no scoreable queries remain.")

    # Lazy imports so --dry-run / --no-judge don't need ragas/datasets installed at import time
    from datasets import Dataset
    from ragas import evaluate
    # Modern import path (the bare `ragas.metrics` names are deprecated for v1.0)
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall  # noqa: legacy path kept since collections variants need different invocation
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_nvidia_ai_endpoints import ChatNVIDIA, NVIDIAEmbeddings

    judge_llm = LangchainLLMWrapper(ChatNVIDIA(
        model="meta/llama-3.1-70b-instruct",
        api_key=api_key,
        temperature=0.0,
        max_tokens=2048,
    ))
    judge_embeds = LangchainEmbeddingsWrapper(NVIDIAEmbeddings(
        model="nvidia/llama-nemotron-embed-1b-v2",
        api_key=api_key,
        truncate="NONE",
    ))

    # Build HuggingFace Dataset (RAGAS v1 API)
    dataset = Dataset.from_dict({
        "question":      [r["query"]        for r in scoreable],
        "answer":        [r["answer"]       for r in scoreable],
        "contexts":      [r["contexts"]     for r in scoreable],
        "ground_truth":  [r["ground_truth"] for r in scoreable],
    })

    t_judge_start = time.time()
    result = evaluate(
        dataset,
        metrics     = [faithfulness, answer_relevancy, context_precision, context_recall],
        llm         = judge_llm,
        embeddings  = judge_embeds,
        raise_exceptions = False,
    )
    judge_elapsed = round(time.time() - t_judge_start, 1)
    print(f"\nRAGAS scoring complete in {judge_elapsed}s")

    # Convert to pandas for per-row + summary
    df = result.to_pandas()

    # Print per-query
    print("\n=== Per-query (scoreable) ===")
    metric_cols = [c for c in df.columns if c in ("faithfulness", "answer_relevancy", "context_precision", "context_recall")]
    # Compact non-colliding abbreviations
    METRIC_ABBR = {
        "faithfulness":      "faith",
        "answer_relevancy":  "ans_rel",
        "context_precision": "ctx_prec",
        "context_recall":    "ctx_rec",
    }
    for i, r in enumerate(scoreable):
        scores = {m: df.iloc[i][m] for m in metric_cols}
        scores_str = "  ".join(
            f"{METRIC_ABBR.get(m, m)}={v:.3f}" if isinstance(v, (int, float)) and v == v else f"{METRIC_ABBR.get(m, m)}=nan"
            for m, v in scores.items()
        )
        warn_tag = " [TOOL!]" if r.get("tool_warning") else ""
        print(f"  {r['qid']:>5} [{r['category']:<10}]{warn_tag}  {scores_str}")

    # Aggregate summary
    print("\n=== Summary ===")
    summary = {}
    for m in metric_cols:
        col = df[m].dropna()
        summary[m] = round(float(col.mean()), 4) if len(col) else None
        print(f"  {m:20} {summary[m]} (n={len(col)})")

    # By-category breakdown
    print("\n=== By category ===")
    by_cat: dict[str, dict] = {}
    for i, r in enumerate(scoreable):
        cat = r["category"]
        by_cat.setdefault(cat, []).append({m: df.iloc[i][m] for m in metric_cols})
    cat_summary = {}
    for cat, rows_in in by_cat.items():
        cat_summary[cat] = {"n": len(rows_in)}
        for m in metric_cols:
            vals = [r[m] for r in rows_in if isinstance(r[m], (int, float)) and r[m] == r[m]]
            cat_summary[cat][m] = round(sum(vals) / len(vals), 4) if vals else None
        cs = cat_summary[cat]
        bits = [f"{METRIC_ABBR.get(m, m)}={cs[m]}" for m in metric_cols]
        print(f"  {cat:<10} n={cs['n']:<3}  " + "  ".join(bits))

    # Save full result
    ragas_path = args.output_dir / f"ragas_full_{stamp}.json"
    full_records = df.to_dict(orient="records")
    # Attach qid/category back onto records for easier downstream analysis
    for rec, src in zip(full_records, scoreable):
        rec["qid"]          = src["qid"]
        rec["category"]     = src["category"]
        rec["tool_warning"] = src.get("tool_warning")
    ragas_path.write_text(json.dumps({
        "config": {"limit": args.limit, "skip_solidworks": args.skip_solidworks,
                   "n_scored": len(scoreable), "n_dropped": n_drop,
                   "judge_model": "meta/llama-3.1-70b-instruct",
                   "judge_elapsed_s": judge_elapsed},
        "summary":      summary,
        "by_category":  cat_summary,
        "per_query":    full_records,
    }, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved RAGAS output: {ragas_path.relative_to(Path.cwd())}" if ragas_path.is_relative_to(Path.cwd()) else f"\nSaved RAGAS output: {ragas_path}")


if __name__ == "__main__":
    main()
