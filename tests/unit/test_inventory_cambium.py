"""B6 electricity from the packaged Cambium 2024 extract (#85, record 0021).

The expected values were worked out by hand from NLR's source files and
posted on issue #85 before the code ran (C0-C6, 2026-11-20). CAISO,
10 000 kWh/yr = 10 MWh; study year y is calendar year `year_zero` + y.

1. Mid-case, year_zero 2024, study year 6 = 2030: aer_gen_co2_c 108.8 kg/MWh
   x 10 = 1 088.0 kg CO2; aer_gen_ch4_c 2.1 g/MWh x 10 = 0.021 kg ch4_fossil;
   aer_gen_n2o_c 0.21 g/MWh x 10 = 0.0021 kg N2O.
2. Join, Mid-case, year_zero 2024, study year 1 = 2025: straight line from
   the 2023 historical 182.4750604 to the 2030 Cambium 108.8 kg/MWh (Cambium's
   2025 point dropped): 161.4250431 kg/MWh -> 1 614.2504 kg CO2.
3. Historical year, year_zero 2020, study year 3 = 2023: 182.4750604 x 10 =
   1 824.7506 kg CO2.
4. After 2050, Mid-case: the 2050 value 44.1 held -> 441.0 kg CO2.
5. HighDemandGrowth, 2030: 105.2 x 10 = 1 052.0 kg CO2.

Tolerance on CO2: 0.01 kg absolute (Jay, #85). CH4 and N2O use 1e-6 kg
absolute, because 0.01 kg is coarser than the values themselves.
"""

import csv
from importlib.resources import files

import numpy as np
import pytest
from pydantic import ValidationError

from dlca.inventory import BuildingResult, BuildingTotals, EnergyUse, assess_building, timeline
from dlca.inventory.operational import CAMBIUM_FILE, CAMBIUM_HISTORICAL_FILE
from dlca.inventory.schema import CambiumGea, CambiumScenario

RSP = 30
CO2_TOL = 0.01


def line(gea="CAISO", year_zero=2024, **extra):
    return {"fuel": "electricity", "amount": 10_000.0, "unit": "kWh", "cambium_gea": gea,
            "year_zero": year_zero} | extra  # fmt: skip


def b6(*lines, rsp=RSP, **extra):
    building = BuildingTotals.model_validate(
        {"schema": "dlca.building_totals", "name": "b", "study_period": rsp, "energy": list(lines)}
        | extra
    )
    return timeline(building, horizon=1).by_module()["B6"]


# Independent checks (#85) -------------------------------------------------------


def test_check_1_cambium_point_2030():
    out = b6(line())
    np.testing.assert_allclose(out["co2"][6], 1088.0, rtol=0, atol=CO2_TOL)
    np.testing.assert_allclose(out["ch4_fossil"][6], 0.021, rtol=0, atol=1e-6)
    np.testing.assert_allclose(out["n2o"][6], 0.0021, rtol=0, atol=1e-6)
    assert np.all(out["ch4"] == 0.0)


def test_check_2_join_drops_cambium_2025():
    out = b6(line())
    np.testing.assert_allclose(out["co2"][1], 1614.2504, rtol=0, atol=CO2_TOL)


def test_check_3_historical_year():
    out = b6(line(year_zero=2020))
    np.testing.assert_allclose(out["co2"][3], 1824.7506, rtol=0, atol=CO2_TOL)


def test_check_4_after_2050_holds():
    out = b6(line())
    # Study years 26..30 are 2050..2054.
    np.testing.assert_allclose(out["co2"][26 : RSP + 1], 441.0, rtol=0, atol=CO2_TOL)


def test_check_5_scenario_column():
    out = b6(line(cambium_scenario="HighDemandGrowth"))
    np.testing.assert_allclose(out["co2"][6], 1052.0, rtol=0, atol=CO2_TOL)


# Timing ------------------------------------------------------------------------


def test_b6_only_in_years_1_to_rsp():
    out = b6(line(), rsp=5)
    assert out["co2"][0] == 0.0
    assert np.all(out["co2"][1:6] > 0.0)
    assert np.all(out["co2"][6:] == 0.0)


def test_default_scenario_is_midcase_and_scenarios_differ():
    default = b6(line())["co2"]
    np.testing.assert_array_equal(default, b6(line(cambium_scenario="MidCase"))["co2"])
    # Positive control: the same comparison sees another scenario.
    assert not np.array_equal(default, b6(line(cambium_scenario="LowNGPrice"))["co2"])


def test_unit_conversion():
    kwh = b6(line())
    mj = b6(line(amount=36_000.0, unit="MJ"))
    for gas in ("co2", "ch4_fossil", "n2o"):
        np.testing.assert_allclose(mj[gas], kwh[gas], rtol=1e-12)


def test_constant_trajectory_allowed():
    np.testing.assert_array_equal(
        b6(line(trajectory={"kind": "constant"}))["co2"], b6(line())["co2"]
    )


# Input rules -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("extra", "error"),
    [
        ({"fuel": "natural_gas"}, "electricity only"),
        ({"egrid_subregion": "CAMX"}, "exactly one"),
        ({"factor": {"co2": 1.0}}, "exactly one"),
        ({"year_zero": None}, "year_zero"),
        ({"cambium_gea": None}, "cambium_gea"),
        ({"trajectory": {"kind": "linear", "target": 0.5, "target_year": 5}}, "scaled twice"),
        ({"cambium_gea": "CAMX"}, "cambium_gea"),
        ({"cambium_scenario": "Mid-case"}, "cambium_scenario"),
    ],
)
def test_bad_cambium_line_refused(extra, error):
    data = {k: v for k, v in (line() | extra).items() if v is not None}
    with pytest.raises(ValidationError, match=error):
        EnergyUse.model_validate(data)


def test_scenario_without_gea_refused():
    with pytest.raises(ValidationError, match="cambium_gea"):
        EnergyUse.model_validate(
            {"fuel": "electricity", "amount": 1.0, "unit": "kWh", "egrid_subregion": "CAMX",
             "cambium_scenario": "MidCase"}
        )  # fmt: skip


def test_cambium_needs_schema_version_6():
    with pytest.raises(ValidationError, match="schema_version 6"):
        b6(line(), schema_version=5)


def test_round_trip_and_unset_fields_left_out():
    building = BuildingTotals.model_validate(
        {"schema": "dlca.building_totals", "name": "b", "study_period": 5, "energy": [line()]}
    )
    dumped = building.model_dump(mode="json")
    assert "cambium_scenario" not in dumped["energy"][0]
    assert BuildingTotals.model_validate(dumped) == building
    back = BuildingResult.from_dict(assess_building(building, horizon=10).to_dict())
    assert back.building == building


# Packaged data -----------------------------------------------------------------


def _column(file_name, name):
    with files("dlca.data").joinpath(file_name).open(encoding="utf-8") as f:
        return sorted({row[name] for row in csv.DictReader(f)})


def test_schema_names_match_packaged_files():
    assert sorted(CambiumGea.__args__) == _column(CAMBIUM_FILE, "gea")
    assert sorted(CambiumGea.__args__) == _column(CAMBIUM_HISTORICAL_FILE, "gea")
    assert sorted(CambiumScenario.__args__) == _column(CAMBIUM_FILE, "scenario")
