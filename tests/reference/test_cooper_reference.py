"""Characterization tests: dlca.assess() against the Cooper et al. (2020) spreadsheet.

Each case in ``cases/`` holds the inflows (``inputs.csv``), the settings
(``settings.csv``) and the spreadsheet's recalculated results
(``expected.csv``), produced by ``generate_cases.py``. See ``README.md`` for
the citation, attribution and column provenance.

The spreadsheet is an independent implementation of the same AR5 model, so
these tests check the *port*, not the physics. Known disagreements are marked
``xfail(strict=True)`` with the suspected cause; they are fixed in M1, not
here. Never edit the expected values or the tolerances to make a test pass.
"""

from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import dlca
from dlca import engine as DLCA
from dlca.climate import agwp
from dlca.parameters import get_parameters

CASES_DIR = Path(__file__).parent / "cases"
CASES = sorted(p.name for p in CASES_DIR.iterdir() if (p / "expected.csv").exists())

RTOL = 1e-9
# atol is scaled to each column: RTOL times the largest |expected| value in it,
# so values far below the column's magnitude (for example near-zero tails) do
# not demand more relative precision than the spreadsheet carries.

# The second check (test_engine_matches_spreadsheet_where_nonzero) uses rtol only,
# atol=0, on every year where the expected value is not zero (Jay's decision on
# PR #24, 2026-11-17).

# expected.csv column -> the same series in a dlca.Result (issue #31). The
# cumulative net emissions are the running sums of the inputs the result holds;
# CH4 counts both keys.
COLUMNS = {
    "CO2_mass": lambda r: r.burden.co2,
    "CH4_mass": lambda r: r.burden.ch4,
    "N2O_mass": lambda r: r.burden.n2o,
    "CO2_mass0": lambda r: r.burden.co2_pools[0],
    "CO2_mass1": lambda r: r.burden.co2_pools[1],
    "CO2_mass2": lambda r: r.burden.co2_pools[2],
    "CO2_mass3": lambda r: r.burden.co2_pools[3],
    "CH4_to_CO2": lambda r: r.burden.ch4_to_co2,
    "CO2_radfor": lambda r: r.forcing.co2,
    "CH4_radfor": lambda r: r.forcing.ch4,
    "N2O_radfor": lambda r: r.forcing.n2o,
    "CO2_IRF": lambda r: r.forcing.co2_integrated,
    "CH4_IRF": lambda r: r.forcing.ch4_integrated,
    "N2O_IRF": lambda r: r.forcing.n2o_integrated,
    "IRF_all": lambda r: r.forcing.total_integrated,
    "CO2_temp": lambda r: r.temperature.co2,
    "CH4_temp": lambda r: r.temperature.ch4,
    "N2O_temp": lambda r: r.temperature.n2o,
    "temp_change": lambda r: r.temperature.total,
    "CO2_net": lambda r: np.cumsum(r.emissions["co2"]),
    "CH4_net": lambda r: np.cumsum(r.emissions["ch4"] + r.emissions["ch4_fossil"]),
    "N2O_net": lambda r: np.cumsum(r.emissions["n2o"]),
    "IRF_over_AGWP_CO2": lambda r: r.gwi.dynamic,
    "GWP_static_CO2e": lambda r: r.gwi.static,
    "GWP_sliding_CO2e": lambda r: r.gwi.sliding,
    "GTP_static_CO2e": lambda r: r.gtp.static,
    "temp_over_AGTP_CO2": lambda r: r.gtp.dynamic,
    "GTP_sliding_CO2e": lambda r: r.gtp.sliding,
}

# The spreadsheet holds AR5 values only (README "Parameter set"), so every case
# must say AR5. Checked by test_every_case_is_ar5 (Jay, #31 comment of 2026-11-18).
SPREADSHEET_PARAMETER_SET = "AR5"

# (case, column) pairs where dlca.climate disagrees with the spreadsheet on purpose.
KNOWN_DIFFERENCES = {
    ("ch4_pulse_fossil", "GWP_sliding_CO2e"): (
        "Decision D2 on #28: gwi().sliding counts the CO2 formed from fossil CH4. The "
        "spreadsheet's sliding GWP uses its pasted CH4 AGWP table, which leaves the "
        "oxidised CO2 out, so it is 28.456 at every year while its own LCA_dyn[100] is "
        "29.687. Measured: up to 4.3% higher than the spreadsheet (29.687 from year 100)."
    ),
    ("ch4_pulse_fossil", "GWP_static_CO2e"): (
        "Decision S3 on #30: static GWP counts the CO2 formed from fossil CH4, by "
        "the closed form of AR5 Table 8.A.1 (GWP100 = 30). The spreadsheet's static "
        "GWP uses the CH4-only GWP100 (28.456). Measured: 29.693, 4.3% higher than "
        "the spreadsheet at every year."
    ),
    ("ch4_pulse_fossil", "GTP_static_CO2e"): (
        "Decision S3 on #30 (replacing T3 on #29): static GTP counts the CO2 formed "
        "from fossil CH4, by the closed form of AR5 Table 8.A.1 (GTP100 = 6). The "
        "spreadsheet's static GTP uses the CH4-only GTP100 (4.270). Measured: 5.674, "
        "33% higher than the spreadsheet at every year."
    ),
    ("ch4_pulse_fossil", "GTP_sliding_CO2e"): (
        "Decision T2 on #29: gtp().sliding counts the CO2 formed from fossil CH4. The "
        "spreadsheet's sliding GTP uses its pasted CH4 AGTP table, which leaves the "
        "oxidised CO2 out, so it is 4.270 at every year while its own "
        "temp_over_AGTP_CO2[100] is 5.676. Measured: up to 33% higher than the "
        "spreadsheet (5.676 from year 100)."
    ),
}


