"""
Tool-use enforcement regression — replays the real failed shock-mount chat
(shock_mount_chat_20260621_213812.md) and asserts every technical turn is backed
by its CORRECT tool.

Why replay CUMULATIVELY: the failure is history-driven — once the conversation is
full of prior tool-derived answers, the model starts pattern-completing and skips
the tool. So we grow chat_history turn by turn (not isolated questions) to reproduce
that, then check the expected tool fired each turn.

This is STRICTER than the runtime guard: the guard only requires >=1 tool; here each
turn must call its specific expected tool (select/verify/catalog/reference).

Run:  .\\mpd\\Scripts\\python.exe evaluation/eval_shock_tooluse.py
      .\\mpd\\Scripts\\python.exe evaluation/eval_shock_tooluse.py --json results.json
"""
import argparse
import json
import os
import sys
import time

from dotenv import load_dotenv

# Repo root on sys.path (this file lives in evaluation/; agent.py uses flat imports).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# (question, expected_tool) in the exact order of the exported chat.
TURNS = [
    ("Select an isolator for a 1500 kg rack with 6 bottom and 4 wall mounts.", "select_isolator"),
    ("Select an isolator for an 850 kg rack with 6 bottom and 4 wall mounts.",  "select_isolator"),
    ("Pick the best CB1400 isolator for an 850 kg rack with standard 6+4 mounts.", "select_isolator"),
    ("What mount should I use for a 1200 kg cabinet? Use default mounts.",      "select_isolator"),
    ("Select an isolator for 900 kg, but I want maximum clearance margin.",     "select_isolator"),
    ("Does CB1400-15 pass for 950 kg with the standard 6+4 config?",            "run_shock_analysis"),
    ("Verify CB1500-30 for a 1500 kg rack.",                                    "run_shock_analysis"),
    ("Does CB1400-12 pass for 900 kg with a half-sine 15G 11ms pulse?",         "run_shock_analysis"),
    ("What is the stiffness and rated travel of CB1400-30?",                    "get_isolator_data"),
    ("How is transmitted G calculated?",                                        "lookup_knowledge"),
    ("Why do we divide by 2 for roll wall but not comp bottom?",                "lookup_knowledge"),
    ("Why does the softest valid spring give best isolation?",                  "lookup_knowledge"),
]


def run_turn(agent, question, history, max_retries=4):
    """Stream one turn; return (tools_called, final_answer).

    Retries the whole turn on a 429 (free-tier rate limit) with exponential
    backoff so the cumulative replay can finish."""
    for attempt in range(max_retries):
        tools, answer = [], ""
        try:
            for ev in agent.stream(question, chat_history=history):
                if ev["type"] == "tool_call":
                    tools.append(ev["name"])
                elif ev["type"] == "final":
                    answer = ev["content"]
            return tools, answer
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait = 30 * (attempt + 1)
                print(f"    (429 rate-limited; backing off {wait}s...)")
                time.sleep(wait)
                continue
            raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write results to this JSON file")
    args = ap.parse_args()

    if not os.environ.get("NVIDIA_API_KEY"):
        raise SystemExit("ERROR: NVIDIA_API_KEY not set.")

    from agent import build_agent
    agent = build_agent("shock_mount", os.environ["NVIDIA_API_KEY"])

    history, rows = [], []
    print(f"{'#':>2}  {'expected':<18}{'tools called':<28}{'verdict'}")
    print("-" * 72)
    for i, (q, expected) in enumerate(TURNS):
        if i:
            time.sleep(12)   # stay under the NVIDIA API rate limit between turns
        tools, answer = run_turn(agent, q, history)
        ok = expected in tools
        rows.append({"turn": i + 1, "question": q, "expected": expected,
                     "tools_called": tools, "ok": ok, "answer": answer[:300]})
        print(f"{i+1:>2}  {expected:<18}{str(tools):<28}{'OK' if ok else 'MISS <<<'}")
        # grow the conversation exactly as the UI would
        history += [("human", q), ("ai", answer)]

    passed = sum(r["ok"] for r in rows)
    n = len(rows)
    print("-" * 72)
    print(f"Correct-tool turns: {passed}/{n} ({passed/n:.0%})")
    if passed < n:
        print("MISSES:", [r["turn"] for r in rows if not r["ok"]])

    if args.json:
        out = {"summary": {"correct_tool": f"{passed}/{n}"}, "turns": rows}
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"\nWrote {args.json}")

    # non-zero exit if any technical turn skipped its tool (CI-friendly)
    raise SystemExit(0 if passed == n else 1)


if __name__ == "__main__":
    main()
