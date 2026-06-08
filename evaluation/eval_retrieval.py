"""
Recall@k retrieval eval for the shock_mount RAG.

Run from project root:
    python -m evaluation.eval_retrieval

Reads ground-truth queries from `evaluation/retrieval_qrels.jsonl`,
runs each through NVIDIA embeddings + JSONVectorStore.search, and reports
hit@k, recall@k, and MRR. Writes a timestamped JSON to evaluation/results/.

Extend the eval by appending lines to retrieval_qrels.jsonl — no code change.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Project imports (run from repo root so these resolve)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nvidia_embedder import NVIDIAEmbedder, JSONVectorStore

# ---------- config ----------
QRELS_PATH    = Path(__file__).parent / "retrieval_qrels.jsonl"
STORE_PATH    = "artifacts/knowledge_embeddings.json"          # matches agent.py
TOP_K_VALUES  = [1, 3, 5]
RESULTS_DIR   = Path(__file__).parent / "results"

# ---------- metrics ----------
def hit_at_k(retrieved_ids, relevant_ids, k):
    return int(any(r in relevant_ids for r in retrieved_ids[:k]))

def recall_at_k(retrieved_ids, relevant_ids, k):
    if not relevant_ids:
        return 0.0
    hits = sum(1 for r in retrieved_ids[:k] if r in relevant_ids)
    return hits / len(relevant_ids)

def reciprocal_rank(retrieved_ids, relevant_ids):
    for i, r in enumerate(retrieved_ids, 1):
        if r in relevant_ids:
            return 1.0 / i
    return 0.0

# ---------- runner ----------
def main():
    load_dotenv()
    api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not api_key:
        sys.exit("ERROR: NVIDIA_API_KEY not set in .env")

    if not QRELS_PATH.exists():
        sys.exit(f"ERROR: qrels file not found: {QRELS_PATH}")
    qrels = [json.loads(l) for l in QRELS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not qrels:
        sys.exit("ERROR: no queries in qrels file")

    embedder = NVIDIAEmbedder(api_key=api_key)
    store    = JSONVectorStore(STORE_PATH)
    max_k    = max(TOP_K_VALUES)

    print(f"Evaluating {len(qrels)} queries against {STORE_PATH} (top_k={max_k})\n")

    per_query = []
    for q in qrels:
        qvec = embedder.embed_text(q["query"])
        hits = store.search(qvec, top_k=max_k, parent_topic=q.get("topic"))
        retrieved = [h["child_name"] for h in hits]

        row = {
            "qid":          q["qid"],
            "category":     q.get("category", "unspecified"),
            "adversarial":  bool(q.get("adversarial", False)),
            "query":        q["query"],
            "relevant":     q["relevant"],
            "retrieved":    retrieved,
            "similarities": [round(h["similarity"], 4) for h in hits],
            "mrr":          round(reciprocal_rank(retrieved, q["relevant"]), 4),
        }
        for k in TOP_K_VALUES:
            row[f"hit@{k}"]    = hit_at_k(retrieved, q["relevant"], k)
            row[f"recall@{k}"] = round(recall_at_k(retrieved, q["relevant"], k), 4)
        per_query.append(row)

    # split adversarial out of main metrics
    main_rows = [r for r in per_query if not r["adversarial"]]
    adv_rows  = [r for r in per_query if r["adversarial"]]

    # ---- main summary (non-adversarial) ----
    summary = {"n_main": len(main_rows)}
    if main_rows:
        n_m = len(main_rows)
        for k in TOP_K_VALUES:
            summary[f"hit@{k}"]    = round(sum(r[f"hit@{k}"]    for r in main_rows) / n_m, 4)
            summary[f"recall@{k}"] = round(sum(r[f"recall@{k}"] for r in main_rows) / n_m, 4)
        summary["mrr"] = round(sum(r["mrr"] for r in main_rows) / n_m, 4)

    # per-category breakdown (informational)
    by_cat = {}
    for r in main_rows:
        c = r["category"]
        by_cat.setdefault(c, []).append(r)
    cat_summary = {
        c: {
            "n":       len(rows),
            "hit@1":   round(sum(r["hit@1"] for r in rows) / len(rows), 4),
            "hit@3":   round(sum(r["hit@3"] for r in rows) / len(rows), 4),
            "mrr":     round(sum(r["mrr"]   for r in rows) / len(rows), 4),
        }
        for c, rows in by_cat.items()
    }

    # ---- adversarial summary ----
    # Goal: top-1 similarity should be LOW. Any adv query whose top-1 sim is
    # comparable to legitimate queries is a potential confidence-leak.
    adv_summary = {"n_adversarial": len(adv_rows)}
    if adv_rows:
        adv_top1 = [r["similarities"][0] if r["similarities"] else 0.0 for r in adv_rows]
        adv_summary["adv_top1_sim_mean"] = round(sum(adv_top1) / len(adv_top1), 4)
        adv_summary["adv_top1_sim_max"]  = round(max(adv_top1), 4)

    # ---- print per-query ----
    print("=== Per-query ===")
    for r in per_query:
        if r["adversarial"]:
            tag = "ADV "          # hit@1=0 expected; we care about sim
        else:
            tag = "OK  " if r["hit@1"] else "MISS"
        top1 = r["retrieved"][0] if r["retrieved"] else "<none>"
        rel  = ",".join(r["relevant"]) if r["relevant"] else "-"
        sim  = r["similarities"][0] if r["similarities"] else "n/a"
        print(f"[{tag}] {r['qid']:>4} [{r['category'][:6]:<6}]  top1={top1:<18}  relevant={rel:<22}  sim={sim}")

    # ---- print main summary ----
    print("\n=== Main summary (non-adversarial) ===")
    for k, v in summary.items():
        print(f"  {k:12} {v}")

    print("\n=== By category ===")
    for c, s in cat_summary.items():
        print(f"  {c:12} n={s['n']:<3}  hit@1={s['hit@1']:<6}  hit@3={s['hit@3']:<6}  mrr={s['mrr']}")

    # ---- print adversarial summary ----
    print("\n=== Adversarial summary ===")
    for k, v in adv_summary.items():
        print(f"  {k:22} {v}")
    if adv_rows:
        # quick interpretation hint
        main_top1_mean = (
            sum((r["similarities"][0] if r["similarities"] else 0.0) for r in main_rows) / len(main_rows)
            if main_rows else 0.0
        )
        print(f"  (main top1 sim mean   {round(main_top1_mean, 4)})")
        print(f"  Adv mean should be NOTICEABLY lower than main mean -- that's the gate working.")

    # ---- save ----
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"recall_at_k_{datetime.now():%Y%m%d_%H%M%S}.json"
    out_path.write_text(json.dumps(
        {"summary": summary, "by_category": cat_summary, "adversarial": adv_summary, "per_query": per_query},
        indent=2,
    ))
    print(f"\nSaved: {out_path.relative_to(Path.cwd())}" if out_path.is_relative_to(Path.cwd()) else f"\nSaved: {out_path}")

if __name__ == "__main__":
    main()