@cache
def load_case(case):
    d = CASES_DIR / case
    inputs = pd.read_csv(d / "inputs.csv")
    expected = pd.read_csv(d / "expected.csv")
    settings = dict(pd.read_csv(d / "settings.csv", dtype=str).values)
    return inputs, expected, settings


@cache
def run_case(case):
    """The case through dlca.assess(), with the case's own parameter set and horizon."""
    inputs, _, settings = load_case(case)
    # The fossil_CH4 setting puts the case's CH4 under the ch4_fossil key (#30, S4).
    fossil = {"TRUE": True, "FALSE": False}[settings["fossil_CH4"]]
    ch4_key = "ch4_fossil" if fossil else "ch4"
    emissions = {
        "co2": inputs["CO2_flux"].to_numpy(),
        ch4_key: inputs["CH4_flux"].to_numpy(),
        "n2o": inputs["N2O_flux"].to_numpy(),
    }
    # No default: a case without a parameter_set row raises KeyError.
    result = dlca.assess(
        emissions,
        parameters=settings["parameter_set"],
        horizon=int(settings["time_horizon"]),
    )
    assert result.parameter_set == settings["parameter_set"]
    return result


def _params():
    for case in CASES:
        for col in COLUMNS:
            reason = KNOWN_DIFFERENCES.get((case, col))
            marks = [pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason)]
            yield pytest.param(case, col, id=f"{case}-{col}", marks=marks if reason else [])


def test_cases_present():
    assert CASES == sorted(
        [
            "building_lifecycle",
            "ch4_pulse_biogenic",
            "ch4_pulse_fossil",
            "co2_pulse",
            "late_pulse",
            "n2o_pulse",
            "negative_uptake",
        ]
    )


@pytest.mark.parametrize("case", CASES)
def test_every_case_is_ar5(case):
    """Each case names its parameter set, and it is the spreadsheet's (AR5)."""
    _, _, settings = load_case(case)
    assert settings["parameter_set"] == SPREADSHEET_PARAMETER_SET


def test_reference_uses_corrected_agtp():
    """The reference must be generated with the AGTP p_1->p_3 correction.

    By definition, AGTP_100(CO2) is the temperature change 100 years after a
    1 kg CO2 pulse, so for co2_pulse both ratios below are exactly 1. With the
    uncorrected spreadsheet (intro!E50 using p_1 for the third pool) they are
    1.000599 instead.
    """
    _, expected, _ = load_case("co2_pulse")
    np.testing.assert_allclose(expected["temp_over_AGTP_CO2"][100], 1.0, rtol=RTOL)
    np.testing.assert_allclose(expected["GTP_sliding_CO2e"][0], 1.0, rtol=RTOL)


def test_reference_uses_corrected_ch4_tables():
    """The reference must be generated with the CH4 table correction (16.05 g/mol).

    For a 1 kg CH4 pulse at year 0, year 0 of the sliding GWP and GTP is
    AGWP_100(CH4) / AGWP_100(CO2) and AGTP_100(CH4) / AGTP_100(CO2). The
    spreadsheet's own results give each AGWP and AGTP: the year-100 IRF and
    temperature change of the 1 kg pulse cases. With the shipped CH4 tables
    (made with 16.00 g/mol) both ratios below are 1.003125 instead of 1.
    """
    _, ch4, _ = load_case("ch4_pulse_biogenic")
    _, co2, _ = load_case("co2_pulse")
    gwp100 = ch4["CH4_IRF"][100] / co2["CO2_IRF"][100]
    gtp100 = ch4["CH4_temp"][100] / co2["CO2_temp"][100]
    np.testing.assert_allclose(ch4["GWP_sliding_CO2e"][0] / gwp100, 1.0, rtol=RTOL)
    np.testing.assert_allclose(ch4["GTP_sliding_CO2e"][0] / gtp100, 1.0, rtol=RTOL)


