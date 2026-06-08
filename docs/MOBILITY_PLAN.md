# Mobility Pillar — Implementation Plan

Mirror of the tie-down pillar. Source workbook (NOT committed, defence data):
`C:\Users\qujia\Downloads\Spinel -E2 Measured CG in FIT_13-5-2026_Turning Radius R_Final 1.xls`
Override path via env `MOBILITY_XLS`.

Sheets that matter:
- `E2 Measured CG` (73x13)        -> CG inputs + Z-CG tilt-test method
- `E2 Measured Mobility Analysis` -> all 5 modules, MEASURED CG
- `E2 Theory Mobility Analysis`   -> same layout, THEORY CG
- `E2 CG Table` (2018 rows)        -> per-item CG buildup (optional, later)

All formulas VERIFIED against stored cells (see "Verified anchors" below).

---

## Architecture (one file per tie-down counterpart)

| Tie-down file            | Mobility file              | Role |
|--------------------------|----------------------------|------|
| tiedown_engine.py        | mobility_engine.py         | physics + dataclasses + analyze + format |
| fastener_catalog.py      | (none / inline params)     | mobility has no catalog; slope grades are constants |
| tiedown_import.py        | mobility_import.py         | read yellow-input cells -> Vehicle; read stored SFs |
| validate_tiedown_excel.py| validate_mobility_excel.py | engine vs stored cells (proof harness) |
| tiedown_tools.py         | mobility_tools.py          | LangChain tools |
| tiedown_report.py        | mobility_report.py         | SAR Mobility/Stability chapter generator |
| test_tiedown_*.py        | test_mobility_*.py         | unit tests |
| knowledge/tiedown/*.md   | knowledge/mobility/*.md    | RAG docs |
| app.py Tie-Down tab      | app.py Mobility tab        | UI |
| agent.py "tiedown" domain| agent.py "mobility" domain | tab-routed specialist |

---

## PHASE 1 — mobility_engine.py  (do first, no deps)

### Dataclasses
```
@dataclass
class Vehicle:
    name: str
    gw_kg: float            # gross weight
    xcg_mm: float           # CG from FRONT axle (longitudinal)
    ycg_mm: float           # CG from vehicle centreline (lateral, +driverside)
    zcg_mm: float           # CG above ground
    wheelbase_mm: float
    track_mm: float
    rstat_mm: float = 580.0  # static tyre radius (CG calc only)
    front_axle_limit_kg: float = 8000.0
    rear_axle_limit_kg: float = 10600.0
    gvw_limit_kg: float = 18600.0

@dataclass
class Aero:                 # for cornering + variable-slope modules
    air_density: float = 1.18      # kg/m3
    cd: float = 1.0                # drag coefficient
    front_area_m2: float = 9.0     # MPFA front (L x H)
    side_area_m2: float = 35.52    # MPFA side
    wind_height_m: float = 2.05    # height wind force acts

G = 9.81
```

### Functions (each returns a small result dataclass with .SF where applicable)

1. `axle_loads(v) -> AxleResult`
   front_kg = gw * (wheelbase - xcg) / wheelbase
   rear_kg  = gw - front_kg
   front_pct = front_kg / gw * 100
   driverside_kg / kerbside_kg from ycg about track (see anchors)
   pass = front<=front_limit and rear<=rear_limit and gw<=gvw_limit

2. `steerability(v, min_front_pct=25.0) -> bool/result`
   pass = front_pct >= min_front_pct   # bodybuilder guideline

3. `slope_stability(v, grade_pct, direction) -> SlopeResult`
   direction in {"ascending","descending"}
   theta = atan(grade_pct/100)
   lever_mm = (wheelbase - xcg) if ascending else xcg     # moment arm to downhill axle
   stab = G*gw*cos(theta)*lever_mm/1000
   over = G*gw*sin(theta)*zcg_mm/1000
   SF   = stab/over
   crit_angle_deg = degrees(atan(lever_mm/zcg_mm))

4. `side_slope_stability(v, grade_pct, side) -> SlopeResult`
   side in {"kerbside","roadside"}   # kerbside uses +Y, roadside uses -Y (driverside)
   theta = atan(grade_pct/100)
   lever_mm = track/2 + ycg  (kerbside)  OR  track/2 - ycg (roadside)
   stab = G*gw*cos(theta)*lever_mm/1000
   over = G*gw*sin(theta)*zcg_mm/1000
   SF   = stab/over
   crit_angle_deg = degrees(atan(lever_mm/zcg_mm))

5. `cornering_stability(v, aero, speed_kmh, radius_m, wind_kmh) -> CornerResult`
   S = speed_kmh/3.6
   Fc = S**2 / radius_m * gw                      # centrifugal (N)  [GW in kg -> already N? see anchor: Fc=28172 with gw=17850 => uses kg as mass, /1000? check]
   over_fc   = Fc * zcg_mm/1000
   Vw = wind_kmh/3.6
   Fw = 0.5*air_density*cd*Vw**2 * front_area_m2   # wind force (N)
   over_wind = Fw * wind_height_m
   over_total= over_fc + over_wind
   yprime_m  = (track/2 - |ycg|)/1000  if turning toward less-stable side  (use min lever)
   resist    = gw * G * yprime_m
   SF = resist / over_total

6. `mobility_summary(v, aero, ...) -> MobilityReport`  # runs all modules, collects SFs + verdicts

### Formatters
- `format_mobility_report(report)`  -> console table (like format_report)
- `format_slope_table(report)`      -> grade vs SF grid (ascending/descending/side)

### Pass criterion
Configurable `min_SF` (default 1.0 for "won't tip"; the SAR may require >1).
Required slope capability: stable at 60% longitudinal + 30% side (mil test-track spec).
Keep `standard` a string param (e.g. "AVTP / Def Stan") like tie-down's MIL-STD-209K.

---

## PHASE 2 — mobility_import.py

`xlrd.open_workbook(path)` (legacy .xls; xlrd 2.0.2 already installed).
- `vehicle_from_sheet(sheet)` -> read the labelled input cells:
    GW, Xcg, Ycg, Zcg, WB, track, axle limits.
  Measured-CG values live on `E2 Measured CG` D9..D12 (GW,X,Y,Z) and D6/D7/D8 (WB,track,Rstat).
  Theory-CG values: pull from the `E2 Theory Mobility Analysis` C-block header (C6/D6/E6/F6).
- `stored_sf_map(sheet)` -> dict of {label: stored_SF_cell} for validation
  (e.g. ascending60 = AA17, side30 = AK17, cornering = BH71/CI71...).
- `import_measured(path)` / `import_theory(path)` -> (Vehicle, stored_sf_map)

KEEP cell refs in a CONSTANTS block at top so they're easy to fix if the sheet shifts.

---

## PHASE 3 — validate_mobility_excel.py  (the "177/177" proof)

For both Measured and Theory:
  run engine -> compare every SF/axle-load against stored_sf_map to < 1e-3 (sheet rounds).
Print per-row diff table, total pass count e.g. "34/34".
This is the headline credibility number for the report.

---

## PHASE 4 — tests
- test_mobility_engine.py : anchor each module to the verified numbers below.
- test_mobility_import.py : Vehicle fields match known inputs.
- test_mobility_report.py : section headings, table numbers, pass/fail prose.

---

## PHASE 5 — mobility_report.py
`generate_mobility_chapter(report, *, project, variant, standard) -> str` (Markdown):
  H.1 Scope & basis (CG inputs, slope/cornering criteria, standard)
  H.2 Axle loadings & steerability (table + limit checks)
  H.3 Static slope stability (grade vs SF grid + critical angles)
  H.4 Cornering stability (Fc, wind, safe speed, SF)
  H.5 Assessment (governing case, pass/fail vs required slope capability)
Deterministic: numbers from engine only, LLM never in numeric path (same rule as tie-down).

---

## PHASE 6 — mobility_tools.py + agent.py domain
Tools (LangChain, parent_topic="mobility", OMIT rule):
  - run_mobility_check(path|measured/theory) -> summary + governing case
  - slope_limit(vehicle params) -> max stable grade per direction
  - cornering_speed_limit(radius, wind) -> max safe speed for SF>=1
  - flag_unstable(min_SF) -> cases below target  (RETURN full context: case, SF, lever, Z -- learn from tie-down's flag_critical_items gap)
Register in agent.py DOMAINS = {... "mobility": {"prompt": _MOBILITY_PROMPT, "tools": _MOBILITY_TOOLS}}.

---

## PHASE 7 — knowledge/mobility/*.md  (RAG)
- slope_stability.md   : moment-balance theory, grade->angle, critical angle
- cornering.md         : centrifugal + wind moment, safe speed
- axle_loading.md      : front/rear from CG, axle/GVW limits, 25% steerability rule
- mobility_standard.md : the test-track / mil requirement (60% long, 30% side)
Then re-run setup_knowledge.py to re-embed (will go from 9 -> ~13 chunks).

---

## PHASE 8 — app.py Mobility tab
Sections (mirror tie-down tab):
  1. Vehicle inputs (GW, Xcg, Ycg, Zcg, WB, track) OR load from workbook (measured/theory toggle)
  2. Slope stability grid (ascending/descending/side) with SF + critical angle
  3. Cornering calculator (speed/radius/wind sliders -> SF, safe speed)
  4. Generate Mobility chapter (preview + download .md/.txt)
  5. Mobility assistant chat (domain="mobility")

---

## Verified anchors (use as test asserts) -- MEASURED CG

Inputs: GW=17850, Xcg=2655.4622, Ycg=20.4706, Zcg=1617.8285, WB=4800, track=2088.

- Front axle load = 7975.0 kg           (GW*(4800-2655.46)/4800)
- Rear axle load  = 9875.0 kg
- Front axle %    = 44.678 %
- Ascending 60% : stab=321826.47 Nm, over=145897.19 Nm, SF=2.2058, crit=52.969 deg
- Descending 60%: SF=2.7314  (lever=Xcg)
- Side 30% kerbside: stab=178569.14, over=81305.81, SF=2.1963, crit=33.343 deg
- Side 30% roadside: SF=2.1118  (lever=track/2 - Y)
- Ascending 50% : SF=2.6511     (grade 50% -> 26.56 deg, cos0.894 sin0.447)
- Cornering @15km/h, R=11m, wind 60km/h: Fc=28172.35 N, over_fc=45578.03 Nm, SF=2.051

NOTE on Fc units: sheet uses Fc = S^2/R * GW with GW in kg and result called "N";
S=4.1667 m/s -> 17.361/11*17850 = 28172. So mass is kg and g is folded later via Z lever.
Confirm exact moment convention when coding (anchor over_fc=45578 nails it).

## Verified anchors -- THEORY CG
Pull Theory Xcg/Ycg/Zcg from `E2 Theory Mobility Analysis` C6:F6 and assert its
own stored SFs (lower block of same sheet). Same formulas.

---

## Execution order
1. mobility_engine.py + test_mobility_engine.py  (TDD against anchors)  <- START HERE
2. mobility_import.py + test_mobility_import.py
3. validate_mobility_excel.py  -> confirm NN/NN
4. mobility_report.py + test
5. mobility_tools.py + agent.py domain + knowledge docs + re-embed
6. app.py Mobility tab
7. commit per phase on branch (new branch: mobility-pillar off main after tie-down merges)
