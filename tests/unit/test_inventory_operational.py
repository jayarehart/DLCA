"""Operational energy B6 from energy use by fuel (#82, record 0019).

The expected values are hand calculations from published tables, written in
issue #82 before the code ran:

1. 10 000 kWh/yr in CAMX at eGRID2023 Rev 2 428.464 lb CO2/MWh:
   10 MWh x 428.464 x 0.45359237 = 1 943.4800 kg CO2 in each of years 1..RSP.
2. 100 mmBtu/yr of natural gas at EPA Hub 2025 Table 1 (53.06 kg CO2,
   1.0 g CH4, 0.10 g N2O per mmBtu): 5 306 kg CO2, 0.1 kg ch4_fossil,
   0.01 kg N2O per year.
3. to_study_years({2025: 0.4, 2027: 0.2}, 2024, 6) = [0.4, 0.4, 0.3, 0.2, 0.2, 0.2].
4. 1 000 kWh/yr with a user CO2 factor series [0.4, 0.4, 0.3, 0.2] per kWh
   (index = study year), RSP 5: 400, 300, 200, 200, 200 kg CO2 in years 1..5.
"""

import csv
from importlib.resources import files

import numpy as np
import pytest
from pydantic import ValidationError

from dlca.inventory import (
    BuildingInventory,
    BuildingTotals,
    EnergyUse,
    assess_building,
    timeline,
    to_study_years,
)
from dlca.inventory.operational import (
    EGRID_STATE_FILE,
    EGRID_SUBREGION_FILE,
    electricity_factor_per_mj,
)
from dlca.inventory.schema import EgridState, EgridSubregion, EnergyUnit
from dlca.inventory.units import MJ_PER_UNIT

RSP = 5


def totals(energy, *, rsp=RSP, **extra):
    return BuildingTotals.model_validate(
        {"schema": "dlca.building_totals", "name": "b", "study_period": rsp, "energy": energy}
        | extra
    )


def b6(building):
    t = timeline(building, horizon=1)
    return t.by_module()["B6"]


# 1. Electricity, CAMX ---------------------------------------------------------


def test_check_1_camx_electricity():
    out = b6(totals([{"fuel": "electricity", "amount": 10_000.0, "unit": "kWh",
                      "egrid_subregion": "CAMX"}]))  # fmt: skip
    co2 = out["co2"]
    assert co2[0] == 0.0
    np.testing.assert_allclose(co2[1 : RSP + 1], 1943.4800, rtol=0, atol=0.01)
    assert np.all(co2[RSP + 1 :] == 0.0)


def test_subregion_and_state_are_separate_tables():
    # CA (state) is not CAMX (subregion): a lookup in the wrong table fails the check.
    ca = electricity_factor_per_mj(state="CA")["co2"] * 36_000
    camx = electricity_factor_per_mj(subregion="CAMX")["co2"] * 36_000
    assert abs(camx - 1943.4800) <= 0.01
    assert abs(ca - 1943.4800) > 0.01
    with pytest.raises(ValueError, match="unknown eGRID state"):
        electricity_factor_per_mj(state="CAMX")
    with pytest.raises(ValueError, match="exactly one"):
        electricity_factor_per_mj(subregion="CAMX", state="CA")


def test_state_code_refused_as_subregion_in_schema():
    with pytest.raises(ValidationError):
        totals([{"fuel": "electricity", "amount": 1.0, "unit": "kWh", "egrid_subregion": "CA"}])


def test_electricity_ch4_is_fossil():
    out = b6(totals([{"fuel": "electricity", "amount": 10_000.0, "unit": "kWh",
                      "egrid_subregion": "CAMX"}]))  # fmt: skip
    # 10 MWh x 0.025 lb CH4/MWh x 0.45359237 = 0.1133980925 kg
    np.testing.assert_allclose(out["ch4_fossil"][1], 0.1133980925, rtol=1e-12)
    assert np.all(out["ch4"] == 0.0)


# 2. Natural gas ---------------------------------------------------------------


def test_check_2_natural_gas():
    out = b6(totals([{"fuel": "natural_gas", "amount": 100.0, "unit": "MMBtu"}]))
    np.testing.assert_allclose(out["co2"][1 : RSP + 1], 5306.0, rtol=1e-12)
    np.testing.assert_allclose(out["ch4_fossil"][1 : RSP + 1], 0.1, rtol=1e-12)
    np.testing.assert_allclose(out["n2o"][1 : RSP + 1], 0.01, rtol=1e-12)
    assert np.all(out["ch4"] == 0.0)


def test_natural_gas_in_therms_matches_mmbtu():
    # 1 MMBtu = 10 therm, by definition of both units.
    a = b6(totals([{"fuel": "natural_gas", "amount": 100.0, "unit": "MMBtu"}]))
    b = b6(totals([{"fuel": "natural_gas", "amount": 1000.0, "unit": "therm"}]))
    np.testing.assert_allclose(a["co2"], b["co2"], rtol=1e-12)


