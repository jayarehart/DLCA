"""Property tests for the climate engine (issues #32 and #40).

Functions covered: ``burden()``, ``forcing()``, ``gwi()`` (#32), and
``temperature()``, ``gtp()`` and ``agtp()`` (#40).

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
the dynamic and sliding GWI, the temperature change of each gas, and the
dynamic, sliding and static GTP. ``agwp()`` and ``agtp()`` are checked through
``gwi()`` and ``gtp()``, which call them for the sliding and static series and
the CO2 normalisation. ``agtp()`` is also checked directly as the impulse
response of ``temperature()`` for a pulse in any year.

Tolerance. The functions are sums of products, so rounding error in an output
is bounded by a small multiple of machine epsilon times the same output
computed from the absolute values of the emissions, f(|x|). The kernels and
specific forcings are all positive (so is the two-box response to a decaying
forcing, for tau above or below d), so f(|x|) >= |f(x)| element by element.
(The carbon-cycle feedback of AR6, #33, adds a CO2 release that turns negative
after some decades as the sinks take carbon back, so for it this bound is not
exact. The CCF part is about 5% of a CH4 or N2O output and its negative tail is
smaller still, so the allowance still holds with a wide margin.) The
comparisons allow ``RTOL * max(f(|x|))`` per output array; any real fault (an
offset, a dropped sign, a year shift) moves an output by a fraction of order
one of that scale.

Hypothesis runs ``MAX_EXAMPLES`` examples per test. Set ``CI`` in the
environment to derandomise (fixed examples), as the CI workflow on GitHub does.
"""

from __future__ import annotations

import dataclasses
import os

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from dlca.climate import GASES, agtp, burden, forcing, gtp, gwi, temperature
from dlca.parameters import get_parameters

PARAMS = {name: get_parameters(name) for name in ("AR5", "AR6")}
NO_CCF = {name: dataclasses.replace(p, carbon_cycle_feedback=False) for name, p in PARAMS.items()}
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


def as_fossil(e, fossil_ch4: bool):
    """The profile with its CH4 under the ``ch4_fossil`` key if fossil_ch4 (#30, S4)."""
    if not fossil_ch4:
        return e
    return {("ch4_fossil" if gas == "ch4" else gas): v for gas, v in e.items()}


