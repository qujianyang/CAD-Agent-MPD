# Verification Workflow

**Chunk:** `shock_mount/verification_workflow`
**Source:** `physics_engine.py` (`run_analysis` with an explicit `isolator=`), `catalog.py` (`to_isolator_spec`), `agent.py` shock analysis tool.
**Grounding:** validated-in-repo

---

Use this workflow when the engineer already has a specific part in mind and
wants to **check** it — as opposed to asking the tool to pick one
(`selection_workflow.md`).

## Select vs. verify — which to use

| Situation                                             | Workflow                |
|-------------------------------------------------------|-------------------------|
| "Which isolator should I use for this rack?"          | Selection               |
| "Does CB1400-15 pass at 850 kg on 6+4?"               | Verification            |
| "Is the part already used on the other bays adequate?"| Verification            |
| "Give me the softest / tightest-clearance option"     | Selection (+ objective) |

## Pipeline

```
Receive mass M + the named part
  -> confirm mount configuration (n_bottom, n_wall)
  -> confirm shock profile and GT limit
  -> load the part's spec (k_comp, k_shear, d_max_comp, d_max_shear,
     Max Static F) from the catalogue
  -> run the four load cases against THAT part only
  -> apply static / GT / travel gates
  -> report PASS/FAIL + the governing check (governing_check.md)
```

## What verification returns

- Per-case `GT` and `ΔD` with their limits and OK/FAIL flags.
- The static-gate result (or an "unrated — verify" warning for parts without a
  published Max Static F).
- The governing case and worst utilisation ratios.

Verification does **not** search for alternatives. If the named part fails,
report it plainly and suggest switching to the selection workflow rather than
silently substituting a different part.
