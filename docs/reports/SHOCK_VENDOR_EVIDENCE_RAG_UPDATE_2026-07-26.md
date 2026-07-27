# Shock-Mount Vendor Evidence and Product Update Proposal

**Date:** 2026-07-26
**Scope:** Shock-mount RAG corpus, explanatory visual, and supplier enquiry pack

## 1. Purpose

The supplied internal report, vendor catalogue, nonlinear calculation sheets,
simulation reports, and dynamic stiffness plots were reviewed to improve the
shock-mount knowledge base and identify product changes that are supported by
real engineering evidence.

The central evidence rule is:

> A project calculation, vendor simulation, functional road trial, and physical
> qualification test are different evidence levels. The assistant must identify
> which one supports each claim.

## 2. Important findings from the supplied documents

### 2.1 The vendor model is nonlinear

The CB1390 dynamic plots and supplier SDNL calculation sheets use nonlinear,
axis-specific load-deflection behaviour. The project engine uses average
compression and shear stiffness in four deterministic load cases.

The project result is therefore a preliminary screening result. It is useful
for consistent selection, rejection, explanation, and supplier communication,
but it is not an exact reproduction of the supplier simulation.

### 2.2 Physical and effective mount counts are different

The vendor sheets show:

| Physical arrangement | Physical total | Vendor calculation field |
|---|---:|---:|
| 4 bottom + 2 stabilizers | 6 | 4.66 |
| 6 bottom + 2 stabilizers | 8 | 6.66 |

The supplier does not explain the derivation of `4.66` or `6.66`. These values
must not be used as physical mount counts in the project engine.

### 2.3 Rack type does not uniquely determine arrangement

The internal report and vendor cases contain several arrangements:

- 1-gang example: 4 bottom + 1 stabilizer;
- supplied 1-gang vendor case: 4 bottom + 2 stabilizers;
- supplied 2-gang vendor case: 6 bottom + 2 stabilizers;
- supplied larger rack cases: 6 bottom + 4 stabilizers.

The assistant must ask for the actual arrangement. A `1-gang` or `2-gang`
label is not enough.

### 2.4 Shock passing does not prove vibration compliance

The 850 kg and 1050 kg CB1400-15 simulations predict shock accelerations below
the requested 10 g limit. Both reports nevertheless state that the
configuration does not meet the required 40-minute random-vibration duration.

Shock status and vibration status must always be reported separately.

### 2.5 The supplied evidence contains no physical qualification report

The supplied set contains:

- one internal working report;
- one vendor catalogue;
- vendor calculation and simulation reports;
- image-only dynamic stiffness plots.

It does not contain a physical laboratory shock or vibration qualification
report. The application must not use the words `qualified` or `tested` for
these simulation results.

## 3. RAG corpus update completed

The new knowledge pages cover:

- evidence source classification;
- Socitec CB1390 construction, dimensions, materials, and interfaces;
- CB1390-20 and CB1390-30 reference performance;
- CB1390, HH14, and CB1400 vendor case evidence;
- supplier effective-count warning;
- project-model versus vendor-model boundary;
- project-specific installation arrangements;
- functional acceptance workflow;
- shock versus random-vibration separation;
- required supplier enquiry inputs and outputs.

The live mixed index was rebuilt using local BGE-M3:

| Item | Result |
|---|---:|
| Total live chunks | 67 |
| Shock-mount chunks | 44 |
| New vendor retrieval questions | 12 |
| Vendor Hit@1 | 100% |
| Vendor Hit@3 | 100% |
| Original shock-suite Hit@1 | 87.5% |
| Original shock-suite Hit@3 | 100% |
| Original shock-suite MRR | 0.9271 |

The frozen formal-evaluation index was not changed. This is a post-release
product/RAG update.

## 4. Proposed update: Generate explanatory visual

### 4.1 Keep the image non-authoritative

The generated picture must remain a training illustration. The Python
calculation, deterministic mount layout, and supplier drawing remain the
engineering authority.

Do not ask the image model to invent:

- exact isolator part geometry;
- exact mount coordinates or quantities;
- brackets, interfaces, or fasteners;
- certification, test, or qualification claims.

### 4.2 Add a visual-purpose selector

Add these modes above the current free-text instructions:

| Mode | Intended output | Best implementation |
|---|---|---|
| Installation concept | Bottom isolators and high wall stabilizers in a rack | OpenAI image generation with an approved reference image |
| Shock load path | Red input shock, isolator deformation, smaller blue rack response | OpenAI image generation plus deterministic captions |
| Axis and load mode | Compression, shear/roll, and X/Y/Z directions | Deterministic diagram, not generative AI |
| Shock versus vibration | Short shock event versus duration-based random vibration | Deterministic comparison chart |
| Supplier case comparison | Mass, modal frequency, travel, and acceleration comparison | Deterministic chart from approved data |

