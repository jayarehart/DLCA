"""Illustrative example inventories in `tests/data/inventories/` (#60).

The expected values are the hand calculations in that folder's README, worked
out before the code ran. Faults these catch that no other test does: an
example file that no longer validates (schema drift or a typo); a factor in a
file that differs from the README (for example off by 10, or moved to another
module); a B4/B5 event or per-year amount in the wrong year; a file read as
the wrong schema; a fixture that loads the wrong file.
"""

import numpy as np
import pytest

from dlca.climate import EMISSION_KEYS
from dlca.inventory import BuildingInventory, BuildingTotals, biogenic_balance, timeline

NAMES = ("timber", "timber_biogenic", "steel", "concrete", "totals")

# Hand totals from tests/data/inventories/README.md, kg of each gas.
A1_A3 = {
    "timber": {"co2": 32_200, "ch4": 0, "ch4_fossil": 52, "n2o": 2.4},
    "timber_biogenic": {"co2": 32_200, "ch4": 0, "ch4_fossil": 52, "n2o": 2.4},
    "steel": {"co2": 114_750, "ch4": 0, "ch4_fossil": 144, "n2o": 3.42},
    "concrete": {"co2": 100_000, "ch4": 0, "ch4_fossil": 137.5, "n2o": 3.25},
    "totals": {"co2": 250_000, "ch4": 0, "ch4_fossil": 300, "n2o": 8},
}
WHOLE_SERIES = {
    "timber": {"co2": 42_472, "ch4": 460, "ch4_fossil": 52, "n2o": 2.4},
    "timber_biogenic": {"co2": -126_808, "ch4": 460, "ch4_fossil": 52, "n2o": 2.4},
    "steel": {"co2": 133_827, "ch4": 0, "ch4_fossil": 144, "n2o": 3.42},
    "concrete": {"co2": 112_150, "ch4": 0, "ch4_fossil": 137.5, "n2o": 3.25},
    "totals": {"co2": 350_000, "ch4": 50, "ch4_fossil": 320, "n2o": 8},
}
# co2 by module, kg over the whole series.
CO2_BY_MODULE = {
    "timber": {
        "A1-A3": 32_200, "A4": 5_850, "A5": 1_190, "B5": 400,
        "C1": 710, "C2": 470, "C3": 1_190, "C4": 462,
    },
    "timber_biogenic": {
        "biogenic-uptake": -176_870,
        "A1-A3": 32_200, "A4": 5_850, "A5": 1_190, "B5": 400,
        "C1": 710, "C2": 470, "C3": 1_190, "C4": 8_052,
    },
    "steel": {
        "A1-A3": 114_750, "A4": 3_015, "A5": 3_015, "B1": -1_440, "B4": 9_000,
        "C1": 1_620, "C2": 1_650, "C3": 1_440, "C4": 777,
    },
    "concrete": {
        "A1-A3": 100_000, "A4": 2_500, "A5": 4_250, "B1": -3_000,
        "C1": 2_750, "C2": 3_125, "C3": 1_750, "C4": 775,
    },
    "totals": {
        "A1-A3": 250_000, "A4": 10_000, "A5": 15_000, "B2": 25_000, "B4": 16_000,
        "B5": 20_000, "C1": 5_000, "C2": 4_000, "C3": 3_000, "C4": 2_000,
    },
}  # fmt: skip
# Years with a nonzero B4/B5 amount (co2, kg in that year).
EVENTS = {
    "timber": {"B5": {30: 400}},
    "timber_biogenic": {"B5": {30: 400}},
    "steel": {"B4": {25: 4_500, 50: 4_500}},
    "concrete": {},
    "totals": {"B4": {20: 8_000, 40: 8_000}, "B5": {25: 20_000}},
}
# Per-year modules (co2, kg in each of years 1..study_period).
PER_YEAR = {
    "timber": {},
    "timber_biogenic": {},
    "steel": {"B1": -24},
    "concrete": {"B1": -50},
    "totals": {"B2": 500},
}
STUDY_PERIOD = {"timber": 60, "timber_biogenic": 60, "steel": 60, "concrete": 60, "totals": 50}


def close(value, expected):
    return value == pytest.approx(expected, rel=1e-12, abs=1e-12)


@pytest.fixture
def buildings(example_inventories, example_totals):
    return {**example_inventories, "totals": example_totals}


def test_every_file_in_the_folder_is_loaded(example_inventory_dir):
    assert {p.stem for p in example_inventory_dir.glob("*.json")} == set(NAMES)


def test_files_validate_as_their_schema(example_inventories, example_totals):
    assert set(example_inventories) == {"timber", "timber_biogenic", "steel", "concrete"}
    for building in example_inventories.values():
        assert isinstance(building, BuildingInventory)
    assert isinstance(example_totals, BuildingTotals)


@pytest.mark.parametrize("name", NAMES)
def test_study_period(buildings, name):
    assert buildings[name].study_period == STUDY_PERIOD[name]


@pytest.mark.parametrize("name", NAMES)
def test_a1_a3_matches_hand_total(buildings, name):
    a1_a3 = timeline(buildings[name]).by_module()["A1-A3"]
    for gas in EMISSION_KEYS:
        assert close(a1_a3[gas][0], A1_A3[name][gas]), gas
        assert a1_a3[gas][1:].sum() == 0, gas


@pytest.mark.parametrize("name", NAMES)
def test_whole_series_matches_hand_total(buildings, name):
    emissions = timeline(buildings[name]).emissions()
    for gas in EMISSION_KEYS:
        assert close(emissions[gas].sum(), WHOLE_SERIES[name][gas]), gas


@pytest.mark.parametrize("name", NAMES)
def test_co2_by_module_matches_hand_total(buildings, name):
    by_module = timeline(buildings[name]).by_module()
    assert set(by_module) == set(CO2_BY_MODULE[name])
    for module, expected in CO2_BY_MODULE[name].items():
        assert close(by_module[module]["co2"].sum(), expected), module


def test_timber_biogenic_storage_matches_hand_total(example_inventories):
    """README hand total: 769 declared - 33 released as CO2 - 2.0 x 44.01 / 16.043
    as CH4 = 730.513 kg CO2 per m3 stored, times 200 m3 (CLT) and 30 m3 (glulam)."""
    balance = biogenic_balance(example_inventories["timber_biogenic"])
    per_m3 = 769 - 33 - 2.0 * 44.01 / 16.043
    for key, m3 in ((("Floor", "CLT panels"), 200), (("Frame", "Glulam beams"), 30)):
        assert close(balance[key].declared, 769 * m3)
        assert close(balance[key].stored, per_m3 * m3)
    assert set(balance) == {("Floor", "CLT panels"), ("Frame", "Glulam beams")}


@pytest.mark.parametrize("name", NAMES)
def test_events_and_per_year_amounts_fall_in_their_years(buildings, name):
    tl = timeline(buildings[name])
    by_module = tl.by_module()
    for module, years in EVENTS[name].items():
        co2 = by_module[module]["co2"]
        assert set(np.flatnonzero(co2)) == set(years), module
        for year, expected in years.items():
            assert close(co2[year], expected), (module, year)
    rsp = tl.study_period
    for module, expected in PER_YEAR[name].items():
        co2 = by_module[module]["co2"]
        assert np.flatnonzero(co2).tolist() == list(range(1, rsp + 1)), module
        assert all(close(v, expected) for v in co2[1 : rsp + 1]), module