def test_fuel_oil_2():
    out = b6(totals([{"fuel": "fuel_oil_2", "amount": 100.0, "unit": "MMBtu"}]))
    np.testing.assert_allclose(out["co2"][1], 7396.0, rtol=1e-12)
    np.testing.assert_allclose(out["ch4_fossil"][1], 0.3, rtol=1e-12)
    np.testing.assert_allclose(out["n2o"][1], 0.06, rtol=1e-12)


# 3. Calendar-year helper ------------------------------------------------------


def test_check_3_to_study_years():
    got = to_study_years({2025: 0.4, 2027: 0.2}, 2024, 6)
    np.testing.assert_allclose(got, [0.4, 0.4, 0.3, 0.2, 0.2, 0.2], rtol=1e-12)
    # Deliberate mistake: a step (hold previous) would give 0.4 for 2026.
    assert abs(got[2] - 0.4) > 1e-9


@pytest.mark.parametrize(
    "values, year_zero, n_years, error",
    [
        ({}, 2024, 3, ValueError),
        ({2025: -1.0}, 2024, 3, ValueError),
        ({2025: float("nan")}, 2024, 3, ValueError),
        ({2025.0: 1.0}, 2024, 3, TypeError),
        ({2025: 1.0}, 2024.0, 3, TypeError),
        ({2025: 1.0}, 2024, 0, ValueError),
    ],
)
def test_to_study_years_refuses(values, year_zero, n_years, error):
    with pytest.raises(error):
        to_study_years(values, year_zero, n_years)


# 4. Absolute factor series ----------------------------------------------------


def test_check_4_absolute_factor_series():
    series = [{"co2": v} for v in (0.4, 0.4, 0.3, 0.2)]
    out = b6(totals([{"fuel": "electricity", "amount": 1000.0, "unit": "kWh", "factor": series}]))
    np.testing.assert_allclose(out["co2"][1 : RSP + 1], [400, 300, 200, 200, 200], rtol=1e-12)
    assert out["co2"][0] == 0.0 and out["co2"][RSP + 1] == 0.0


def test_constant_user_factor_keeps_its_gas_keys():
    factor = {"co2": 0.1, "ch4": 0.01}
    out = b6(totals([{"fuel": "natural_gas", "amount": 10.0, "unit": "GJ", "factor": factor}]))
    np.testing.assert_allclose(out["co2"][1], 1.0)
    np.testing.assert_allclose(out["ch4"][1], 0.1)
    assert np.all(out["ch4_fossil"] == 0.0)


# Input rules ------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        {"fuel": "electricity", "amount": 1.0, "unit": "kWh"},
        {"fuel": "electricity", "amount": 1.0, "unit": "kWh", "egrid_subregion": "CAMX",
         "egrid_state": "CA"},
        {"fuel": "electricity", "amount": 1.0, "unit": "kWh", "egrid_state": "CA",
         "factor": {"co2": 1.0}},
        {"fuel": "natural_gas", "amount": 1.0, "unit": "MMBtu", "egrid_state": "CA"},
        {"fuel": "natural_gas", "amount": -1.0, "unit": "MMBtu"},
        {"fuel": "natural_gas", "amount": 1.0, "unit": "Wh"},
        {"fuel": "coal", "amount": 1.0, "unit": "MMBtu"},
        {"fuel": "electricity", "amount": 1.0, "unit": "kWh", "factor": []},
    ],
)  # fmt: skip
def test_bad_energy_line_refused(line):
    with pytest.raises(ValidationError):
        EnergyUse.model_validate(line)


def test_energy_and_per_year_b6_refused_together():
    with pytest.raises(ValidationError, match="not both"):
        totals(
            [{"fuel": "natural_gas", "amount": 1.0, "unit": "MMBtu"}],
            per_year={"B6": {"co2": 1.0}},
        )
    with pytest.raises(ValidationError, match="not both"):
        BuildingInventory.model_validate(
            {
                "schema": "dlca.building_inventory",
                "name": "b",
                "study_period": RSP,
                "assemblies": [{"name": "a", "materials": [
                    {"name": "m", "quantity": 1.0, "unit": "kg"}]}],
                "per_year": {"B6": {"co2": 1.0}},
                "energy": [{"fuel": "natural_gas", "amount": 1.0, "unit": "MMBtu"}],
            }
        )  # fmt: skip


def test_energy_needs_schema_version_5():
    with pytest.raises(ValidationError, match="schema_version 5"):
        totals([{"fuel": "natural_gas", "amount": 1.0, "unit": "MMBtu"}], schema_version=4)


def test_inventory_energy_equals_totals_energy():
    line = {"fuel": "electricity", "amount": 10_000.0, "unit": "kWh", "egrid_state": "CO"}
    inv = BuildingInventory.model_validate(
        {
            "schema": "dlca.building_inventory",
            "name": "b",
            "study_period": RSP,
            "assemblies": [{"name": "a", "materials": [{"name": "m", "quantity": 1.0,
                                                        "unit": "kg"}]}],
            "energy": [line],
        }
    )  # fmt: skip
    np.testing.assert_array_equal(b6(inv)["co2"], b6(totals([line]))["co2"])


