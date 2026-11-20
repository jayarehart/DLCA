"""Static GWP and GTP, fossil and non-fossil CH4, and the ch4_fossil key (issue #30).

Independent check: the expected values are typed from AR5 WG1 Chapter 8, Table
8.A.1 (Myhre et al. 2013, p. 731), no carbon-cycle feedback, not read from dlca
or from the parameter JSON files:

- CH4 (non-fossil): GWP20 84, GWP100 28, GTP20 67, GTP100 4.
- Fossil CH4 (footnote: 50% of the carbon becomes CO2): GWP20 85, GWP100 30,
  GTP20 68, GTP100 6.

Tolerance (decision D4 on #28): half a unit in the last printed digit. The AR6
Table 7.15 values include a carbon-cycle feedback, which the AR6 set now has
(#33); its checks are in test_ccf.py (decision S7 on #30). AR6 is covered here
only by the closed-form-against-quadrature test.

Faults these catch that no other test does: the oxidised CO2 left out of the
fossil static factor, or added to non-fossil CH4; the whole-year route used for
the static factor instead of the closed form (fails GWP20 = 85); a wrong yield
in the static factor (GTP20); an algebra slip in the closed forms of
``agwp("ch4_fossil")`` or ``agtp("ch4_fossil")`` in either set; the
``ch4_fossil`` key dropped from any of burden(), gwi() or gtp() when it is given
together with ``ch4``; and ``StaticGWP`` series or ``GWI.static`` not matching
cumulative emissions times the factors.
"""

import dataclasses
import json

import numpy as np
import pytest

from dlca.climate import (
    EMISSION_KEYS,
    StaticGWP,
    agtp,
    agwp,
    burden,
    gtp,
    gwi,
    specific_forcing,
    static_gwp,
)
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


def pulse(key: str, n: int = 201) -> dict[str, np.ndarray]:
    return {key: np.r_[1.0, np.zeros(n - 1)]}


# (key, horizon, printed value) from AR5 Table 8.A.1, no carbon-cycle feedback.
AR5_STATIC_GWP = [
    ("ch4", 20, "84"),
    ("ch4", 100, "28"),
    ("ch4_fossil", 20, "85"),
    ("ch4_fossil", 100, "30"),
]
AR5_STATIC_GTP = [
    ("ch4", 20, "67"),
    ("ch4", 100, "4"),
    ("ch4_fossil", 20, "68"),
    ("ch4_fossil", 100, "6"),
]


@pytest.mark.parametrize(("key", "horizon", "printed"), AR5_STATIC_GWP)
def test_ar5_static_gwp_matches_table_8a1(key, horizon, printed):
    """1 kg of CH4 at year 0. Under the whole-year route fossil GWP20 would be 84.49."""
    p = get_parameters("AR5")
    result = static_gwp(pulse(key), p, horizon=horizon)
    assert_matches_table(result.gwp[key], printed)
    assert_matches_table(result.total[-1], printed)
    assert_matches_table(gwi(pulse(key), p, horizon=horizon).static[-1], printed)


@pytest.mark.parametrize(("key", "horizon", "printed"), AR5_STATIC_GTP)
def test_ar5_static_gtp_matches_table_8a1(key, horizon, printed):
    """gtp().static now counts the oxidised CO2 of fossil CH4 (S3, replacing T3 on #29)."""
    p = get_parameters("AR5")
    assert_matches_table(gtp(pulse(key), p, horizon=horizon).static[-1], printed)


def _quadrature(metric, params, horizon: float) -> float:
    """metric("ch4", H) + Y 44/16 int_0^H (1/tau) e^(-t/tau) metric("co2", H-t) dt, by trapezoid."""
    tau = params.ch4_lifetime
    t = np.linspace(0.0, horizon, 400_001)
    ox = np.trapezoid(np.exp(-t / tau) / tau * metric("co2", horizon - t, params), t)
    return metric("ch4", horizon, params) + params.fossil_ch4_co2_yield() * 44 / 16 * ox


@pytest.mark.parametrize("name", ["AR5", "AR6"])
@pytest.mark.parametrize("metric", [agwp, agtp], ids=["agwp", "agtp"])
@pytest.mark.parametrize("horizon", [1.0, 20.0, 100.0, 500.0])
def test_fossil_closed_form_equals_quadrature(name, metric, horizon):
    """Not independent (both are dlca), but the quadrature shares only the CO2
    response: catches an algebra slip in either closed form, in AR6 too."""
    p = get_parameters(name)
    np.testing.assert_allclose(
        metric("ch4_fossil", horizon, p), _quadrature(metric, p, horizon), rtol=1e-8
    )


@pytest.mark.parametrize("name", ["AR5", "AR6"])
def test_fossil_static_close_to_sliding(name):
    """Decision S2-A: for a fossil pulse, static (closed form) and sliding (whole
    years) differ only by the whole-year timing of the oxidised CO2: measured
    0.019% to 0.050% (AR6, H = 20); this bounds it at 0.1%. For non-fossil CH4
    they agree to rounding. Without CCF (C6 on #33): the CCF adds its own
    whole-year timing, tested in test_ccf.py."""
    p = dataclasses.replace(get_parameters(name), carbon_cycle_feedback=False)
    for horizon in (20, 100):
        fossil = gwi(pulse("ch4_fossil"), p, horizon=horizon)
        np.testing.assert_allclose(fossil.static[-1], fossil.sliding[-1], rtol=1e-3)
        bio = gwi(pulse("ch4"), p, horizon=horizon)
        np.testing.assert_allclose(bio.static[-1], bio.sliding[-1], rtol=1e-12)


