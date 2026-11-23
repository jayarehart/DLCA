"""Roll-up and breakdown `assess_building()` (#59, decisions R1-R8, record 0015).

Expected values were written down before the code ran, in the proposal on
#59. The independent check uses a two-material building with one CO2 pulse
each (AR6, H = 100, RSP = 60):

- Concrete: 1000 kg CO2 in year 0 (A1-A3).
- Timber: 200 kg CO2 in year 61 (C3, the end-of-life year RSP + 1).

By hand, with a(h) = AGWP_CO2(h) / AGWP_CO2(H):

- static GWI: 1000 and 200 kg CO2e. CO2 has GWP 1 by definition.
- dynamic GWI, H years after a pulse: exactly the pulse mass. So Timber's
  dynamic GWI at year 161 is 200, by the definition of the normalisation.
  Concrete's at year 161 is 1000 a(161).
- sliding GWI: an emission in year k gets horizon H - k. So 1000 a(100) =
  1000 and 200 a(39).

`agwp()` is the closed form of AR6 Table 7.15's CO2 impulse response. It is
not the roll-up code and not the discrete forcing integration behind
`gwi().dynamic`.

Faults these catch that no other test does:
- a part placed under the wrong breakdown key;
- a material or module counted twice or dropped (the worked example's totals
  move by a whole part);
- B6/B7 left out of the material and assembly rows, so those rows stop adding
  up to the total;
- a gas row that splits fossil CH4's oxidised CO2 into the `co2` row;
- an emission at year >= H not flagged in `sliding_incomplete`, or no warning;
- a flag on a row whose emissions all fall before year H;
- a JSON round trip that is not exact, or that drops the building input;
- `Timeline` JSON that loses a part's (None, None) key or reorders the gases.
"""

from __future__ import annotations

import json
import warnings

import numpy as np
import pytest

import dlca
from dlca.climate import EMISSION_KEYS, agwp
from dlca.inventory import (
    BuildingInventory,
    BuildingResult,
    BuildingTotals,
    Metrics,
    Timeline,
    assess_building,
    timeline,
)

METRICS = ("gwi_dynamic", "gwi_sliding", "gwi_static", "gtp_dynamic", "gtp_sliding", "gtp_static")
AR6 = dlca.get_parameters("AR6")


def inventory(study_period, materials, per_year=None):
    """`materials`: {(assembly, material): material fields without the name}."""
    assemblies: dict[str, list] = {}
    for (assembly, name), fields in materials.items():
        assemblies.setdefault(assembly, []).append(
            {"name": name, "unit": "m3", "quantity": 1.0, **fields}
        )
    return BuildingInventory.model_validate(
        {
            "schema": "dlca.building_inventory",
            "name": "Hand case",
            "study_period": study_period,
            "assemblies": [{"name": a, "materials": m} for a, m in assemblies.items()],
            "per_year": per_year or {},
        }
    )


def totals(study_period, modules=None, per_year=None, b4=()):
    return BuildingTotals.model_validate(
        {
            "schema": "dlca.building_totals",
            "name": "Hand case",
            "study_period": study_period,
            "modules": modules or {},
            "per_year": per_year or {},
            "b4": [{"year": y, "amounts": a} for y, a in b4],
        }
    )


def two_materials(study_period=60):
    return inventory(
        study_period,
        {
            ("Frame", "Concrete"): {"modules": {"A1-A3": {"co2": 1000.0}}},
            ("Frame", "Timber"): {"modules": {"C3": {"co2": 200.0}}},
        },
    )


