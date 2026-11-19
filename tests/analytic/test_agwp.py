"""agwp(), forcing() and gwi() against published IPCC values (issue #28).

The expected values are typed from the IPCC tables, not read from dlca or from
the parameter JSON files:

- AR5 WG1 Chapter 8, Table 8.A.1 (Myhre et al. 2013, p. 731), no carbon-cycle
  feedback: AGWP20 and AGWP100 of CO2; AGWP100 of CH4 and N2O; GWP20 and GWP100
  of CH4 and N2O; GWP100 of fossil CH4 (30, footnote: 50% of the carbon becomes
  CO2).
- AR6 WG1 Chapter 7: AGWP100 of CO2 (Table 7.SM.7) and the CH4 and N2O
  radiative efficiencies with chemical effects (Table 7.15). The AR6 CH4 and
  N2O GWPs include a carbon-cycle feedback that the AR6 set leaves out, so they
  are checked in #33, not here (decision D3 on #28).

Tolerance (decision D4 on #28): half a unit in the last printed digit, so 28
means 28 +/- 0.5 and 9.17e-14 means 9.17e-14 +/- 0.005e-14.

Faults these catch that no other test does: a wrong or missing indirect factor
(CH4 o3/h2o, N2O CH4 term), radiative efficiencies of one set with lifetimes of
the other, a wrong ppb-per-kg conversion (molar mass or atmospheric mass), a
wrong closed form in agwp(), a wrong AGWP normalisation in gwi(), the fossil
CH4 CO2 left out of gwi(), anything in AR6 (the Cooper reference covers AR5
only), and a function that writes to its inputs.
"""

import dataclasses

import numpy as np
import pytest

from dlca.climate import agwp, burden, forcing, gwi, specific_forcing
from dlca.parameters import get_parameters


def half_unit(value: str) -> float:
    """Half a unit in the last printed digit of ``value``, for example '9.17e-14'."""
    mantissa, _, exponent = value.lower().partition("e")
    decimals = len(mantissa.partition(".")[2])
    return 0.5 * 10.0 ** (-decimals) * 10.0 ** int(exponent or 0)


def assert_matches_table(got: float, printed: str) -> None:
    want = float(printed)
    tol = half_unit(printed)
    assert abs(got - want) <= tol, f"got {got!r}, table {printed} +/- {tol:g}"


# (gas, horizon, printed value) from AR5 Table 8.A.1, W m-2 yr kg-1.
AR5_AGWP = [
    ("co2", 20, "2.49e-14"),
    ("co2", 100, "9.17e-14"),
    ("ch4", 100, "2.61e-12"),
    ("n2o", 100, "2.43e-11"),
]
# (gas, horizon, printed value) from AR5 Table 8.A.1, no carbon-cycle feedback.
AR5_GWP = [
    ("ch4", 20, "84"),
    ("ch4", 100, "28"),
    ("n2o", 20, "264"),
    ("n2o", 100, "265"),
]


@pytest.mark.parametrize(("gas", "horizon", "printed"), AR5_AGWP)
def test_ar5_agwp_matches_table_8a1(gas, horizon, printed):
    assert_matches_table(agwp(gas, horizon, get_parameters("AR5")), printed)


@pytest.mark.parametrize(("gas", "horizon", "printed"), AR5_GWP)
def test_ar5_gwp_matches_table_8a1(gas, horizon, printed):
    p = get_parameters("AR5")
    assert_matches_table(agwp(gas, horizon, p) / agwp("co2", horizon, p), printed)


def test_ar5_fossil_ch4_gwp100_matches_table_8a1():
    """A 1 kg fossil CH4 pulse: GWP100 = 30 (Table 8.A.1), against 28 if biogenic.

    Decision D2 on #28. The oxidised CO2 comes from burden(); the spreadsheet's
    sliding value (28.46) leaves it out and would fail this.
    """
    p = get_parameters("AR5")
    e = {"ch4_fossil": np.r_[1.0, np.zeros(200)]}
    result = gwi(e, p, horizon=100)
    assert_matches_table(result.dynamic[100], "30")
    assert_matches_table(result.sliding[100], "30")


