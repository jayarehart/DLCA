"""dlca.assess() against published IPCC values (issue #31, independent check).

The same printed values as ``test_agwp.py`` and ``test_agtp.py``, typed from the
IPCC tables (not read from dlca or the parameter files), but reached through the
public entry point: 1 kg pulses go into ``assess()`` and the result's own series
are compared with the tables.

- AR5 WG1 Ch. 8, Table 8.A.1 (Myhre et al. 2013, p. 731), no carbon-cycle
  feedback: AGWP20/100 and AGTP20/100 of CO2; AGWP100 and AGTP100 of CH4 and
  N2O; GWP20/100 of CH4 and N2O; GWP100 of fossil CH4 (30).
- AR6 WG1 Ch. 7, Table 7.SM.7: AGWP100(CO2) = 8.95e-14, AGTP100(CO2) = 3.95e-16.

Tolerance: half a unit in the last printed digit (decision D4 on #28).

Faults these catch that no other test does: ``assess()`` using a parameter set
other than the one asked for (or not AR6 by default), and ``assess()`` passing
the wrong horizon to ``gwi()`` or ``gtp()``. The function-level tests call
``agwp()``/``agtp()`` directly and cannot see either.
"""

import numpy as np
import pytest

import dlca

YEARS = 201


def assert_matches_table(got: float, printed: str) -> None:
    mantissa, _, exponent = printed.lower().partition("e")
    tol = 0.5 * 10.0 ** (-len(mantissa.partition(".")[2])) * 10.0 ** int(exponent or 0)
    want = float(printed)
    assert abs(got - want) <= tol, f"got {got!r}, table {printed} +/- {tol:g}"


def pulse(key: str) -> dict[str, np.ndarray]:
    return {key: np.r_[1.0, np.zeros(YEARS - 1)]}


# (gas, H, printed AGWP_H [W m-2 yr kg-1], printed AGTP_H [K kg-1]), AR5 Table 8.A.1.
AR5_ABSOLUTE = [
    ("co2", 20, "2.49e-14", "6.84e-16"),
    ("co2", 100, "9.17e-14", "5.47e-16"),
    ("ch4", 100, "2.61e-12", "2.34e-15"),
    ("n2o", 100, "2.43e-11", "1.28e-13"),
]

# (emissions key, H, printed GWP_H), AR5 Table 8.A.1, no carbon-cycle feedback.
AR5_GWP = [
    ("ch4", 20, "84"),
    ("ch4", 100, "28"),
    ("n2o", 20, "264"),
    ("n2o", 100, "265"),
    ("ch4_fossil", 100, "30"),
]


@pytest.mark.parametrize(("gas", "horizon", "agwp_printed", "agtp_printed"), AR5_ABSOLUTE)
def test_ar5_pulse_through_assess_matches_table_8a1(gas, horizon, agwp_printed, agtp_printed):
    """Integrated forcing and temperature H years after a 1 kg pulse are AGWP_H, AGTP_H."""
    r = dlca.assess(pulse(gas), parameters="AR5", horizon=horizon)
    assert r.parameter_set == "AR5"
    assert_matches_table(r.forcing.total_integrated[horizon], agwp_printed)
    assert_matches_table(r.temperature.total[horizon], agtp_printed)


@pytest.mark.parametrize(("key", "horizon", "printed"), AR5_GWP)
def test_ar5_gwp_through_assess_matches_table_8a1(key, horizon, printed):
    """For a 1 kg pulse, the dynamic GWI at year H is GWP_H."""
    r = dlca.assess(pulse(key), parameters="AR5", horizon=horizon)
    assert_matches_table(r.gwi.dynamic[horizon], printed)


@pytest.mark.parametrize("horizon", [20, 100])
def test_ar5_normalisation_uses_the_given_horizon(horizon):
    """gwi() and gtp() inside assess() both get H: their CO2 references are the table's."""
    agwp_co2 = {20: "2.49e-14", 100: "9.17e-14"}[horizon]
    agtp_co2 = {20: "6.84e-16", 100: "5.47e-16"}[horizon]
    r = dlca.assess(pulse("co2"), parameters="AR5", horizon=horizon)
    assert r.horizon == r.gwi.horizon == r.gtp.horizon == r.static_gwp.horizon == horizon
    assert_matches_table(r.gwi.agwp_co2, agwp_co2)
    assert_matches_table(r.gtp.agtp_co2, agtp_co2)


@pytest.mark.parametrize("parameters", ["AR6", "ar6", None])
def test_ar6_pulse_through_assess_matches_table_7sm7(parameters):
    """AR6 by name, case-insensitive, and as the default (record 0002)."""
    kwargs = {} if parameters is None else {"parameters": parameters}
    r = dlca.assess(pulse("co2"), horizon=100, **kwargs)
    assert r.parameter_set == "AR6"
    assert_matches_table(r.forcing.total_integrated[100], "8.95e-14")
    assert_matches_table(r.temperature.total[100], "3.95e-16")
    assert_matches_table(r.gwi.agwp_co2, "8.95e-14")
    assert_matches_table(r.gtp.agtp_co2, "3.95e-16")
