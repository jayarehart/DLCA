"""Carbon-cycle feedback (CCF) for CH4 and N2O (issue #33, decisions C1-C8).

Independent check (decision C2): the IPCC Chapter-7 code (``ar6.metrics.gasser``,
commit 2f948c8, FaIR 1.6.2), run at dt = 0.02 and 0.01 yr and
Richardson-extrapolated to dt -> 0, gives the AR6 AGWP and AGTP with CCF stored
in the ``*_ccf`` checks of ``ar6.json`` (``scripts/check_ar6_against_ipcc_code.py``).
They come from code outside DLCA, not from ``agwp()``/``agtp()``. They are stored
in full and compared at 1e-5 relative (tolerance approved by Jay on 2026-11-19,
PR #48); the closed form agrees with them to 4.8e-6 or better, about a quarter
of the spread between two Richardson estimates. At this tolerance a +0.1% error
in gamma fails all eight checks.

The printed Table 7.SM.7 values (CH4 GWP100 27.9, N2O 273) come from the same
code at dt = 0.1 yr, whose CCF term carries a 10-30% step-size error. DLCA's exact
values (28.02, 274.4) do not round to them; that test is xfail(strict=True)
(decision C2).

Faults these catch that no other test does:

- the CCF left out, its sign flipped, gamma read as kg CO2 instead of kg C, or a
  wrong weight or time constant (``test_ar6_closed_form_matches_ipcc_code``);
- the CCF CO2 added a year late in ``burden()``, the left rule instead of the
  trapezoid, or the CCF counted twice in the sliding GWI
  (``test_pulse_dynamic_and_sliding_close_to_closed_form``); a year early
  (``test_ccf_co2_is_zero_in_pulse_year_and_shifts_with_the_pulse``);
- CO2, the CO2 from fossil CH4 or the CCF CO2 itself driving a CCF
  (``test_co2_drives_no_ccf``, ``test_ccf_cancels_in_fossil_minus_non_fossil``);
- CCF applied when the switch is off (``test_off_switch_gives_no_ccf``).
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from dlca.climate import agtp, agwp, burden, gtp, gwi
from dlca.parameters import get_parameters, load_document

AR6 = get_parameters("AR6")
AR6_NO_CCF = dataclasses.replace(AR6, carbon_cycle_feedback=False)
CHECKS = {k: v["value"] for k, v in load_document("AR6")["checks"].items()}
# Relative tolerance of the IPCC-code CCF checks (Jay, 2026-11-19, PR #48).
CCF_CHECK_RTOL = 1e-5


def half_unit(printed: float, digits: int = 5) -> float:
    """Half a unit in the last of ``digits`` significant figures of ``printed``."""
    exponent = int(np.floor(np.log10(abs(printed))))
    return 0.5 * 10.0 ** (exponent - digits + 1)


def pulse(key: str, n: int = 201, at: int = 0) -> dict[str, np.ndarray]:
    e = np.zeros(n)
    e[at] = 1.0
    return {key: e}


@pytest.mark.parametrize("gas", ["ch4", "n2o"])
@pytest.mark.parametrize("metric", ["agwp", "agtp"])
@pytest.mark.parametrize("horizon", [20, 100])
def test_ar6_closed_form_matches_ipcc_code(gas, metric, horizon):
    """agwp()/agtp() with CCF equal the IPCC code taken to dt -> 0 (1e-5 relative)."""
    expected = CHECKS[f"{metric}{horizon}_{gas}_ccf"]
    got = {"agwp": agwp, "agtp": agtp}[metric](gas, horizon, AR6)
    np.testing.assert_allclose(got, expected, rtol=CCF_CHECK_RTOL, atol=0)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Decision C2 on #33: the printed 27.9 / 273 carry the IPCC code's dt = 0.1 yr "
        "step-size error in the CCF term; DLCA computes the CCF exactly (28.02 / 274.4)."
    ),
)
@pytest.mark.parametrize(("gas", "digits"), [("ch4", 1), ("n2o", 0)])
def test_ar6_gwp100_with_ccf_matches_table_7sm7(gas, digits):
    gwp = agwp(gas, 100, AR6) / agwp("co2", 100, AR6)
    assert round(gwp, digits) == CHECKS[f"gwp100_{gas}_ccf_published"]


def test_ccf_adds_the_expected_amount_positive_control():
    """With CCF, CH4 GWP100 moves from 26.37 to 28.02 (values measured in the
    #33 proposal); the closed-form check above would see a dropped CCF term."""
    ref = agwp("co2", 100, AR6)
    assert round(agwp("ch4", 100, AR6_NO_CCF) / ref, 2) == 26.37
    assert round(agwp("ch4", 100, AR6) / ref, 2) == 28.02


@pytest.mark.parametrize("gas", ["ch4", "n2o"])
@pytest.mark.parametrize("horizon", [20, 100])
def test_pulse_dynamic_and_sliding_close_to_closed_form(gas, horizon):
    """Whole-year CCF (trapezoid, C4) against the closed form, for a 1 kg pulse.

    Measured worst case 8.2e-4 (N2O GWP20); the bound is 1e-3 (approved by Jay on
    2026-11-19, PR #48). Deliberate-mistake
    runs on #33: the CCF CO2 a year late, the left rule, a dropped whole-year CCF,
    or the CCF also in the sliding CH4 term all fail here. (A year early passes
    here; the time-shift tests catch it.) The sliding GWI and GTP must equal the
    dynamic values at the horizon (CCF CO2 counted as CO2 emitted the year it
    forms, C4).
    """
    e = pulse(gas)
    w = gwi(e, AR6, horizon=horizon)
    t = gtp(e, AR6, horizon=horizon)
    gwp = agwp(gas, horizon, AR6) / agwp("co2", horizon, AR6)
    gtp_h = agtp(gas, horizon, AR6) / agtp("co2", horizon, AR6)
    np.testing.assert_allclose(w.dynamic[horizon], gwp, rtol=1e-3)
    np.testing.assert_allclose(t.dynamic[horizon], gtp_h, rtol=1e-3)
    np.testing.assert_allclose(w.sliding[-1], w.dynamic[horizon], rtol=1e-12)
    np.testing.assert_allclose(t.sliding[-1], t.dynamic[horizon], rtol=1e-12)
    # Static uses the closed form (C4), exactly.
    np.testing.assert_allclose(w.static[-1], gwp, rtol=1e-12)
    np.testing.assert_allclose(t.static[-1], gtp_h, rtol=1e-12)


def test_ccf_co2_is_zero_in_pulse_year_and_shifts_with_the_pulse():
    """The first CCF CO2 comes the year after the pulse, and a later pulse gives
    the same series shifted (the CCF is time-invariant)."""
    early = burden(pulse("ch4", 120), AR6).ccf_co2
    late = burden(pulse("ch4", 120, at=15), AR6).ccf_co2
    assert early[0] == 0.0 and early[1] > 0.0
    assert not np.any(late[:16])
    np.testing.assert_allclose(late[15:], early[:-15], rtol=1e-12, atol=0)


def test_co2_drives_no_ccf():
    """CO2 emissions give the same burden with CCF on and off (the Joos IRF already
    holds CO2's own feedback); positive control: CH4 does not."""
    co2 = {"co2": np.linspace(1.0, -0.5, 80)}
    on, off = burden(co2, AR6), burden(co2, AR6_NO_CCF)
    assert not np.any(on.ccf_co2)
    np.testing.assert_array_equal(on.co2_pools, off.co2_pools)
    ch4 = {"ch4": np.linspace(1.0, -0.5, 80)}
    assert np.any(burden(ch4, AR6).ccf_co2 != 0.0)
    assert not np.array_equal(burden(ch4, AR6).co2, burden(ch4, AR6_NO_CCF).co2)


@pytest.mark.parametrize("horizon", [20, 100])
def test_ccf_cancels_in_fossil_minus_non_fossil(horizon):
    """Decision C8: fossil minus non-fossil CH4 is the oxidised CO2 alone, with or
    without CCF, because the oxidised CO2 drives no CCF. Positive control: the same
    comparison on non-fossil CH4 alone moves by the CCF (1.65 at GWP100)."""
    ref = agwp("co2", horizon, AR6)

    def gap(p):
        return (agwp("ch4_fossil", horizon, p) - agwp("ch4", horizon, p)) / ref

    np.testing.assert_allclose(gap(AR6), gap(AR6_NO_CCF), rtol=1e-12)
    e = {"ch4_fossil": pulse("ch4_fossil")["ch4_fossil"]}
    np.testing.assert_allclose(
        burden(e, AR6).ccf_co2, burden(pulse("ch4"), AR6).ccf_co2, rtol=1e-12, atol=0
    )
    shift = (agwp("ch4", horizon, AR6) - agwp("ch4", horizon, AR6_NO_CCF)) / ref
    assert shift > 1.0


def test_off_switch_gives_no_ccf():
    """With carbon_cycle_feedback False, ccf_co2 is zero and agwp()/agtp() equal
    the IPCC code without CCF (the M1 checks, 6 sig. fig.). Positive control: with
    the switch on, the same comparison fails."""
    rng = np.random.default_rng(33)
    e = {key: rng.uniform(-1.0, 1.0, 60) for key in ("co2", "ch4", "n2o")}
    assert not np.any(burden(e, AR6_NO_CCF).ccf_co2)
    assert np.any(burden(e, AR6).ccf_co2)
    for gas in ("ch4", "n2o"):
        for metric, f in (("agwp", agwp), ("agtp", agtp)):
            expected = CHECKS[f"{metric}100_{gas}"]
            assert abs(f(gas, 100, AR6_NO_CCF) - expected) <= half_unit(expected, 6)
            assert abs(f(gas, 100, AR6) - expected) > half_unit(expected, 6)


def test_ar5_refuses_ccf():
    """Decision C1: AR5 has no CCF formulation in DLCA."""
    with pytest.raises(ValueError, match="no carbon-cycle feedback values"):
        dataclasses.replace(get_parameters("AR5"), carbon_cycle_feedback=True)


@pytest.mark.parametrize(
    "change",
    [
        {"ccf_gamma": None},
        {"ccf_weights": (0.6, 0.3, 0.2)},
        {"ccf_timescales": (2.0, 0.0, 400.0)},
        {"ccf_gamma": -1.0},
        {"molar_mass_c": 0.0},
        {"ccf_weights": (0.5, 0.5)},
    ],
)
def test_bad_ccf_values_rejected(change):
    with pytest.raises(ValueError):
        dataclasses.replace(AR6, **change)


def test_ccf_values_without_the_switch_are_kept_and_fingerprinted():
    """Turning CCF off keeps the values but changes the fingerprint, so the #37
    guard tells the two sets apart."""
    assert AR6_NO_CCF.ccf_gamma == AR6.ccf_gamma
    assert AR6_NO_CCF.fingerprint() != AR6.fingerprint()
