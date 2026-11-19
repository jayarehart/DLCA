"""agtp(), temperature() and gtp() against published IPCC values (issue #29).

The expected values are typed from the IPCC tables, not read from dlca or from
the parameter JSON files:

- AR5 WG1 Chapter 8, Table 8.A.1 (Myhre et al. 2013, p. 731), no carbon-cycle
  feedback: AGTP20 and AGTP100 of CO2; AGTP100 of CH4 and N2O; GTP20 and
  GTP100 of CH4, N2O and fossil CH4 (footnote: 50% of the carbon becomes CO2).
- AR6 WG1 Chapter 7: AGTP100 of CO2 (Table 7.SM.7). The AR6 CH4 and N2O GTPs
  include a carbon-cycle feedback that the AR6 set leaves out, so they are
  checked in #33 (decision T4 on #29). The AR6 CH4 and N2O AGTP100 are checked
  against values from the IPCC Chapter 7 code (``ar6.json`` checks); these are
  **not a published table**.

Tolerance (decision T5 on #29): half a unit in the last printed digit.

The AGTP100(CO2) row alone does not catch the AGTP p1 -> p3 slip: the slip
moves it by -0.06%, inside the table's rounding of +/- 0.09%. AGTP20(CO2),
GTP20(N2O), the pulse test below and the Cooper reference GTP columns do.

Faults these catch that no other test does: the p1 -> p3 slip; d1 and d2
swapped; a wrong closed form in agtp(); temperature() and agtp() disagreeing
(including in AR6, which the Cooper reference does not cover); a wrong
normalisation or an off-by-one remaining horizon in gtp(); the fossil CH4 CO2
left out of gtp(); a wrong value in any year of the CH4 AGTP table; tau equal
to a climate response time not being refused; and a function writing to its inputs.
"""

import dataclasses
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dlca.climate import Temperature, agtp, burden, gtp, temperature
from dlca.parameters import get_parameters

CASES_DIR = Path(__file__).parent.parent / "reference" / "cases"


def half_unit(value: str) -> float:
    """Half a unit in the last printed digit of ``value``, for example '5.47e-16'."""
    mantissa, _, exponent = value.lower().partition("e")
    decimals = len(mantissa.partition(".")[2])
    return 0.5 * 10.0 ** (-decimals) * 10.0 ** int(exponent or 0)


def assert_matches_table(got: float, printed: str) -> None:
    want = float(printed)
    tol = half_unit(printed)
    assert abs(got - want) <= tol, f"got {got!r}, table {printed} +/- {tol:g}"


def pulse(gas: str, n: int = 301) -> dict[str, np.ndarray]:
    return {gas: np.r_[1.0, np.zeros(n - 1)]}


# (gas, horizon, printed value) from AR5 Table 8.A.1, K kg-1.
AR5_AGTP = [
    ("co2", 20, "6.84e-16"),
    ("co2", 100, "5.47e-16"),
    ("ch4", 100, "2.34e-15"),
    ("n2o", 100, "1.28e-13"),
]
# (gas, horizon, printed value) from AR5 Table 8.A.1, no carbon-cycle feedback.
AR5_GTP = [
    ("ch4", 20, "67"),
    ("ch4", 100, "4"),
    ("n2o", 20, "277"),
    ("n2o", 100, "234"),
]


@pytest.mark.parametrize(("gas", "horizon", "printed"), AR5_AGTP)
def test_ar5_agtp_matches_table_8a1(gas, horizon, printed):
    assert_matches_table(agtp(gas, horizon, get_parameters("AR5")), printed)


@pytest.mark.parametrize(("gas", "horizon", "printed"), AR5_GTP)
def test_ar5_gtp_matches_table_8a1(gas, horizon, printed):
    p = get_parameters("AR5")
    assert_matches_table(agtp(gas, horizon, p) / agtp("co2", horizon, p), printed)


