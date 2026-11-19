import numpy as np

from dlca import engine as DLCA
from dlca.models import (
    BldgDetails,
    BldgUseType,
    ClimateZone,
    ResHeatSystem,
    Scenario,
    USSubgrid,
)

RTOL = 1e-12


def make_emissions(emissions_a, emissions_c=0):
    """Build a CO2/CH4/N2O inventory for the TEST material (CH4 and N2O in CO2e)."""
    kwargs = {"material": DLCA.MaterialTypes.TEST, "emissions_B": 0}
    co2 = DLCA.EmissionsInventoryGHGi(
        ghg=DLCA.GHGTypes.CO2, emissions_A=emissions_a, emissions_C=emissions_c, **kwargs
    )
    ch4 = DLCA.EmissionsInventoryGHGi(
        ghg=DLCA.GHGTypes.CH4, emissions_A=emissions_a / 25, emissions_C=emissions_c / 25, **kwargs
    )
    n2o = DLCA.EmissionsInventoryGHGi(
        ghg=DLCA.GHGTypes.N2O,
        emissions_A=emissions_a / 298,
        emissions_C=emissions_c / 298,
        **kwargs,
    )
    # No biogenic carbon, but for the same material (the material check is strict).
    bio = DLCA.EmissionInventoryBio(material=DLCA.MaterialTypes.TEST, CO2_bio=0.0, rot_period=0)
    return DLCA.EmissionsInventoryAllGHG(CO2=co2, CH4=ch4, N2O=n2o, CO2bio=bio)


def make_flux(emissions_inv):
    return DLCA.EmissionsFluxEngine.create_flux_mat(
        material=DLCA.MaterialTypes.TEST,
        time=DLCA.AnalysisPeriod(0, 500),
        timing=DLCA.MatEmissionsTiming(bldg_lifespan=60),
        emissions_inv=emissions_inv,
    )


def test_analysis_period():
    period = DLCA.AnalysisPeriod(0, 500)
    assert period.years_vec[0] == 0
    assert period.years_vec[-1] == 500


def test_create_flux_mat():
    inv = make_emissions(1, emissions_c=1)
    flux_mat_1 = make_flux(inv)
    np.testing.assert_allclose(flux_mat_1.flux_df["CO2_flux"][0], 1, rtol=RTOL)

    flux_mat_2 = make_flux(inv)
    flux_total = DLCA.EmissionsFluxEngine.flux_total([flux_mat_1, flux_mat_2])
    np.testing.assert_allclose(flux_total.flux_df["CO2_flux"][0], 2, rtol=RTOL)


def test_dlca_engine_calc_decay():
    engine = DLCA.DLCAEngine()
    engine.calc_decay(input_flux=make_flux(make_emissions(1)))

    atm = engine.Results.mass_in_atm_df
    np.testing.assert_allclose(sum(atm["CO2"]), 184.2837146985627, rtol=RTOL)
    np.testing.assert_allclose(sum(atm["CH4"]), 0.5162687880706308, rtol=RTOL)
    np.testing.assert_allclose(sum(atm["N2O"]), 0.40123157841290424, rtol=RTOL)


def test_dlca_engine_calc_warming():
    engine = DLCA.DLCAEngine()
    engine.calc_decay(input_flux=make_flux(make_emissions(1)))
    engine.calc_AGWP(time_horizon=100)
    engine.calc_AGTP(time_horizon=100)

    # N2O is not included in the AGTP or AGWP calculations.
    np.testing.assert_allclose(
        engine.Results.temp_change_df["temp_change"][100], 1.0700561631626676e-15, rtol=RTOL
    )
    np.testing.assert_allclose(
        engine.Results.equiv_df["LCA_dyn"][100], 3.0267395007015145, rtol=RTOL
    )


def test_load_eui_and_ef():
    bldg = BldgDetails(
        use_type=BldgUseType.SMALLOFFICE,
        heating_system=ResHeatSystem.NONE,
        climate_zone=ClimateZone._2B,
        eGrid=USSubgrid.RMPA,
        area_m2=15000,
        lifespan=60,
        scenario=Scenario.S1,
    )

    assert bldg.ref_bldg.naturalgas_site_GJ is not None
    assert bldg.ref_bldg.electricity_site_GJ is not None
    assert bldg.ref_bldg.fueloilno2_kBtu is not None

    assert bldg.EF_electricity is not None
    assert bldg.EF_naturalgas is not None
    assert bldg.EF_fueloilno2 is not None
