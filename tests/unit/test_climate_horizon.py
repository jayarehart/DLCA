"""The minimum horizon of gwi(), gtp() and static_gwp() (issue #47, decision H2).

Below about 1e-9 yr the closed forms of AGWP and AGTP lose precision, because
``1 - exp(-H/tau)`` rounds to 0 when H/tau is below machine epsilon. At
H = 2.22e-16, AR5 ``gtp()`` raised ``ZeroDivisionError`` and the other functions
returned values up to 300% off without an error. Jay set the minimum to 1e-6 yr
(#47, 2026-11-19); the value below is typed from that decision, not read from dlca.

Faults these catch that no other test does: a horizon below the minimum
accepted (the ZeroDivisionError of #47, or a silently wrong result); the
minimum itself refused; one of the three functions left without the check.
"""

import math

import numpy as np
import pytest

from dlca.climate import gtp, gwi, static_gwp
from dlca.parameters import get_parameters

MIN_HORIZON = 1e-6  # yr, decision H2 on #47
FUNCTIONS = [gwi, gtp, static_gwp]
SETS = ["AR5", "AR6"]

BELOW = [
    math.nextafter(MIN_HORIZON, 0.0),
    MIN_HORIZON * (1 - 1e-12),
    2.220446049250313e-16,  # the horizon of #47
    5e-324,  # smallest subnormal float
]


def emissions() -> dict[str, np.ndarray]:
    return {key: np.array([1.0, 0.5]) for key in ("co2", "ch4", "ch4_fossil", "n2o")}


@pytest.mark.parametrize("name", SETS)
@pytest.mark.parametrize("fn", FUNCTIONS, ids=lambda f: f.__name__)
@pytest.mark.parametrize("horizon", BELOW)
def test_horizon_below_minimum_raises(fn, name, horizon):
    with pytest.raises(ValueError, match="1e-06"):
        fn(emissions(), get_parameters(name), horizon=horizon)


@pytest.mark.parametrize("name", SETS)
@pytest.mark.parametrize("fn", FUNCTIONS, ids=lambda f: f.__name__)
def test_minimum_horizon_is_accepted(fn, name):
    out = fn(emissions(), get_parameters(name), horizon=MIN_HORIZON)
    assert out.horizon == MIN_HORIZON
    for key, value in out.to_dict().items():
        if isinstance(value, list):
            assert np.all(np.isfinite(value)), key


def test_minimum_horizon_constant():
    from dlca.climate import MIN_HORIZON as value

    assert value == MIN_HORIZON
