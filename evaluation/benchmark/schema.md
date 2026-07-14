# Evaluation Case Schema

Status: Draft for the Phase 1 harness

Each line of a benchmark JSONL file is one independent, single-turn case.

```json
{
  "case_id": "shock_select_001",
  "benchmark_version": "dev-v0.1",
  "domain": "shock_mount",
  "category": "tool_routing",
  "question": "Select an isolator for an 850 kg rack with 4 bottom and 2 wall mounts.",
  "provided_inputs": {
    "mass_kg": 850,
    "n_bottom": 4,
    "n_wall": 2
  },
  "gold": {
    "verdict": "PASS",
    "tool_calls": [
      {
        "name": "select_isolator",
        "args": {
          "mass_kg": 850,
          "n_bottom": 4,
          "n_wall": 2
        },
        "tolerances": {}
      }
    ],
    "tool_calls_by_system": {
      "B": [],
      "C": [{"name": "select_isolator", "args": {"mass_kg": 850}, "tolerances": {}}],
      "D": [{"name": "select_isolator", "args": {"mass_kg": 850}, "tolerances": {}}]
    },
    "missing_inputs": [],
    "required_chunk_ids": []
  },
  "oracle": {
    "function": "catalog.select_and_analyze",
    "source_version": "pending"
  }
}
```

## Required fields

- `case_id`: unique across every file loaded in one run.
- `domain`: a key from `agent.DOMAINS`.
- `question`: exact text sent to the agent.
- `gold.verdict`: `PASS`, `FAIL`, or `ASK`. Use JSON null for catalogue or
  reference questions with no engineering safety decision; these cases still
  score routing and grounding but are excluded from verdict accuracy.
- `gold.tool_calls`: ordered expected calls. Use an empty list when the correct
  behavior is to ask for missing information without calling a tool.
- `gold.tool_calls_by_system`: optional system-specific expected calls. Use this
  for final B/C/D cases: B normally expects no calls; C expects deterministic
  tools for engineering cases; D additionally expects `lookup_knowledge` for
  reference questions. When absent, `gold.tool_calls` applies to all systems for
  backwards compatibility with development cases.
- `gold.missing_inputs`: exact field names required when verdict is `ASK`.
- `gold.required_chunk_ids`: stable RAG chunk IDs for reference cases. On System
  D only, the scorer calculates Hit@3, recall@3, MRR, citation precision/recall,
  and whether cited IDs were actually retrieved.

## Argument tolerances

Strings, enums, integers, and directly supplied numerical values should normally
be exact. When an expected argument is a derived or converted number, specify an
absolute or relative tolerance:

```json
"tolerances": {
  "mass_kg": {"relative": 0.001, "absolute": 0.01}
}
```

The accepted numerical difference is the larger of the absolute tolerance and
the expected magnitude multiplied by the relative tolerance.

## Dataset rules

- Development, screening, training, and final cases use disjoint parameter draws
  and question templates.
- Gold numerical outputs come from the deterministic Python engines.
- Missing-input cases delete one required input from an otherwise valid case.
- RAG cases identify stable `required_chunk_ids`; routine numerical cases leave
  the list empty.
- The final benchmark is immutable after its hash is recorded in `FREEZE.md`.
