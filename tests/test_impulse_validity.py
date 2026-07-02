"""
Impulse-approximation validity guard.

V = 1/2*g*Ao*to treats the saw-tooth pulse as an ideal impulse, valid only
while the pulse is short relative to the mount's natural period:
fn * t0 <= IMPULSE_VALIDITY_RATIO (0.25, i.e. t0 <= T/4).

Reference workbook operates at fn 6.7-10.5 Hz with t0 = 11 ms
(fn*t0 = 0.07-0.12) -- comfortably valid, so the guard must stay silent
there. It must fire when a stiff mount / tiny mass pushes fn past
1/(4*t0) ~ 22.7 Hz.
"""
import pytest

from physics_engine import (
    IMPULSE_VALIDITY_RATIO, IsolatorSpec, ShockEnv, run_analysis, CB1400_15,
)


def test_ratio_constant():
    assert IMPULSE_VALIDITY_RATIO == 0.25


def test_reference_case_valid_no_warning():
    """850 kg / CB1400-15 reference: fn 6.7-10.5 Hz, all directions valid."""
    report = run_analysis(850.0, 6, 4,
                          shock_env=ShockEnv(Ao_G=20.0, to_s=0.011, GT_limit_G=10.0))
    assert all(d.impulse_valid for d in report.directions)
    assert not any("impulse" in w.lower() for w in report.warnings)


def test_tiny_mass_invalidates_impulse():
    """1 kg on CB1400-15 bottom: fn = sqrt(464086/0.1667)/2pi >> 22.7 Hz."""
    report = run_analysis(1.0, 6, 4,
                          shock_env=ShockEnv(Ao_G=20.0, to_s=0.011, GT_limit_G=10.0))
    assert any(not d.impulse_valid for d in report.directions)
    assert any("impulse" in w.lower() for w in report.warnings)


def test_long_pulse_invalidates_impulse():
    """Same reference mass but a 100 ms pulse: fn*t0 = 0.67-1.05 > 0.25."""
    report = run_analysis(850.0, 6, 4,
                          shock_env=ShockEnv(Ao_G=20.0, to_s=0.100, GT_limit_G=10.0))
    assert all(not d.impulse_valid for d in report.directions)
    assert any("impulse" in w.lower() for w in report.warnings)


def test_boundary_both_sides():
    """fn*t0 just below 0.25 is valid; just above is flagged.

    (Exact equality at the boundary is FP-fragile through the sqrt round-trip,
    so probe each side with a small margin instead.)
    """
    import math
    m = 100.0
    fn = 10.0
    k = m * (2 * math.pi * fn) ** 2
    spec = IsolatorSpec("boundary", k, k, 100.0, 100.0)

    below = run_analysis(m * 6, 6, 4, isolator=spec,
                         shock_env=ShockEnv(Ao_G=20.0, to_s=0.2499 / fn, GT_limit_G=1e9))
    assert below.directions[0].impulse_valid

    above = run_analysis(m * 6, 6, 4, isolator=spec,
                         shock_env=ShockEnv(Ao_G=20.0, to_s=0.2501 / fn, GT_limit_G=1e9))
    assert not above.directions[0].impulse_valid
