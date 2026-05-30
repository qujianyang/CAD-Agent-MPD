# Tie-Down Selection and Pass Rules

Per fastener, per axis: `SF = yield_force(force_type) / (design_force_axis / qty)`,
where the force type (tension or shear) comes from the mount face.

An item PASSES when its minimum SF across the three axes is >= the target
(default 1.0 = no yield at the ultimate transport load).

Active sizing ("smallest valid fastener"): for a target SF, the minimum quantity is
`ceil( max over axes of [ target_SF * design_axis / yield_force(force_type) ] )`.
Among options meeting the target, prefer the fewest fasteners, then the smallest real
bolt (straps carry a sentinel area = 1 and must not count as the "smallest").

The reference workbook is conservative: many items are bolted far above SF = 1
(e.g. the 1269 kg generator uses 10 x M12 giving SF 4.9, where 3 x M10 already
meets SF 1.0).
