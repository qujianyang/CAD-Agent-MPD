# Missing-Input Policy (ASK, never guess)

**Chunk:** `shock_mount/missing_input_policy`
**Source:** `.claude/memory/conventions.md` (OMIT rule, anti-hallucination layers); `agent.py` tool docstrings and tool-use guard; `physics_engine.py` (`_loads_per_isolator` raises on bad mounts).
**Grounding:** validated-in-repo

---

The agent must not fabricate engineering inputs. Missing safety-relevant inputs
force an **ASK**, not a guessed number.

## Mass is never guessed

Mass drives every load case. If mass is not supplied (and not available from
CAD), the agent must ASK for it. It must not assume a placeholder (e.g. 100 kg
or the 850 kg reference) and proceed.

## The OMIT rule for optional parameters

Tool docstrings instruct the model to **OMIT** any parameter the user did not
specify, rather than invent a value. Tools then clamp missing/zero values to
safe defaults and inject a `NOTE:` in the return string so the substitution is
visible and can be surfaced to the user. Example: pulse duration is model-facing
as `to_ms` (ms), defaulting to 11.0 with a NOTE if 0/None — this also avoids the
`0.011 → 0` truncation bug.

## What forces an ASK

- **Mass** unknown → ASK (no guessing).
- Mount counts (`n_bottom`, `n_wall`) must be `> 0`; the engine raises on `≤ 0`.
  Confirm rather than assume when the configuration is ambiguous.
- Shock profile / GT limit stated as "per the equipment spec" but not given →
  ASK or fall back to the documented default **and say so**.

## Decision outcomes

| Outcome | When                                                            |
|---------|-----------------------------------------------------------------|
| PASS    | All gates pass on real, supplied inputs.                        |
| FAIL    | A deterministic gate is violated on real inputs.                |
| ASK     | A required input (esp. mass) is missing or ambiguous.           |

User pressure ("just assume something") does not convert an ASK into a guess for
a safety-relevant input. See `safety and decision rules` framing in
`governing_check.md` and `selection_workflow.md`.
