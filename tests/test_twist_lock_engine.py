"""
Twist-lock engine tests — anchored to T1 Measured CG_23-10-2025.xlsx.

Sheet StrengthChk_TwistLock(Measured), W = 9405 kg:
    Longitudinal: F=369052.2 N, per-lock=92263.05 N
    Lateral:      F=138394.575, per-lock=34598.64375
    Vertical:     F=184526.1, per-lock=46131.525
Sheet (Theory), W = 10492.9 kg:
    Longitudinal: F=411741.396, per-lock=102935.349
    Lateral:      F=154403.02349999998, per-lock=38600.755874999995
    Vertical:     F=205870.698, per-lock=51467.6745
Allowables (OEM): 170 kN long & lat, 85 kN vertical. 4 twist-locks.
"""
import pytest

from twist_lock_engine import (
    analyze_twist_locks, format_twist_lock_report, DESIGN_G, ALLOWABLE_N, AXES,
)

TOL = 1e-6


def test_measured_shelter_forces():
    r = analyze_twist_locks(9405.0)
    lo = r.by_axis("longitudinal")
    la = r.by_axis("lateral")
    ve = r.by_axis("vertical")
    assert abs(lo.design_force_N - 369052.2) < TOL
    assert abs(lo.force_per_lock_N - 92263.05) < TOL
    assert abs(la.design_force_N - 138394.575) < TOL
    assert abs(la.force_per_lock_N - 34598.64375) < TOL
    assert abs(ve.design_force_N - 184526.1) < TOL
    assert abs(ve.force_per_lock_N - 46131.525) < TOL


def test_theory_shelter_forces():
    r = analyze_twist_locks(10492.9)
    assert abs(r.by_axis("longitudinal").force_per_lock_N - 102935.349) < TOL
    assert abs(r.by_axis("lateral").force_per_lock_N - 38600.755874999995) < TOL
    assert abs(r.by_axis("vertical").force_per_lock_N - 51467.6745) < TOL


def test_design_load_factors():
    assert DESIGN_G == {"longitudinal": 4.0, "lateral": 1.5, "vertical": 2.0}


def test_allowables():
    assert ALLOWABLE_N["longitudinal"] == 170_000.0
    assert ALLOWABLE_N["lateral"] == 170_000.0
    assert ALLOWABLE_N["vertical"] == 85_000.0


def test_measured_safety_factors_and_pass():
    r = analyze_twist_locks(9405.0)
    # SF = allowable / per-lock; longitudinal & vertical share the same 1.84
    assert abs(r.by_axis("longitudinal").SF - 1.8426) < 1e-3
    assert abs(r.by_axis("vertical").SF - 1.8426) < 1e-3
    assert abs(r.by_axis("lateral").SF - 4.9135) < 1e-3
    assert r.all_passed
    assert abs(r.min_SF - 1.8426) < 1e-3


def test_all_axes_present_in_order():
    r = analyze_twist_locks(9405.0)
    assert [a.axis for a in r.axes] == list(AXES)


def test_overload_fails():
    """A very heavy shelter drives per-lock force over the vertical allowable."""
    # vertical allowable 85 kN; per-lock = W*2*9.81/4 > 85000 -> W > 17329 kg
    r = analyze_twist_locks(20000.0)
    assert not r.by_axis("vertical").passed
    assert not r.all_passed


def test_custom_lock_count():
    r4 = analyze_twist_locks(9405.0, n_locks=4)
    r8 = analyze_twist_locks(9405.0, n_locks=8)
    assert abs(r8.by_axis("longitudinal").force_per_lock_N
               - r4.by_axis("longitudinal").force_per_lock_N / 2) < TOL


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        analyze_twist_locks(0.0)
    with pytest.raises(ValueError):
        analyze_twist_locks(9405.0, n_locks=0)


def test_format_report_has_verdict_and_numbers():
    txt = format_twist_lock_report(analyze_twist_locks(9405.0))
    assert "TWIST-LOCK" in txt
    assert "92,263" in txt or "92263" in txt
    assert "PASS" in txt
