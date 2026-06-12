# Design / Modification Study Workflow

Use the **Design / modification study** vehicle source to assess the effect of changing the
vehicle — for example fitting a roof-mounted component, removing a stowage box, or moving
equipment.

## How it works

You start from a workbook baseline, then list changes in the modifications table. The tab
recomputes the combined weight and CG, and can show the delta against the baseline so you can
see how far the CG moved.

## The coordinate datum

All component coordinates use the vehicle datum:

- **X** — measured from the front axle, positive rearward.
- **Y** — measured from the centreline, positive to the right.
- **Z** — measured from the ground, positive upward.

A roof-mounted item therefore has a large positive Z, which raises the CG height and reduces
slope and cornering margins.

## The three actions

Each row in the modifications table has an "Action":

- **add** — add a new component. Provide its mass and its New X / Y / Z position.
- **remove** — remove an existing component. Provide its mass and its Old X / Y / Z position.
- **relocate** — move a component. Provide both Old and New X / Y / Z; the mass is unchanged.

Fill in the mass and the coordinates each action needs, then build the modified vehicle.

## After building

Once the modified vehicle is built, "Run Analysis" becomes enabled. To analyse a new
roof-mounted component, add it as an **add** row with its mass and roof position (high Z),
build, then run the analysis to see the new safety factors.
