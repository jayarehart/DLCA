"""Trajectories on buildings with biogenic items (#86, record 0020).

Every expected value here was worked by hand in #86 (decisions comment of
2026-11-20) before the code existed. RSP = 60 and ``linear`` to ``target`` =
0 in ``target_year`` = 50, so m(25) = 0.5 and m(61) = 0. A material that has
a `biogenic` field (its own, or on any B4 or B5 event) keeps the `co2` of its
C1-C4 and B4 amounts as entered; its `ch4_fossil` and `n2o` are still scaled.
Other materials get the full trajectory. A `BuildingTotals` is one item.

Faults these catch that no other test does: a biogenic material's CO2
release scaled (cut while its uptake stays whole); the exemption applied to
the whole building instead of per material; the exemption applied to
`ch4_fossil` or `n2o` too; a `biogenic` field on a B4 or B5 event not
counted; `released_co2` used to split the amount (the issue's first
example would then give 80 instead of 100); the uptake changed by the
trajectory.
"""

import numpy as np
import pytest

from dlca.climate import EMISSION_KEYS
from dlca.inventory import BuildingInventory, BuildingTotals, assess_building, timeline

LINEAR_TO_ZERO = {"kind": "linear", "target": 0.0, "target_year": 50}
TIMBER_BIOGENIC = {"co2": 100.0, "regrowth": "instant", "released_co2": 80.0}


def inventory(trajectory=None):
    d = {
        "schema": "dlca.building_inventory",
        "name": "Biogenic trajectory hand case",
        "study_period": 60,
        "assemblies": [
            {
                "name": "Wall",
                "materials": [
                    {
                        "name": "Timber",
                        "quantity": 1.0,
                        "unit": "m3",
                        "biogenic": TIMBER_BIOGENIC,
                        "modules": {"C3": {"co2": 100.0, "n2o": 1.0}},
                        "b4": [
                            {
                                "year": 25,
                                "amounts": {"co2": 40.0, "ch4_fossil": 2.0, "n2o": 0.2},
                            }
                        ],
                    },
                    {
                        "name": "Steel",
                        "quantity": 1.0,
                        "unit": "kg",
                        "modules": {"C3": {"co2": 100.0}},
                        "b4": [{"year": 25, "amounts": {"co2": 40.0}}],
                    },
                    {
                        "name": "Steel B5",
                        "quantity": 1.0,
                        "unit": "kg",
                        "modules": {"C3": {"co2": 100.0}},
                        "b5": [
                            {
                                "year": 10,
                                "amounts": {"co2": 10.0},
                                "biogenic": {"co2": 5.0, "regrowth": "none"},
                            }
                        ],
                    },
                ],
            }
        ],
    }
    if trajectory is not None:
        d["b4_c_trajectory"] = trajectory
    return BuildingInventory.model_validate(d)


def totals(trajectory=None):
    d = {
        "schema": "dlca.building_totals",
        "name": "Biogenic trajectory hand case",
        "study_period": 60,
        "biogenic": {"co2": 100.0, "regrowth": "instant"},
        "modules": {"C3": {"co2": 100.0, "n2o": 1.0}},
        "b4": [{"year": 25, "amounts": {"co2": 40.0}}],
    }
    if trajectory is not None:
        d["b4_c_trajectory"] = trajectory
    return BuildingTotals.model_validate(d)


def part(t, module, material=None):
    assembly = None if material is None else "Wall"
    return t.parts[(assembly, material, module)]


def test_biogenic_material_keeps_its_co2_and_scales_the_rest():
    t = timeline(inventory(LINEAR_TO_ZERO), horizon=10)
    c3 = part(t, "C3", "Timber")
    assert c3["co2"][61] == 100.0  # not 80 (released_co2 is not read), not 0
    assert c3["n2o"][61] == 0.0
    b4 = part(t, "B4", "Timber")
    assert b4["co2"][25] == 40.0
    assert b4["ch4_fossil"][25] == pytest.approx(1.0, rel=1e-12)
    assert b4["n2o"][25] == pytest.approx(0.1, rel=1e-12)


def test_other_materials_keep_the_full_trajectory():
    # Positive control: the comparison that shows "no change" for Timber
    # detects the change for Steel in the same building.
    t = timeline(inventory(LINEAR_TO_ZERO), horizon=10)
    assert part(t, "C3", "Steel")["co2"][61] == 0.0
    assert part(t, "B4", "Steel")["co2"][25] == pytest.approx(20.0, rel=1e-12)
    flat = timeline(inventory(), horizon=10)
    assert part(flat, "C3", "Steel")["co2"][61] == 100.0
    assert part(flat, "B4", "Steel")["co2"][25] == 40.0


def test_biogenic_b5_event_exempts_the_material():
    t = timeline(inventory(LINEAR_TO_ZERO), horizon=10)
    assert part(t, "C3", "Steel B5")["co2"][61] == 100.0
    assert part(t, "B5", "Steel B5")["co2"][10] == 10.0


def test_uptake_is_not_changed_by_the_trajectory():
    t = timeline(inventory(LINEAR_TO_ZERO), horizon=10)
    flat = timeline(inventory(), horizon=10)
    uptake = part(t, "biogenic-uptake", "Timber")["co2"]
    assert uptake[0] == -100.0
    np.testing.assert_array_equal(uptake, part(flat, "biogenic-uptake", "Timber")["co2"])


def test_totals_with_biogenic_is_one_item():
    t = timeline(totals(LINEAR_TO_ZERO), horizon=10)
    assert part(t, "C3")["co2"][61] == 100.0
    assert part(t, "C3")["n2o"][61] == 0.0
    assert part(t, "B4")["co2"][25] == 40.0


def test_explicit_constant_matches_no_trajectory_bit_for_bit():
    for make in (inventory, totals):
        none = timeline(make(), horizon=10)
        constant = timeline(make({"kind": "constant"}), horizon=10)
        assert none.parts.keys() == constant.parts.keys()
        for key in none.parts:
            for gas in EMISSION_KEYS:
                np.testing.assert_array_equal(none.parts[key][gas], constant.parts[key][gas])


def test_breakdown_rows_still_add_up():
    r = assess_building(inventory(LINEAR_TO_ZERO), horizon=100)
    for rows in (r.by_module, r.by_gas, r.by_material, r.by_assembly):
        total = sum(row.gwi_dynamic for row in rows.values())
        scale = sum(np.abs(row.gwi_dynamic) for row in rows.values())
        assert np.all(np.abs(total - r.total.gwi.dynamic) <= 1e-9 * scale)
