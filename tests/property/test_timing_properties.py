"""Property tests for the timing engine `timeline()` (#58, record 0014).

For any valid building, of either schema:

- mass is conserved: for each gas, the sum of the yearly series equals the
  inventory total (one-off modules, RSP times each per-year module, every B4
  and B5 event, with quantities applied);
- nothing is emitted after the end-of-life year (RSP + 1), and the parts add
  up to the total;
- an inventory gives the same series as the `BuildingTotals` made by scaling
  and summing its materials by hand.

Faults these catch that no other test does: an amount lost or counted twice
for some mix of modules, events and materials that the hand cases do not
cover (for example a material's events dropped when another material has
none, or per-year modules spread over RSP - 1 or RSP + 1 years); the totals
and inventory paths drifting apart for random input.

Tolerance. The sums are of at most a few hundred terms of magnitude up to 1e6,
so rounding is bounded by a small multiple of machine epsilon times the sum of
absolute values. The check allows ``RTOL * sum(|terms|)``; a lost or doubled
amount moves a sum by at least one whole term.
"""

from __future__ import annotations

import os

import numpy as np
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from dlca.climate import EMISSION_KEYS
from dlca.inventory import BuildingInventory, BuildingTotals, timeline

RTOL = 1e-12
SETTINGS = settings(
    max_examples=100,
    deadline=None,
    derandomize=bool(os.environ.get("CI")),
    suppress_health_check=[HealthCheck.too_slow],
)

ONE_OFF = ["A1-A3", "A4", "A5", "C1", "C2", "C3", "C4"]


def signed(lo: float, hi: float) -> st.SearchStrategy[float]:
    magnitude = st.floats(lo, hi)
    return st.just(0.0) | magnitude | magnitude.map(lambda v: -v)


gas_amounts = st.fixed_dictionaries({}, optional={k: signed(1e-6, 1e6) for k in EMISSION_KEYS})


def module_map(names):
    return st.dictionaries(st.sampled_from(names), gas_amounts, max_size=len(names))


def event_list(study_period):
    return st.lists(
        st.fixed_dictionaries({"year": st.integers(1, study_period), "amounts": gas_amounts}),
        max_size=4,
    )


@st.composite
def building_totals(draw):
    sp = draw(st.integers(1, 80))
    return BuildingTotals.model_validate(
        {
            "schema": "dlca.building_totals",
            "name": "Random",
            "study_period": sp,
            "modules": draw(module_map(ONE_OFF)),
            "per_year": draw(module_map(["B1", "B2", "B3", "B6", "B7"])),
            "b4": draw(event_list(sp)),
            "b5": draw(event_list(sp)),
        }
    )


@st.composite
def building_inventory(draw):
    sp = draw(st.integers(1, 80))
    assemblies = []
    for a in range(draw(st.integers(1, 3))):
        materials = []
        for m in range(draw(st.integers(1, 3))):
            materials.append(
                {
                    "name": f"m{m}",
                    "quantity": draw(st.floats(1e-3, 1e4)),
                    "unit": "m3",
                    "modules": draw(module_map(ONE_OFF)),
                    "per_year": draw(module_map(["B1", "B2", "B3"])),
                    "b4": draw(event_list(sp)),
                    "b5": draw(event_list(sp)),
                }
            )
        assemblies.append({"name": f"a{a}", "materials": materials})
    return BuildingInventory.model_validate(
        {
            "schema": "dlca.building_inventory",
            "name": "Random",
            "study_period": sp,
            "assemblies": assemblies,
            "per_year": draw(module_map(["B6", "B7"])),
        }
    )


def terms(building, key):
    """Every amount of gas `key` the building emits over its life, in kg."""
    sp = building.study_period
    out = []

    def add(scale, modules, per_year, b4, b5):
        out.extend(scale * getattr(g, key) for g in modules.values())
        out.extend(scale * sp * getattr(g, key) for g in per_year.values())
        out.extend(scale * getattr(e.amounts, key) for e in [*b4, *b5])

    if isinstance(building, BuildingTotals):
        add(1.0, building.modules, building.per_year, building.b4, building.b5)
    else:
        add(1.0, {}, building.per_year, [], [])
        for assembly in building.assemblies:
            for m in assembly.materials:
                add(m.quantity, m.modules, m.per_year, m.b4, m.b5)
    return np.array(out, dtype=float)


def assert_close(got, want, scale):
    np.testing.assert_allclose(got, want, rtol=0, atol=RTOL * max(scale, 1e-300))


any_building = building_totals() | building_inventory()


@SETTINGS
@given(building=any_building, horizon=st.integers(1, 150))
def test_mass_is_conserved(building, horizon):
    t = timeline(building, horizon=horizon)
    for key in EMISSION_KEYS:
        parts = terms(building, key)
        assert_close(t.emissions()[key].sum(), parts.sum(), np.abs(parts).sum())


@SETTINGS
@given(building=any_building, horizon=st.integers(1, 150))
def test_nothing_after_end_of_life_and_parts_add_up(building, horizon):
    t = timeline(building, horizon=horizon)
    assert t.end_of_life_year == building.study_period + 1
    assert t.years == building.study_period + horizon + 2
    total = t.emissions()
    for key in EMISSION_KEYS:
        assert not np.any(total[key][t.end_of_life_year + 1 :])
        summed = sum((p[key] for p in t.parts.values()), np.zeros(t.years))
        np.testing.assert_array_equal(summed, total[key])
        by_module = sum((p[key] for p in t.by_module().values()), np.zeros(t.years))
        assert_close(by_module, total[key], np.abs(terms(building, key)).sum())


@SETTINGS
@given(building=building_inventory(), horizon=st.integers(1, 20))
def test_inventory_equals_hand_made_totals(building, horizon):
    """Scale and sum the materials by hand into a BuildingTotals."""
    modules: dict[str, dict[str, float]] = {}
    per_year: dict[str, dict[str, float]] = {
        name: g.model_dump() for name, g in building.per_year.items()
    }
    b4, b5 = [], []

    def add(into, name, amounts, q):
        slot = into.setdefault(name, dict.fromkeys(EMISSION_KEYS, 0.0))
        for key in EMISSION_KEYS:
            slot[key] += q * getattr(amounts, key)

    for assembly in building.assemblies:
        for m in assembly.materials:
            q = m.quantity
            for name, g in m.modules.items():
                add(modules, name, g, q)
            for name, g in m.per_year.items():
                add(per_year, name, g, q)
            for e, into in [*((e, b4) for e in m.b4), *((e, b5) for e in m.b5)]:
                into.append(
                    {
                        "year": e.year,
                        "amounts": {k: q * getattr(e.amounts, k) for k in EMISSION_KEYS},
                    }
                )
    hand = BuildingTotals.model_validate(
        {
            "schema": "dlca.building_totals",
            "name": "Hand",
            "study_period": building.study_period,
            "modules": modules,
            "per_year": per_year,
            "b4": b4,
            "b5": b5,
        }
    )
    got = timeline(building, horizon=horizon).emissions()
    want = timeline(hand, horizon=horizon).emissions()
    for key in EMISSION_KEYS:
        scale = np.abs(terms(building, key)).sum()
        assert_close(got[key], want[key], scale)
