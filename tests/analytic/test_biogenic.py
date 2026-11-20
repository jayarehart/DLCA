"""Biogenic uptake through the whole chain against IPCC AR6 (#73, independent check).

A 1 kg instant biogenic uptake in year 0 is a -1 kg CO2 pulse. H = 100 years
later its integrated forcing and temperature change are -AGWP100(CO2) and
-AGTP100(CO2). Values typed from AR6 WG1 Ch. 7, Table 7.SM.7 (8.95e-14
W m-2 yr kg-1, 3.95e-16 K kg-1), the same printed values as
``test_assess.py``; tolerance half a unit in the last printed digit.

Fault this catches that no other test does: uptake reaching ``assess()`` with
the wrong sign, in the wrong year or in the wrong unit (kg C instead of kg
CO2, a factor 44.01/12.011), through the schema, ``timeline()`` and the sum.
"""

import dlca
from dlca.inventory import BuildingTotals, timeline


def assert_matches_table(got: float, printed: str) -> None:
    mantissa, _, exponent = printed.lower().partition("e")
    tol = 0.5 * 10.0 ** (-len(mantissa.partition(".")[2])) * 10.0 ** int(exponent or 0)
    want = float(printed)
    assert abs(got - want) <= tol, f"got {got!r}, table {printed} +/- {tol:g}"


def test_instant_uptake_of_1_kg_is_minus_agwp100_and_minus_agtp100():
    b = BuildingTotals.model_validate(
        {
            "schema": "dlca.building_totals",
            "schema_version": 2,
            "name": "One kg uptake",
            "study_period": 1,
            "biogenic": {"co2": 1.0, "regrowth": "instant"},
        }
    )
    r = dlca.assess(timeline(b, horizon=100).emissions(), horizon=100)
    assert r.parameter_set == "AR6"
    assert_matches_table(r.forcing.total_integrated[100], "-8.95e-14")
    assert_matches_table(r.temperature.total[100], "-3.95e-16")
