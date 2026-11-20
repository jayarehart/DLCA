"""Property tests for the roll-up `assess_building()` (#59, R2, R6, R8).

For any valid building, of either schema, and any whole-number horizon:

- each breakdown's rows add up to the total, for all six metric series
  (GWI and GTP; dynamic, sliding and static);
- a row is listed in `sliding_incomplete` exactly when its emissions have a
  non-zero value in some year >= H.

Faults these catch that no other test does: a part dropped from, or counted
twice in, some breakdown for a mix of modules, events, materials and gases
the hand cases do not cover; B6/B7 missing from the material or assembly
rows; a gas row built from the wrong key; the sliding flag off by one year
(> H instead of >= H) or set from the wrong row.

Tolerance (R8). The engine is linear, so the rows equal the total up to
rounding. The check allows ``RTOL * sum(|row|)`` per year, since amounts can
be negative and rows can cancel. A part lost or counted twice moves the sum by
a whole row, far more than this.
"""

from __future__ import annotations

import os
import warnings

import numpy as np
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from dlca.climate import EMISSION_KEYS
from dlca.inventory import BuildingInventory, BuildingTotals, assess_building, timeline

RTOL = 1e-9
METRICS = ("gwi_dynamic", "gwi_sliding", "gwi_static", "gtp_dynamic", "gtp_sliding", "gtp_static")
SETTINGS = settings(
    max_examples=40,
    deadline=None,
    derandomize=bool(os.environ.get("CI")),
    suppress_health_check=[HealthCheck.too_slow],
)
ONE_OFF = ["A1-A3", "A4", "A5", "C1", "C2", "C3", "C4"]


def signed(lo, hi):
    magnitude = st.floats(lo, hi)
    return st.just(0.0) | magnitude | magnitude.map(lambda v: -v)


gas_amounts = st.fixed_dictionaries({}, optional={k: signed(1e-3, 1e4) for k in EMISSION_KEYS})


def module_map(names):
    return st.dictionaries(st.sampled_from(names), gas_amounts, max_size=3)


def event_list(sp):
    return st.lists(
        st.fixed_dictionaries({"year": st.integers(1, sp), "amounts": gas_amounts}), max_size=2
    )


@st.composite
def building_totals(draw):
    sp = draw(st.integers(1, 60))
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
    sp = draw(st.integers(1, 60))
    assemblies = []
    for i in range(draw(st.integers(1, 2))):
        materials = [
            {
                "name": f"m{j}",
                "quantity": draw(st.floats(1e-2, 1e3)),
                "unit": "kg",
                "modules": draw(module_map(ONE_OFF)),
                "per_year": draw(module_map(["B1", "B2", "B3"])),
                "b4": draw(event_list(sp)),
                "b5": draw(event_list(sp)),
            }
            for j in range(draw(st.integers(1, 2)))
        ]
        assemblies.append({"name": f"a{i}", "materials": materials})
    return BuildingInventory.model_validate(
        {
            "schema": "dlca.building_inventory",
            "name": "Random",
            "study_period": sp,
            "assemblies": assemblies,
            "per_year": draw(module_map(["B6", "B7"])),
        }
    )


any_building = building_totals() | building_inventory()


def run(building, horizon, parameters):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return assess_building(building, horizon=horizon, parameters=parameters)


@SETTINGS
@given(
    building=any_building,
    horizon=st.integers(1, 120),
    parameters=st.sampled_from(["AR5", "AR6"]),
)
def test_every_breakdown_adds_up_to_the_total(building, horizon, parameters):
    r = run(building, horizon, parameters)
    total = r.total_metrics
    breakdowns = {"module": r.by_module, "gas": r.by_gas}
    if isinstance(building, BuildingInventory):
        breakdowns |= {"material": r.by_material, "assembly": r.by_assembly}
    else:
        assert r.by_material == {} and r.by_assembly == {}
    for name, rows in breakdowns.items():
        if not rows:  # a building with no amounts has no module rows
            for metric in METRICS:
                assert not np.any(getattr(total, metric))
            continue
        for metric in METRICS:
            series = [getattr(row, metric) for row in rows.values()]
            summed = np.sum(series, axis=0)
            scale = np.sum(np.abs(series), axis=0)
            gap = np.abs(summed - getattr(total, metric))
            assert np.all(gap <= RTOL * scale), (
                f"{name} rows do not add up to the total in {metric}: "
                f"worst gap {gap.max()} at scale {scale[gap.argmax()]}"
            )


@SETTINGS
@given(building=any_building, horizon=st.integers(1, 120))
def test_sliding_flag_marks_rows_with_emissions_at_or_after_horizon(building, horizon):
    r = run(building, horizon, "AR6")
    t = timeline(building, horizon=horizon)
    groups = {
        "module": t.by_module(),
        "gas": {k: {k: v} for k, v in t.emissions().items()},
    }
    if isinstance(building, BuildingInventory):
        by_material: dict = {}
        by_assembly: dict = {}
        for (assembly, material, _), series in t.parts.items():
            key = None if assembly is None else (assembly, material)
            for into, k in ((by_material, key), (by_assembly, assembly)):
                slot = into.setdefault(k, {g: np.zeros(t.years) for g in EMISSION_KEYS})
                for g in EMISSION_KEYS:
                    slot[g] = slot[g] + series[g]
        groups |= {"material": by_material, "assembly": by_assembly}
    want = {}
    for name, rows in groups.items():
        late = tuple(
            key for key, series in rows.items() if any(np.any(s[horizon:]) for s in series.values())
        )
        if late:
            want[name] = set(late)
    assert {k: set(v) for k, v in r.sliding_incomplete.items()} == want
    assert r.sliding_cutoff_year == horizon
