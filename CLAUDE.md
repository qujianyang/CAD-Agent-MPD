# CAD-Aware AI Assistant — Shock Isolator Selection

FYP project at ST Engineering. Two real pillars: **validated shock-isolation physics** + **LLM agent with hierarchical RAG**. The CAD layer (SolidWorks COM) is intentionally thin — it only feeds mass / CG / bbox into the physics engine.

This file is the entry point for every new Claude session in this repo. Keep it short.

---

## On every session, read first

1. `.claude/memory/project-overview.md` — what this is, scope, status, the two-pillars framing
2. `.claude/memory/conventions.md` — coding rules (especially LLM tool patterns and the OMIT rule)

That's it. Do **not** load everything up front — token budget.

## Read on demand (pick based on what the user asks)

| When the user is... | Read |
|---|---|
| Touching any `.py` file, or asks "how is X wired" | `architecture.md` |
| Touching `physics_engine.py` / `catalog.py`, or asks about loads / formulas / the Excel | `physics-reference.md` |
| Debugging anything weird (SW COM, NVIDIA API, the to_s=0 bug, Streamlit silently failing) | `gotchas.md` |
| Asking "what's next" / "what's the state" / FYP report progress | `current-status.md` |

If unsure, just load `architecture.md` — it has the file map.

---

## User profile

Mech eng FYP student. Familiar with ReAct, comfortable with code, wants practical tooling. Prefers terse explanations over hand-holding. Windows machine, PowerShell or Git Bash. Project directory: `C:\Users\qujia\QuantumKeyDistribution\CAD-Agent-MPD`.

## How to update this memory

After a meaningful work session, ask Claude to:
> "Update .claude/memory/current-status.md to reflect what we just did, and add anything new to gotchas.md if we hit a new pitfall."

Keep each file dense. Bullet points and tables over prose.
