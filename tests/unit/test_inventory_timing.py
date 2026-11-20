"""Timing engine `timeline()` (#58, record 0014).

Every expected series here was worked out by hand from Jay's timing rule (T1
on #58) before the engine was written:

- A1-A3, A4, A5: year 0.
- B1, B2, B3, B6, B7: the yearly amount in each of years 1..RSP.
- C1-C4: one pulse in year RSP + 1 (the end-of-life year).
- B4, B5: in the year the event gives.
- Amounts in the same year add.
- Length: RSP + 1 + H + 1 (years 0..RSP + 1 + H), so the end-of-life pulse
  gets a full H years.

Faults these catch that no other test does: a module placed in the wrong year
(A after year 0, B starting in year 0 or stopping early, C in year RSP or over
several years); two amounts in one year overwriting instead of adding (the
`create_flux_mat` bug); C spread over 15 years (the `MatEmissionsTiming` bug);
a quantity not applied, or applied to B6/B7; a gas written under the wrong
key; a series too short for the horizon; totals and inventory input giving
different series; a breakdown that does not add up to the total.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import dlca
from dlca.climate import EMISSION_KEYS
from dlca.inventory import BuildingInventory, BuildingTotals, Timeline, timeline


def totals(study_period, modules=None, per_year=None, b4=(), b5=()):
    return BuildingTotals.model_validate(
        {
            "schema": "dlca.building_totals",
            "name": "Hand case",
            "study_period": study_period,
            "modules": modules or {},
            "per_year": per_year or {},
            "b4": [{"year": y, "amounts": a} for y, a in b4],
            "b5": [{"year": y, "amounts": a} for y, a in b5],
        }
    )


def inventory(study_period, materials, per_year=None):
    """`materials`: {(assembly, material): material fields without the name}."""
    assemblies: dict[str, list] = {}
    for (assembly, name), fields in materials.items():
        assemblies.setdefault(assembly, []).append({"name": name, "unit": "m3", **fields})
    return BuildingInventory.model_validate(
        {
            "schema": "dlca.building_inventory",
            "name": "Hand case",
            "study_period": study_period,
            "assemblies": [{"name": a, "materials": m} for a, m in assemblies.items()],
            "per_year": per_year or {},
        }
    )


def events(pairs):
    return [{"year": y, "amounts": a} for y, a in pairs]


def assert_series(t: Timeline, expected: dict[str, list[float]]):
    """Each gas in `expected` matches exactly; every other gas is all zero."""
    got = t.emissions()
    assert set(got) == set(EMISSION_KEYS)
    for key in EMISSION_KEYS:
        want = np.array(expected.get(key, [0.0] * t.years), dtype=float)
        np.testing.assert_array_equal(got[key], want, err_msg=key)


# --- the hand-worked cases -----------------------------------------------------------


def test_worked_example_totals():
    # RSP 3, H 2: end of life in year 4, length 3 + 1 + 2 + 1 = 7.
    t = timeline(
        totals(
            3,
            modules={"A1-A3": {"co2": 100}, "A5": {"co2": 10}, "C3": {"co2": 20}, "C4": {"co2": 4}},
            per_year={"B6": {"co2": 5}},
            b4=[(2, {"co2": 30})],
            b5=[(1, {"co2": 7})],
        ),
        horizon=2,
    )
    assert t.years == 7
    assert t.end_of_life_year == 4
    # year 0 = 100 + 10; 1 = 5 + 7; 2 = 5 + 30; 3 = 5; 4 = 20 + 4.
    assert_series(t, {"co2": [110, 12, 35, 5, 24, 0, 0]})


def worked_example_inventory():
    # The same building as one material of quantity 2 with halved amounts.
    return inventory(
        3,
        {
            ("Frame", "Timber"): {
                "quantity": 2.0,
                "modules": {
                    "A1-A3": {"co2": 50},
                    "A5": {"co2": 5},
                    "C3": {"co2": 10},
                    "C4": {"co2": 2},
                },
                "b4": events([(2, {"co2": 15})]),
                "b5": events([(1, {"co2": 3.5})]),
            }
        },
        per_year={"B6": {"co2": 5}},  # kg per year, not scaled by quantity
    )


def test_worked_example_inventory_gives_same_series():
    t = timeline(worked_example_inventory(), horizon=2)
    assert_series(t, {"co2": [110, 12, 35, 5, 24, 0, 0]})


def test_one_material_with_a_b_c_all_gases():
    # RSP 3, H 1: end of life year 4, length 6. Quantity 2.
    t = timeline(
        inventory(
            3,
            {
                ("Floor", "Slab"): {
                    "quantity": 2.0,
                    "modules": {
                        "A1-A3": {"co2": 50, "ch4_fossil": 0.5},
                        "A4": {"co2": 2},
                        "A5": {"co2": 5, "n2o": 0.25},
                        "C1": {"co2": 1},
                        "C3": {"co2": 10, "ch4": 0.25},
                        "C4": {"co2": 2},
                    },
                    "per_year": {"B2": {"co2": 1, "n2o": 0.125}},
                }
            },
            per_year={"B6": {"co2": 5}},
        ),
        horizon=1,
    )
    assert t.years == 6
    # year 0: 2 * (50 + 2 + 5) = 114; years 1-3: 2 * 1 + 5 = 7; year 4: 2 * 13 = 26.
    assert_series(
        t,
        {
            "co2": [114, 7, 7, 7, 26, 0],
            "ch4": [0, 0, 0, 0, 0.5, 0],
            "ch4_fossil": [1.0, 0, 0, 0, 0, 0],
            "n2o": [0.5, 0.25, 0.25, 0.25, 0, 0],
        },
    )


def test_two_b4_events_in_their_years():
    # RSP 10, H 1: length 13. Two events in year 7 add.
    t = timeline(
        totals(10, b4=[(3, {"co2": 30}), (7, {"co2": 40}), (7, {"co2": 5})]),
        horizon=1,
    )
    want = [0.0] * 13
    want[3], want[7] = 30, 45
    assert_series(t, {"co2": want})


def test_b4_in_last_allowed_year():
    # The last allowed B4 year is RSP (5); end of life is year 6.
    t = timeline(
        totals(5, modules={"C4": {"co2": 10}}, per_year={"B1": {"co2": 2}}, b4=[(5, {"co2": 100})]),
        horizon=1,
    )
    assert_series(t, {"co2": [0, 2, 2, 2, 2, 102, 10, 0]})


def test_b5_events():
    # RSP 4, H 1: length 7. B5 in year 1 and in year RSP, plus B7 1 kg/yr.
    t = timeline(
        totals(4, per_year={"B7": {"co2": 1}}, b5=[(1, {"co2": 7}), (4, {"co2": 3})]),
        horizon=1,
    )
    assert_series(t, {"co2": [0, 8, 1, 1, 4, 0, 0]})


# --- the two old create_flux_mat bugs -----------------------------------------------


def test_same_year_amounts_add_not_overwrite():
    # Year 0: three A modules. Year 2: B1 + B3 + B6 + B4 + B5. Year 3: four C modules.
    t = timeline(
        totals(
            2,
            modules={
                "A1-A3": {"co2": 1},
                "A4": {"co2": 2},
                "A5": {"co2": 4},
                "C1": {"co2": 8},
                "C2": {"co2": 16},
                "C3": {"co2": 32},
                "C4": {"co2": 64},
            },
            per_year={"B1": {"co2": 128}, "B3": {"co2": 256}, "B6": {"co2": 512}},
            b4=[(2, {"co2": 1024})],
            b5=[(2, {"co2": 2048})],
        ),
        horizon=1,
    )
    assert_series(t, {"co2": [7, 896, 3968, 120, 0]})


COOPER_A = {"co2": 1000.0, "ch4": 2.0, "n2o": 0.1}
COOPER_B = {"co2": 10.0, "ch4": 0.05, "n2o": 0.002}
COOPER_C = {"co2": 200.0, "ch4": 1.0, "n2o": 0.02}


def cooper_building():
    """The amounts of the Cooper `building_lifecycle` case (tests/reference/README.md)."""
    return totals(
        60,
        modules={"A1-A3": COOPER_A, "C1": COOPER_C},
        per_year={"B2": COOPER_B},
    )


@pytest.mark.parametrize("gas", ["co2", "ch4", "n2o"])
def test_end_of_life_is_one_year(gas):
    t = timeline(cooper_building(), horizon=100)
    assert t.end_of_life_year == 61
    assert t.years == 60 + 1 + 100 + 1
    want = np.zeros(t.years)
    want[0] = COOPER_A[gas]
    want[1:61] = COOPER_B[gas]
    want[61] = COOPER_C[gas]
    np.testing.assert_array_equal(t.emissions()[gas], want)


@pytest.mark.parametrize("gas", ["CO2", "CH4", "N2O"])
def test_cooper_inputs_match_up_to_end_of_life(gas):
    """The spreadsheet case puts C in year 60; T1 puts it in year 61. Years
    0-59 and the C amount must agree with the spreadsheet's own inputs."""
    case = Path(__file__).resolve().parents[1] / "reference" / "cases" / "building_lifecycle"
    sheet = pd.read_csv(case / "inputs.csv")[f"{gas}_flux"].to_numpy(dtype=float)
    got = timeline(cooper_building(), horizon=100).emissions()[gas.lower()]
    np.testing.assert_array_equal(got[:60], sheet[:60])
    # Spreadsheet year 60 is B + C; here year 60 is B and year 61 is C.
    assert got[60] + got[61] == pytest.approx(sheet[60], rel=1e-12)
    assert not np.any(sheet[61:]) and not np.any(got[62:])


