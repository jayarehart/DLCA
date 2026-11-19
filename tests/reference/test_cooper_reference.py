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
from dlca.climate import agwp, burden, forcing, gwi
from dlca.models import EmissionsFluxTotal
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
    "GWP_sliding_CO2e": ("equiv_df", "GWP_sliding_CO2e"),
}

# (case, column) pairs where dlca.climate disagrees with the spreadsheet on purpose.
KNOWN_DIFFERENCES = {
    ("ch4_pulse_fossil", "GWP_sliding_CO2e"): (
        "Decision D2 on #28: gwi().sliding counts the CO2 formed from fossil CH4. The "
        "spreadsheet's sliding GWP uses its pasted CH4 AGWP table, which leaves the "
        "oxidised CO2 out, so it is 28.456 at every year while its own LCA_dyn[100] is "
        "29.687. Measured: up to 4.3% higher than the spreadsheet (29.687 from year 100)."
    ),
}

# Spreadsheet columns the engine has no output for (see test_metric_missing_from_engine).
MISSING_FROM_ENGINE = [
    "GTP_static_CO2e",
    "temp_over_AGTP_CO2",
    "GTP_sliding_CO2e",
]


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
    # The atmospheric masses come from dlca.climate.burden() (issue #27), which
    # fixes calc_decay's fossil CH4 ordering bug. The old engine's forcing and
    # temperature steps (replaced in #28, #29) then read these masses.
    b = burden(
        {"co2": inputs["CO2_flux"], "ch4": inputs["CH4_flux"], "n2o": inputs["N2O_flux"]},
        get_parameters("AR5"),
        fossil_ch4=engine._inputdata.fossil_CH4,
    )
    results = engine.Results
    results.mass_in_atm_df = pd.DataFrame(
        {"CO2": b.co2, "CH4": b.ch4, "N2O": b.n2o}, index=results.mass_in_atm_df.index
    )
    results.CO2_mass_df = pd.DataFrame(
        {**{f"mass{i}": b.co2_pools[i] for i in range(4)}, "CH4_to_CO2": b.ch4_to_co2},
        index=results.CO2_mass_df.index,
    )
    engine.calc_AGWP(time_horizon=time_horizon)
    engine.calc_AGTP(time_horizon=time_horizon)
    # Forcing, integrated forcing and the dynamic and sliding GWI come from
    # dlca.climate.forcing() and gwi() (issue #28). calc_AGWP still runs because
    # calc_AGTP reads the specific forcings it stores and LCA_static is still
    # its output (#13, #29).
    params = get_parameters("AR5")
    f = forcing(b, params)
    g = gwi(
        {"co2": inputs["CO2_flux"], "ch4": inputs["CH4_flux"], "n2o": inputs["N2O_flux"]},
        params,
        horizon=time_horizon,
        fossil_ch4=engine._inputdata.fossil_CH4,
    )
    index = results.irf_df.index
    results.irf_df = pd.DataFrame(
        {
            "CO2_radfor": f.co2,
            "CH4_radfor": f.ch4,
            "N2O_radfor": f.n2o,
            "CO2_IRF": f.co2_integrated,
            "CH4_IRF": f.ch4_integrated,
            "N2O_IRF": f.n2o_integrated,
            "IRF_all": f.total_integrated,
        },
        index=index,
    )
    results.equiv_df["LCA_dyn"] = g.dynamic
    results.equiv_df["GWP_sliding_CO2e"] = g.sliding
    return results


def _params():
    for case in CASES:
        for col in ENGINE_COLUMNS:
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
    frame, engine_col = ENGINE_COLUMNS[column]
    got = getattr(run_engine(case), frame)[engine_col].to_numpy(dtype=float)
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
    frame, engine_col = ENGINE_COLUMNS[column]
    got = getattr(run_engine(case), frame)[engine_col].to_numpy(dtype=float)
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
    raises=KeyError,
    reason=(
        "Engine gap, not on the audit list: calc_AGTP builds AGTP_rev and AGTP_CO2 but "
        "returns neither, so there is no sliding GTP, static GTP or temperature/AGTP_CO2 "
        "output to compare (#29). GWP_sliding_CO2e now comes from gwi() (#28). "
        "(The spreadsheet's AGTP_CO2, intro!E50, has the same p_1-for-p_3 slip as "
        "the engine's.)"
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