def test_ch4_agwp_table_every_year():
    """Every year 0-500 of the corrected CH4 AGWP table against closed-form agwp().

    The pasted table (equivalency_metrics!O7:O507) is not committed.
    generate_cases.py checks that, once corrected, it equals the CH4_IRF of
    ch4_pulse_biogenic to 1e-12 at every year (the IRF of a 1 kg pulse is, by
    definition, AGWP(t)); this compares that column with agwp("ch4", t) at every
    year, not one row (PR #25 review point; decision D5 on #28). With the
    uncorrected 16.00 g/mol table every year would be off by 0.31%.
    """
    _, ch4, _ = load_case("ch4_pulse_biogenic")
    years = ch4["year"].to_numpy()
    want = ch4["CH4_IRF"].to_numpy(dtype=float)
    got = agwp("ch4", years, get_parameters("AR5"))
    assert want[0] == 0.0 and got[0] == 0.0
    np.testing.assert_allclose(got[1:], want[1:], rtol=RTOL, atol=0)
    assert len(years) == 501 and years[-1] == 500


@pytest.mark.parametrize(("case", "column"), list(_params()))
def test_engine_matches_spreadsheet(case, column):
    _, expected, _ = load_case(case)
    got = np.asarray(COLUMNS[column](run_case(case)), dtype=float)
    want = expected[column].to_numpy(dtype=float)
    atol = RTOL * np.max(np.abs(want))
    np.testing.assert_allclose(got, want, rtol=RTOL, atol=atol, err_msg=f"{case}: {column}")


@pytest.mark.parametrize(("case", "column"), list(_params()))
def test_engine_matches_spreadsheet_where_nonzero(case, column):
    """Second check: relative error only, on every year the expected value is not 0.

    The first check's atol (RTOL x column peak) lets any error pass once a value
    falls below 1e-9 of the peak, for example the CH4 mass after about year 260.
    This one drops atol and compares every year where expected != 0. Years where
    expected == 0 are covered by the first check; an all-zero column is compared
    in full here too, so it must match exactly.
    """
    _, expected, _ = load_case(case)
    got = np.asarray(COLUMNS[column](run_case(case)), dtype=float)
    want = expected[column].to_numpy(dtype=float)
    keep = want != 0 if np.any(want) else np.ones_like(want, dtype=bool)
    np.testing.assert_allclose(
        got[keep],
        want[keep],
        rtol=RTOL,
        atol=0,
        err_msg=f"{case}: {column} (years {np.flatnonzero(keep)[[0, -1]]})",
    )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "Audit bug: module fluxes overwrite each other. create_flux_mat assigns (not adds) "
        "the A, B and C fluxes, and MatEmissionsTiming puts C in years 60-74, so year 60 "
        "gets C instead of B + C and years 61-74 get C again. Measured at year 60: CO2 200 "
        "instead of 210 kg, CH4 1 instead of 1.05 kg, N2O 0.02 instead of 0.022 kg; years "
        "61-74 repeat the C value instead of 0. Both causes (assign-not-add and the "
        "15-year C_time) must be fixed for this to pass."
    ),
)
@pytest.mark.parametrize("gas", ["CO2", "CH4", "N2O"])
def test_building_lifecycle_flux_builder(gas):
    """The inventory's A/B/C flux builder should reproduce the case's inflows."""
    inputs, _, _ = load_case("building_lifecycle")
    kwargs = {"material": DLCA.MaterialTypes.TEST}
    inv = DLCA.EmissionsInventoryAllGHG(
        CO2=DLCA.EmissionsInventoryGHGi(
            ghg=DLCA.GHGTypes.CO2, emissions_A=1000.0, emissions_B=10.0, emissions_C=200.0, **kwargs
        ),
        CH4=DLCA.EmissionsInventoryGHGi(
            ghg=DLCA.GHGTypes.CH4, emissions_A=2.0, emissions_B=0.05, emissions_C=1.0, **kwargs
        ),
        N2O=DLCA.EmissionsInventoryGHGi(
            ghg=DLCA.GHGTypes.N2O, emissions_A=0.1, emissions_B=0.002, emissions_C=0.02, **kwargs
        ),
        # No biogenic uptake (rot_period 0 gives zero growth_biomass), for the same
        # material: the material check is strict (decision A8 on #31).
        CO2bio=DLCA.EmissionInventoryBio(
            material=DLCA.MaterialTypes.TEST, CO2_bio=0.0, rot_period=0
        ),
    )
    flux = DLCA.EmissionsFluxEngine.create_flux_mat(
        material=DLCA.MaterialTypes.TEST,
        time=DLCA.AnalysisPeriod(0, 500),
        timing=DLCA.MatEmissionsTiming(bldg_lifespan=60),
        emissions_inv=inv,
    )
    np.testing.assert_allclose(
        flux.flux_df[f"{gas}_flux"].to_numpy(dtype=float),
        inputs[f"{gas}_flux"].to_numpy(dtype=float),
        rtol=RTOL,
        atol=0,
        err_msg=gas,
    )
