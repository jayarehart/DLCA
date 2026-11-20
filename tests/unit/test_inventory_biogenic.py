"""Biogenic carbon uptake (#73, decisions B1-B7 and follow-ups, 2026-11-20).

Every expected value here was worked out by hand before the code was written:

- Instant uptake: the whole declared ``co2`` as negative ``co2`` in the
  product's year (year 0, or the event year for a B4/B5 event).
- Gaussian uptake (Cherubini et al. 2011): mu = rotation / 2, sigma = mu / 2,
  the pdf integrated over each year [k, k + 1) from the product's year,
  rescaled over [0, inf). For rotation 4 (mu = 2, sigma = 1) the yearly shares
  follow from the standard normal table, Phi(1) = 0.841345, Phi(2) = 0.977250,
  Phi(3) = 0.998650 (printed to six digits):
  share_k = (Phi(k + 1 - 2) - Phi(k - 2)) / Phi(2).
- Uptake is its own part, module ``"biogenic-uptake"`` (B7).
- Storage = co2 - released_co2 - ch4 x 44.01 / 16.043 (B6 amended).
- Net uptake = co2 - ch4 x 44.01 / 16.043 (B5, Option 1): the carbon released
  as non-fossil CH4 is not taken up, because the engine's ch4 already nets it.

Faults these catch that no other test does: uptake with the wrong sign, in the
wrong year or the wrong part; the quantity not applied; the old sampled and
cut Gaussian (97.9 % of the carbon, `test_gaussian_takes_up_exactly_the_declared_co2`);
a B4 replacement with no uptake of its own; CH4 carbon counted twice (declared as uptake
while the engine's ch4 already nets it, the fault the #73 review found); a
biogenic field accepted under schema version 1; a ``"none"`` option that still
emits uptake.
"""

import math
import warnings

import numpy as np
import pytest
from pydantic import ValidationError

from dlca.climate import EMISSION_KEYS
from dlca.inventory import (
    BiogenicCarbonWarning,
    BuildingInventory,
    BuildingTotals,
    Timeline,
    assess_building,
    biogenic_balance,
    timeline,
)

UPTAKE = "biogenic-uptake"
CO2_PER_CH4 = 44.01 / 16.043  # B5: kg CO2 the carbon of 1 kg CH4 took from the air

# Standard normal table, six digits (not computed by dlca).
PHI1, PHI2, PHI3 = 0.841345, 0.977250, 0.998650
ROTATION_4_SHARES = [
    (PHI2 - PHI1) / PHI2,  # k = 0: Phi(-1) - Phi(-2) = Phi(2) - Phi(1)
    (PHI1 - 0.5) / PHI2,  # k = 1: Phi(0) - Phi(-1)
    (PHI1 - 0.5) / PHI2,  # k = 2: Phi(1) - Phi(0)
    (PHI2 - PHI1) / PHI2,  # k = 3: Phi(2) - Phi(1)
    (PHI3 - PHI2) / PHI2,  # k = 4: Phi(3) - Phi(2)
]
TABLE_TOL = 2e-6  # six printed digits, divided by Phi(2)


def inventory(material_extra=None, study_period=10, schema_version=2, **material):
    m = {"name": "CLT", "quantity": 10.0, "unit": "m3", **material}
    m.update(material_extra or {})
    return BuildingInventory.model_validate(
        {
            "schema": "dlca.building_inventory",
            "schema_version": schema_version,
            "name": "Hand case",
            "study_period": study_period,
            "assemblies": [{"name": "Floor", "materials": [m]}],
        }
    )


def totals(study_period=10, schema_version=2, **fields):
    return BuildingTotals.model_validate(
        {
            "schema": "dlca.building_totals",
            "schema_version": schema_version,
            "name": "Hand case",
            "study_period": study_period,
            **fields,
        }
    )


def uptake(t: Timeline, assembly="Floor", material="CLT"):
    return t.parts[(assembly, material, UPTAKE)]


# --- Placement -------------------------------------------------------------------


def test_instant_uptake_is_negative_co2_in_year_zero_times_quantity():
    t = timeline(inventory(biogenic={"co2": 800.0, "regrowth": "instant"}), horizon=5)
    co2 = uptake(t)["co2"]
    assert co2[0] == -8000.0
    assert not np.any(co2[1:])
    for gas in ("ch4", "ch4_fossil", "n2o"):
        assert not np.any(uptake(t)[gas])
    assert t.emissions()["co2"].sum() == -8000.0