@pytest.mark.parametrize(("horizon", "printed"), [(20, "68"), (100, "6")])
def test_ar5_fossil_ch4_gtp_matches_table_8a1(horizon, printed):
    """A 1 kg fossil CH4 pulse: GTP20 = 68, GTP100 = 6 (Table 8.A.1).

    Decision T2 on #29: the oxidised CO2 comes from burden(). At H = 100 the
    biogenic value (4.27) would fail this; at H = 20 the gap (67.4 vs 68.4) is
    only just outside the rounding, so H = 100 is the real check.
    """
    p = get_parameters("AR5")
    result = gtp(pulse("ch4"), p, horizon=horizon, fossil_ch4=True)
    assert_matches_table(result.dynamic[horizon], printed)
    assert_matches_table(result.sliding[horizon], printed)


def test_ar6_agtp100_co2_matches_table_7sm7():
    assert_matches_table(agtp("co2", 100, get_parameters("AR6")), "3.95e-16")


@pytest.mark.parametrize(("gas", "code_value"), [("ch4", "1.93488e-15"), ("n2o", "8.63187e-14")])
def test_ar6_agtp100_matches_ipcc_code(gas, code_value):
    """Not a published table: IPCC Chapter 7 code values, no carbon-cycle feedback."""
    assert_matches_table(agtp(gas, 100, get_parameters("AR6")), code_value)


@pytest.mark.parametrize("name", ["AR5", "AR6"])
@pytest.mark.parametrize("gas", ["co2", "ch4", "n2o"])
def test_temperature_of_pulse_equals_agtp(name, gas):
    """By definition, the temperature change H years after a 1 kg pulse is AGTP_H.

    temperature() steps the two boxes year by year on the burden's pools; agtp()
    is the closed form. They share only the box-response helper, so this catches
    the p1 -> p3 slip, a wrong pool weight or lifetime in either, and an
    off-by-one in temperature()'s convolution, in AR6 too.
    """
    p = get_parameters(name)
    t = np.arange(501)
    got = getattr(temperature(burden(pulse(gas, 501), p), p), gas)
    want = agtp(gas, t, p)
    assert got[0] == 0.0 and want[0] == 0.0
    np.testing.assert_allclose(got[1:], want[1:], rtol=1e-12, atol=0)


def test_ch4_agtp_table_every_year():
    """Every year 0-500 of the corrected CH4 AGTP table against closed-form agtp().

    The pasted table (equivalency_metrics!T7:T507) is not committed.
    generate_cases.py checks that, once corrected, it equals the CH4_temp of
    ch4_pulse_biogenic to 1e-12 at every year; this compares that column with
    agtp("ch4", t) at every year (decision T6 on #29). With the uncorrected
    16.00 g/mol table every year would be off by 0.31%.
    """
    ch4 = pd.read_csv(CASES_DIR / "ch4_pulse_biogenic" / "expected.csv")
    years = ch4["year"].to_numpy()
    want = ch4["CH4_temp"].to_numpy(dtype=float)
    got = agtp("ch4", years, get_parameters("AR5"))
    assert len(years) == 501 and years[-1] == 500
    assert want[0] == 0.0 and got[0] == 0.0
    np.testing.assert_allclose(got[1:], want[1:], rtol=1e-9, atol=0)


@pytest.mark.parametrize("name", ["AR5", "AR6"])
def test_gtp_of_co2_pulse_is_one_at_horizon(name):
    """Catches gtp() normalising by AGTP(CO2) at the wrong horizon or from another
    set (dynamic), an off-by-one in the sliding remaining horizon, and static not
    using GTP_H(CO2) = 1."""
    p = get_parameters(name)
    for horizon in (20, 100):
        result = gtp(pulse("co2", 151), p, horizon=horizon)
        np.testing.assert_allclose(result.dynamic[horizon], 1.0, rtol=1e-12)
        np.testing.assert_allclose(result.sliding, 1.0, rtol=1e-12)
        np.testing.assert_allclose(result.static, 1.0, rtol=1e-12)


