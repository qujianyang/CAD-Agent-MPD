"""
Static-load gate for isolator selection.

Source: Helical_English.pdf pp.30/32/36 — "Max Static F" (daN) per model per
mounting mode. Bottom mounts carry the full static weight in compression
(reference-workbook model; wall mounts are statically unloaded), so the gate
compares (M/n_bottom)*g against the compression Max Static F.

Anchor case (found during verification): a 1500 kg rack on 6 bottom mounts
puts 245 daN on each mount — over CB1400-50's 206 daN rating, within
CB1400-30's 261 daN. CB61400 has no published static rating (absent from the
English catalog) → stays selectable with static_ok None + warning.
"""
import pytest

from physics_engine import ShockEnv, run_analysis
from catalog import (
    CB1400_CATALOG, CB61400_CATALOG, ALL_CATALOGS,
    select_isolator, select_and_analyze, format_selection_table,
    _loads_per_isolator,
)

ENV = ShockEnv(Ao_G=20.0, to_s=0.011, GT_limit_G=10.0)


def _by_part(candidates):
    return {c.entry.part_no: c for c in candidates}


def _candidates(mass_kg, catalog):
    loads = _loads_per_isolator(mass_kg, 6, 4)
    return select_isolator(
        m_comp_bottom_kg=loads["m_comp_bottom_kg"],
        m_comp_wall_kg=loads["m_comp_wall_kg"],
        m_roll_wall_kg=loads["m_roll_wall_kg"],
        m_roll_bottom_kg=loads["m_roll_bottom_kg"],
        env=ENV, catalog=catalog,
    )


def test_catalog_static_data_present():
    by = {e.part_no: e for e in ALL_CATALOGS}
    assert by["CB1400-50"].max_static_comp_daN == 206
    assert by["CB1400-15"].max_static_comp_daN == 416
    assert by["CB1500-12"].max_static_comp_daN == 846
    assert by["CB1700-15"].max_static_comp_daN == 1528
    # unpublished → None
    assert by["CB61400-50"].max_static_comp_daN is None
    assert by["CB1400-10"].max_static_comp_daN is None
    assert by["CB1400-25"].max_static_comp_daN is None


def test_static_gate_fails_cb1400_50_at_1500kg():
    """250 kg/mount = 245 daN > 206 daN rating → invalid despite passing shock."""
    by = _by_part(_candidates(1500.0, CB1400_CATALOG))
    c = by["CB1400-50"]
    assert abs(c.static_load_daN - 245.25) < 0.01
    assert c.static_ok is False
    assert not c.valid


def test_static_gate_passes_cb1400_30_at_1500kg():
    """245 daN <= 261 daN rating → static OK."""
    by = _by_part(_candidates(1500.0, CB1400_CATALOG))
    c = by["CB1400-30"]
    assert c.static_ok is True


def test_unknown_rating_stays_selectable_with_none():
    by = _by_part(_candidates(1500.0, CB61400_CATALOG))
    c = by["CB61400-50"]
    assert c.static_ok is None
    assert c.static_rating_daN is None
    # unknown rating must NOT hard-fail the candidate
    assert c.valid == all(d.passed for d in c._dirs)


def test_recommended_part_not_statically_overloaded():
    """At 1500 kg the recommended CB1400-series part must satisfy the gate."""
    _, candidates = select_and_analyze(1500.0, 6, 4, shock_env=ENV,
                                       catalog=CB1400_CATALOG)
    rec = next(c for c in candidates if c.valid)
    assert rec.static_ok is not False


def test_run_analysis_warns_on_static_overload():
    """Physics report for CB1400-50 at 1500 kg carries a static FAIL warning."""
    by = {e.part_no: e for e in CB1400_CATALOG}
    report = run_analysis(1500.0, 6, 4, shock_env=ENV,
                          isolator=by["CB1400-50"].to_isolator_spec())
    assert any("static" in w.lower() and "exceed" in w.lower()
               for w in report.warnings)


def test_run_analysis_warns_on_unknown_rating():
    by = {e.part_no: e for e in CB61400_CATALOG}
    report = run_analysis(1500.0, 6, 4, shock_env=ENV,
                          isolator=by["CB61400-50"].to_isolator_spec())
    assert any("no published static" in w.lower() for w in report.warnings)


def test_reference_case_static_ok_no_warning():
    """850 kg / CB1400-15: 141.7 kg/mount = 139 daN << 416 daN — silent."""
    report = run_analysis(850.0, 6, 4, shock_env=ENV)
    assert not any("static" in w.lower() for w in report.warnings)


def test_selection_table_has_static_column():
    candidates = _candidates(1500.0, CB1400_CATALOG)
    table = format_selection_table(candidates)
    assert "Static" in table