def test_gaussian_rotation_4_matches_normal_table():
    t = timeline(
        inventory(biogenic={"co2": 1.0, "regrowth": "gaussian", "rotation": 4}, quantity=1.0),
        horizon=50,
    )
    co2 = uptake(t)["co2"]
    for k, share in enumerate(ROTATION_4_SHARES):
        assert abs(-co2[k] - share) <= TABLE_TOL, k
    assert np.all(co2 <= 0)


def test_gaussian_takes_up_exactly_the_declared_co2():
    """The old sampled, cut Gaussian took up 97.9 % for rotation 80."""
    t = timeline(
        inventory(biogenic={"co2": 769.0, "regrowth": "gaussian", "rotation": 80}, quantity=1.0),
        horizon=300,
    )
    assert math.isclose(-uptake(t)["co2"].sum(), 769.0, rel_tol=1e-12)


def test_regrowth_none_emits_nothing_and_matches_no_biogenic_input():
    """Positive control: the same comparison does see instant uptake."""
    base = timeline(inventory(modules={"A1-A3": {"co2": 100.0}}), horizon=5)
    none = timeline(
        inventory(modules={"A1-A3": {"co2": 100.0}}, biogenic={"co2": 800.0, "regrowth": "none"}),
        horizon=5,
    )
    instant = timeline(
        inventory(
            modules={"A1-A3": {"co2": 100.0}}, biogenic={"co2": 800.0, "regrowth": "instant"}
        ),
        horizon=5,
    )
    for gas in EMISSION_KEYS:
        assert np.array_equal(none.emissions()[gas], base.emissions()[gas])
    assert UPTAKE not in {m for (_, _, m) in none.parts}
    assert not np.array_equal(instant.emissions()["co2"], base.emissions()["co2"])


def test_b4_replacement_gets_its_own_uptake_in_the_event_year():
    b = inventory(
        biogenic={"co2": 800.0, "regrowth": "instant"},
        b4=[
            {"year": 7, "amounts": {"co2": 50.0}, "biogenic": {"co2": 800.0, "regrowth": "instant"}}
        ],
    )
    co2 = uptake(timeline(b, horizon=5))["co2"]
    assert co2[0] == -8000.0
    assert co2[7] == -8000.0
    assert co2.sum() == -16000.0


def test_b5_event_gaussian_uptake_starts_in_the_event_year():
    b = inventory(
        quantity=1.0,
        b5=[
            {
                "year": 3,
                "amounts": {},
                "biogenic": {"co2": 1.0, "regrowth": "gaussian", "rotation": 4},
            }
        ],
    )
    co2 = uptake(timeline(b, horizon=50))["co2"]
    assert not np.any(co2[:3])
    for k, share in enumerate(ROTATION_4_SHARES):
        assert abs(-co2[3 + k] - share) <= TABLE_TOL, k


def test_totals_building_level_uptake():
    b = totals(biogenic={"co2": 5000.0, "regrowth": "instant"}, modules={"A1-A3": {"co2": 9.0}})
    t = timeline(b, horizon=5)
    assert t.parts[(None, None, UPTAKE)]["co2"][0] == -5000.0
    assert t.emissions()["co2"][0] == 9.0 - 5000.0


# --- CH4 carbon counted once (record 0010, C8; B5 as fixed by Jay, Option 1) --------
#
# The engine does not oxidise non-fossil ch4 to CO2, so its ch4 already nets
# the carbon's uptake against its return (the AR6 non-fossil convention). The
# carbon released as ch4 is therefore taken off the declared uptake:
# net uptake = co2 - ch4 x 44.01 / 16.043, per material, spread over its
# uptake items in proportion to their co2.


def test_carbon_all_released_as_ch4_takes_up_nothing():
    """Same emissions as no biogenic input at all: no lasting cooling (#73 review)."""
    with_bio = inventory(
        quantity=1.0,
        modules={"C4": {"ch4": 1.0}},
        biogenic={"co2": CO2_PER_CH4, "regrowth": "instant"},
    )
    without = inventory(quantity=1.0, modules={"C4": {"ch4": 1.0}})
    with warnings.catch_warnings():
        warnings.simplefilter("error", BiogenicCarbonWarning)
        a = timeline(with_bio, horizon=5).emissions()
        b = timeline(without, horizon=5).emissions()
    assert abs(a["co2"]).max() <= 1e-15
    for gas in ("ch4", "ch4_fossil", "n2o"):
        assert np.array_equal(a[gas], b[gas])
    balance = biogenic_balance(with_bio)[("Floor", "CLT")]
    assert abs(balance.uptake) <= 1e-15
    assert abs(balance.stored) <= 1e-15


