# Transmitted-G Limit (10 G)

**Chunk:** `shock_mount/transmitted_g_limit`
**Grounding:** HYBRID — the default value and its use are grounded in code; the ORIGIN is AWAITING SOURCE.
**Source:** code = `physics_engine.py` (`ShockEnv.GT_limit_G = 10.0`, `DirectionResult.GT_ok`); origin = `[SOURCE NEEDED].`

---

The transmitted-G limit is the acceptance threshold that the computed `GT` is
compared against in every load case.

## Grounded (code)

```
GT_limit default = 10 G          (ShockEnv.GT_limit_G = 10.0)
PASS (case)      ⇔  GT < GT_limit        (strict inequality)
```

It is the equipment-protection threshold, distinct from the **input** shock
magnitude `Ao` (20 G). Confusing the input 20 G with the transmitted limit 10 G
is a classic error — they are different quantities (`transmitted_acceleration.md`).

## Confirmed: the limit is not part of MIL-STD-810

MIL-STD-810H Table 516.8-IV (verified 2026-07-14) defines default **input**
pulses only; Method 516.8 sets no transmitted-acceleration acceptance value.
The 10 G limit therefore comes from the equipment/customer side, consistent
with the VMC Tech Notes describing shock output tolerance as the equipment's
"fragility".

## [SOURCE NEEDED] Origin of the 10 G limit

<!-- Fill from the equipment/customer fragility document or project spec. -->
- Is 10 G a **customer/equipment fragility limit**, not part of the military
  standard? `[FILL]`
- Which equipment sets it (electronics / displays / other) and its documented
  fragility level: `[FILL]`
- Whether it is a single global limit or varies by protected item: `[FILL]`
- Is `<` (strict) vs `≤` the intended acceptance boundary per the spec? (code
  uses strict `<`): `[FILL]`

## Provide

- The equipment/customer acceleration (fragility) limit document.
- Any project requirement fixing the transmitted-G acceptance value.

## If no part meets the limit

Do not silently relax it. Report the failure; relaxing `GT_limit` is valid only
if the protected equipment's spec actually permits a higher level — confirm,
don't guess (`selection_workflow.md`, `missing_input_policy.md`).

**Retrieval distractor to preserve:** input acceleration (20 G) vs. transmitted
acceleration limit (10 G).
