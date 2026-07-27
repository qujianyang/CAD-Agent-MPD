# Shock-Mount Supplier Study and Mechanical Research Direction

**Project:** CAD-Aware AI Assistant - Shock Isolator Selection
**Date:** 19 July 2026
**Status:** Working research note for supervisor and company discussion

## 1. Purpose

This document consolidates the current discussion about:

- differences between the VMC, Vibratec and Socitec wire-rope isolator data;
- why the current project will focus on VMC for detailed calculations;
- the limitations of the existing shock-isolation model;
- how an installed shock-isolator system should be validated;
- possible mechanical research directions related to the supervisor's interests;
- experiments that are realistic within an undergraduate project; and
- information that must be obtained before the mechanical topic is frozen.

The mechanical research direction is not yet frozen. One important decision remains:

> Should the study improve the isolation performance of the wire-rope isolator, or optimise the mounting bracket and interface structure?

These are different engineering problems and must not be presented as equivalent.

## 2. Current Company Problem

Wire-rope isolators are installed between a server rack and its supporting structure to reduce the acceleration transmitted into the rack during movement or shock. The current selection workflow uses rack mass, mount count, mounting orientation, shock pulse and equipment fragility to select a suitable catalogue isolator.

The present simplified calculation evaluates:

1. static load capacity;
2. isolator natural frequency;
3. transmitted acceleration;
4. dynamic displacement;
5. available travel and installation clearance; and
6. four directional loading cases.

The current model treats the rack as a rigid body and each load case as a single-degree-of-freedom spring-mass system. It uses an average directional stiffness rather than modelling the wire strands, cable friction or complete nonlinear load-deflection loop.

## 3. Supplier Data Comparison

ST Engineering considers wire-rope isolators from VMC, Vibratec and Socitec. Their products perform a similar general function, but their catalogues describe performance differently. The data must therefore be normalised before products can be compared using one calculation method.

The common engineering fields required by the project are:

- compression stiffness;
- shear stiffness;
- maximum static load;
- maximum dynamic travel;
- physical dimensions;
- mounting orientation; and
- data provenance and validation level.

### 3.1 Main Difference in Published Performance Data

| Supplier | Main published input | Conversion used by the project | Confidence for shock analysis |
|---|---|---|---|
| VMC | Shock Average K and Vibration Average K | Use the appropriate published K directly | Highest compatibility with the present method |
| Vibratec | Rated supported mass at 10 Hz | Derive K = m(2*pi*f)^2 | Screening estimate unless shock data are obtained |
| Socitec | Maximum shock force and corresponding deflection | Derive secant K = F/delta | Screening estimate unless the complete curve or equivalence is confirmed |

These three forms of stiffness must not be described as equally validated.

### 3.2 VMC

VMC publishes direction-specific values for compression, 45-degree compression/roll and shear/roll. The reviewed CB-series data include separate Shock Average K and Vibration Average K values.

For shock calculations, the project uses:

```text
fn = (1 / 2*pi) * sqrt(Kshock / m)
```

The Vibration Average K must be used for vibration calculations. It should not be substituted with Shock Average K because a wire-rope isolator is nonlinear and its effective stiffness depends on displacement amplitude and operating point.

VMC data are the most directly compatible with the current deterministic shock engine. However, static-load limits and mounting details still need part-specific confirmation where they are not stated in the reviewed sheet.

### 3.3 Vibratec

Vibratec WRI tables provide the supported mass at a stated natural frequency, normally 10 Hz, instead of publishing a shock-average stiffness.

An equivalent stiffness can be estimated using:

```text
Kderived = mrated * (2*pi*10)^2
```

The natural frequency at another supported mass can then be estimated as:

```text
fn,estimated = 10 * sqrt(mrated / mactual)
```

For the A060146-059-XX example:

| Direction | Rated load at 10 Hz | Approximate derived stiffness |
|---|---:|---:|
| Compression | 35 kg | 138.2 N/mm |
| 45-degree compression/roll | 21 kg | 82.9 N/mm |
| Shear/roll | 5.6 kg | 22.1 N/mm |

The same model lists a maximum static compression load of 44 kg and maximum compression travel of 32 mm.

This is useful for preliminary screening, but the 10 Hz rating is not explicitly the same quantity as VMC Shock Average K. Supplier shock data or a force-displacement curve should be obtained before final shock qualification.

