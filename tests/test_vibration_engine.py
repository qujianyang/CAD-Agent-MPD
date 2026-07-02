"""
Vibration engine tests — anchored to SPF_Vibration.xls (the company's own
random-vibration workbook: chassis PSD -> damped transmissibility -> g_rms).

Sheet anchors (verified by hand during source study):
    fn = 27.106 Hz (the sheet's damped natural frequency), zeta = 0.12
    T(20 Hz)  = 2.0777 (amplification region)
    T(70 Hz)  = 0.2063 (isolation region)
    grms_in   = 3.9405  (right-endpoint rectangular integration)
"""
import math

import pytest

from vibration_engine import (
    CHASSIS_PSD_TRUCK, transmissibility, grms_right_rect,
    run_vibration_analysis, vibration_check_for_entry, format_vibration_report,
)
from catalog import ALL_CATALOGS

SHEET_FN = 27.10601099173321   # SPF D42
ZETA = 0.12


def _entry(part_no):
    return next(e for e in ALL_CATALOGS if e.part_no == part_no)


# --- transmissibility anchors (SPF column I) --------------------------------

def test_T_at_20Hz_matches_sheet():
    assert abs(transmissibility(20.0, SHEET_FN, ZETA) - 2.0776906021699153) < 1e-12


def test_T_at_70Hz_matches_sheet():
    assert abs(transmissibility(70.0, SHEET_FN, ZETA) - 0.20629954827990105) < 1e-12


def test_T_at_resonance_is_Q():
    """At f = fn, T = sqrt(1+(2z)^2)/(2z) ~ 4.3 for zeta=0.12."""
    q = transmissibility(SHEET_FN, SHEET_FN, ZETA)
    expected = math.sqrt(1 + (2 * ZETA) ** 2) / (2 * ZETA)
    assert abs(q - expected) < 1e-12


# --- PSD integration (SPF Area/grms columns) --------------------------------

def test_grms_in_matches_sheet():
    assert abs(grms_right_rect(CHASSIS_PSD_TRUCK) - 3.9405266145529327) < 1e-9


def test_psd_table_shape():
    assert len(CHASSIS_PSD_TRUCK) == 28
    assert CHASSIS_PSD_TRUCK[0] == (1.0, 0.012)
    assert CHASSIS_PSD_TRUCK[-1] == (650.0, 0.0115)


# --- full analysis -----------------------------------------------------------

def test_analysis_attenuates_for_stiff_mount():
    """SPF's own system (K=29430 N/m, fn~27 Hz): 3.94 -> ~1.52 grms."""
    res = run_vibration_analysis(m_kg=1.0, k_vib_Nm=29430.0, zeta=ZETA)
    assert abs(res.grms_in - 3.9405266145529327) < 1e-9
    # engine fn (damped) ~27.1; sheet used 27.106 — grms_out lands near 1.52
    assert 1.4 < res.grms_out < 1.6


def test_resonance_flag_fires_on_psd_peak():
    """CB61400-50 @ 250 kg: fn_vib ~ 4.1 Hz sits on the 3.6-4.3 Hz PSD peak."""
    entry = _entry("CB61400-50")
    res = vibration_check_for_entry(entry, m_comp_bottom_kg=250.0)
    assert res is not None
    assert 3.0 < res.fn_Hz < 5.0
    assert res.resonance_flag


def test_no_resonance_flag_for_stiff_part():
    """CB1700-15 @ 250 kg: K_vib=20000 lb/in -> fn ~ 18.8 Hz, off the peak."""
    entry = _entry("CB1700-15")
    res = vibration_check_for_entry(entry, m_comp_bottom_kg=250.0)
    assert res is not None
    assert res.fn_Hz > 10.0
    assert not res.resonance_flag


def test_entry_without_vibration_k_returns_none():
    assert vibration_check_for_entry(_entry("CB1400-10"), 100.0) is None


def test_format_report_contains_key_numbers():
    res = run_vibration_analysis(m_kg=1.0, k_vib_Nm=29430.0, zeta=ZETA)
    txt = format_vibration_report(res)
    assert "grms" in txt.lower() or "g_rms" in txt.lower()
    assert "3.94" in txt


def test_damped_fn():
    """fn reported is the damped natural frequency fd = fn*sqrt(1-zeta^2)."""
    res = run_vibration_analysis(m_kg=1.0, k_vib_Nm=29430.0, zeta=ZETA)
    undamped = math.sqrt(29430.0 / 1.0) / (2 * math.pi)
    assert abs(res.fn_Hz - undamped * math.sqrt(1 - ZETA ** 2)) < 1e-9
