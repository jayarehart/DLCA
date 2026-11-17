"""Characterization tests: dlca.engine against the Cooper et al. (2020) spreadsheet.

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

from dlca import engine as DLCA
from dlca.models import EmissionsFluxTotal

CASES_DIR = Path(__file__).parent / "cases"
CASES = sorted(p.name for p in CASES_DIR.iterdir() if (p / "expected.csv").exists())

RTOL = 1e-9
# atol is scaled to each column: RTOL times the largest |expected| value in it,
# so values far below the column's magnitude (for example near-zero tails) do
# not demand more relative precision than the spreadsheet carries.

# The second check (test_engine_matches_spreadsheet_where_large) uses rtol only,
# on years where |expected| >= WINDOW x column peak. Below 1e-15 of the peak a
# value is smaller than the rounding error on the peak itself (the spreadsheet
# stores 15 significant digits), so in columns that add or subtract peak-sized
# terms it may be rounding noise. Above it, every passing comparison agreed to
# 5.4e-15 relative when this was written (2026-11-17).
WINDOW = 1e-15

# expected.csv column -> (DLCAResults attribute, column in that DataFrame).
ENGINE_COLUMNS = {
    "CO2_mass": ("mass_in_atm_df", "CO2"),
    "CH4_mass": ("mass_in_atm_df", "CH4"),
    "N2O_mass": ("mass_in_atm_df", "N2O"),
    "CO2_mass0": ("CO2_mass_df", "mass0"),
    "CO2_mass1": ("CO2_mass_df", "mass1"),
    "CO2_mass2": ("CO2_mass_df", "mass2"),
    "CO2_mass3": ("CO2_mass_df", "mass3"),
    "CH4_to_CO2": ("CO2_mass_df", "CH4_to_CO2"),
    "CO2_radfor": ("irf_df", "CO2_radfor"),
    "CH4_radfor": ("irf_df", "CH4_radfor"),
    "N2O_radfor": ("irf_df", "N2O_radfor"),
    "CO2_IRF": ("irf_df", "CO2_IRF"),
    "CH4_IRF": ("irf_df", "CH4_IRF"),
    "N2O_IRF": ("irf_df", "N2O_IRF"),
    "IRF_all": ("irf_df", "IRF_all"),
    "CO2_temp": ("temp_change_df", "CO2_temp"),
    "CH4_temp": ("temp_change_df", "CH4_temp"),
    "N2O_temp": ("temp_change_df", "N2O_temp"),
    "temp_change": ("temp_change_df", "temp_change"),
    "CO2_net": ("cum_net_emissions", "CO2_net"),
    "CH4_net": ("cum_net_emissions", "CH4_net"),
    "N2O_net": ("cum_net_emissions", "N2O_net"),
    "IRF_over_AGWP_CO2": ("equiv_df", "LCA_dyn"),
    "GWP_static_CO2e": ("equiv_df", "LCA_static"),
}

# Spreadsheet columns the engine has no output for (see test_metric_missing_from_engine).
MISSING_FROM_ENGINE = [
    "GTP_static_CO2e",
    "temp_over_AGTP_CO2",
    "GWP_sliding_CO2e",
    "GTP_sliding_CO2e",
]

FOSSIL_CH4_REASON = (
    "Known bug, fixed in M1 (Jay's decision on PR #24, 2026-11-17): CH4_to_CO2 is "
    "used before it is assigned in calc_decay. With fossil_CH4=True, calc_decay adds "
    "CO2_mass_df['CH4_to_CO2'] to the CO2 pools before it assigns that row's value, "
    "so the oxidised-CH4 CO2 is never added. CH4_to_CO2 itself matches; CO2 mass, "
    "forcing and temperature miss it."
)
# Columns that fail for ch4_pulse_fossil, with the measured disagreement
# (max |engine - spreadsheet| / max |spreadsheet| over years 0-500).
XFAIL = {
    ("ch4_pulse_fossil", col): f"{FOSSIL_CH4_REASON} Measured: {size}."
    for col, size in {
        "CO2_mass": "1.0 (engine CO2 mass is 0; spreadsheet peaks at 0.769 kg)",
        "CO2_mass0": "1.0",
        "CO2_mass1": "1.0",
        "CO2_mass2": "1.0",
        "CO2_mass3": "1.0",
        "CO2_radfor": "1.0",
        "CO2_IRF": "1.0",
        "IRF_all": "0.142",
        "IRF_over_AGWP_CO2": "0.142",
        "CO2_temp": "1.0",
        "temp_change": "0.0143",
    }.items()
}


@cache
def load_case(case):
    d = CASES_DIR / case
    inputs = pd.read_csv(d / "inputs.csv")
    expected = pd.read_csv(d / "expected.csv")
    settings = dict(pd.read_csv(d / "settings.csv", dtype=str).values)
    return inputs, expected, settings


@cache
def run_engine(case):
    inputs, _, settings = load_case(case)
    engine = DLCA.DLCAEngine()
    engine._inputdata.fossil_CH4 = {"TRUE": True, "FALSE": False}[settings["fossil_CH4"]]
    flux = EmissionsFluxTotal(
        time=inputs["year"].to_numpy(),
        CO2_flux=inputs["CO2_flux"].to_numpy(),
        CH4_flux=inputs["CH4_flux"].to_numpy(),
        N2O_flux=inputs["N2O_flux"].to_numpy(),
    )
    time_horizon = int(settings["time_horizon"])
    engine.calc_decay(input_flux=flux)
    engine.calc_AGWP(time_horizon=time_horizon)
    engine.calc_AGTP(time_horizon=time_horizon)
    return engine.Results


def _params():
    for case in CASES:
        for col in ENGINE_COLUMNS:
            marks = []
            if (case, col) in XFAIL:
                marks = [
                    pytest.mark.xfail(strict=True, raises=AssertionError, reason=XFAIL[(case, col)])
                ]
            yield pytest.param(case, col, id=f"{case}-{col}", marks=marks)


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


@pytest.mark.parametrize(("case", "column"), list(_params()))
def test_engine_matches_spreadsheet(case, column):
    _, expected, _ = load_case(case)
    frame, engine_col = ENGINE_COLUMNS[column]
    got = getattr(run_engine(case), frame)[engine_col].to_numpy(dtype=float)
    want = expected[column].to_numpy(dtype=float)
    atol = RTOL * np.max(np.abs(want))
    np.testing.assert_allclose(got, want, rtol=RTOL, atol=atol, err_msg=f"{case}: {column}")


@pytest.mark.parametrize(("case", "column"), list(_params()))
def test_engine_matches_spreadsheet_where_large(case, column):
    """Second check: relative error only, on every year the value is resolvable.

    The first check's atol (RTOL x column peak) lets any error pass once a value
    falls below 1e-9 of the peak, for example the CH4 mass after about year 260.
    This one drops atol and compares only years where |expected| >= WINDOW x peak
    (an all-zero column keeps every year, so it must match exactly).
    """
    _, expected, _ = load_case(case)
    frame, engine_col = ENGINE_COLUMNS[column]
    got = getattr(run_engine(case), frame)[engine_col].to_numpy(dtype=float)
    want = expected[column].to_numpy(dtype=float)
    keep = np.abs(want) >= WINDOW * np.max(np.abs(want))
    np.testing.assert_allclose(
        got[keep],
        want[keep],
        rtol=RTOL,
        atol=0,
        err_msg=f"{case}: {column} (years {np.flatnonzero(keep)[[0, -1]]})",
    )


@pytest.mark.xfail(
    strict=True,
    raises=KeyError,
    reason=(
        "Engine gap, not on the audit list: calc_AGWP/calc_AGTP build AGWP_rev/AGTP_rev "
        "and AGTP_CO2 but return none of them, so there is no sliding GWP/GTP, static "
        "GTP or temperature/AGTP_CO2 output to compare. (The spreadsheet's AGTP_CO2, "
        "intro!E50, has the same p_1-for-p_3 slip as the engine's.)"
    ),
)
@pytest.mark.parametrize("column", MISSING_FROM_ENGINE)
def test_metric_missing_from_engine(column):
    results = run_engine("building_lifecycle")
    _, expected, _ = load_case("building_lifecycle")
    got = results.equiv_df[column].to_numpy(dtype=float)  # KeyError today
    want = expected[column].to_numpy(dtype=float)
    np.testing.assert_allclose(got, want, rtol=RTOL, atol=RTOL * np.max(np.abs(want)))


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
    """The engine's own A/B/C flux builder should reproduce the case's inflows."""
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
        # CO2bio is left at its default (material NA, no uptake). Passing TEST here
        # trips the inverted material check in EmissionsInventoryAllGHG.__post_init__,
        # which raises when the materials *match*.
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