### 3.4 Socitec

Socitec publishes maximum static force, maximum shock force and shock deflection for several Helical wire-rope isolators. An approximate secant stiffness can be calculated using:

```text
Ksecant = Fshock / delta_shock
```

This value represents the slope between the origin and one operating point. It does not describe the complete nonlinear loading and unloading response or the hysteretic damping loop.

VMC and Socitec publish overlapping CB-series names and physically similar products. They must still be treated as separate suppliers unless exact product equivalence is confirmed through part number, dimensions, materials, performance data and document revision.

## 4. Material Comparison

The suppliers disclose different levels of material information. All material statements must be checked against the current model-specific drawing before procurement or qualification.

| Material feature | VMC | Vibratec | Socitec |
|---|---|---|---|
| Standard wire grade publicly identified | Series 302 stainless steel in reviewed CB data | Exact alloy not identified in reviewed public WRI data | Stainless or heavy-duty steel options stated generally |
| Alternative wire options | Galvanized steel, Inconel 600, Type 305 and Type 316 stainless steel, and other options | Not confirmed in reviewed WRI documents | Heavy-duty steel, stainless steel and enhanced-damping options |
| Standard retainer material | Aluminium 6061 family in reviewed CB data | Exact alloy not identified | Treated aluminium or passivated stainless options; exact grade part-dependent |
| Non-magnetic option | Requires supplier confirmation | Not identified | Published as an available option |
| Fasteners and inserts | Part-specific confirmation required | Part-specific confirmation required | Part-specific confirmation required |

VMC currently provides the clearest public material description and the most directly usable shock stiffness data. The detailed mechanical study will therefore focus on VMC unless the company provides better validated data for another supplier.

## 5. Physical Size Comparison

The closest physical rope-diameter classes are approximately:

```text
VMC CB1400  ~ Socitec CB1400  ~ Vibratec A13
VMC CB1500  ~ Socitec CB1500  ~ Vibratec A16
VMC CB1700  ~ Socitec CB1700  ~ Vibratec A22
```

This comparison describes physical class only. Similar rope diameter and envelope dimensions do not prove equivalent stiffness, damping, load capacity or travel.

| Approximate class | VMC nominal H x W range | Socitec nominal H x W range | Vibratec nominal H x W range |
|---|---|---|---|
| 13 mm rope | 76-155 x 92-180 mm | 76-166 x 92-186 mm | 76-108 x 92-133 mm |
| 16 mm rope | 89-146 x 102-185 mm | 89-146 x 102-185 mm | 89-127 x 102-165 mm |
| 22 mm rope | 133-216 x 140-235 mm | 133-216 x 140-235 mm | 133-190 x 140-210 mm |

Softer variants are generally larger and permit more movement. Stiffer variants are more compact but commonly have higher natural frequency and may transmit more acceleration. Size must therefore be evaluated together with stiffness, supported load, travel, clearance, shock direction and mounting interface.

## 6. Why the Existing Model Is Useful but Limited

The current engine is suitable for catalogue screening and controlled comparison because it applies the same equations and gates to every candidate. Its main relationships are:

```text
Natural frequency:
fn = (1 / 2*pi) * sqrt(K / m)

Transmitted acceleration for the impulse approximation:
GT = 2*pi*fn*V/g

Dynamic displacement:
delta_D = V / (2*pi*fn)
```

These equations expose the central trade-off:

```text
Lower stiffness and lower fn
  -> lower transmitted acceleration
  -> greater isolator movement and clearance requirement
```

Important limitations are:

- average linear stiffness does not reproduce the full nonlinear cable response;
- shock stiffness and vibration stiffness are not interchangeable;
- damping and hysteresis are simplified;
- the model does not include fatigue or permanent-set life;
- multi-axis coupling and rack rocking are not solved directly;
- the rack is treated as rigid;
- CG offset is not included in the present load split; and
- a catalogue PASS is not equivalent to installation qualification.

## 7. How to Test Whether the Isolator Is Working

Checking whether screws loosen after a test is useful, but it checks only installation integrity. It does not directly prove that the isolator reduced the shock.

The basic validation principle is:

```text
Measure shock entering the mount
  -> measure shock reaching the rack
  -> measure or observe mount travel
  -> inspect mounting and equipment
  -> confirm equipment still operates
```