def test_energy_equals_the_same_amount_as_per_year_b6():
    # Positive control for "same result": a kg-of-gas B6 equal to the energy
    # line's hand value gives the same assess() result, and a different one does not.
    line = [{"fuel": "natural_gas", "amount": 100.0, "unit": "MMBtu"}]
    same = {"co2": 5306.0, "ch4_fossil": 0.1, "n2o": 0.01}
    other = {"co2": 5307.0, "ch4_fossil": 0.1, "n2o": 0.01}
    by_energy = assess_building(totals(line), horizon=20).total.gwi.dynamic
    by_kg = assess_building(totals([], per_year={"B6": same}), horizon=20).total.gwi.dynamic
    by_other = assess_building(totals([], per_year={"B6": other}), horizon=20).total.gwi.dynamic
    np.testing.assert_allclose(by_energy, by_kg, rtol=1e-12)
    assert not np.allclose(by_energy, by_other, rtol=1e-12)


def test_round_trip_and_empty_energy_left_out():
    b = totals([{"fuel": "electricity", "amount": 1.0, "unit": "kWh", "egrid_subregion": "NYUP"}])
    assert BuildingTotals.model_validate(b.model_dump()) == b
    assert "energy" not in totals([]).model_dump()


# Packaged data in step with the schema ----------------------------------------


def _codes(file_name):
    with files("dlca.data").joinpath(file_name).open(encoding="utf-8") as f:
        return [next(iter(row.values())) for row in csv.DictReader(f)]


def test_schema_codes_match_packaged_files():
    assert list(EgridSubregion.__args__) == _codes(EGRID_SUBREGION_FILE)
    assert list(EgridState.__args__) == _codes(EGRID_STATE_FILE)


def test_schema_units_match_unit_table():
    assert set(EnergyUnit.__args__) == set(MJ_PER_UNIT)


# Trajectories (record 0018 kinds, record 0019) --------------------------------


def test_linear_trajectory_scales_fossil_gases_only():
    # m(y) = 1 - y/10 (linear to 0 in year 10). Year 2: m = 0.8.
    line = {
        "fuel": "electricity",
        "amount": 1000.0,
        "unit": "kWh",
        "factor": {"co2": 0.5, "ch4": 0.01, "ch4_fossil": 0.02, "n2o": 0.001},
        "trajectory": {"kind": "linear", "target": 0.0, "target_year": 10},
    }
    out = b6(totals([line]))
    np.testing.assert_allclose(out["co2"][2], 400.0, rtol=1e-12)
    np.testing.assert_allclose(out["ch4_fossil"][2], 16.0, rtol=1e-12)
    np.testing.assert_allclose(out["n2o"][2], 0.8, rtol=1e-12)
    np.testing.assert_allclose(out["ch4"][2], 10.0, rtol=1e-12)  # non-fossil: not scaled
    # Year 1 gets m(1) = 0.9, not m(0) = 1 (indexing by year - 1 would give 500).
    np.testing.assert_allclose(out["co2"][1], 450.0, rtol=1e-12)


def test_trajectory_per_line():
    grid = {"fuel": "electricity", "amount": 1000.0, "unit": "kWh", "factor": {"co2": 1.0},
            "trajectory": {"kind": "series", "values": [1.0, 0.5]}}  # fmt: skip
    gas = {"fuel": "natural_gas", "amount": 100.0, "unit": "MMBtu"}
    out = b6(totals([grid, gas]))
    np.testing.assert_allclose(out["co2"][1 : RSP + 1], 500.0 + 5306.0, rtol=1e-12)


def test_constant_trajectory_same_as_none_and_linear_differs():
    # Positive control: the same comparison detects a non-constant trajectory.
    base = {"fuel": "natural_gas", "amount": 100.0, "unit": "MMBtu"}
    none = b6(totals([base]))["co2"]
    const = b6(totals([base | {"trajectory": {"kind": "constant"}}]))["co2"]
    linear = b6(totals([base | {"trajectory": {"kind": "linear", "target": 0.5,
                                               "target_year": 5}}]))["co2"]  # fmt: skip
    np.testing.assert_array_equal(none, const)
    assert not np.array_equal(none, linear)


def test_series_factor_with_trajectory_refused():
    with pytest.raises(ValidationError, match="scaled twice"):
        EnergyUse.model_validate(
            {"fuel": "electricity", "amount": 1.0, "unit": "kWh", "factor": [{"co2": 1.0}],
             "trajectory": {"kind": "linear", "target": 0.0, "target_year": 5}}
        )  # fmt: skip


def test_building_result_round_trip_with_energy():
    from dlca.inventory import BuildingResult

    b = totals([{"fuel": "electricity", "amount": 1.0, "unit": "kWh", "egrid_state": "TX",
                 "trajectory": {"kind": "linear", "target": 0.2, "target_year": 3}}])  # fmt: skip
    r = assess_building(b, horizon=10)
    back = BuildingResult.from_dict(r.to_dict())
    assert back.building == b