def quiet(building, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return assess_building(building, **kwargs)


def a(h):
    return agwp("co2", h, AR6) / agwp("co2", 100, AR6)


# --- Independent check -------------------------------------------------------


def test_two_material_building_matches_closed_form():
    r = quiet(two_materials(), horizon=100)
    concrete = r.by_material[("Frame", "Concrete")]
    timber = r.by_material[("Frame", "Timber")]
    assert r.total.emissions["co2"].shape == (60 + 100 + 2,)

    # Static: kg CO2 times GWP 1.
    assert concrete.gwi_static[-1] == pytest.approx(1000.0, rel=1e-12)
    assert timber.gwi_static[-1] == pytest.approx(200.0, rel=1e-12)
    # Dynamic: H years after a pulse equals its mass; Concrete at year 161.
    assert timber.gwi_dynamic[161] == pytest.approx(200.0, rel=1e-9)
    assert concrete.gwi_dynamic[161] == pytest.approx(1000.0 * a(161), rel=1e-9)
    # Sliding: horizon H - k for an emission in year k.
    assert concrete.gwi_sliding[-1] == pytest.approx(1000.0, rel=1e-12)
    assert timber.gwi_sliding[-1] == pytest.approx(200.0 * a(39), rel=1e-12)

    # The building is the sum of its two parts, and the one assembly is the total.
    assert r.total.gwi.static[-1] == pytest.approx(1200.0, rel=1e-12)
    assert r.total.gwi.dynamic[161] == pytest.approx(1000.0 * a(161) + 200.0, rel=1e-9)
    assert r.total.gwi.sliding[-1] == pytest.approx(1000.0 + 200.0 * a(39), rel=1e-12)
    for name in METRICS:
        np.testing.assert_allclose(
            getattr(r.by_assembly["Frame"], name), getattr(r.total_metrics, name), rtol=1e-12
        )
        np.testing.assert_allclose(
            getattr(r.by_gas["co2"], name), getattr(r.total_metrics, name), rtol=1e-12
        )
    assert r.sliding_incomplete == {}


# --- Breakdown keys ------------------------------------------------------------


def test_breakdown_keys_for_an_inventory():
    b = inventory(
        10,
        {
            ("Floor", "Slab"): {
                "modules": {"A1-A3": {"co2": 5.0}, "C4": {"ch4": 0.1}},
                "b4": [{"year": 5, "amounts": {"co2": 1.0}}],
            },
            ("Wall", "Stud"): {"per_year": {"B2": {"n2o": 0.01}}},
        },
        per_year={"B6": {"co2": 2.0}},
    )
    r = assess_building(b, horizon=20)
    assert list(r.by_module) == ["A1-A3", "B2", "B4", "B6", "C4"]  # EN 15978 order
    assert list(r.by_gas) == list(EMISSION_KEYS)
    assert list(r.by_material) == [("Floor", "Slab"), ("Wall", "Stud"), None]
    assert list(r.by_assembly) == ["Floor", "Wall", None]
    # The None row is the building's own B6, whatever an assembly is called.
    np.testing.assert_array_equal(r.by_material[None].gwi_static, r.by_module["B6"].gwi_static)
    np.testing.assert_array_equal(r.by_assembly[None].gwi_static, r.by_module["B6"].gwi_static)


def test_assembly_named_building_does_not_collide_with_the_building_row():
    b = inventory(
        5,
        {("building", "Slab"): {"modules": {"A1-A3": {"co2": 3.0}}}},
        per_year={"B6": {"co2": 1.0}},
    )
    r = assess_building(b, horizon=10)
    assert set(r.by_assembly) == {"building", None}
    assert r.by_assembly["building"].gwi_static[-1] == pytest.approx(3.0)
    assert r.by_assembly[None].gwi_static[-1] == pytest.approx(5.0)


def test_totals_have_no_material_or_assembly_rows():
    r = assess_building(totals(5, modules={"A1-A3": {"co2": 3.0}}), horizon=10)
    assert r.by_material == {}
    assert r.by_assembly == {}
    assert list(r.by_module) == ["A1-A3"]


def test_inventory_without_operational_has_no_building_row():
    r = assess_building(two_materials(), horizon=100)
    assert None not in r.by_material
    assert None not in r.by_assembly


def test_fossil_ch4_row_keeps_its_oxidised_co2():
    r = assess_building(totals(5, modules={"A1-A3": {"ch4_fossil": 1.0}}), horizon=100)
    for name in METRICS:
        assert not np.any(getattr(r.by_gas["co2"], name))
        np.testing.assert_array_equal(
            getattr(r.by_gas["ch4_fossil"], name), getattr(r.total_metrics, name)
        )
    # Its static GWI includes the oxidised CO2, so it is above non-fossil CH4's.
    other = assess_building(totals(5, modules={"A1-A3": {"ch4": 1.0}}), horizon=100)
    assert r.by_gas["ch4_fossil"].gwi_static[-1] > other.by_gas["ch4"].gwi_static[-1]


def test_rows_match_assess_on_the_same_emissions():
    """A row is `assess()` of that row's emissions, not a scaled total."""
    b = two_materials()
    r = quiet(b, horizon=100, parameters="AR5")
    t = timeline(b, horizon=100)
    direct = dlca.assess(t.by_module()["C3"], parameters="AR5", horizon=100)
    np.testing.assert_array_equal(r.by_module["C3"].gtp_dynamic, direct.gtp.dynamic)
    assert r.total.parameter_set == "AR5"


# --- Sliding cut-off (R6) ------------------------------------------------------


def test_end_of_life_at_or_after_horizon_is_flagged_and_warned():
    b = two_materials(study_period=100)  # C3 in year 101 >= H = 100
    with pytest.warns(UserWarning, match=r"year 100 or later.*C3"):
        r = assess_building(b, horizon=100)
    c3 = r.by_module["C3"]
    assert not np.any(c3.gwi_sliding)
    assert not np.any(c3.gtp_sliding)
    assert c3.gwi_dynamic[-1] > 0  # still counted by the dynamic metric
    assert c3.gwi_static[-1] == pytest.approx(200.0)
    assert r.sliding_cutoff_year == 100
    assert r.sliding_incomplete == {
        "module": ("C3",),
        "gas": ("co2",),
        "material": (("Frame", "Timber"),),
        "assembly": ("Frame",),
    }


def test_positive_control_one_percent_change_in_c_is_seen():
    """The comparison that shows C as zero in sliding can see a 1% change."""
    base = two_materials(study_period=60)
    more = inventory(
        60,
        {
            ("Frame", "Concrete"): {"modules": {"A1-A3": {"co2": 1000.0}}},
            ("Frame", "Timber"): {"modules": {"C3": {"co2": 202.0}}},
        },
    )
    r0 = assess_building(base, horizon=100)
    r1 = assess_building(more, horizon=100)
    ratio = r1.by_module["C3"].gwi_sliding[-1] / r0.by_module["C3"].gwi_sliding[-1]
    assert ratio == pytest.approx(1.01, rel=1e-12)
    # With C past H the sliding value stays zero, but dynamic sees the change.
    late0 = quiet(two_materials(study_period=100), horizon=100)
    late1 = quiet(
        inventory(
            100,
            {
                ("Frame", "Concrete"): {"modules": {"A1-A3": {"co2": 1000.0}}},
                ("Frame", "Timber"): {"modules": {"C3": {"co2": 202.0}}},
            },
        ),
        horizon=100,
    )
    ratio = late1.by_module["C3"].gwi_dynamic[-1] / late0.by_module["C3"].gwi_dynamic[-1]
    assert ratio == pytest.approx(1.01, rel=1e-12)


def test_late_operational_years_are_flagged():
    """RSP 60, H 50: B6 in years 50..60 gets zero sliding weight."""
    b = totals(60, modules={"A1-A3": {"co2": 10.0}}, per_year={"B6": {"co2": 1.0}})
    with pytest.warns(UserWarning):
        r = assess_building(b, horizon=50)
    assert r.sliding_incomplete == {"module": ("B6",), "gas": ("co2",)}
    # Only years 1..49 count, each with less than the full horizon.
    assert 0 < r.by_module["B6"].gwi_sliding[-1] < 49.0


def test_emission_in_year_before_horizon_is_not_flagged():
    b = totals(98, modules={"C1": {"co2": 1.0}})  # C1 in year 99 < H = 100
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        r = assess_building(b, horizon=100)
    assert r.sliding_incomplete == {}
    assert r.by_module["C1"].gwi_sliding[-1] > 0


def test_emission_exactly_in_year_horizon_is_flagged():
    """Year H itself gets horizon 0, so the flag starts at H, not H + 1."""
    b = totals(99, modules={"C1": {"co2": 1.0}})  # C1 in year 100 = H
    with pytest.warns(UserWarning):
        r = assess_building(b, horizon=100)
    assert not np.any(r.by_module["C1"].gwi_sliding)
    assert r.sliding_incomplete == {"module": ("C1",), "gas": ("co2",)}


# --- Inputs --------------------------------------------------------------------


@pytest.mark.parametrize("horizon", [100.0, "100", True])
def test_horizon_must_be_a_whole_number(horizon):
    with pytest.raises(TypeError):
        assess_building(two_materials(), horizon=horizon)


def test_years_pads_every_row():
    r = quiet(two_materials(), horizon=100, years=200)
    assert r.years == 200
    assert r.total.gwi.dynamic.shape == (200,)
    assert r.by_module["C3"].gwi_dynamic.shape == (200,)


def test_not_a_building_refused():
    with pytest.raises(TypeError):
        assess_building({"co2": [1.0]})


def test_arrays_are_read_only():
    r = assess_building(two_materials(), horizon=100)
    with pytest.raises(ValueError):
        r.by_module["C3"].gwi_dynamic[0] = 1.0
    with pytest.raises(TypeError):
        r.by_module["X"] = r.by_module["C3"]


# --- JSON ----------------------------------------------------------------------


def roundtrip(obj, cls):
    return cls.from_dict(json.loads(json.dumps(obj.to_dict())))


def assert_metrics_equal(x: Metrics, y: Metrics):
    for name in METRICS:
        np.testing.assert_array_equal(getattr(x, name), getattr(y, name), strict=True)


@pytest.mark.parametrize(
    "building",
    [
        two_materials(study_period=100),
        inventory(
            8,
            {("A", "m"): {"quantity": 2.5, "b4": [{"year": 3, "amounts": {"n2o": 0.5}}]}},
            per_year={"B7": {"ch4_fossil": 0.25}},
        ),
        totals(7, modules={"A4": {"ch4": 0.3}}, per_year={"B1": {"co2": -1.0}}),
    ],
)
def test_building_result_json_round_trip_is_exact(building):
    r = quiet(building, horizon=100, parameters="AR6")
    back = roundtrip(r, BuildingResult)
    assert back.building == building
    assert (back.horizon, back.years, back.sliding_cutoff_year) == (r.horizon, r.years, 100)
    assert back.sliding_incomplete == r.sliding_incomplete
    for name in ("by_module", "by_gas", "by_material", "by_assembly"):
        assert list(getattr(back, name)) == list(getattr(r, name))
        for key, row in getattr(r, name).items():
            assert_metrics_equal(getattr(back, name)[key], row)
    np.testing.assert_array_equal(back.total.gwi.dynamic, r.total.gwi.dynamic, strict=True)
    assert back.total.parameter_fingerprint == r.total.parameter_fingerprint
    assert json.dumps(back.to_dict()) == json.dumps(r.to_dict())


def test_building_result_from_dict_refuses_other_schema_or_version():
    d = assess_building(two_materials(), horizon=100).to_dict()
    assert d["schema"] == "dlca.building_result"
    assert d["schema_version"] == 6
    with pytest.raises(ValueError, match="schema"):
        BuildingResult.from_dict({**d, "schema": "dlca.result"})
    with pytest.raises(ValueError, match="schema_version"):
        BuildingResult.from_dict({**d, "schema_version": 7})


def test_building_result_from_dict_refuses_a_horizon_that_differs_from_total():
    d = assess_building(two_materials(), horizon=100).to_dict()
    with pytest.raises(ValueError, match="horizon"):
        BuildingResult.from_dict({**d, "horizon": 50})


def test_timeline_json_round_trip_is_exact():
    b = inventory(
        6,
        {("A", "m"): {"quantity": 1.5, "modules": {"C2": {"co2": 0.1}}}},
        per_year={"B6": {"ch4": 0.2, "n2o": 1e-3}},
    )
    t = timeline(b, horizon=7, years=20)
    d = t.to_dict()
    assert d["schema"] == "dlca.timeline"
    assert d["schema_version"] == 3
    back = roundtrip(t, Timeline)
    assert (back.study_period, back.horizon, back.years) == (6, 7, 20)
    assert list(back.parts) == list(t.parts) == [("A", "m", "C2"), (None, None, "B6")]
    for key, series in t.parts.items():
        assert list(back.parts[key]) == list(EMISSION_KEYS)
        for gas in EMISSION_KEYS:
            np.testing.assert_array_equal(back.parts[key][gas], series[gas], strict=True)
            assert not back.parts[key][gas].flags.writeable


@pytest.mark.parametrize(
    "change",
    [
        {"schema": "dlca.result"},
        {"schema_version": 4},
        {"years": 19},  # arrays are 20 long
    ],
)
def test_timeline_from_dict_refuses_bad_input(change):
    t = timeline(totals(3, modules={"A5": {"co2": 1.0}}), horizon=5, years=20)
    with pytest.raises(ValueError):
        Timeline.from_dict({**t.to_dict(), **change})


def _broken(change):
    d = json.loads(json.dumps(assess_building(two_materials(), horizon=100).to_dict()))
    change(d)
    return d


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(
            lambda d: d["breakdowns"]["module"].append(d["breakdowns"]["module"][0]),
            id="repeated-row",
        ),
        pytest.param(lambda d: d["breakdowns"]["gas"].pop(), id="missing-gas-row"),
        pytest.param(lambda d: d["sliding_incomplete"].update(module=["B6"]), id="flag-not-a-row"),
        pytest.param(lambda d: d.pop("sliding_incomplete"), id="missing-field"),
        pytest.param(lambda d: d["building"].update(study_period=59), id="building-changed"),
        pytest.param(
            lambda d: d["breakdowns"]["module"][0]["gwi_dynamic"].__setitem__(3, "NaN"), id="nan"
        ),
        pytest.param(lambda d: d["breakdowns"].pop("assembly"), id="missing-breakdown"),
    ],
)
def test_building_result_from_dict_refuses_inconsistent_input(change):
    with pytest.raises(ValueError):
        BuildingResult.from_dict(_broken(change))


def test_building_result_from_dict_refuses_a_float_horizon():
    with pytest.raises(TypeError):
        BuildingResult.from_dict(_broken(lambda d: d.update(horizon=100.0)))


@pytest.mark.parametrize(
    "change",
    [{"horizon": 0}, {"years": 3 + 5 + 1}],
)
def test_timeline_from_dict_refuses_short_or_zero_horizon(change):
    t = timeline(totals(3, modules={"A5": {"co2": 1.0}}), horizon=5)
    d = t.to_dict()
    d.update(change)
    for part in d["parts"]:
        for gas in EMISSION_KEYS:
            part[gas] = part[gas][: d["years"]]
    with pytest.raises(ValueError):
        Timeline.from_dict(d)


def test_timeline_from_dict_refuses_unknown_module():
    d = timeline(totals(3, modules={"A5": {"co2": 1.0}}), horizon=5).to_dict()
    d["parts"][0]["module"] = "D"
    with pytest.raises(ValueError, match="module"):
        Timeline.from_dict(d)
