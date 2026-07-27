# Vendor Effective Configuration Count Is Not Physical Mount Count

**Chunk:** `shock_mount/vendor_effective_configuration_count`
**Sources:** SRC-SIM-01 and SRC-SIM-02
**Grounding:** vendor calculation-sheet fields; derivation not supplied

---

Two supplied nonlinear SDOF calculation sheets contain a field labelled
`number` that does not equal the physical isolator count:

| Physical arrangement | Physical total | Vendor `number` field |
|---|---:|---:|
| 4 bottom + 2 stabilizers, CB1390-30 | 6 | 4.66 |
| 6 bottom + 2 stabilizers, CB1390-20 | 8 | 6.66 |

The supplied sheets do not explain how `4.66` or `6.66` is derived. Treat it as
a supplier-specific effective configuration input to the nonlinear SDOF model,
not as a fractional physical mount count.

## Assistant rule

- Never enter `4.66` or `6.66` as `n_bottom`, `n_wall`, or total mount count.
- Use the actual drawing or stated arrangement for physical counts.
- If reproducing or reviewing the supplier simulation, ask the supplier to
  define the field, derivation, orientation assumptions, and load-sharing
  method.
- Keep the project engine's four-case mass distribution separate from this
  undocumented vendor factor.
