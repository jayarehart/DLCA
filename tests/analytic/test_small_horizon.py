"""GWP and GTP at the minimum horizon against their limit as H -> 0 (issue #47, H5).

Independent check, derived by hand before the code ran (#47, decision H5). For
a 1 kg pulse of any key, as H -> 0:

- AGWP_x(H) = A_x H + O(H^2). For CO2, ``a0 H + sum a_i tau_i (1 - exp(-H/tau_i))``
  -> ``(sum a) H = H``; for CH4 and N2O, ``tau (1 - exp(-H/tau))`` -> H. The
  oxidised CO2 of fossil CH4 is O(H^2) and the carbon-cycle feedback O(H^3).
- AGTP_x(H) = A_x (sum_i q_i / d_i) H + O(H^2). Each box response,
  ``q (1 - exp(-H/d))`` or ``q tau / (tau - d) (exp(-H/tau) - exp(-H/d))``, is
  ``q H / d`` to first order, whatever the lifetime, so the sum is the same for
  every gas.

So GWP_H and GTP_H of every key tend to ``A_x / A_CO2``, with ``A`` the
specific forcing (``A_ch4_fossil = A_ch4``). ``A`` is taken from
``specific_forcing()``: this checks the closed forms at small H, not the
specific forcings, which the IPCC-table tests check. The second-order terms are of
relative size H / (2 tau) or H / (2 d); with the shortest time scale above
1 yr in both sets that is below 1e-6 at H = 1e-6 yr, so the check allows
``RTOL = 1e-5``. A wrong closed form, a lost term at small H or a wrong CO2
normalisation moves the ratio by far more. It detects a minimum of about
1e-12 yr or lower (the factors are then about 1e-2 off), not 1e-9 (2e-6 off);
the unit tests in test_climate_horizon.py pin the minimum itself.

Faults these catch that no other test does: the closed forms inaccurate at the
minimum horizon (as they are below about 1e-9 yr, #47); a minimum set so low
that the static factors are off by more than 1e-5.
"""

import numpy as np
import pytest

from dlca.climate import MIN_HORIZON, gtp, specific_forcing, static_gwp
from dlca.parameters import get_parameters

RTOL = 1e-5
KEYS = ["co2", "ch4", "ch4_fossil", "n2o"]


def limit(key: str, params) -> float:
    gas = "ch4" if key == "ch4_fossil" else key
    return specific_forcing(gas, params) / specific_forcing("co2", params)


def shortest_time_scale(params) -> float:
    return min(*params.co2_tau, *params.climate_d, params.ch4_lifetime, params.n2o_lifetime)


@pytest.mark.parametrize("name", ["AR5", "AR6"])
def test_time_scales_allow_the_tolerance(name):
    """The bound on the second-order terms in the docstring holds."""
    p = get_parameters(name)
    assert sum(p.co2_a) == pytest.approx(1.0, abs=1e-12)  # AGWP_CO2 -> H
    assert MIN_HORIZON / (2 * shortest_time_scale(get_parameters(name))) < RTOL / 10


@pytest.mark.parametrize("name", ["AR5", "AR6"])
@pytest.mark.parametrize("key", KEYS)
def test_static_gwp_factor_tends_to_forcing_ratio(name, key):
    p = get_parameters(name)
    factor = static_gwp({key: np.ones(1)}, p, horizon=MIN_HORIZON).gwp[key]
    assert factor == pytest.approx(limit(key, p), rel=RTOL)


@pytest.mark.parametrize("name", ["AR5", "AR6"])
@pytest.mark.parametrize("key", KEYS)
def test_static_gtp_factor_tends_to_forcing_ratio(name, key):
    p = get_parameters(name)
    factor = gtp({key: np.ones(1)}, p, horizon=MIN_HORIZON).static[0]
    assert factor == pytest.approx(limit(key, p), rel=RTOL)
