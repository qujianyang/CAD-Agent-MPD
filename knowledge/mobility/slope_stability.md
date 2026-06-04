# Slope Stability — Moment Balance Theory

## Core Formula

```
SF = stabilising_moment / overturning_moment
   = (mg · cosθ · lever_m) / (mg · sinθ · Zcg_m)
   = lever_m / (Zcg_m · tanθ)
```

where:
- θ = slope angle = atan(grade_pct / 100)
- lever_m = moment arm from the downhill axle to the CG (see below)
- Zcg_m = CG height above ground (m)
- g cancels — mass cancels — SF depends only on CG geometry and slope angle

## Moment Arm by Direction

| Direction | Downhill pivot | Lever (mm) |
|---|---|---|
| Ascending | Rear axle | WB − Xcg |
| Descending | Front axle | Xcg |
| Kerbside (tips left) | Left/kerbside axle | track/2 + Ycg |
| Roadside (tips right) | Right/roadside axle | track/2 − Ycg |

Ycg is positive toward driverside (right). If Ycg > 0, kerbside has the larger lever
(more stable kerbside) and roadside has the smaller lever (less stable roadside).

## Critical Tip Angle

The vehicle tips when SF = 1, which gives:
```
θ_crit = atan(lever_m / Zcg_m)
```
This is a geometric property of the CG — independent of the slope being tested.
The vehicle can traverse any slope less than θ_crit without tipping.

## Spinel E2 Measured CG — Verified Values

| Case | Grade | SF | Critical angle |
|---|---|---|---|
| Ascending | 60% (30.96°) | 2.206 | 52.97° |
| Ascending | 50% (26.57°) | 2.651 | 52.97° |
| Descending | 60% | 2.731 | 58.65° |
| Descending | 50% | 3.283 | 58.65° |
| Kerbside | 30% (16.70°) | 2.196 | 33.34° |
| Roadside | 30% | 2.112 | 32.32° |
| Kerbside | 25% | 2.637 | 33.34° |
| Roadside | 25% | 2.531 | 32.32° |

## Required Capability

Minimum requirement: stable at **60% longitudinal** and **30% lateral** grade.
All Spinel E2 cases satisfy SF > 2.1 — large margins above the tipping threshold.
