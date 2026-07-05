"""
CG engine tests — anchored to the T1 workbook.

Combined (theory buildup): unladen transporter 15550 kg + laden shelter
10492.9 kg -> GW 26042.9 kg, Xcg 2843.9176, Ycg 10.1667, Zcg 1750.3799.

Payload reverse-CG (measured): combined 26175 kg minus unladen 16450 kg
-> payload 9725 kg, X 4021.851, Y -62.082, Z 2821.753 (T1 'Re-engrg Laden
Shelter Weight' sheet).
"""
import pytest

from cg_engine import CGState, combined_cg, derive_payload_cg

TOL = 1e-3   # mm


def test_combined_cg_theory():
    transporter = CGState("Unladen N1", 15550.0, 1958.0, 15.0, 1117.0)
    shelter = CGState("Laden T1 shelter", 10492.9,
                      4156.807219643759, 3.0038788132927983, 2689.0201245604167)
    c = combined_cg([transporter, shelter], name="T1 theory")
    assert abs(c.mass_kg - 26042.9) < 1e-6
    assert abs(c.x_mm - 2843.9176311009905) < TOL
    assert abs(c.y_mm - 10.166663466818212) < TOL
    assert abs(c.z_mm - 1750.3799217829044) < TOL


def test_combined_single_item_is_identity():
    a = CGState("solo", 500.0, 100.0, -20.0, 800.0)
    c = combined_cg([a])
    assert (c.mass_kg, c.x_mm, c.y_mm, c.z_mm) == (500.0, 100.0, -20.0, 800.0)


def test_derive_payload_cg_measured():
    combined = CGState("Laden T1", 26175.0,
                       2717.765042979943, -13.037249283667734, 1750.3799217829044)
    base = CGState("Unladen N1", 16450.0,
                   1946.8085106382978, 15.957446808510667, 1117.0)
    pl = derive_payload_cg(combined, base, payload_name="T1 shelter")
    assert abs(pl.mass_kg - 9725.0) < 1e-6
    assert abs(pl.x_mm - 4021.850899742931) < TOL
    assert abs(pl.y_mm - (-62.08226221079726)) < TOL
    assert abs(pl.z_mm - 2821.752642947817) < TOL


def test_combined_then_subtract_roundtrips():
    """combined(base, payload) then derive_payload(combined, base) == payload."""
    base = CGState("base", 16450.0, 1946.8, 16.0, 1117.0)
    payload = CGState("pl", 9725.0, 4021.85, -62.08, 2821.75)
    comb = combined_cg([base, payload])
    back = derive_payload_cg(comb, base)
    assert abs(back.mass_kg - payload.mass_kg) < 1e-6
    assert abs(back.x_mm - payload.x_mm) < TOL
    assert abs(back.y_mm - payload.y_mm) < TOL
    assert abs(back.z_mm - payload.z_mm) < TOL


def test_empty_list_raises():
    with pytest.raises(ValueError):
        combined_cg([])


def test_zero_total_mass_raises():
    with pytest.raises(ValueError):
        combined_cg([CGState("a", 0.0, 1.0, 1.0, 1.0)])


def test_payload_non_positive_raises():
    """base heavier than combined -> non-positive payload mass."""
    combined = CGState("c", 100.0, 1.0, 1.0, 1.0)
    base = CGState("b", 100.0, 1.0, 1.0, 1.0)
    with pytest.raises(ValueError):
        derive_payload_cg(combined, base)
