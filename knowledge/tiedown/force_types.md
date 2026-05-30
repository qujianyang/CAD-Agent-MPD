# Mount Face -> Tension vs Shear

The face an item is fastened to decides, per load axis, whether each fastener is
loaded in TENSION (pulled straight out) or SHEAR (sideways). Tensile capacity is
`sigma_t * area`; shear capacity is `sigma_s * area`.

| Mount face (normal) | Longitudinal (X) | Vertical (Z) | Lateral (Y) |
|---|---|---|---|
| Front / rear wall (X) | Tensile | Shear | Shear |
| Floor / ceiling / top / base (Z) | Shear | Tensile | Shear |
| Left / right side wall (Y) | Shear | Shear | Tensile |

Rule: the load axis whose direction is normal to the mounting face is the TENSILE
axis; the other two axes are SHEAR.
