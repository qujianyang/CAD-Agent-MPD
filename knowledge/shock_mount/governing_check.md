# Governing Check

**Chunk:** `shock_mount/governing_check`
**Source:** `catalog.py` (`CatalogCandidate.worst_GT_ratio`, `worst_delta_ratio`, `worst_overall_ratio`, `limiting_direction`, `valid`).
**Grounding:** validated-in-repo

---

A part is judged by its **worst** case, not its average. The "governing check"
is the single gate closest to (or over) its limit — the reason a part passes or
fails, and the number to report to the engineer.

## Utilisation ratios

For each case the code computes utilisation as `actual / limit`:

```
GT ratio    = GT_G    / GT_limit
delta ratio = delta_mm / delta_limit_mm
```

Across the four cases:

```
worst_GT_ratio      = max GT ratio    over the 4 cases
worst_delta_ratio   = max delta ratio over the 4 cases
worst_overall_ratio = max( worst_GT_ratio , worst_delta_ratio )
```

A ratio `< 1.0` means pass with margin; `≥ 1.0` means that gate is violated.

## Validity and the limiting direction

```
valid ⇔ all four cases pass  AND  static gate not False
```

The **limiting direction** reported is the case with the highest `GT/limit`
ratio (`limiting_direction` = `max` over cases by GT ratio). That is the case to
quote when explaining "why this part, and how close to the edge."

> Note: `limiting_direction` ranks by **GT** utilisation. If a part is instead
> travel-critical, `worst_delta_ratio` may govern the actual pass/fail even when
> the reported limiting direction is chosen on GT. Report both worst ratios.

## What to report

1. PASS/FAIL and the `worst_overall_ratio` (percent of limit used).
2. The governing case label and whether GT or ΔD drove it.
3. The static-gate status (`static_load_gate.md`).

Example (CB1400-15, 850 kg): governing case Comp-Bottom, GT ratio ≈ 63 % of the
10 G limit, ΔD ratio ≈ 53 % of 35.56 mm — comfortable margin.
