# Design / Modification Study Workflow

Use the **Design / modification study** vehicle source to assess the effect of changing the
vehicle — for example fitting a roof-mounted component, removing a stowage box, or moving
equipment.

## The workflow

Load baseline → review/search existing components → select a component → relocate, remove
or add → apply changes → new mass, CG, axle loads and stability.

1. **Baseline summary** — once the workbook loads, the top row shows the number of existing
   components, the total shelter mass, and the baseline GW and CG.
2. **"Existing baseline components (69)"** expander — a read-only, scrollable list of every
   baseline component from the workbook's CG table. Use **"Search by description"** and
   **"Filter by subsystem"** (Shelter Structure, Wet Cabin, Dry Cabin, Antenna, Rack &
   Cabin Electrical Control) to find an item. The list cannot be edited, so the baseline
   cannot be changed by accident.
3. **Select a row** — a "Selected: …" line appears with the component's mass and position,
   plus two buttons: **"Relocate component"** and **"Remove component"**. Pressing either
   copies the component into the Proposed changes table with its existing (Old) position
   prefilled. For a relocate, type the New X/Y/Z; a remove needs nothing more.
4. **"Proposed changes"** table — the only editable table. It holds just your changes, never
   the baseline. To **add** a brand-new component, type a row directly (Action=add, mass,
   New X/Y/Z). The caption shows how many pending changes are valid; **"Clear all"** empties
   the table.
5. **"Apply changes and recalculate"** — builds the modified vehicle. The Derived Vehicle
   panel then shows the new GW/CG with deltas against the baseline, and "Run Analysis"
   recomputes axle loads and stability.

## The coordinate datum (design datum O)

All coordinates in this section — the component list AND the changes table — use the
**design datum**:

- **X** — measured rearward from the **front ISO twist-lock plane**.
- **Y** — measured from the shelter centreline, positive to the right.
- **Z** — measured from the ground, positive upward.

The app converts X internally to the front-axle **analysis datum** before computing axle
loads and slopes: `X_axle = X_ISO + 1450 mm`. You never enter front-axle X yourself.

Note when cross-checking against the raw Excel CG table: the workbook stores components in
the **shelter frame** datum (X from the shelter front surface, Z from the shelter bottom).
The list shows those values already converted to the design datum, so they differ from the
raw spreadsheet by a fixed offset: X is 101.5 mm smaller (ISO corner inset) and Z is
1593 mm larger (shelter bottom height above ground). Example: Generator 1 is X=2320 /
Z=424 in the Excel but X=2218.5 / Z=2017.1 here.

After a calculation the Derived Vehicle panel shows the combined Xcg in **both** datums —
e.g. 2,655.5 mm from the front axle (analysis) = 1,205.5 mm from the front ISO plane
(design) — plus a "CG datum label" expander that prints the datum-O definition and the
combined CG coordinates for drawings and reports.

A roof-mounted item has a large positive Z, which raises the CG height and reduces slope
and cornering margins.