# --- length and the horizon (T3) ----------------------------------------------------


@pytest.mark.parametrize("study_period, horizon", [(1, 1), (60, 100), (75, 20)])
def test_length_gives_end_of_life_a_full_horizon(study_period, horizon):
    t = timeline(totals(study_period, modules={"C4": {"co2": 1}}), horizon=horizon)
    assert t.years == study_period + horizon + 2
    assert t.end_of_life_year + horizon == t.years - 1
    assert t.emissions()["co2"][t.end_of_life_year] == 1


def test_longer_series_pads_with_zeros():
    short = timeline(totals(3, modules={"A4": {"co2": 1}, "C2": {"co2": 2}}), horizon=2)
    long = timeline(totals(3, modules={"A4": {"co2": 1}, "C2": {"co2": 2}}), horizon=2, years=20)
    assert long.years == 20
    np.testing.assert_array_equal(long.emissions()["co2"][:7], short.emissions()["co2"])
    assert not np.any(long.emissions()["co2"][7:])


@pytest.mark.parametrize("years", [6, 0, -1, 7.0, True])
def test_shorter_or_bad_length_refused(years):
    with pytest.raises((ValueError, TypeError)):
        timeline(totals(3), horizon=2, years=years)


def test_numpy_integers_accepted():
    t = timeline(totals(3), horizon=np.int64(2), years=np.int32(9))
    assert (t.horizon, t.years) == (2, 9) and type(t.years) is int