def outputs(e, params, *, fossil_ch4: bool, horizon: float) -> dict[str, np.ndarray]:
    """Every array that burden(), forcing(), gwi(), temperature() and gtp() return."""
    e = as_fossil(e, fossil_ch4)
    b = burden(e, params)
    f = forcing(b, params)
    g = gwi(e, params, horizon=horizon)
    t = temperature(b, params)
    p = gtp(e, params, horizon=horizon)
    out = {f"burden.{k}": v for k, v in b.to_dict().items()}
    out |= {f"forcing.{k}": v for k, v in f.to_dict().items()}
    out |= {"gwi.dynamic": g.dynamic, "gwi.sliding": g.sliding}
    out |= {f"temperature.{k}": v for k, v in t.to_dict().items()}
    out |= {"gtp.dynamic": p.dynamic, "gtp.sliding": p.sliding, "gtp.static": p.static}
    # parameter_fingerprint is a string, not a series (#37).
    return {
        k: np.asarray(v, dtype=float)
        for k, v in out.items()
        if not k.endswith(".parameter_fingerprint")
    }


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

    The sliding GWI and sliding GTP are the exception by design: an emission in
    year k is counted to the fixed year H, so its horizon is H - k, and a delay
    shortens it. They are checked separately in ``test_time_shift_sliding``.
    """
    e, s = es
    n = len(e["co2"])
    p = PARAMS[set_name]
    run = lambda x: outputs(x, p, fossil_ch4=fossil_ch4, horizon=h)  # noqa: E731
    late, early, bound = run(delay(e, s)), run(e), run(absolute(e))
    for out in (late, early, bound):
        del out["gwi.sliding"], out["gtp.sliding"]
    assert_close(
        {k: v[..., s:] for k, v in late.items()},
        {k: v[..., : n - s] for k, v in early.items()},
        bound,
    )


def absolute_sliding(e, params, *, fossil_ch4: bool, horizon: float) -> dict[str, np.ndarray]:
    """Sliding GWI and GTP times their CO2 normalisation (AGWP_H, AGTP_H)."""
    e = as_fossil(e, fossil_ch4)
    g = gwi(e, params, horizon=horizon)
    p = gtp(e, params, horizon=horizon)
    return {"gwi.sliding": g.sliding * g.agwp_co2, "gtp.sliding": p.sliding * p.agtp_co2}


@both_sets
@both_ch4_modes
@SETTINGS
@given(es=profile_and_shift(), h=horizon)
def test_time_shift_sliding(set_name, fossil_ch4, es, h):
    """Sliding GWI and GTP: a delay of s years under H equals no delay under H - s.

    In absolute terms (times AGWP_H or AGTP_H of CO2), since the normalisation
    differs.
    """
    e, s = es
    if h - s <= 0:
        h = s + 1.0
    n = len(e["co2"])
    run = lambda x, horizon: absolute_sliding(  # noqa: E731
        x, PARAMS[set_name], fossil_ch4=fossil_ch4, horizon=horizon
    )
    late = run(delay(e, s), h)
    early = run(e, h - s)
    for name, out in late.items():
        assert np.all(out[:s] == 0.0), name
    assert_close(
        {k: v[s:] for k, v in late.items()},
        {k: v[: n - s] for k, v in early.items()},
        run(absolute(e), h - s),
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
    output. Integrated forcing (from year 0 to the start of year t), the CO2
    formed from fossil CH4 (removed during year t), and the temperature and
    dynamic GTP (at the start of year t, before that year's forcing acts) are
    also exactly zero at year k.
    """
    e, k = ek
    after_a_year = ("_integrated", "ch4_to_co2", "temperature.", "gtp.dynamic")
    for name, out in outputs(e, PARAMS[set_name], fossil_ch4=fossil_ch4, horizon=h).items():
        zero_to = k + 1 if any(tag in name for tag in after_a_year) else k
        assert np.all(out[..., :zero_to] == 0.0), name


@st.composite
def pulse(draw):
    """One gas, n years, a pulse of m kg (either sign) in year k, zero elsewhere."""
    n = draw(st.integers(1, MAX_YEARS))
    k = draw(st.integers(0, n - 1))
    m = draw(signed(1e-6, 1e6).filter(lambda v: v != 0.0))
    return draw(st.sampled_from(GASES)), n, k, m


@both_sets
@SETTINGS
@given(pkm=pulse())
def test_temperature_of_pulse_in_any_year_equals_agtp(set_name, pkm):
    """A pulse of m kg in year k gives temperature() == m * agtp(gas, t - k), all years.

    The analytic test checks this for a 1 kg pulse in year 0 only. Here the
    pulse can be in any year, of any size and sign, and the other two gases
    must stay exactly zero. Before year k, agtp() is not defined (negative
    horizon) and the temperature must be exactly zero; at year k,
    ``agtp(gas, 0)`` and the temperature must both be exactly zero.
    """
    gas, n, k, m = pkm
    # Without CCF (C6 on #33): with it, CH4 and N2O also warm through CO2.
    p = NO_CCF[set_name]
    e = {gas: np.r_[np.zeros(k), m, np.zeros(n - k - 1)]}
    t = temperature(burden(e, p), p)
    expected = m * agtp(gas, np.arange(n - k, dtype=float), p)
    assert agtp(gas, 0.0, p) == 0.0
    assert np.all(getattr(t, gas)[: k + 1] == 0.0)
    for other in set(GASES) - {gas}:
        assert np.all(getattr(t, other) == 0.0), other
    atol = RTOL * float(np.max(np.abs(expected)))
    np.testing.assert_allclose(getattr(t, gas)[k:], expected, rtol=0, atol=atol)
