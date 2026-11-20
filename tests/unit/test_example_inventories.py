"""Illustrative example inventories in `tests/data/inventories/` (#60).

The expected totals are the hand calculations in that folder's README, worked
out before the code ran. Faults these catch that no other test does: an
example file that no longer validates (schema drift or a typo); a number in a
file that differs from the README's table (for example a factor off by 10);
a file read as the wrong schema; a fixture that loads the wrong file.
"""

from pathlib import Path

import pytest

from dlca.climate import EMISSION_KEYS
from dlca.inventory import BuildingInventory, BuildingTotals, timeline

INVENTORY_DIR = Path(__file__).resolve().parents[1] / "data" / "inventories"
EXAMPLE_INVENTORY_NAMES = ("timber", "steel", "concrete")

# Hand totals from tests/data/inventories/README.md, kg of each gas.
A1_A3 = {
    "timber": {"co2": 32_200, "ch4": 0, "ch4_fossil": 52, "n2o": 2.4},
    "steel": {"co2": 114_750, "ch4": 0, "ch4_fossil": 144, "n2o": 3.42},
    "concrete": {"co2": 100_000, "ch4": 0, "ch4_fossil": 137.5, "n2o": 3.25},
    "totals": {"co2": 250_000, "ch4": 0, "ch4_fossil": 300, "n2o": 8},
}
WHOLE_SERIES = {
    "timber": {"co2": 42_472, "ch4": 460, "ch4_fossil": 52, "n2o": 2.4},
    "steel": {"co2": 133_827, "ch4": 0, "ch4_fossil": 144, "n2o": 3.42},
    "concrete": {"co2": 112_150, "ch4": 0, "ch4_fossil": 137.5, "n2o": 3.25},
    "totals": {"co2": 350_000, "ch4": 50, "ch4_fossil": 320, "n2o": 8},
}
STUDY_PERIOD = {"timber": 60, "steel": 60, "concrete": 60, "totals": 50}


@pytest.fixture
def buildings(example_inventories, example_totals):
    return {**example_inventories, "totals": example_totals}


def test_every_file_in_the_folder_is_loaded():
    files = {p.stem for p in INVENTORY_DIR.glob("*.json")}
    assert files == {*EXAMPLE_INVENTORY_NAMES, "totals"}


def test_files_validate_as_their_schema(example_inventories, example_totals):
    assert set(example_inventories) == set(EXAMPLE_INVENTORY_NAMES)
    for building in example_inventories.values():
        assert isinstance(building, BuildingInventory)
    assert isinstance(example_totals, BuildingTotals)


@pytest.mark.parametrize("name", [*EXAMPLE_INVENTORY_NAMES, "totals"])
def test_study_period(buildings, name):
    assert buildings[name].study_period == STUDY_PERIOD[name]


@pytest.mark.parametrize("name", [*EXAMPLE_INVENTORY_NAMES, "totals"])
def test_a1_a3_matches_hand_total(buildings, name):
    a1_a3 = timeline(buildings[name]).by_module()["A1-A3"]
    for gas in EMISSION_KEYS:
        assert a1_a3[gas][0] == pytest.approx(A1_A3[name][gas], rel=1e-12, abs=1e-12), gas
        assert a1_a3[gas][1:].sum() == 0, gas


@pytest.mark.parametrize("name", [*EXAMPLE_INVENTORY_NAMES, "totals"])
def test_whole_series_matches_hand_total(buildings, name):
    emissions = timeline(buildings[name]).emissions()
    for gas in EMISSION_KEYS:
        assert emissions[gas].sum() == pytest.approx(
            WHOLE_SERIES[name][gas], rel=1e-12, abs=1e-12
        ), gas