@pytest.mark.parametrize("horizon", [0, -5, 100.0, 100.5, "100", True, None])
def test_bad_horizon_refused(horizon):
    with pytest.raises((ValueError, TypeError)):
        timeline(totals(3), horizon=horizon)


def test_not_a_building_refused():
    with pytest.raises(TypeError):
        timeline({"schema": "dlca.building_totals"})


# --- output: assess() and the breakdown (T4) ----------------------------------------


def test_emissions_feed_assess_without_change():
    t = timeline(worked_example_inventory(), horizon=20)
    result = dlca.assess(t.emissions(), horizon=20)
    assert result.gwi.dynamic.shape == (t.years,)
    np.testing.assert_array_equal(result.emissions["co2"], t.emissions()["co2"])


def test_parts_keys_for_both_schemas():
    t = timeline(worked_example_inventory(), horizon=2)
    assert set(t.parts) == {
        ("Frame", "Timber", "A1-A3"),
        ("Frame", "Timber", "A5"),
        ("Frame", "Timber", "C3"),
        ("Frame", "Timber", "C4"),
        ("Frame", "Timber", "B4"),
        ("Frame", "Timber", "B5"),
        (None, None, "B6"),
    }
    t = timeline(totals(3, modules={"A4": {"co2": 1}}, b5=[(1, {"co2": 1})]), horizon=2)
    assert set(t.parts) == {(None, None, "A4"), (None, None, "B5")}


def test_breakdowns_by_module_and_material():
    t = timeline(
        inventory(
            2,
            {
                ("Floor", "Slab"): {"quantity": 3.0, "modules": {"A1-A3": {"co2": 1}}},
                ("Roof", "Slab"): {
                    "quantity": 1.0,
                    "modules": {"A1-A3": {"co2": 10}, "C3": {"n2o": 1}},
                },
            },
            per_year={"B6": {"co2": 100}},
        ),
        horizon=1,
    )
    by_module = t.by_module()
    assert set(by_module) == {"A1-A3", "C3", "B6"}
    np.testing.assert_array_equal(by_module["A1-A3"]["co2"], [13, 0, 0, 0, 0])
    np.testing.assert_array_equal(by_module["B6"]["co2"], [0, 100, 100, 0, 0])
    np.testing.assert_array_equal(by_module["C3"]["n2o"], [0, 0, 0, 1, 0])

    by_material = t.by_material()
    assert set(by_material) == {("Floor", "Slab"), ("Roof", "Slab")}  # B6 is no material
    np.testing.assert_array_equal(by_material[("Floor", "Slab")]["co2"], [3, 0, 0, 0, 0])
    np.testing.assert_array_equal(by_material[("Roof", "Slab")]["co2"], [10, 0, 0, 0, 0])


def test_output_arrays_are_read_only_and_emissions_is_a_copy():
    t = timeline(totals(2, modules={"A4": {"co2": 1}}), horizon=1)
    part = t.parts[(None, None, "A4")]["co2"]
    with pytest.raises(ValueError):
        part[0] = 5
    with pytest.raises(TypeError):
        t.parts[(None, None, "X")] = {}
    out = t.emissions()
    out["co2"][0] = 99
    assert t.emissions()["co2"][0] == 1


def test_empty_building_gives_zeros():
    t = timeline(totals(4), horizon=3)
    assert t.parts == {}
    assert_series(t, {})
