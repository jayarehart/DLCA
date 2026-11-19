"""Property tests for ``burden()``, ``forcing()`` and ``gwi()`` (issue #32).

The analytic and reference tests check fixed cases: unit pulses and a few
spreadsheet profiles. These tests check invariants that must hold for *any*
emission profile, with mixed signs (uptake), all three gases at once, and both
parameter sets:

- linearity: f(a x) = a f(x), including a < 0;
- superposition: f(x + y) = f(x) + f(y);
- time shift: delaying all emissions by s years delays every output by s years;
- zero in, zero out: exactly zero (``==``), also in leading zero years.

Every output array is checked: the burden (total CO2, the four CO2 pools, CH4,
N2O, CO2 from fossil CH4), the forcing and integrated forcing of each gas, and
the dynamic and sliding GWI. ``agwp()`` is checked through ``gwi()``, which
calls it for the sliding GWI and the CO2 normalisation.

Tolerance. The functions are sums of products, so rounding error in an output
is bounded by a small multiple of machine epsilon times the same output
computed from the absolute values of the emissions, f(|x|). The kernels and
specific forcings are all positive, so f(|x|) >= |f(x)| element by element. The
comparisons allow ``RTOL * max(f(|x|))`` per output array; any real fault (an
offset, a dropped sign, a year shift) moves an output by a fraction of order
one of that scale.

Hypothesis runs ``MAX_EXAMPLES`` examples per test. Set ``CI`` in the
environment to derandomise (fixed examples), as the CI workflow on GitHub does.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from dlca.climate import GASES, burden, forcing, gwi
from dlca.parameters import get_parameters

PARAMS = {name: get_parameters(name) for name in ("AR5", "AR6")}
RTOL = 1e-9
MAX_EXAMPLES = 50
MAX_YEARS = 130  # past the default 100-year horizon

SETTINGS = settings(
    max_examples=MAX_EXAMPLES,
    deadline=None,
    derandomize=bool(os.environ.get("CI")),
    suppress_health_check=[HealthCheck.too_slow],
)

both_sets = pytest.mark.parametrize("set_name", list(PARAMS))
both_ch4_modes = pytest.mark.parametrize("fossil_ch4", [False, True], ids=["bio", "fossil"])


def signed(lo: float, hi: float) -> st.SearchStrategy[float]:
    """0, or a magnitude in [lo, hi] of either sign.

    Magnitudes are kept well above the floating-point underflow range: an
    emission of 1e-300 kg has no meaning, and its outputs would be subnormal
    numbers whose rounding is not relative, so the tolerance would not apply.
    """
    magnitude = st.floats(lo, hi)
    return st.just(0.0) | magnitude | magnitude.map(lambda v: -v)


value = signed(1e-6, 1e6)  # kg per year
scale = signed(1e-3, 10.0)
horizon = st.floats(1.0, 150.0)


def profile(n: int) -> st.SearchStrategy[dict[str, np.ndarray]]:
    """Emissions of all three gases over n years, mixed signs."""
    return st.fixed_dictionaries({gas: arrays(np.float64, n, elements=value) for gas in GASES})


@st.composite
def one_profile(draw, min_years: int = 1) -> dict[str, np.ndarray]:
    n = draw(st.integers(min_years, MAX_YEARS))
    return draw(profile(n))


@st.composite
def two_profiles(draw) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    n = draw(st.integers(1, MAX_YEARS))
    return draw(profile(n)), draw(profile(n))


def outputs(e, params, *, fossil_ch4: bool, horizon: float) -> dict[str, np.ndarray]:
    """Every array that burden(), forcing() and gwi() return, by name."""
    b = burden(e, params, fossil_ch4=fossil_ch4)
    f = forcing(b, params)
    g = gwi(e, params, horizon=horizon, fossil_ch4=fossil_ch4)
    out = {f"burden.{k}": v for k, v in b.to_dict().items()}
    out |= {f"forcing.{k}": v for k, v in f.to_dict().items()}
    out |= {"gwi.dynamic": g.dynamic, "gwi.sliding": g.sliding}
    return {k: np.asarray(v, dtype=float) for k, v in out.items()}


def absolute(e):
    return {gas: np.abs(v) for gas, v in e.items()}


def assert_close(actual, expected, bound):
    """actual == expected to within RTOL of the scale of each output in bound."""
    assert actual.keys() == expected.keys()
    for name in actual:
        atol = RTOL * float(np.max(bound[name], initial=0.0))
        np.testing.assert_allclose(actual[name], expected[name], rtol=0, atol=atol, err_msg=name)


@both_sets
@both_ch4_modes
@SETTINGS
@given(e=one_profile(), a=scale, h=horizon)
def test_linearity(set_name, fossil_ch4, e, a, h):
    """f(a x) = a f(x), for a of either sign."""
    p = PARAMS[set_name]
    run = lambda x: outputs(x, p, fossil_ch4=fossil_ch4, horizon=h)  # noqa: E731
    scaled = run({gas: a * v for gas, v in e.items()})
    expected = {k: a * v for k, v in run(e).items()}
    bound = {k: abs(a) * v for k, v in run(absolute(e)).items()}
    assert_close(scaled, expected, bound)


@both_sets
@both_ch4_modes
@SETTINGS
@given(xy=two_profiles(), h=horizon)
def test_superposition(set_name, fossil_ch4, xy, h):
    """f(x + y) = f(x) + f(y)."""
    x, y = xy
    p = PARAMS[set_name]
    run = lambda e: outputs(e, p, fossil_ch4=fossil_ch4, horizon=h)  # noqa: E731
    fx, fy = run(x), run(y)
    together = run({gas: x[gas] + y[gas] for gas in GASES})
    ax, ay = run(absolute(x)), run(absolute(y))
    assert_close(together, {k: fx[k] + fy[k] for k in fx}, {k: ax[k] + ay[k] for k in ax})


@st.composite
def profile_and_shift(draw):
    e = draw(one_profile(min_years=2))
    n = len(e["co2"])
    return e, draw(st.integers(1, n - 1))


def delay(e, s):
    """The same profile, s years later, cut to the same length."""
    return {gas: np.r_[np.zeros(s), v[: len(v) - s]] for gas, v in e.items()}


@both_sets
@both_ch4_modes
@SETTINGS
@given(es=profile_and_shift(), h=horizon)
def test_time_shift(set_name, fossil_ch4, es, h):
    """Delaying emissions by s years delays every output by s years.

    The sliding GWI is the exception by design: an emission in year k is
    counted to the fixed year H, so its horizon is H - k, and a delay shortens
    it. It is checked separately in ``test_time_shift_sliding_gwi``.
    """
    e, s = es
    n = len(e["co2"])
    p = PARAMS[set_name]
    run = lambda x: outputs(x, p, fossil_ch4=fossil_ch4, horizon=h)  # noqa: E731
    late, early, bound = run(delay(e, s)), run(e), run(absolute(e))
    for out in (late, early, bound):
        del out["gwi.sliding"]
    assert_close(
        {k: v[..., s:] for k, v in late.items()},
        {k: v[..., : n - s] for k, v in early.items()},
        bound,
    )


@both_sets
@both_ch4_modes
@SETTINGS
@given(es=profile_and_shift(), h=horizon)
def test_time_shift_sliding_gwi(set_name, fossil_ch4, es, h):
    """Sliding GWI: a delay of s years under horizon H equals no delay under H - s.

    In absolute terms (times AGWP_H(CO2)), since the normalisation differs.
    """
    e, s = es
    if h - s <= 0:
        h = s + 1.0
    n = len(e["co2"])
    p = PARAMS[set_name]

    def absolute_sliding(x, horizon):
        g = gwi(x, p, horizon=horizon, fossil_ch4=fossil_ch4)
        return {"gwi.sliding": g.sliding * g.agwp_co2}

    late = absolute_sliding(delay(e, s), h)
    early = absolute_sliding(e, h - s)
    assert np.all(late["gwi.sliding"][:s] == 0.0)
    assert_close(
        {"gwi.sliding": late["gwi.sliding"][s:]},
        {"gwi.sliding": early["gwi.sliding"][: n - s]},
        absolute_sliding(absolute(e), h - s),
    )


@st.composite
def profile_and_zero_years(draw):
    """A profile and a number of leading zero years k, 1 <= k <= n (k = n: all zero)."""
    e = draw(one_profile())
    n = len(e["co2"])
    k = draw(st.integers(1, n))
    return {gas: np.r_[np.zeros(k), v[k:]] for gas, v in e.items()}, k


@both_sets
@both_ch4_modes
@SETTINGS
@given(ek=profile_and_zero_years(), h=horizon)
def test_zero_in_gives_exactly_zero_out(set_name, fossil_ch4, ek, h):
    """No emissions before year k gives exactly zero (``==``) output before year k.

    With k equal to the length, the emissions are all zero and so is every
    output. Integrated forcing (from year 0 to the start of year t) and the CO2
    formed from fossil CH4 (removed during year t) are also exactly zero at
    year k.
    """
    e, k = ek
    for name, out in outputs(e, PARAMS[set_name], fossil_ch4=fossil_ch4, horizon=h).items():
        zero_to = k + 1 if name.endswith(("_integrated", "ch4_to_co2")) else k
        assert np.all(out[..., :zero_to] == 0.0), name