def test_gtp_sliding_equals_dynamic_after_horizon():
    """For mixed emissions spread over years, sliding[t >= H] == dynamic[H].

    Catches the sliding sum and temperature() disagreeing for gases other than
    CO2 and for emissions after year 0, including the fossil CH4 CO2 (T2).
    """
    p = get_parameters("AR5")
    rng = np.random.default_rng(29)
    e = {gas: rng.uniform(0.0, 1.0, 200) for gas in ("co2", "ch4", "n2o")}
    for fossil in (False, True):
        result = gtp(e, p, horizon=100, fossil_ch4=fossil)
        np.testing.assert_allclose(result.sliding[100:], result.dynamic[100], rtol=1e-12)


def test_gtp_static_ignores_fossil_flag():
    """Decision T3 on #29: static GTP counts CH4 only, as the spreadsheet does."""
    p = get_parameters("AR5")
    bio = gtp(pulse("ch4"), p, fossil_ch4=False)
    fos = gtp(pulse("ch4"), p, fossil_ch4=True)
    np.testing.assert_array_equal(bio.static, fos.static)
    # Positive control: the same comparison separates them on dynamic.
    assert fos.dynamic[100] > bio.dynamic[100] * 1.2


def test_agtp_shape_and_scalar():
    p = get_parameters("AR6")
    assert isinstance(agtp("co2", 100, p), float)
    assert agtp("ch4", 0, p) == 0.0
    h = np.arange(6.0).reshape(2, 3)
    assert agtp("n2o", h, p).shape == (2, 3)
    t = temperature(burden(pulse("co2", 5), p), p)
    assert isinstance(t, Temperature)
    assert set(t.to_dict()) == {"co2", "ch4", "n2o"}
    np.testing.assert_array_equal(t.total, t.co2 + t.ch4 + t.n2o)


def test_lifetime_equal_to_response_time_raises():
    """Decision T7 on #29: tau == d_i divides by zero in the closed form."""
    p = get_parameters("AR5")
    bad = dataclasses.replace(p, ch4_lifetime=p.climate_d[0])
    with pytest.raises(ValueError, match="climate response time"):
        agtp("ch4", 100, bad)
    with pytest.raises(ValueError, match="climate response time"):
        temperature(burden(pulse("ch4", 5), bad), bad)


@pytest.mark.parametrize(
    ("call", "match"),
    [
        (lambda p: agtp("sf6", 100, p), "unknown gas"),
        (lambda p: agtp("co2", -1, p), "horizon"),
        (lambda p: agtp("co2", np.nan, p), "horizon"),
        (lambda p: gtp({"co2": [1.0]}, p, horizon=0), "horizon"),
    ],
)
def test_bad_input_raises(call, match):
    with pytest.raises(ValueError, match=match):
        call(get_parameters("AR6"))


def test_inputs_not_mutated():
    """temperature(), agtp() and gtp() accept a frozen ClimateParameters and read-only arrays."""
    p = get_parameters("AR5")
    before = p.fingerprint()
    e = {gas: np.linspace(1.0, 2.0, 50) for gas in ("co2", "ch4", "n2o")}
    for arr in e.values():
        arr.flags.writeable = False
    b = burden(e, p, fossil_ch4=True)
    for name in ("co2", "co2_pools", "ch4", "n2o", "ch4_to_co2"):
        getattr(b, name).flags.writeable = False
    copies = {name: getattr(b, name).copy() for name in ("co2", "co2_pools", "ch4", "n2o")}
    h = np.arange(10.0)
    h.flags.writeable = False

    temperature(b, p)
    agtp("co2", h, p)
    gtp(e, p, fossil_ch4=True)

    assert p.fingerprint() == before
    for name, copy in copies.items():
        np.testing.assert_array_equal(getattr(b, name), copy)
    np.testing.assert_array_equal(h, np.arange(10.0))
    np.testing.assert_array_equal(e["co2"], np.linspace(1.0, 2.0, 50))
