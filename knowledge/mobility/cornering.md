# Cornering Stability

## Physics

A vehicle turning at speed generates centrifugal force Fc that, combined with
wind force Fw, creates an overturning moment. The resisting moment comes from the
vehicle weight acting through the lateral CG offset.

### Centrifugal Force
```
Fc = S² / R × GW    (N)
```
- S = vehicle speed (m/s) = km/h / 3.6
- R = turning radius (m)
- GW = gross weight (kg)  [× g is absorbed into the moment arm]

### Overturning Moment
```
M_over = Fc × Zcg_m + Fw × h
```
- Zcg_m = CG height above ground (m)
- Fw = 0.5 × ρ × Cd × V_wind² × A_side  (wind force, N)
- h = wind force height (2.05 m for Spinel E2)
- ρ = 1.18 kg/m³, Cd = 1.0, A_side = 35.52 m²

### Resisting Moment
```
M_resist = GW × g × Y'_m    (Nm)
```
- Y'_m = critical lateral lever = min(track/2 + Ycg, track/2 − Ycg) / 1000
- The SMALLER side governs — vehicle with Ycg toward driverside is less stable
  turning LEFT (kerbside turn).

### Safety Factor
```
SF = M_resist / M_over
   = (GW × g × Y') / (Fc × Zcg + Fw × h)
```

### Maximum Safe Speed
At SF = 1, solving for S:
```
Fc_crit = (GW × g × Y' − Fw × h) / Zcg_m
S_max = sqrt(Fc_crit × R / GW)    (m/s)
max_speed_kmh = S_max × 3.6
```

## Spinel E2 Measured CG — Verified Values

At 15 km/h, R = 11 m (minimum turning radius), wind = 60 km/h:
- Fc = 28,172 N
- Overturning (Fc) = 45,578 Nm
- Wind force Fw = 5,821 N
- Overturning (wind) = 11,934 Nm
- Total overturning = 57,512 Nm
- Resisting moment = 179,229 Nm
- **SF = 3.116**
- Y' = 1023.5 mm (track/2 − Ycg, left turn is less stable)

## Key Insight

Cornering SF increases with speed reduction (Fc drops as S²). The SF = 3.1 at 15 km/h
means the vehicle could corner at ~3× the centrifugal force before tipping — very
stable. The dominant concern at 15 km/h is actually wind load, not centrifugal force.
