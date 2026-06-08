"""
Agent evaluation harness — runs a fixed question set through the domain agents
and scores routing + argument quality. Every run is also auto-traced to MLflow.

Run:  .\\mpd\\Scripts\\python.exe eval_agent.py
      .\\mpd\\Scripts\\python.exe eval_agent.py --json results_before.json

Each case declares the EXPECTED tool(s). We score:
  - routing      : did the agent call the expected tool at least once?
  - first_try    : did it succeed without a tool ERROR (no wasted retries)?
  - tool_calls   : how many tool calls it made (lower = leaner)
  - latency_s    : wall-clock seconds
This is the ground-truth-oracle eval: the engines are validated, so we can
judge the agent deterministically.
"""
import argparse
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

# (id, domain, question, expected_tool[, must_not_error])
CASES = [
    # --- shock ---
    ("shock-select",   "shock_mount",
     "Select an isolator for a 1500 kg rack with 6 bottom and 4 wall mounts.",
     "select_isolator"),
    ("shock-capacity", "shock_mount",
     "What's the heaviest mass a CB1400-30 can support?",
     "find_capacity_limit"),
    ("shock-clearance","shock_mount",
     "Which isolator keeps deflection under 30 mm for a 1000 kg rack?",
     "filter_by_deflection"),

    # --- tie-down ---
    ("td-flag",        "tiedown",
     "Which secured items fall below a safety factor of 2 in the workbook?",
     "flag_critical_items"),
    ("td-check",       "tiedown",
     "Check a 60 kg item on the front wall held by four 8.8 M8 bolts at SF 2.",
     "run_tiedown_check"),
    ("td-size",        "tiedown",
     "How many M12 8.8 bolts to floor-mount a 1269 kg generator at SF 2?",
     "recommend_fasteners"),

    # --- mobility (known vehicle) ---
    ("mob-slope",      "mobility",
     "Is the Spinel E2 stable on a 60% slope?",
     "run_mobility_check"),
    ("mob-corner",     "mobility",
     "What's the max safe cornering speed for the Spinel?",
     "run_mobility_check"),
    ("mob-axle",       "mobility",
     "Give me the Spinel's axle loadings — are they within limits?",
     "run_mobility_check"),

    # --- mobility (custom CG fully specified) ---
    ("mob-custom",     "mobility",
     "A truck with Zcg 1500 mm, Xcg 2000 mm, wheelbase 4000 mm, track 1800 mm, "
     "GW 3000 kg — is it stable ascending a 30% slope?",
     "slope_limit"),
]


def run_case(agents_cache, domain, question):
    """Run one question; return (tool_names, had_error, n_calls, latency_s, answer)."""
    from agent import build_agent
    if domain not in agents_cache:
        agents_cache[domain] = build_agent(domain, os.environ["NVIDIA_API_KEY"])
    agent = agents_cache[domain]

    tools, had_error, answer = [], False, ""
    t0 = time.time()
    try:
        for ev in agent.stream(question):
            if ev["type"] == "tool_call":
                tools.append(ev["name"])
            elif ev["type"] == "tool_result":
                if "ERROR" in ev["content"][:30] or "Error invoking" in ev["content"][:40]:
                    had_error = True
            elif ev["type"] == "final":
                answer = ev["content"]
    except Exception as e:
        answer = f"<exception: {e}>"
        had_error = True
    return tools, had_error, len(tools), time.time() - t0, answer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write results to this JSON file")
    args = ap.parse_args()

    if not os.environ.get("NVIDIA_API_KEY"):
        raise SystemExit("ERROR: NVIDIA_API_KEY not set.")

    agents, rows = {}, []
    print(f"{'id':<14}{'route':>6}{'1st-try':>8}{'calls':>6}{'lat(s)':>8}  expected")
    print("-" * 70)
    for cid, domain, q, expected in CASES:
        tools, had_err, n, lat, ans = run_case(agents, domain, q)
        routed = expected in tools
        rows.append({
            "id": cid, "domain": domain, "question": q, "expected": expected,
            "tools_called": tools, "routed": routed, "had_error": had_err,
            "n_calls": n, "latency_s": round(lat, 2), "answer": ans[:300],
        })
        print(f"{cid:<14}{'OK' if routed else 'MISS':>6}"
              f"{'no' if had_err else 'yes':>8}{n:>6}{lat:>8.2f}  {expected} "
              f"-> {tools or '[]'}")

    n = len(rows)
    routed = sum(r["routed"] for r in rows)
    clean = sum(not r["had_error"] for r in rows)
    avg_lat = sum(r["latency_s"] for r in rows) / n
    avg_calls = sum(r["n_calls"] for r in rows) / n
    print("-" * 70)
    print(f"Routing accuracy : {routed}/{n} ({routed/n:.0%})")
    print(f"No-error (1st try): {clean}/{n} ({clean/n:.0%})")
    print(f"Avg tool calls   : {avg_calls:.2f}")
    print(f"Avg latency      : {avg_lat:.2f} s")

    if args.json:
        out = {"summary": {"routing": f"{routed}/{n}", "clean": f"{clean}/{n}",
                           "avg_calls": round(avg_calls, 2), "avg_latency_s": round(avg_lat, 2)},
               "cases": rows}
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"\nWrote {args.json}")


if __name__ == "__main__":
    main()
