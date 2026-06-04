# Axle Loading and Steerability

## Longitudinal Axle Loads

Taking moments about the rear axle:
```
Front axle load = GW × (WB − Xcg) / WB
Rear axle load  = GW − Front
```
- Xcg measured from the FRONT axle (mm)
- WB = wheelbase (mm)

## Lateral Axle Loads

Taking moments about the kerbside axle:
```
Driverside load = GW × (track/2 + Ycg) / track
Kerbside load   = GW − Driverside
```
- Ycg measured from centreline, positive toward driverside

## Axle Limits (Spinel E2)

| Axle | Limit | Measured load | Status |
|---|---|---|---|
| Front | 8,000 kg | 7,975 kg | OK |
| Rear | 10,600 kg | 9,875 kg | OK |
| GVW | 18,600 kg | 17,850 kg | OK |

## Steerability Requirement

The front axle must carry at least **25% of GVW** (bodybuilder guideline):
```
Front axle % = (Front load / GW) × 100% >= 25%
```
Spinel E2 Measured CG: 44.68% → satisfactory.

If Xcg moves rearward significantly, front axle load drops. If front axle load
falls below 25%, the vehicle loses steering authority — even though the rear
axle limits are met.

## Effect of CG Position

| CG change | Effect |
|---|---|
| Xcg moves rearward | Less front load → risk of front axle under 25% |
| Xcg moves forward | More front load → risk of front axle over 8,000 kg |
| Zcg increases (taller CG) | All slope and cornering SFs decrease |
| Zcg decreases (lower CG) | All slope and cornering SFs increase |
| Ycg offset increases | One side of lateral slope becomes less stable |
