# Selection Workflow

**Chunk:** `shock_mount/selection_workflow`
**Source:** `catalog.py` (`select_and_analyze`, `select_isolator`, `_objective_sort_key`); `agent.py` shock tools.
**Grounding:** validated-in-repo

---

Use this workflow when the engineer wants the tool to **choose** a part. (To
confirm a part the engineer already named, use `verification_workflow.md`.)

## Required inputs before selection

Before choosing an isolator, provide the assembly mass, bottom and wall mount
counts, shock pulse magnitude and duration, pulse shape, transmitted-G limit,
catalogue scope, and selection objective. The tool may use documented defaults
for optional inputs, but it must ASK when required mass or mount information is
missing.

## Pipeline

```
Receive assembly mass M
  -> confirm mount configuration (n_bottom, n_wall; defaults 6 + 4)
  -> confirm shock profile and transmitted-G limit
     (defaults 20 G / 11 ms sawtooth, GT_limit 10 G — see project_shock_requirements.md)
  -> choose catalogue scope (default AUTO: CB1400 + CB1500 + CB1700)
  -> run EVERY candidate through the four load cases (four_load_cases.md)
  -> apply the gates: static (static_load_gate.md),
                      transmitted-G (transmitted_acceleration.md),
                      travel/clearance (travel_limit_gate.md)
  -> keep only parts valid on all four cases + static
  -> rank passing parts by the selected objective
     (max_clearance | best_isolation — see the objective chunks)
  -> report the recommended part + the governing check (governing_check.md)
```

## Ownership boundary

Python owns the catalogue values, the four-case physics, the gates, and the
final PASS/FAIL ranking. RAG explains **why** a part was chosen, cites the
series datasheet, and states assumptions — it does not compute or override the
numbers.

## Defaults (code)

| Input        | Default                              |
|--------------|--------------------------------------|
| `n_bottom`   | 6                                    |
| `n_wall`     | 4                                    |
| Shock profile| 20 G, 11 ms, sawtooth                |
| `GT_limit`   | 10 G                                 |
| Catalogue    | AUTO = CB1400 + CB1500 + CB1700      |
| Objective    | `max_clearance`                      |

## Series quick reference (choosing catalogue scope)

| Series  | Rope dia | Construction  | Typical use           | Rough load range | Envelope     |
|---------|----------|---------------|-----------------------|------------------|--------------|
| CB61400 | 1/2"     | 6-strand      | Lighter racks, softer | ~150 - 800 kg    | 4" - 7" wide |
| CB1400  | 1/2"     | Standard      | Standard 19" racks    | ~200 - 1000 kg   | 3" - 7" wide |
| CB1500  | 5/8"     | Standard      | Heavy 19" racks       | ~500 - 1800 kg   | 4" - 7" wide |
| CB1700  | 7/8"     | Standard      | Shelter / chassis     | ~800 - 3000 kg   | 6" - 9" wide |

Load ranges are rough guides only — always run the selector against all four
load cases rather than picking by range. CB61400 shares CB1400's envelope but
is ~25 % softer and excluded from AUTO (`cb61400_optional_scope.md`).

## Typical mount configurations

| Rack size           | Typical n_bottom | Typical n_wall | Notes                  |
|---------------------|------------------|----------------|------------------------|
| Single 19" cabinet  | 4                | 4              | 4 corners + 4 wall     |
| 4-bay 35U rack      | 6                | 4              | Reference Excel case   |
| Heavy shelter rack  | 8                | 6              | For > 1500 kg systems  |

## When more than one part passes

The selector returns one recommendation per the objective, but the engineer may
override with a different passing part when:

- **Deflection clearance is tight** — a stiffer part deflects less
  (`max_clearance_objective.md`).
- **Permanent set / fatigue** — a part loaded near its travel limit may degrade
  over many shock cycles (`model_limitations.md`).
- **Standardisation** — reusing a part already qualified on other bays
  simplifies BOM and qualification.

## Hard rules

- **Missing mass is never guessed** — the agent must ASK
  (`missing_input_policy.md`).
- CB61400 is **excluded** from AUTO selection; include it only on explicit
  request (`cb61400_optional_scope.md`).
- If **no** part passes, do not relax a gate silently — report the failure and
  the options (add mounts, move up a series, or re-confirm the shock profile /
  GT limit against the equipment spec).
