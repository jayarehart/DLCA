"""burden() against closed-form impulse responses (issue #27).

Expected values were computed by hand, outside dlca, with Python's ``math``
module and the numbers read from ``src/dlca/data/climate_parameters/*.json``
(not from ``dlca``), on 2026-11-18:

- CO2 (Joos et al. 2013, as in AR5 8.SM.11 and AR6 Ch. 7):
  ``a0 + a1 exp(-t/394.4) + a2 exp(-t/36.54) + a3 exp(-t/4.304)`` with
  a = (0.2173, 0.224, 0.2824, 0.2763); the same in AR5 and AR6.
- CH4, N2O: ``exp(-t/tau)`` with tau = 12.4 and 121 yr (AR5), 11.8 and 109 yr (AR6).
- Fossil CH4, 1 kg pulse at year 0, r = yield * 44/16 kg CO2 per kg CH4
  (yield 0.5 in AR5, 0.75 in AR6), q = exp(-1/tau_CH4):
  year 1 CO2 = r (1 - q); year 2 CO2 = r (1 - q) IRF_CO2(1) + r q (1 - q).
  The AR5 year-1 value, 0.106533653149056, is also the Cooper spreadsheet's.

Faults these catch that no other test does: a wrong pool time constant or
fraction (for example tau2 and tau3 swapped), an off-by-one in the decay (mass
at year t equal to exp(-(t+1)/tau) or exp(-(t-1)/tau)), and in AR6 (which the
Cooper reference does not cover) a wrong lifetime, yield or fossil timing.
"""

import dataclasses

import numpy as np
import pytest

from dlca.climate import burden
from dlca.parameters import get_parameters

YEARS = [0, 1, 10, 100, 500]
N = 501
RTOL = 1e-12

# Hand-computed IRF values at YEARS (see module docstring).
CO2_IRF = [1.0, 0.9345251433514736, 0.677540238510535, 0.40942767199397434, 0.28034839989069876]
EXPECTED = {
    "AR5": {
        "co2": CO2_IRF,
        "ch4": [
            1.0,
            0.9225209795279594,
            0.4464393987758162,
            0.00031450325596978746,
            3.0769874839944985e-18,
        ],
        "n2o": [
            1.0,
            0.9917695939779198,
            0.9206782722788244,
            0.4376016396389107,
            0.01604703141694744,
        ],
    },
    "AR6": {
        "co2": CO2_IRF,
        "ch4": [
            1.0,
            0.9187458341610336,
            0.4285029625845361,
            0.0002087076119901937,
            3.9599658874725096e-19,
        ],
        "n2o": [
            1.0,
            0.9908676436704476,
            0.9123394818817833,
            0.39954407571674166,
            0.010181774575044107,
        ],
    },
}
# CO2 mass [kg] at years 1 and 2 after a 1 kg fossil CH4 pulse at year 0.
FOSSIL_CO2 = {
    "AR5": [0.1065336531490558, 0.19783790753663638],
    "AR6": [0.16758671704286818, 0.31058359891214826],
}


def pulse(n=N, at=0):
    e = np.zeros(n)
    e[at] = 1.0
    return e


@pytest.mark.parametrize("set_name", ["AR5", "AR6"])
@pytest.mark.parametrize("gas", ["co2", "ch4", "n2o"])
def test_pulse_matches_closed_form_irf(set_name, gas):
    b = burden({gas: pulse()}, get_parameters(set_name))
    got = getattr(b, gas)[YEARS]
    np.testing.assert_allclose(got, EXPECTED[set_name][gas], rtol=RTOL, atol=0)


