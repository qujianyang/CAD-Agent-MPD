# Design / Modification Study Workflow

Use the **Design / modification study** vehicle source to assess the effect of changing the
vehicle — for example fitting a roof-mounted component, removing a stowage box, or moving
equipment.

## How it works

You start from a workbook baseline, then list changes in the modifications table. The tab
recomputes the combined weight and CG, and can show the delta against the baseline so you can
see how far the CG moved.

## The coordinate datum (design datum O)

Component coordinates in the table use the **design datum**:

- **X** — measured rearward from the **front ISO twist-lock plane** ("front ISO plane",
  the plane through both front twist-locks).
- **Y** — measured from the shelter centreline, positive to the right.
- **Z** — measured from the ground, positive upward.

The app converts X internally to the front-axle **analysis datum** before computing axle
loads and slopes: `X_axle = X_ISO + 1450 mm` (front axle to front ISO plane, per the E2
report). You never enter front-axle X yourself.

After a calculation the Derived Vehicle panel shows the combined Xcg in **both** datums —
e.g. 2,655.5 mm from the front axle (analysis) = 1,205.5 mm from the front ISO plane
(design) — plus a "CG datum label" expander that prints the datum-O definition and the
combined CG coordinates for drawings and reports.

A roof-mounted item has a large positive Z, which raises the CG height and reduces slope
and cornering margins.

## The three actions

Each row in the modifications table has an "Action":

- **add** — add a new component. Provide its mass and its **New X from front ISO (mm)** /
  **New Y from centreline (mm, +right)** / **New Z from ground (mm)**.
- **remove** — remove an existing component. Provide its mass and its Old X / Y / Z
  (same column naming).
- **relocate** — move a component. Provide both Old and New X / Y / Z; the mass is unchanged.

Fill in the mass and the coordinates each action needs, then build the modified vehicle.

## After building

Once the modified vehicle is built, "Run Analysis" becomes enabled. To analyse a new
roof-mounted component, add it as an **add** row with its mass and roof position (high Z),
build, then run the analysis to see the new safety factors.