def test_ar6_agwp100_co2_matches_table_7sm7():
    assert_matches_table(agwp("co2", 100, get_parameters("AR6")), "8.95e-14")


@pytest.mark.parametrize(("gas", "printed"), [("ch4", "5.7e-4"), ("n2o", "2.8e-3")])
def test_ar6_effective_radiative_efficiency_matches_table_7_15(gas, printed):
    assert_matches_table(get_parameters("AR6").effective_radiative_efficiency(gas), printed)


@pytest.mark.parametrize("name", ["AR5", "AR6"])
@pytest.mark.parametrize("gas", ["co2", "ch4", "n2o"])
def test_integrated_forcing_of_pulse_equals_agwp(name, gas):
    """forcing() (whole-year steps on the burden) and agwp() (closed form) agree.

    Catches forcing() and agwp() using different specific forcings, lifetimes or
    pool weights, in AR6 too (the Cooper reference covers only AR5).
    """
    # Without CCF (C6 on #33): this checks the gas's own response; CCF has its own tests.
    p = dataclasses.replace(get_parameters(name), carbon_cycle_feedback=False)
    t = np.arange(301)
    e = {gas: np.r_[1.0, np.zeros(300)]}
    got = getattr(forcing(burden(e, p), p), f"{gas}_integrated")
    np.testing.assert_allclose(got, agwp(gas, t, p), rtol=1e-12, atol=0)


@pytest.mark.parametrize("name", ["AR5", "AR6"])
def test_gwi_of_co2_pulse_is_one_at_horizon(name):
    """Catches gwi() normalising by AGWP(CO2) at the wrong horizon or from another
    set (dynamic), and an off-by-one in the sliding remaining horizon (H - k - 1
    or H - k + 1 gives a ratio other than 1 at year 0)."""
    p = get_parameters(name)
    for horizon in (20, 100):
        result = gwi({"co2": np.r_[1.0, np.zeros(150)]}, p, horizon=horizon)
        np.testing.assert_allclose(result.dynamic[horizon], 1.0, rtol=1e-12)
        np.testing.assert_allclose(result.sliding, 1.0, rtol=1e-12)


def test_agwp_shape_and_scalar():
    p = get_parameters("AR6")
    assert isinstance(agwp("co2", 100, p), float)
    assert agwp("ch4", 0, p) == 0.0
    h = np.arange(6.0).reshape(2, 3)
    assert agwp("n2o", h, p).shape == (2, 3)


@pytest.mark.parametrize(
    ("call", "match"),
    [
        (lambda p: agwp("sf6", 100, p), "unknown gas"),
        (lambda p: agwp("co2", -1, p), "horizon"),
        (lambda p: specific_forcing("x", p), "unknown gas"),
        (lambda p: gwi({"co2": [1.0]}, p, horizon=0), "horizon"),
    ],
)
def test_bad_input_raises(call, match):
    with pytest.raises(ValueError, match=match):
        call(get_parameters("AR6"))


def test_inputs_not_mutated():
    """forcing(), agwp() and gwi() accept a frozen ClimateParameters and read-only arrays."""
    p = get_parameters("AR5")
    before = p.fingerprint()
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.co2_re = 0.0  # type: ignore[misc]

    e = {key: np.linspace(1.0, 2.0, 50) for key in ("co2", "ch4", "ch4_fossil", "n2o")}
    for arr in e.values():
        arr.flags.writeable = False
    b = burden(e, p)
    for name in ("co2", "co2_pools", "ch4", "n2o", "ch4_to_co2"):
        getattr(b, name).flags.writeable = False
    copies = {name: getattr(b, name).copy() for name in ("co2", "co2_pools", "ch4", "n2o")}
    h = np.arange(10.0)
    h.flags.writeable = False

    forcing(b, p)
    agwp("co2", h, p)
    gwi(e, p)

    assert p.fingerprint() == before
    for name, copy in copies.items():
        np.testing.assert_array_equal(getattr(b, name), copy)
    np.testing.assert_array_equal(h, np.arange(10.0))
    np.testing.assert_array_equal(e["co2"], np.linspace(1.0, 2.0, 50))
