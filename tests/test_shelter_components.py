"""Workbook-backed tests for the shelter component reader ('E2 CG Table' sheet).

Reference values verified by hand against the workbook:
  - 69 real components (item 70 '2 human' is a zero-mass placeholder -> skipped)
  - Generator 1: item 24, Wet Cabin, 375 kg, shelter datum (2320, -136.43, 424.1)
  - Gross shelter weight (row 71): 6557.065 kg
  - Datum offsets: shelter front -> front axle = 1348.5 mm,
                   shelter bottom -> ground   = 1593.0 mm
    (coherence: 1348.5 + 101.5 ISO-corner inset = 1450 = FRONT_AXLE_TO_ISO_PLANE_MM)
"""

import pytest

from mobility_import import shelter_components, shelter_datum_offsets
from mobility_scenarios import (
    FRONT_AXLE_TO_ISO_PLANE_MM,
    MassChange,
    apply_mass_changes,
    axle_x_to_iso_x,
    iso_x_to_axle_x,
    vehicle_from_certified_cg,
)


@pytest.fixture(scope="module")
def components():
    return shelter_components()


@pytest.fixture(scope="module")
def offsets():
    return shelter_datum_offsets()


class TestShelterComponents:
    def test_sixty_nine_components(self, components):
        assert len(components) == 69
        assert [c.item_no for c in components] == list(range(1, 70))

    def test_human_placeholder_excluded(self, components):
        assert not any("human" in c.description.lower() for c in components)

    def test_generator_1_exact(self, components):
        g = next(c for c in components if c.description.startswith("Generator 1"))
        assert g.item_no == 24
        assert g.category == "Wet Cabin"
        assert g.unit_mass_kg == pytest.approx(375.0)
        assert g.qty == pytest.approx(1.0)
        assert g.total_mass_kg == pytest.approx(375.0)
        assert g.x_shelter_mm == pytest.approx(2320.0)
        assert g.y_mm == pytest.approx(-136.43)
        assert g.z_shelter_mm == pytest.approx(424.1)

    def test_total_mass_matches_gross_shelter_weight(self, components):
        assert sum(c.total_mass_kg for c in components) == pytest.approx(6557.065, abs=0.01)

    def test_known_categories(self, components):
        assert {c.category for c in components} == {
            "Shelter Structure", "Wet Cabin", "Dry Cabin", "Antenna",
            "Rack & Cabin Electrical Control",
        }


class TestShelterDatumOffsets:
    def test_offsets_pinned(self, offsets):
        dx_axle, dz_ground = offsets
        assert dx_axle == pytest.approx(1348.5, abs=0.01)
        assert dz_ground == pytest.approx(1593.0, abs=0.01)

    def test_coherent_with_iso_plane_constant(self, offsets):
        """Shelter front + 101.5 (ISO corner inset) = front ISO plane, so
        shelter->axle must equal iso->axle shifted by the inset."""
        dx_axle, _ = offsets
        assert dx_axle + 101.5 == pytest.approx(FRONT_AXLE_TO_ISO_PLANE_MM)

    def test_generator_1_in_design_datum(self, components, offsets):
        dx_axle, dz_ground = offsets
        g = next(c for c in components if c.description.startswith("Generator 1"))
        x_axle = g.x_shelter_mm + dx_axle
        x_iso = axle_x_to_iso_x(x_axle)
        z_ground = g.z_shelter_mm + dz_ground
        assert x_iso == pytest.approx(2218.5, abs=0.01)
        assert z_ground == pytest.approx(2017.1, abs=0.01)
        # round-trip through the change-table pipeline lands back on the axle X
        assert iso_x_to_axle_x(x_iso) == pytest.approx(3668.5, abs=0.01)

    def test_remove_generator_via_design_datum(self, components, offsets):
        dx_axle, dz_ground = offsets
        g = next(c for c in components if c.description.startswith("Generator 1"))
        base = vehicle_from_certified_cg(
            17850, 2655.5, 20.5, 1617.8, 4800, 2088, source="test")
        out = apply_mass_changes(base, [
            MassChange("remove", g.description, g.total_mass_kg,
                       old_xyz_mm=(g.x_shelter_mm + dx_axle, g.y_mm,
                                   g.z_shelter_mm + dz_ground)),
        ])
        assert out.gw_kg == pytest.approx(base.gw_kg - 375.0)
        # removing a high component (2017 mm > Zcg 1617.8) must LOWER the CG
        assert out.zcg_mm < base.zcg_mm
