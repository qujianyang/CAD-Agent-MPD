# Weights, Mounts and Catalog Filter

## The two weight inputs

- **"Equipment weight [kg]"** — the network gear / payload mounted on the shelf.
- **"Rack / chassis weight [kg]"** — the frame / enclosure weight.

The tool adds them: total system mass **M = equipment + rack**, and distributes M/n across
the mounts. If you only know the combined weight, put it all in one field and leave the
other at 0.

## Mount configuration

- **"n_bottom (bottom mounts)"** — isolators under the base (compression orientation).
- **"n_wall (wall mounts)"** — isolators on the wall face (shear orientation).

Both default to the typical 6 bottom + 4 wall arrangement. The four load cases check the
compression and shear behaviour of both groups.

## Catalog filter (Auto mode only)

Restricts which series are searched:

- "All series (CB1400 + CB1500 + CB1700)" — the default search space.
- "CB1400 (1/2\" wire)" / "CB1500 (5/8\" wire)" / "CB1700 (7/8\" wire)" — one series only.
- "All incl. CB61400 (6-strand softer, opt-in)" — adds the softer 6-strand series to the
  search. It is opt-in because the softer wire gives better isolation but larger deflection.
- "CB61400 only (6-strand 1/2\" wire)" — search just the 6-strand series.

## Select part to verify (Manual mode only)

A dropdown of every part across all catalogs. Pick the exact part number you want checked;
the result is the same 4-case table the Auto mode shows for its recommendation.
