# Size Fasteners for a Target SF (Section 2)

The inverse of Section 1: instead of verifying a restraint you already chose, this section
recommends one.

## Inputs

- **"Item weight [kg]"** — the item to secure (default shows the 1,269 kg generator
  example from the workbook).
- **"Mounting surface"** — same three choices and meaning as Section 1 ("Front or rear
  wall", "Floor or ceiling", "Left or right wall"); the surface decides tension vs shear
  per axis.
- **"Target SF"** — the safety factor the arrangement must achieve (default 2.0; the
  MIL-STD-209K design factor is 1.5).

Click **"Recommend fasteners"**.

## Reading the result

- The headline shows the **smallest valid option**: "Smallest valid: <fastener> x<qty>
  (achieved min SF ...)" — the weakest (cheapest) fastener at the lowest quantity that
  still meets your target on every axis.
- The table lists up to six valid options (Fastener, Qty, Achieved min SF) so you can trade
  a stronger fastener against a lower count, or pick a standard size your project already
  stocks.

## Section 1 vs Section 2

- Section 1: "does THIS arrangement pass?" — you supply fastener and quantity.
- Section 2: "WHAT arrangement do I need?" — the tool sweeps the catalog and quantities.

For the same question in chat form, use the "💬 Ask the tie-down assistant" panel:
"How many M12 8.8 bolts to floor-mount a 1269 kg generator at SF 2?"
