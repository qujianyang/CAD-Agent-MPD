# Objective: best_isolation

**Chunk:** `shock_mount/best_isolation_objective`
**Source:** `catalog.py` (`_objective_sort_key`, `SELECT_OBJECTIVES`).
**Grounding:** validated-in-repo

---

`best_isolation` selects the **softest** valid part (lowest `k_comp`) to minimise
transmitted G. It is the non-default objective; request it explicitly.

## Rule (from the sort key)

```
_objective_sort_key("best_isolation") = (not valid, k_comp_lbin)
```

Valid parts first, then **ascending** `k_comp` → the softest valid part is
recommended.

## Why softest → lowest transmitted G

`GT = V·√(k/m)/g` rises monotonically with `k`. The softest spring gives the
lowest `fn` and therefore the lowest `GT` — best protection for fragile
equipment (`transmitted_acceleration.md`).

## Trade-off vs. clearance

Softer means larger `ΔD` (`dynamic_deflection.md`). The `travel_limit_gate.md`
still applies, so `best_isolation` cannot pick a part that would bottom out or
collide — it picks the softest part that **still** clears travel and clearance.

## Choosing between objectives

| Constraint that binds        | Objective       |
|------------------------------|-----------------|
| Tight installation clearance | `max_clearance` |
| Fragile / low-G equipment    | `best_isolation`|

Both draw only from parts that pass every gate; the objective is a tiebreak, not
a gate override.
