"""dlca.assess() against values from the old DLCAEngine (removed in #31).

The expected values below were produced by the old DLCAEngine and are kept
unchanged. They come from the code, not from outside it, so they guard the
port only; the independent checks are in tests/reference and tests/analytic.

The input is the series the old flux builder (`create_flux_mat`) built
for these tests (removed in #61): one pulse in year 0 of 1 kg CO2, 1/25 kg
CH4 and 1/298 kg N2O, over years 0..500.
"""

import numpy as np

import dlca

RTOL = 1e-12


def _pulse_emissions():
    emissions = {gas: np.zeros(501) for gas in ("co2", "ch4", "n2o")}
    emissions["co2"][0] = 1
    emissions["ch4"][0] = 1 / 25
    emissions["n2o"][0] = 1 / 298
    return emissions


def _assess(horizon=100):
    """The pulse through dlca.assess() with AR5 (what DLCAEngine used)."""
    return dlca.assess(_pulse_emissions(), parameters="AR5", horizon=horizon)


def test_assess_burden():
    """Was test_dlca_engine_calc_decay (DLCAEngine.calc_decay)."""
    atm = _assess().burden
    np.testing.assert_allclose(sum(atm.co2), 184.2837146985627, rtol=RTOL)
    np.testing.assert_allclose(sum(atm.ch4), 0.5162687880706308, rtol=RTOL)
    np.testing.assert_allclose(sum(atm.n2o), 0.40123157841290424, rtol=RTOL)


def test_assess_warming():
    """Was test_dlca_engine_calc_warming (DLCAEngine.calc_AGWP and calc_AGTP)."""
    result = _assess(horizon=100)
    np.testing.assert_allclose(result.temperature.total[100], 1.0700561631626676e-15, rtol=RTOL)
    np.testing.assert_allclose(result.gwi.dynamic[100], 3.0267395007015145, rtol=RTOL)