def test_ch4_carbon_comes_off_each_uptake_item_in_proportion():
    """Own item 10 x 769 = 7690 in year 0, B4 item 10 x 100 = 1000 in year 5;
    CH4 carbon 10 x (0.5 + 0.1) x 44.01 / 16.043 off the 8690 total."""
    b = inventory(
        modules={"C4": {"ch4": 0.5}},
        biogenic={"co2": 769.0, "regrowth": "instant"},
        b4=[
            {
                "year": 5,
                "amounts": {"ch4": 0.1},
                "biogenic": {"co2": 100.0, "regrowth": "instant"},
            }
        ],
    )
    co2 = uptake(timeline(b, horizon=5))["co2"]
    f = (8690.0 - 6.0 * CO2_PER_CH4) / 8690.0
    assert math.isclose(co2[0], -7690.0 * f, rel_tol=1e-14)
    assert math.isclose(co2[5], -1000.0 * f, rel_tol=1e-14)
    assert math.isclose(co2.sum(), -(8690.0 - 6.0 * CO2_PER_CH4), rel_tol=1e-14)
    # Positive control: without the CH4 the same comparison sees the full uptake.
    assert co2.sum() > -8690.0


def test_non_fossil_ch4_without_biogenic_does_not_warn():
    """That is the AR6 non-fossil convention, which the engine's ch4 already follows."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", BiogenicCarbonWarning)
        timeline(inventory(modules={"C4": {"ch4": 2.0}}), horizon=5)


def test_ch4_carbon_above_declared_gives_zero_uptake_and_warns():
    b = inventory(
        quantity=1.0,
        modules={"C4": {"ch4": 1.0}},
        biogenic={"co2": 1.0, "regrowth": "instant"},
    )
    with pytest.warns(BiogenicCarbonWarning, match="more"):
        t = timeline(b, horizon=5)
    assert not np.any(uptake(t)["co2"] > 0)
    assert t.emissions()["co2"].sum() == 0.0


def test_release_above_declared_warns():
    b = inventory(
        quantity=1.0,
        modules={"C4": {"ch4": 1.0}},
        biogenic={"co2": 10.0, "regrowth": "instant", "released_co2": 8.0},
    )
    with pytest.warns(BiogenicCarbonWarning, match="more"):
        timeline(b, horizon=5)


def test_storage_balance_per_material():
    b = inventory(
        modules={"C4": {"co2": 30.0, "ch4": 0.5}},
        biogenic={"co2": 769.0, "regrowth": "instant", "released_co2": 25.0},
        b4=[
            {
                "year": 5,
                "amounts": {"co2": 1.0, "ch4": 0.1},
                "biogenic": {"co2": 100.0, "regrowth": "instant", "released_co2": 4.0},
            }
        ],
    )
    bal = biogenic_balance(b)[("Floor", "CLT")]
    q = 10.0
    assert math.isclose(bal.declared, q * (769.0 + 100.0), rel_tol=1e-15)
    assert math.isclose(bal.released_co2, q * (25.0 + 4.0), rel_tol=1e-15)
    assert math.isclose(bal.released_ch4_as_co2, q * 0.6 * CO2_PER_CH4, rel_tol=1e-14)
    want_stored = q * (869.0 - 29.0 - 0.6 * CO2_PER_CH4)
    assert math.isclose(bal.stored, want_stored, rel_tol=1e-14)
    assert math.isclose(bal.uptake, q * (869.0 - 0.6 * CO2_PER_CH4), rel_tol=1e-14)


def test_balance_for_totals_is_keyed_none():
    b = totals(biogenic={"co2": 100.0, "regrowth": "none", "released_co2": 40.0})
    bal = biogenic_balance(b)[None]
    assert (bal.declared, bal.released_co2, bal.stored) == (100.0, 40.0, 60.0)


# --- Series end ----------------------------------------------------------------------


def test_gaussian_cut_by_series_end_warns_and_says_how_much():
    """Jay's window choice: what falls after the series end is cut, and reported."""
    b = inventory(quantity=1.0, biogenic={"co2": 1.0, "regrowth": "gaussian", "rotation": 200})
    with pytest.warns(BiogenicCarbonWarning, match="years"):
        t = timeline(b, horizon=5)
    taken = -uptake(t)["co2"].sum()
    assert 0 < taken < 1.0


