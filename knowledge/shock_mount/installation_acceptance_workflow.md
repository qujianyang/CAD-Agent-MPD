# Reported Installation and Acceptance Workflow

**Chunk:** `shock_mount/installation_acceptance_workflow`
**Source:** SRC-RPT-01, cross-checked against SRC-SIM-01, SRC-SIM-02,
SRC-SIM-05, and SRC-SIM-06
**Grounding:** reported company practice plus vendor arrangement examples

---

The internal working report describes this practical sequence:

1. obtain rack mass, dimensions, CG, required shock pulse, transmitted limit,
   available clearance, and intended mount positions;
2. perform preliminary deterministic sizing;
3. send the requirement and proposed arrangement to the supplier;
4. receive a supplier recommendation and nonlinear simulation;
5. confirm the exact part number, interfaces, brackets, fasteners, and
   clearances;
6. install a prototype;
7. perform the required functional road trial or qualification activity;
8. inspect equipment operation, fastener loosening, cable security, collision,
   visible damage, and permanent isolator deformation.

Optional accelerometers on the vehicle/input side and rack/output side provide
a direct measured transmission ratio. A functional road trial without
instrumentation is useful acceptance evidence but does not identify the input
pulse, transmitted acceleration, resonance, or remaining margin.

## Arrangement is project-specific

The report mentions a usual 1-gang example of four bottom plus one wall
stabilizer and a 2-gang example of six bottom plus two stabilizers. The supplied
vendor cases show:

- one 1-gang case with four bottom plus two stabilizers;
- one 2-gang case with six bottom plus two stabilizers;
- two larger rack cases with six bottom plus four stabilizers.

Therefore the assistant must not infer mount count from `1-gang` or `2-gang`
alone. It should ask for the actual physical arrangement.

High wall stabilizers can increase the resisting moment arm and control rack
rocking. Their location does not by itself prove lower transmitted
acceleration. The model still needs the actual CG, stiffness direction, load
distribution, and travel.

The supplied internal report contains inconsistent statements about whether
equipment is powered during transport. Treat operating state as an unresolved
project input and ask the engineer or supplier to confirm it.
