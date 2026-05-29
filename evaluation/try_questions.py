"""
Ad-hoc manual probe: run a few questions through the full agent and show
(1) which tools were called, (2) which knowledge pages lookup_knowledge
retrieved + match %, and (3) the final agent answer.

Edit QUESTIONS below and re-run to try your own.

    .\\mpd\\Scripts\\python.exe -m evaluation.try_questions
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows console can't encode pi/sqrt

from dotenv import load_dotenv
from agent import ShockMountAgent

QUESTIONS = [
    "Why is the shock input 20G for a truck or trailer mounted shelter rack? What standard backs that value?",
    "What MIL-STD-810H justification is there for using a terminal-peak sawtooth shock pulse?",
    "Why does this analysis track velocity change V instead of just peak G?",
    "For an 850 kg truck-mounted rack, recommend a mount and justify the shock spec against the standard.",
]


def main():
    load_dotenv()
    api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not api_key:
        sys.exit("ERROR: NVIDIA_API_KEY not set in .env")

    agent = ShockMountAgent(api_key)

    for i, q in enumerate(QUESTIONS, 1):
        print("=" * 90)
        print(f"Q{i}: {q}")
        print("=" * 90)

        tool_calls, kb_hits, final = [], [], ""
        for ev in agent.stream(q):
            t = ev.get("type")
            if t == "tool_call":
                tool_calls.append(ev.get("name"))
            elif t == "tool_result" and ev.get("name") == "lookup_knowledge":
                # pull "--- [n] parent/child  (xx% match) ---" lines
                hits = re.findall(r"---\s*\[\d+\]\s*(\S+)\s*\((\d+)% match\)", ev.get("content", ""))
                kb_hits.extend(hits)
            elif t == "final":
                final = ev.get("content", "")

        print(f"Tools called: {tool_calls}")
        if kb_hits:
            print("Knowledge pages retrieved:")
            for page, pct in kb_hits:
                print(f"   {page:30} {pct}% match")
        print("\nANSWER:")
        print(final if final else "(no final answer captured)")
        print()


if __name__ == "__main__":
    main()
