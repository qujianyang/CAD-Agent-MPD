# Objective: max_clearance

**Chunk:** `shock_mount/max_clearance_objective`
**Source:** `catalog.py` (`_objective_sort_key`, `SELECT_OBJECTIVES`, `select_isolator` default `objective="max_clearance"`).
**Grounding:** validated-in-repo

---

`max_clearance` is the **default** selection objective in the code. Among all
parts that pass the four cases and the static gate, it prefers the **stiffest**
(highest `k_comp`).

## Rule (from the sort key)

```
_objective_sort_key("max_clearance") = (not valid, -k_comp_lbin)
```

Valid parts first, then **descending** `k_comp` → the stiffest valid part is
recommended.

## Why stiffest → most clearance

`ΔD = V / (2π·fn)` and `fn` rises with `k`. A **stiffer** spring deflects
**less**, leaving the biggest margin to surrounding structure. Choose this when
installation clearance is the binding constraint (tight racks, close-packed
bays).

## Trade-off vs. isolation

Stiffer also means higher `fn` and therefore higher `GT`
(`transmitted_acceleration.md`) — worse isolation. `max_clearance` deliberately
accepts more transmitted G in exchange for less travel. The opposite objective
is `best_isolation.md`.

## Important: this is the code default, not "softest wins"

Older prose described "prefer the softest valid part" as the default. The
**shipping default is `max_clearance` = stiffest-first**. When explaining a
recommendation, state the objective in force and its consequence:

- `max_clearance` → stiffest valid part → smallest ΔD, highest GT.
- `best_isolation` → softest valid part → lowest GT, largest ΔD.

Both only ever pick from parts that already pass every gate.