@pytest.mark.parametrize("set_name", ["AR5", "AR6"])
def test_co2_pools_match_closed_form(set_name):
    params = get_parameters(set_name)
    b = burden({"co2": pulse()}, params)
    t = np.array(YEARS, dtype=float)
    a = params.co2_a
    # Each pool by hand: a0, then a_i exp(-t/tau_i) with tau = 394.4, 36.54, 4.304.
    want = np.stack(
        [
            np.full_like(t, 0.2173),
            0.224 * np.exp(-t / 394.4),
            0.2824 * np.exp(-t / 36.54),
            0.2763 * np.exp(-t / 4.304),
        ]
    )
    assert a == (0.2173, 0.224, 0.2824, 0.2763)
    np.testing.assert_allclose(b.co2_pools[:, YEARS], want, rtol=RTOL, atol=0)
    np.testing.assert_allclose(b.co2, b.co2_pools.sum(axis=0), rtol=1e-15)


@pytest.mark.parametrize("set_name", ["AR5", "AR6"])
def test_fossil_ch4_oxidised_co2_same_step(set_name):
    b = burden({"ch4_fossil": pulse()}, get_parameters(set_name))
    assert b.co2[0] == 0.0
    np.testing.assert_allclose(b.co2[[1, 2]], FOSSIL_CO2[set_name], rtol=RTOL, atol=0)
    # The CH4 itself is unchanged by oxidation to CO2.
    np.testing.assert_allclose(b.ch4[YEARS], EXPECTED[set_name]["ch4"], rtol=RTOL, atol=0)


@pytest.mark.parametrize(("set_name", "r"), [("AR5", 0.5 * 44 / 16), ("AR6", 0.75 * 44 / 16)])
def test_fossil_ch4_conserves_carbon_every_year(set_name, r):
    """All CH4 that leaves becomes CO2, in every year, not just years 1 and 2.

    By year k the CO2 formed must be r * (1 - CH4 left), where CH4 left is the
    hand-computed exp(-k/tau). Over the full 500 years that is r (1 - exp(-500/tau)),
    which is 1.375 (AR5) and 2.0625 (AR6) to double precision. Catches a timing,
    lifetime or yield fault after year 2 that the year-1/2 check would miss.
    """
    tau = {"AR5": 12.4, "AR6": 11.8}[set_name]
    b = burden({"ch4_fossil": pulse()}, get_parameters(set_name))
    t = np.arange(N)
    np.testing.assert_allclose(np.cumsum(b.ch4_to_co2), r * (1 - np.exp(-t / tau)), rtol=1e-12)
    np.testing.assert_allclose(b.ch4_to_co2.sum(), r * (1 - np.exp(-500 / tau)), rtol=1e-12)


def test_biogenic_ch4_makes_no_co2():
    b = burden({"ch4": pulse()}, get_parameters("AR6"))
    assert not np.any(b.co2) and not np.any(b.ch4_to_co2)


def test_late_pulse_is_shifted_irf():
    params = get_parameters("AR5")
    b = burden({"co2": pulse(at=60)}, params)
    assert not np.any(b.co2[:60])
    np.testing.assert_allclose(b.co2[[60, 61, 70]], CO2_IRF[:3], rtol=RTOL, atol=0)


def test_fossil_ch4_needs_a_yield():
    params = dataclasses.replace(get_parameters("AR6"), ch4_fossil_co2_yield=None)
    burden({"ch4": pulse()}, params)  # fine without fossil CH4
    with pytest.raises(ValueError, match="fossil CH4"):
        burden({"ch4_fossil": pulse()}, params)


@pytest.mark.parametrize(
    "emissions",
    [
        {"co2": np.zeros(3), "ch4": np.zeros(4)},
        {"co2": np.zeros((2, 3))},
        {"co2": [0.0, np.nan]},
        {"sf6": np.zeros(3)},
        {},
        {"co2": []},
    ],
    ids=["unequal-lengths", "not-1d", "nan", "unknown-gas", "empty-mapping", "zero-length"],
)
def test_bad_input_raises(emissions):
    with pytest.raises(ValueError):
        burden(emissions, get_parameters("AR6"))


def test_to_dict_is_plain_lists():
    d = burden({"co2": [1.0, 0.0]}, get_parameters("AR6")).to_dict()
    assert set(d) == {"co2", "co2_pools", "ch4", "n2o", "ch4_to_co2"}
    assert isinstance(d["co2_pools"][0][0], float)
