# Boundary Between Project Screening and Vendor Nonlinear Simulation

**Chunk:** `shock_mount/vendor_nonlinear_model_boundary`
**Sources:** SRC-CURVE-01 and SRC-SIM-01 through SRC-SIM-06
**Grounding:** comparison of supplied vendor evidence with the project engine

---

The supplier calculations use nonlinear single-degree-of-freedom models and
axis-specific dynamic load-deflection curves. SRC-CURVE-01 shows different
CB1390-20 and CB1390-30 curves in the local X, Y, and Z directions. The curves
are nonlinear and asymmetric, so one constant `K` cannot reproduce them over
the full motion.

The project engine instead uses constant average compression and shear
stiffness values in four independent load cases. It is suitable for:

- preliminary sizing and comparison;
- deterministic rejection by static, transmitted-G, and travel gates;
- explaining which case governs;
- producing a consistent supplier enquiry.

It is not an exact reproduction of the supplier simulation. It does not model:

- the full nonlinear force-deflection curve;
- hysteresis or amplitude-dependent damping;
- coupled translation and rotation;
- the supplier's effective configuration factors such as `4.66` or `6.66`;
- fatigue or duration-dependent random-vibration failure.

## Required wording

Call the project result a `preliminary deterministic screening result`. Call
the supplied SDNL1/WINSDNL1 result a `vendor nonlinear simulation result`.
Reserve `test result`, `qualified`, and `validated installation` for physical
evidence that actually demonstrates those claims.

Near a load, travel, or acceleration limit, request the supplier's nonlinear
analysis and confirm its assumptions before final selection.