def test_fossil_and_non_fossil_same_without_ch4_positive_control():
    """With no CH4, labelling CH4 fossil or not changes nothing; with CH4 the same
    comparison separates them (positive control, AGENTS.md rule 3)."""
    p = get_parameters("AR5")
    rng = np.random.default_rng(30)
    base = {"co2": rng.uniform(-1.0, 1.0, 150), "n2o": rng.uniform(0.0, 0.01, 150)}
    zero = np.zeros(150)
    for ch4 in (zero, rng.uniform(0.0, 1.0, 150)):
        bio = gwi(base | {"ch4": ch4}, p).static
        fos = gwi(base | {"ch4_fossil": ch4}, p).static
        if ch4 is zero:
            np.testing.assert_array_equal(bio, fos)
        else:
            # Fossil adds about 1.24 kg CO2e per kg CH4 at GWP100 (29.69 vs 28.46).
            gap = (agwp("ch4_fossil", 100, p) - agwp("ch4", 100, p)) / agwp("co2", 100, p)
            np.testing.assert_allclose(fos[-1] - bio[-1], gap * ch4.sum(), rtol=1e-9)
            assert gap > 1.2


def test_one_call_equals_two_calls():
    """S4: fossil and non-fossil CH4 in one call equal the sum of separate calls,
    for every output of burden(), gwi(), gtp() and static_gwp()."""
    p = get_parameters("AR6")
    rng = np.random.default_rng(31)
    bio = {"ch4": rng.uniform(-1.0, 1.0, 120)}
    fos = {"ch4_fossil": rng.uniform(-1.0, 1.0, 120)}
    both = bio | fos

    def flat(e):
        b, g, t, s = burden(e, p), gwi(e, p, horizon=50), gtp(e, p, horizon=50), static_gwp(e, p)
        out = {
            f"burden.{k}": np.asarray(v)
            for k, v in b.to_dict().items()
            if k != "parameter_fingerprint"  # a string, not a series (#37)
        }
        out |= {f"gwi.{k}": getattr(g, k) for k in ("dynamic", "sliding", "static")}
        out |= {f"gtp.{k}": getattr(t, k) for k in ("dynamic", "sliding", "static")}
        out |= {f"static.{k}": getattr(s, k) for k in EMISSION_KEYS}
        return out

    one, a, b = flat(both), flat(bio), flat(fos)
    for name in one:
        scale = np.max(np.abs(a[name]) + np.abs(b[name]), initial=0.0)
        np.testing.assert_allclose(one[name], a[name] + b[name], rtol=0, atol=1e-12 * scale)
    # The fossil part is oxidised, the non-fossil part is not.
    assert not np.any(burden(bio, p).ch4_to_co2)
    assert np.any(burden(fos, p).ch4_to_co2)


def test_static_gwp_series_by_key():
    """Each StaticGWP series is cumsum(E) times its factor; total sums the keys."""
    p = get_parameters("AR5")
    rng = np.random.default_rng(32)
    e = {key: rng.uniform(-1.0, 1.0, 60) for key in EMISSION_KEYS}
    s = static_gwp(e, p, horizon=100)
    assert isinstance(s, StaticGWP) and s.horizon == 100.0
    assert s.gwp["co2"] == 1.0
    for key in EMISSION_KEYS:
        np.testing.assert_allclose(getattr(s, key), np.cumsum(e[key]) * s.gwp[key], rtol=1e-15)
    np.testing.assert_allclose(s.total, sum(getattr(s, k) for k in EMISSION_KEYS), rtol=1e-15)
    np.testing.assert_array_equal(gwi(e, p, horizon=100).static, s.total)
    d = json.loads(json.dumps(s.to_dict()))
    assert set(d) == {*EMISSION_KEYS, "horizon", "gwp", "parameter_fingerprint"}  # #46


def test_set_without_yield():
    """A set with no fossil CH4 yield works without fossil CH4 and refuses it otherwise."""
    p = dataclasses.replace(get_parameters("AR6"), ch4_fossil_co2_yield=None)
    s = static_gwp({"ch4": [1.0, 0.0]}, p)
    assert "ch4_fossil" not in s.gwp
    np.testing.assert_array_equal(s.ch4_fossil, 0.0)
    gtp({"ch4": [1.0, 0.0]}, p)
    for call in (static_gwp, gwi, gtp):
        with pytest.raises(ValueError, match="fossil CH4"):
            call({"ch4_fossil": [1.0, 0.0]}, p)


def test_non_fossil_input_ignores_fossil_closed_form_limits():
    """A CH4 lifetime equal to a CO2 pool time breaks only the fossil closed form:
    non-fossil input still works in gwi(), gtp() and static_gwp(); fossil input raises.
    (Found in the fresh-session review of #30.)"""
    p = get_parameters("AR5")
    bad = dataclasses.replace(p, ch4_lifetime=p.co2_tau[2])
    e = {"co2": [1.0, 0.0], "ch4": [1.0, 0.0]}
    for call in (static_gwp, gwi, gtp):
        call(e, bad)
    assert "ch4_fossil" not in static_gwp(e, bad).gwp
    with pytest.raises(ValueError, match="fossil CH4 closed form"):
        static_gwp({"ch4_fossil": [1.0, 0.0]}, bad)


@pytest.mark.parametrize(
    ("call", "match"),
    [
        (lambda p: static_gwp({"ch4_bio": [1.0]}, p), "unknown emissions key"),
        (lambda p: static_gwp({"co2": [1.0]}, p, horizon=0), "horizon"),
        (lambda p: specific_forcing("ch4_fossil", p), "unknown gas"),
        (lambda p: agwp("ch4_fossil", -1, p), "horizon"),
    ],
)
def test_bad_input_raises(call, match):
    with pytest.raises(ValueError, match=match):
        call(get_parameters("AR5"))
