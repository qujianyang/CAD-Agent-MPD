# Interpreting Mobility Results

This page explains how to read the Mobility tab results and common questions about the
controls. It does not compute numbers — the analysis engine does that.

## Safety factor vs critical tip angle

- A **safety factor (SF)** is dimensionless. Compare it to the target: SF ≥ 1 means the
  vehicle will not tip; higher is safer. The OEM recommended margin is the higher bar the
  verdict checks against.
- A **critical tip angle** is in degrees. Compare it to the slope angle, not to the SF.
- Never compare a safety factor to an angle — they are different quantities and are reported
  separately.

## Verdict labels

Each case is judged against the OEM recommended margin and shown as one of:

- **MEETS RECOMMENDED MARGIN** — at or above the recommended margin. Good.
- **STABLE, BELOW RECOMMENDED MARGIN** — will not tip (SF ≥ 1) but below the recommended
  margin. Acceptable with caution; review the case.
- **UNSTABLE** — below the structural limit; the case fails and must be addressed.

The overall verdict is the worst case: if any case is UNSTABLE the overall is UNSTABLE;
otherwise if any is BELOW the overall is BELOW; otherwise it MEETS.

## OEM recommended margins

The OEM recommended margins are the thresholds the verdict compares against. Raising a margin
makes the verdict stricter (more cases fall into "below recommended"); it does not change the
computed safety factor, only how it is judged.

## Why is "Run Analysis" disabled?

"Run Analysis" is disabled until a vehicle scenario is built. Its tooltip says "Build a
scenario in step 1 first." Complete step 1: pick a "Vehicle source" and load (workbook),
derive (wheel-load — remember Zcg is required), or build (modification / certified) the
vehicle. Once a vehicle exists, the button enables.

## Getting the actual numbers

For real safety-factor numbers, use "Run Analysis", or ask the engineering "Ask the mobility
assistant" panel a question such as "Which mobility cases are below SF 2.2?" or "Is the
measured Spinel stable on a 60% slope?"
