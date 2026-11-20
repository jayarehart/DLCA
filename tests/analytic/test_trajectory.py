"""Emission-factor trajectories against closed-form values (#81, record 0018).

Every expected value here was written in #81 (decisions comment of
2026-11-20) before the code existed. RSP = 60 and ``linear`` to ``target`` =
0 in ``target_year`` = 50, so m(y) = 1 - y/50 up to year 50 and 0 after:

- 100 kg CO2 in a B4 event in year 25 -> 50 kg.
- 10 kg ``ch4``, 10 kg ``ch4_fossil``, 1 kg ``n2o`` in that event -> 10, 5, 0.5
  (non-fossil CH4 is not scaled).
- A B4 event in year 55 -> 0. C (year 61) -> 0. A1-A3, B1 and B5 unchanged.
- ``series`` [1, 0.5] holds 0.5: B4 in year 25 -> 50 kg, C -> 50 kg.

Faults these catch that no other test does: the multiplier taken at the wrong
year (event year - 1, or RSP instead of RSP + 1 for C); the multiplier applied
to A1-A3, B1-B3 or B5, or to non-fossil CH4; a `linear` trajectory not held at
its target after the target year; a short `series` not holding its last value;
the material quantity and the multiplier not both applied.
"""

import numpy as np
import pytest

import dlca
from dlca.climate import EMISSION_KEYS
from dlca.inventory import BuildingInventory, BuildingTotals, assess_building, timeline

LINEAR_TO_ZERO = {"kind": "linear", "target": 0.0, "target_year": 50}

EVENT_25 = {"co2": 100.0, "ch4": 10.0, "ch4_fossil": 10.0, "n2o": 1.0}


def totals(trajectory=None, **fields):
    d = {
        "schema": "dlca.building_totals",
        "name": "Trajectory hand case",
        "study_period": 60,
        "modules": {"A1-A3": {"co2": 100.0}, "C3": {"co2": 100.0}},
        "per_year": {"B1": {"co2": 1.0}},
        "b4": [
            {"year": 25, "amounts": EVENT_25},
            {"year": 55, "amounts": {"co2": 100.0}},
        ],
        "b5": [{"year": 25, "amounts": {"co2": 100.0}}],
        **fields,
    }
    if trajectory is not None:
        d["b4_c_trajectory"] = trajectory
    return BuildingTotals.model_validate(d)


def part(t, module, assembly=None, material=None):
    return t.parts[(assembly, material, module)]


def test_linear_to_zero_closed_form():
    t = timeline(totals(LINEAR_TO_ZERO), horizon=10)
    b4 = part(t, "B4")
    assert b4["co2"][25] == pytest.approx(50.0, rel=1e-12)
    assert b4["ch4"][25] == 10.0
    assert b4["ch4_fossil"][25] == pytest.approx(5.0, rel=1e-12)
    assert b4["n2o"][25] == pytest.approx(0.5, rel=1e-12)
    assert b4["co2"][55] == 0.0
    assert part(t, "C3")["co2"][61] == 0.0
    assert part(t, "A1-A3")["co2"][0] == 100.0
    assert part(t, "B5")["co2"][25] == 100.0
    np.testing.assert_array_equal(part(t, "B1")["co2"][1:61], np.ones(60))


def test_linear_held_at_a_nonzero_target_after_the_target_year():
    # target 0.4 in year 20: m(10) = 1 - 0.6 * 10/20 = 0.7, m(30) = 0.4, m(61) = 0.4.
    trajectory = {"kind": "linear", "target": 0.4, "target_year": 20}
    b = totals(
        trajectory,
        b4=[{"year": 10, "amounts": {"co2": 100.0}}, {"year": 30, "amounts": {"co2": 100.0}}],
    )
    t = timeline(b, horizon=10)
    assert part(t, "B4")["co2"][10] == pytest.approx(70.0, rel=1e-12)
    assert part(t, "B4")["co2"][30] == pytest.approx(40.0, rel=1e-12)
    assert part(t, "C3")["co2"][61] == pytest.approx(40.0, rel=1e-12)


def test_short_series_holds_its_last_value():
    t = timeline(totals({"kind": "series", "values": [1.0, 0.5]}), horizon=10)
    assert part(t, "B4")["co2"][25] == pytest.approx(50.0, rel=1e-12)
    assert part(t, "C3")["co2"][61] == pytest.approx(50.0, rel=1e-12)
    assert part(t, "A1-A3")["co2"][0] == 100.0


def test_inventory_applies_quantity_and_multiplier():
    # Quantity 2 m3: 2 x 100 kg x m(25) = 100 kg; C4 2 x 100 x m(61) = 0.
    b = BuildingInventory.model_validate(
        {
            "schema": "dlca.building_inventory",
            "name": "Trajectory hand case",
            "study_period": 60,
            "b4_c_trajectory": LINEAR_TO_ZERO,
            "assemblies": [
                {
                    "name": "Wall",
                    "materials": [
                        {
                            "name": "Board",
                            "quantity": 2.0,
                            "unit": "m3",
                            "modules": {"A1-A3": {"co2": 100.0}, "C4": {"co2": 100.0}},
                            "b4": [{"year": 25, "amounts": {"co2": 100.0}}],
                        }
                    ],
                }
            ],
        }
    )
    t = timeline(b, horizon=10)
    assert part(t, "B4", "Wall", "Board")["co2"][25] == pytest.approx(100.0, rel=1e-12)
    assert part(t, "C4", "Wall", "Board")["co2"][61] == 0.0
    assert part(t, "A1-A3", "Wall", "Board")["co2"][0] == 200.0


def test_positive_control_constant_matches_none_and_linear_does_not():
    """A "no difference" result (constant = none) next to a case the same
    comparison detects (linear differs)."""

    def same(a, b):
        return np.array_equal(a.gwi.dynamic, b.gwi.dynamic) and all(
            np.array_equal(a.emissions[g], b.emissions[g]) for g in EMISSION_KEYS
        )

    none = dlca.assess(timeline(totals(), horizon=100).emissions(), horizon=100)
    constant = dlca.assess(
        timeline(totals({"kind": "constant"}), horizon=100).emissions(), horizon=100
    )
    linear = dlca.assess(timeline(totals(LINEAR_TO_ZERO), horizon=100).emissions(), horizon=100)
    assert same(none, constant)
    assert not same(none, linear)


def test_breakdown_rows_still_add_up_with_a_trajectory():
    r = assess_building(totals(LINEAR_TO_ZERO), horizon=100)
    rows = sum(row.gwi_dynamic for row in r.by_module.values())
    scale = sum(np.abs(row.gwi_dynamic) for row in r.by_module.values())
    assert np.all(np.abs(rows - r.total.gwi.dynamic) <= 1e-9 * scale)
    assert r.by_module["C3"].gwi_dynamic[61] == 0.0
