# Tie-Down Tab — Overview

The Tie-Down tab checks cargo restraint per MIL-STD-209K: design loads of 4G longitudinal,
2G vertical and 1.5G lateral (g = 9.81). The engine is validated against the MCDLL workbook
(177/177 safety factors reproduced). This page explains how to operate the tab; the
calculations are done by the section buttons and the "💬 Ask the tie-down assistant" panel.

## The three sections

1. **"1. Check one item"** — verify whether a specific item + fastener + quantity passes a
   target safety factor. Use when you already have a proposed restraint and want a verdict.
2. **"2. Size fasteners for a target SF"** — the inverse: you give the weight, surface and
   target SF, and the tool recommends the smallest valid fastener and quantity.
3. **"3. Generate the Appendix G report section"** — runs the whole workbook and drafts the
   SAR Appendix G section (scope, MIL-STD-209K basis, results table, pass/fail assessment).
   Every number comes from the validated engine — no AI in the numbers.

## Which section should I use?

- "Does my 4-bolt M8 arrangement hold this 60 kg box?" → **Section 1**.
- "How many bolts (and what size) do I need for this generator?" → **Section 2**.
- "I need the report chapter for the whole vehicle." → **Section 3**.

## Two assistants, different jobs

- **🧭 Tie-Down UI Guide** (this assistant) — explains how to operate the tab. It never
  computes safety factors.
- **💬 Ask the tie-down assistant** — the engineering agent with the validated tools, e.g.
  "how many M12 bolts to floor-mount a 1269 kg generator at SF 2?"