### 7.1 Before the Test

Record:

- rack mass and CG;
- installed equipment;
- isolator supplier and part number;
- number, coordinates and orientation of mounts;
- available movement clearance;
- interface-plate arrangement;
- fastener type and tightening torque; and
- initial equipment functional condition.

Apply witness marks across important fasteners and photograph the installation.

### 7.2 During the Test

Use one accelerometer on the input structure and another on the rack or protected equipment. Where travel is important, use an appropriate displacement sensor or high-speed observation method.

The actual applied shock pulse must be recorded. The commanded value should not automatically be assumed to equal the achieved input.

### 7.3 Acceptance Checks

An installation should pass only when:

1. transmitted acceleration is below the equipment limit;
2. isolator movement remains within rated travel and installed clearance;
3. no unacceptable loosening, bottoming, damage or permanent set occurs; and
4. the protected equipment remains functional.

Full shock qualification requires approved facilities and is outside the proposed undergraduate experimental scope unless existing company facilities and supervision are provided.

## 8. Mechanical Research Direction A: Improve Isolation Performance

### Research question

Can the VMC wire-rope isolator or its supporting mechanism be modified to reduce transmitted acceleration or extend isolation toward lower frequencies without exceeding static-load, stability and travel constraints?

Possible topics include:

- effect of loop geometry, number of loops or preload;
- the trade-off between natural frequency, transmitted acceleration and travel;
- a high-static-low-dynamic-stiffness or quasi-zero-stiffness supporting concept; and
- nonlinear reduced-order modelling of an existing VMC isolator.

### Advantages

- Closest to the supervisor's verbal comment about improving the isolator.
- Directly addresses shock or vibration isolation performance.
- Could produce a meaningful mechanical contribution if a specific modification is defined and validated.

### Main difficulties

- Individual cable strands, contact and friction are difficult to model credibly.
- One mount and two catalogue points are insufficient to identify geometry-to-performance relationships.
- Static testing alone cannot validate dynamic shock performance.
- A QZS mechanism is a new device concept, not simply a minor modification of the commercial cable.
- Meaningful optimisation requires either multiple design variants, supplier curves, a validated reduced-order model or prototype manufacture.

### Feasible undergraduate boundary

Use a nonlinear lumped-parameter model calibrated from published or measured force-displacement data. Compare one clearly defined modification against the VMC baseline. Describe results as numerical predictions unless a suitable prototype and dynamic test are available.

Do not attempt strand-level wire-rope FEA as the main FYP task.

## 9. Mechanical Research Direction B: Optimise the Mounting Bracket

### Proposed title

**Shock-Load-Aware Topology Optimisation of a VMC Wire-Rope-Isolator Interface Bracket**

### Research question

Can topology optimisation reduce the mass or manufacturing burden of the VMC interface bracket while maintaining acceptable stress, displacement, safety factor and modal performance under representative server-rack loads?

### Proposed ANSYS workflow

1. Obtain the actual interface bracket drawing, material, mass and manufacturing process.
2. Create the baseline model in SolidWorks, SpaceClaim or ANSYS.
3. Preserve bolt holes, attachment faces and required installation envelopes.
4. Apply vertical, lateral, longitudinal and overturning reaction loads.
5. Run baseline static structural and modal analyses.
6. Minimise bracket mass subject to stress, displacement, safety-factor and manufacturability constraints.
7. Reconstruct the topology result into manufacturable CAD.
8. Remesh and verify the reconstructed design.
9. Optionally perform a transient sensitivity study using the VMC directional stiffness and clearly stated damping assumptions.

### Feasible experiment

Manufacture baseline and optimised specimens using the same material and process where possible. Under a supervised test arrangement, apply controlled static loads and compare measured displacement with ANSYS predictions. Repeat each measurement at least three times.

Polymer prototypes can demonstrate relative stiffness and deformation trends, but they cannot qualify the final metal bracket for the real shock environment.

### Important limitation

Making the bracket lighter does not automatically improve shock isolation. This direction improves the mounting structure, not the commercial wire-rope isolator's natural frequency or damping. It is defensible only if the real bracket is substantial enough for topology optimisation to produce useful savings.

## 10. Comparison of the Two Directions