### 4.3 Require a reference for installation-detail mode

The poor generated image showed loose guy wires and vertical rope columns
instead of loop-and-clamp wire-rope isolators. For the `Installation concept`
mode, require an approved CB-series reference image or clearly downgrade the
result to a generic physics concept.

The prompt should state that a wall stabilizer is the same looped wire-rope
isolator mounted in a different orientation. It is not a cable tie-down.

### 4.4 Keep numerical labels outside the generated pixels

After generation, overlay or display deterministic values from the analysis:

- analysis ID;
- verdict;
- actual bottom and wall mount counts;
- input shock;
- worst transmitted acceleration;
- governing case;
- concept-only warning.

This avoids distorted text and unsupported numbers inside the AI image.

### 4.5 Protect vendor information

Do not automatically send any vendor PDF, internal report, CAD file, customer
name, or project code to the cloud image service. Only an image that the user
explicitly selects and confirms as approved should be uploaded.

## 5. Proposed update: Generate supplier enquiry pack

This should be the first implementation priority because it turns the verified
calculation and new vendor evidence into an immediately useful client output.

### 5.1 Add a requirement-completeness section

Show every field as `CONFIRMED`, `ASSUMED`, or `TO BE CONFIRMED`:

- mass and tolerance;
- rack dimensions and CG;
- exact physical mount arrangement;
- wall stabilizer height and face;
- X/Y/Z axis convention;
- shock pulse, duration, and velocity change;
- transmitted acceleration limit;
- clearance in both directions;
- random-vibration PSD/category and duration;
- equipment operating state;
- environment and corrosion requirement.

The pack should not appear complete when critical data is missing.

### 5.2 Separate three evidence levels

Add a table with:

1. **Project deterministic screening** - values generated by Python.
2. **Supplier nonlinear simulation** - pending or attached supplier output.
3. **Physical test or functional trial** - pending, passed, failed, or not
   required.

This prevents a vendor simulation from being presented as test evidence.

### 5.3 Request the same outputs seen in the vendor reports

Ask the supplier to return:

- exact part number, loop count, material, finish, and interface suffix;
- nonlinear static and dynamic load-deflection curves by relevant axis;
- physical mount count and any effective model-count assumption;
- static deflection;
- modal frequencies in X, Y, and Z;
- minimum and maximum shock displacement and acceleration per axis;
- random-vibration resonance, RMS acceleration, maximum PSD, and duration
  compliance;
- fastener, torque, engagement, bracket, orientation, clearance, and snubbing
  requirements;
- evidence classification: catalogue, simulation, similarity, or physical
  test.

### 5.4 Add explicit shock and vibration decisions

Use separate rows:

| Requirement | Project screening | Supplier confirmation | Physical evidence |
|---|---|---|---|
| Static capacity | Result | Pending | Pending |
| Shock transmitted G | Result | Pending | Pending |
| Shock travel | Result | Pending | Pending |
| Random vibration | Not fully assessed / result | Pending | Pending |
| Functional road trial | Not applicable to calculation | Not applicable | Pending |

Never use one overall `PASS` to hide an unassessed vibration requirement.

### 5.5 Treat old vendor reports as references, not transferable approval

The supplied reports may be listed in an optional `Historical reference
evidence` appendix if company approval permits. Their values must not be copied
as approval for a new rack. The new supplier should be asked to issue a fresh
analysis for the actual mass, geometry, CG, arrangement, interfaces, and duty.

### 5.6 Add a road-trial acceptance record

Include fields for:

- equipment operating state;
- pre- and post-trial functional check;
- fastener loosening;
- cable or connector movement;
- rack-to-structure collision;
- visible isolator deformation;
- input-side and rack-side accelerometer IDs, if instrumented;
- reviewer, date, route, duration, and disposition.

## 6. Recommended implementation order

1. **Supplier pack v2**
   - add completeness and evidence-level tables;
   - add CG, vibration, operating-state, interface, and environment inputs;
   - add supplier nonlinear-output request and road-trial record;
   - render and visually verify the Word document.

2. **Explanatory visual v3**
   - add purpose presets;
   - require an approved reference for installation-detail mode;
   - use deterministic diagrams for axes and numerical comparisons;
   - keep all authoritative values outside the generated image.

3. **Assistant integration**
   - add quick actions for vendor evidence, shock-versus-vibration status, and
     missing supplier inputs;
   - use the new RAG pages for citations;
   - keep document and image generation as explicit user actions, separate from
     the chat agent's calculations.

4. **Acceptance checks**
   - supplier pack contains no unsupported qualification claim;
   - missing fields are visible;
   - image never invents an exact part or mount layout;
   - vendor retrieval checks remain at Hit@3 100%;
   - existing deterministic physics and frozen evaluation results remain
     unchanged.
