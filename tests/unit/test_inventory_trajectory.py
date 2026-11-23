"""The `Trajectory` type and the `b4_c_trajectory` field (#81, record 0018).

Faults these catch that no other test does: a multiplier series of the wrong
length or shape (a short series not held, a long one not cut, linear not held
after its target year); a bad trajectory accepted (empty or negative series, a
first value other than 1, a negative target, a target year below 1 or not a
whole number, an unknown kind); the field accepted in a schema version 1-3
file; a non-constant trajectory refused on a building with a `biogenic`
field (record 0020 lifted the record 0018 refusal); an absent field written
into the JSON (so old files would not round-trip unchanged); the trajectory
lost in `BuildingResult` JSON.
"""

import json

import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError

from dlca.inventory import (
    BUILDING_RESULT_SCHEMA_VERSION,
    SCHEMA_VERSION,
    BuildingInventory,
    BuildingResult,
    BuildingTotals,
    ConstantTrajectory,
    LinearTrajectory,
    SeriesTrajectory,
    Trajectory,
    assess_building,
)

LINEAR = {"kind": "linear", "target": 0.0, "target_year": 50}
BIOGENIC = {"co2": 10.0, "regrowth": "instant"}

trajectory = TypeAdapter(Trajectory)


def totals(**fields):
    return BuildingTotals.model_validate(
        {
            "schema": "dlca.building_totals",
            "name": "Case",
            "study_period": 60,
            "modules": {"C4": {"co2": 1.0}},
            **fields,
        }
    )


def inventory(material=None, **fields):
    return BuildingInventory.model_validate(
        {
            "schema": "dlca.building_inventory",
            "name": "Case",
            "study_period": 60,
            "assemblies": [
                {
                    "name": "Wall",
                    "materials": [
                        {"name": "Board", "quantity": 1.0, "unit": "m3", **(material or {})}
                    ],
                }
            ],
            **fields,
        }
    )


def test_versions():
    # #85 (record 0021) bumped both to 6; the trajectory field arrived in 4.
    assert SCHEMA_VERSION == 6
    assert BUILDING_RESULT_SCHEMA_VERSION == 6


def test_constant_multipliers_are_one():
    np.testing.assert_array_equal(ConstantTrajectory(kind="constant").multipliers(5), np.ones(5))


def test_linear_multipliers():
    linear = trajectory.validate_python({"kind": "linear", "target": 0.5, "target_year": 4})
    m = linear.multipliers(7)
    np.testing.assert_allclose(m, [1.0, 0.875, 0.75, 0.625, 0.5, 0.5, 0.5], rtol=0, atol=1e-15)


def test_series_shorter_is_held_longer_is_cut():
    s = trajectory.validate_python({"kind": "series", "values": [1.0, 0.8, 0.6]})
    assert isinstance(s, SeriesTrajectory)
    np.testing.assert_array_equal(s.multipliers(5), [1.0, 0.8, 0.6, 0.6, 0.6])
    np.testing.assert_array_equal(s.multipliers(2), [1.0, 0.8])


def test_integer_values_accepted_where_floats_are():
    assert isinstance(
        trajectory.validate_python({"kind": "linear", "target": 0, "target_year": 50}),
        LinearTrajectory,
    )
    trajectory.validate_python({"kind": "series", "values": [1, 0]})


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "series", "values": []},
        {"kind": "series", "values": [0.9, 0.5]},
        {"kind": "series", "values": [1.0, -0.1]},
        {"kind": "series", "values": [1.0, float("nan")]},
        {"kind": "series", "values": [1.0, float("inf")]},
        {"kind": "linear", "target": -0.1, "target_year": 10},
        {"kind": "linear", "target": float("nan"), "target_year": 10},
        {"kind": "linear", "target": 0.0, "target_year": 0},
        {"kind": "linear", "target": 0.0, "target_year": 10.0},
        {"kind": "linear", "target": 0.0},
        {"kind": "constant", "target": 0.0},
        {"kind": "exponential"},
        {"target": 0.0, "target_year": 10},
    ],
)
def test_bad_trajectory_refused(bad):
    with pytest.raises(ValidationError):
        trajectory.validate_python(bad)


@pytest.mark.parametrize("version", [1, 2, 3])
def test_field_refused_before_schema_version_4(version):
    with pytest.raises(ValidationError, match="schema_version 4"):
        totals(schema_version=version, b4_c_trajectory=LINEAR)
    with pytest.raises(ValidationError, match="schema_version 4"):
        inventory(schema_version=version, b4_c_trajectory=LINEAR)


def test_old_version_file_without_field_round_trips_unchanged():
    d = {"schema": "dlca.building_totals", "schema_version": 3, "name": "Old", "study_period": 5}
    dumped = BuildingTotals.model_validate(d).model_dump(mode="json", by_alias=True)
    assert "b4_c_trajectory" not in dumped
    assert dumped["schema_version"] == 3


@pytest.mark.parametrize(
    "make",
    [
        lambda t: totals(biogenic=BIOGENIC, b4_c_trajectory=t),
        lambda t: totals(b4=[{"year": 5, "amounts": {}, "biogenic": BIOGENIC}], b4_c_trajectory=t),
        lambda t: totals(b5=[{"year": 5, "amounts": {}, "biogenic": BIOGENIC}], b4_c_trajectory=t),
        lambda t: inventory({"biogenic": BIOGENIC}, b4_c_trajectory=t),
        lambda t: inventory(
            {"b4": [{"year": 5, "amounts": {}, "biogenic": BIOGENIC}]}, b4_c_trajectory=t
        ),
        lambda t: inventory(
            {"b5": [{"year": 5, "amounts": {}, "biogenic": BIOGENIC}]}, b4_c_trajectory=t
        ),
    ],
    ids=["totals", "totals-b4", "totals-b5", "material", "material-b4", "material-b5"],
)
def test_non_constant_accepted_with_any_biogenic_field(make):
    # Record 0020 (#86) replaces the record 0018 refusal with a per-material
    # exemption; see tests/analytic/test_trajectory_biogenic.py.
    for t in (LINEAR, {"kind": "series", "values": [1.0]}, {"kind": "constant"}):
        assert make(t).b4_c_trajectory is not None


def test_released_co2_zero_accepted():
    b = inventory({"biogenic": {**BIOGENIC, "released_co2": 0.0}}, b4_c_trajectory=LINEAR)
    assert b.b4_c_trajectory.kind == "linear"


def test_building_result_json_keeps_the_trajectory():
    r = assess_building(
        inventory({"modules": {"C4": {"co2": 1.0}}}, b4_c_trajectory=LINEAR), horizon=20
    )
    d = json.loads(json.dumps(r.to_dict()))
    assert d["schema_version"] == 6
    assert d["building"]["b4_c_trajectory"] == LINEAR
    back = BuildingResult.from_dict(d)
    assert back.building == r.building
    assert back.by_module["C4"].gwi_dynamic[61] == 0.0