def test_long_series_gives_no_cut_warning():
    b = inventory(quantity=1.0, biogenic={"co2": 1.0, "regrowth": "gaussian", "rotation": 20})
    with warnings.catch_warnings():
        warnings.simplefilter("error", BiogenicCarbonWarning)
        timeline(b, horizon=100)


# --- Schema ---------------------------------------------------------------------------


def test_schema_version_1_without_biogenic_still_loads():
    b = inventory(schema_version=1, modules={"A1-A3": {"co2": 1.0}})
    assert b.schema_version == 1


@pytest.mark.parametrize(
    "biogenic",
    [
        {"co2": 1.0, "regrowth": "instant"},
    ],
)
def test_biogenic_refused_under_schema_version_1(biogenic):
    with pytest.raises(ValidationError, match="schema_version 2"):
        inventory(schema_version=1, biogenic=biogenic)
    with pytest.raises(ValidationError, match="schema_version 2"):
        totals(schema_version=1, biogenic=biogenic)
    with pytest.raises(ValidationError, match="schema_version 2"):
        inventory(
            schema_version=1,
            b4=[{"year": 1, "amounts": {}, "biogenic": biogenic}],
        )


@pytest.mark.parametrize(
    "biogenic",
    [
        {"co2": -1.0, "regrowth": "instant"},
        {"co2": 1.0, "regrowth": "instant", "released_co2": -1.0},
        {"co2": 1.0, "regrowth": "gaussian"},  # rotation missing
        {"co2": 1.0, "regrowth": "gaussian", "rotation": 1},
        {"co2": 1.0, "regrowth": "gaussian", "rotation": 4.0},
        {"co2": 1.0, "regrowth": "instant", "rotation": 4},  # rotation only for gaussian
        {"co2": 1.0, "regrowth": "sigmoid"},
        {"co2": float("nan"), "regrowth": "instant"},
        {"regrowth": "instant"},
        {"co2": 1.0},
    ],
)
def test_bad_biogenic_refused(biogenic):
    with pytest.raises(ValidationError):
        inventory(biogenic=biogenic)


# --- Timeline and roll-up ----------------------------------------------------------


def test_timeline_json_round_trip_keeps_uptake_part():
    t = timeline(
        inventory(biogenic={"co2": 1.0, "regrowth": "gaussian", "rotation": 10}), horizon=20
    )
    back = Timeline.from_dict(t.to_dict())
    assert np.array_equal(uptake(back)["co2"], uptake(t)["co2"])


def test_uptake_is_its_own_row_in_the_building_result():
    b = inventory(modules={"A1-A3": {"co2": 100.0}}, biogenic={"co2": 800.0, "regrowth": "instant"})
    r = assess_building(b, horizon=20)
    assert UPTAKE in r.by_module
    assert list(r.by_module)[0] == UPTAKE
    assert r.by_module[UPTAKE].gwi_dynamic[20] < 0
    assert r.by_module["A1-A3"].gwi_dynamic[20] > 0
    assert r.biogenic[("Floor", "CLT")].declared == 8000.0


# --- Edge cases from the second fresh review -------------------------------------


def test_negative_ch4_never_raises_uptake_above_declared():
    b = inventory(
        quantity=1.0,
        modules={"C4": {"ch4": -1.0}},
        biogenic={"co2": 1.0, "regrowth": "instant"},
    )
    t = timeline(b, horizon=5)
    assert uptake(t)["co2"].sum() == -1.0
    assert biogenic_balance(b)[("Floor", "CLT")].uptake == 1.0


def test_ch4_carbon_above_what_can_be_taken_up_warns():
    """A "none" item declares 10, an instant B4 item 1; CH4 carbon 3 x 2.743 = 8.23
    is below the 11 declared but above the 1 that can be taken up."""
    b = inventory(
        quantity=1.0,
        modules={"C4": {"ch4": 3.0}},
        biogenic={"co2": 10.0, "regrowth": "none"},
        b4=[{"year": 5, "amounts": {}, "biogenic": {"co2": 1.0, "regrowth": "instant"}}],
    )
    with pytest.warns(BiogenicCarbonWarning, match="taken up"):
        t = timeline(b, horizon=5)
    assert uptake(t)["co2"].sum() == 0.0


def test_no_cut_warning_when_net_uptake_is_zero():
    b = inventory(
        quantity=1.0,
        modules={"C4": {"ch4": 1.0}},
        biogenic={"co2": CO2_PER_CH4, "regrowth": "gaussian", "rotation": 80},
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error", BiogenicCarbonWarning)
        timeline(b, horizon=5)
