"""Unit tests for the inventory data models in ``dlca.models``."""

import pytest

from dlca.models import (
    EmissionInventoryBio,
    EmissionsInventoryAllGHG,
    EmissionsInventoryGHGi,
    GHGTypes,
    MaterialTypes,
)


def _ghg(ghg, material):
    return EmissionsInventoryGHGi(
        material=material, ghg=ghg, emissions_A=1.0, emissions_B=0.0, emissions_C=0.0
    )


def _inventory(co2, ch4, n2o, bio):
    return EmissionsInventoryAllGHG(
        CO2=_ghg(GHGTypes.CO2, co2),
        CH4=_ghg(GHGTypes.CH4, ch4),
        N2O=_ghg(GHGTypes.N2O, n2o),
        CO2bio=EmissionInventoryBio(material=bio, CO2_bio=0.0, rot_period=0),
    )


def test_matching_materials_are_accepted():
    T = MaterialTypes.TEST
    inv = _inventory(T, T, T, T)
    assert inv.material is T


def test_default_inventory_is_accepted():
    # Every part defaults to MaterialTypes.NA, so the materials match.
    assert EmissionsInventoryAllGHG().material is MaterialTypes.NA


@pytest.mark.parametrize("odd_one", ["CO2", "CH4", "N2O", "CO2bio"])
def test_mismatched_materials_raise(odd_one):
    """Audit bug (#31): the check raised on matching materials and passed mismatches."""
    materials = dict.fromkeys(["CO2", "CH4", "N2O", "CO2bio"], MaterialTypes.TEST)
    materials[odd_one] = MaterialTypes.CLT
    with pytest.raises(ValueError, match="mismatched materials"):
        _inventory(materials["CO2"], materials["CH4"], materials["N2O"], materials["CO2bio"])