| Criterion | Direction A: isolation improvement | Direction B: bracket optimisation |
|---|---|---|
| Matches verbal comment about improving mount | Strong | Indirect |
| Matches supervisor's topology/ANSYS interests | Moderate | Strong |
| Directly reduces transmitted acceleration | Potentially | Normally no |
| Modelling difficulty | High | Moderate |
| Undergraduate experiment | Difficult without dynamic facilities | Static bracket test is feasible |
| Main evidence needed | Nonlinear curves, prototype or dynamic data | Real bracket drawing, material and loads |
| Primary risk | Unvalidated nonlinear concept | Solving a low-value or wrong problem |

## 11. Recommended Decision Process

Before beginning ANSYS or developing a nonlinear simulator:

1. Ask the supervisor whether the target is the isolator's isolation performance or the mounting bracket.
2. Ask whether the target excitation is transient shock, continuous vibration, or both.
3. Obtain the real company installation drawing and confirm whether a substantial interface bracket exists.
4. Confirm the available experimental facilities, technician support and prototype budget.
5. Freeze one component, one material, one design objective and one validation method.

Suggested supervisor question:

> Should the mechanical study focus on improving the VMC wire-rope isolator's shock or vibration isolation performance, or on topology optimisation of its mounting bracket and interface structure? I would also like to confirm whether the target input is the 20 G/11 ms shock, continuous vehicle vibration, or both.

## 12. Information Required from the Company

- exact VMC isolator model and current datasheet revision;
- one spare isolator, if available;
- current rack mass, CG and dimensions;
- actual number, position and orientation of mounts;
- interface plate or bracket CAD/drawing;
- bracket material, mass and manufacturing process;
- available travel and surrounding clearance;
- fastener specification, torque and locking method;
- equipment fragility or allowable transmitted acceleration;
- required shock pulse and axes;
- existing qualification or transport test reports;
- photographs of the installed arrangement; and
- access to previous failures or maintenance observations.

## 13. Realistic Experimental Ladder

| Level | Evidence | Feasibility |
|---|---|---|
| 1 | Catalogue and existing company report comparison | Immediate |
| 2 | Supervised static or cyclic force-displacement test | Feasible if a suitable test frame is available |
| 3 | Small-scale prototype or bracket stiffness test | Feasible with clear limitations |
| 4 | Shaker transmissibility or instrumented dynamic test | Stretch goal requiring equipment and supervision |
| 5 | Full 20 G shock qualification | Outside normal undergraduate scope |

An improvised high-load test rig should not be used. Any physical loading must be reviewed and supervised by the responsible laboratory staff.

## 14. Relationship to the AI System

The mechanical study and the local-LLM evaluation should remain separate contributions with a clear interface.

```text
Validated physics or optimisation module
  -> exposed as a deterministic Python tool
  -> local LLM selects the correct workflow
  -> local RAG retrieves standards and catalogue evidence
  -> evaluation measures safety, tool use and traceability
```

The LLM must not perform or override the engineering calculations. If a bracket optimiser or nonlinear isolator model is developed, it can later become an additional deterministic tool used by the assistant.

## 15. Current Recommendation

Continue using VMC as the primary supplier for the detailed shock calculations because its reviewed data provide direct directional Shock Average K and Vibration Average K values and clearer material information.

Do not freeze either mechanical direction until the supervisor answers the scope question and the company supplies the real interface details.

If the supervisor prioritises improved isolation, pursue a bounded numerical feasibility study of one defined modification and state experimental shock qualification as future work.

If the supervisor prioritises ANSYS, topology optimisation and a practical static experiment, first verify that the real interface bracket is substantial enough to justify optimisation. Do not claim that bracket mass reduction improves isolator performance.

## 16. Source Inventory and Verification Status

Current project sources include:

- VMC Wire Rope Isolators Tech Notes;
- VMC CB-series catalogue data represented in `catalog.py`;
- Vibratec WRI-A06 technical workbook;
- Socitec Helical catalogues previously reviewed;
- `physics_engine.py` and `catalog.py`;
- `knowledge/shock_mount/model_assumptions.md`;
- `knowledge/shock_mount/model_limitations.md`;
- `knowledge/shock_mount/selection_workflow.md`; and
- `knowledge/shock_mount/installation_considerations.md`.

Supplier dimensions, materials and performance values in this working note must be checked against the exact current datasheet or supplier drawing before they are used in procurement, qualification or a final thesis claim.
