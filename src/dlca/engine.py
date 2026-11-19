# import libraries
import numpy as np

from dlca.data.csv_loader import *
from dlca.models import *


class EmissionsFluxEngine:
    # Engine to create the emissions inventory for a given material over a given analysis period
    @staticmethod
    def create_flux_mat(
        material: MaterialTypes,
        time: AnalysisPeriod,
        timing: MatEmissionsTiming,
        emissions_inv: EmissionsInventoryAllGHG,
    ) -> EmissionsFluxMat:
        # initialize flux vectors
        CO2_flux = np.linspace(start=0, stop=0, num=(time.end_year - time.start_year + 1))
        CH4_flux = np.linspace(start=0, stop=0, num=(time.end_year - time.start_year + 1))
        N2O_flux = np.linspace(start=0, stop=0, num=(time.end_year - time.start_year + 1))

        # my comment

        # Add in A fluxes
        CO2_flux[timing.A_time] = emissions_inv.CO2.emissions_A
        CH4_flux[timing.A_time] = emissions_inv.CH4.emissions_A
        N2O_flux[timing.A_time] = emissions_inv.N2O.emissions_A
        # Add in B fluxes
        CO2_flux[timing.B_time] = emissions_inv.CO2.emissions_B
        CH4_flux[timing.B_time] = emissions_inv.CH4.emissions_B
        N2O_flux[timing.B_time] = emissions_inv.N2O.emissions_B
        # Add in C fluxes
        CO2_flux[timing.C_time] = emissions_inv.CO2.emissions_C
        CH4_flux[timing.C_time] = emissions_inv.CH4.emissions_C
        N2O_flux[timing.C_time] = emissions_inv.N2O.emissions_C

        # Calculate the CO2 uptake due to biomass regrowth
        if emissions_inv.CO2bio.rot_period > 1:
            emissions_inv.CO2bio.growth_biomass = (
                1
                / (emissions_inv.CO2bio.sigma * np.sqrt(2 * np.pi))
                * np.exp(
                    -0.5
                    * ((time.years_vec - emissions_inv.CO2bio.mu) / emissions_inv.CO2bio.sigma) ** 2
                )
                * emissions_inv.CO2bio.CO2_bio
            )
        elif emissions_inv.CO2bio.rot_period == 1:
            emissions_inv.CO2bio.growth_biomass = (time.years_vec * 0).astype(float)
            emissions_inv.CO2bio.growth_biomass[1] = emissions_inv.CO2bio.CO2_bio
        elif emissions_inv.CO2bio.rot_period < 1:
            emissions_inv.CO2bio.growth_biomass = (time.years_vec * 0).astype(float)
            emissions_inv.CO2bio.growth_biomass[1] = emissions_inv.CO2bio.CO2_bio

        # Add in the carbon uptake
        CO2_flux = CO2_flux - emissions_inv.CO2bio.growth_biomass

        # Create and return the result
        res = EmissionsFluxMat(time.years_vec, CO2_flux, CH4_flux, N2O_flux, material)
        return res

    @staticmethod
    def flux_total(flux_list: [EmissionsFluxMat]) -> EmissionsFluxTotal:
        # Function to calculate the total flux of multiple materials.
        # flux_total_res= EmissionsFluxTotal(time=[], CO2_flux=[], CH4_flux=[], N2O_flux=[])
        # flux_total_res.time = flux_list[0].time
        flux_total_res = EmissionsFluxTotal(time=[], CO2_flux=[], CH4_flux=[], N2O_flux=[])
        flux_total_res.zeros(time=flux_list[0].time)
        for mat_flux in flux_list:
            flux_total_res.CO2_flux = flux_total_res.CO2_flux + mat_flux.CO2_flux
            flux_total_res.CH4_flux = flux_total_res.CH4_flux + mat_flux.CH4_flux
            flux_total_res.N2O_flux = flux_total_res.N2O_flux + mat_flux.N2O_flux
        flux_total_res.create_flux_df()
        return flux_total_res

    @staticmethod
    def create_flux_operational(
        bldg: BldgDetails, time: AnalysisPeriod
    ) -> EmissionsFluxOperational:
        # initialize flux vectors
        CO2_flux = np.linspace(start=0, stop=0, num=(time.end_year - time.start_year + 1))
        CH4_flux = np.linspace(start=0, stop=0, num=(time.end_year - time.start_year + 1))
        N2O_flux = np.linspace(start=0, stop=0, num=(time.end_year - time.start_year + 1))

        electricty_GJ_annual = bldg.ref_bldg.electricity_UI_GJm2 * bldg.area_m2
        naturalgas_GJ_annual = bldg.ref_bldg.naturalgas_UI_GJm2 * bldg.area_m2
        fueloilno2_kBtu_annual = bldg.ref_bldg.fueloilno2_UI_kBtum2 * bldg.area_m2

        # Electricity Emissions (kg)
        CO2_annual_electricity = (
            electricty_GJ_annual * bldg.EF_electricity.CO2 * 277.778
        )  # converting from GJ to kWh
        CH4_annual_electricity = electricty_GJ_annual * bldg.EF_electricity.CH4 * 277.778
        N2O_annual_electricity = electricty_GJ_annual * bldg.EF_electricity.N2O * 277.778

        # Natural Gas Emissions (kg)
        if bldg.EF_naturalgas.unit != Unit.KG_GJ:
            raise Exception(
                "Unit conversion is required. Current calculation of emissions factors is incorrect"
            )
        CO2_annual_naturalgas = naturalgas_GJ_annual * bldg.EF_naturalgas.CO2
        CH4_annual_naturalgas = naturalgas_GJ_annual * bldg.EF_naturalgas.CH4
        N2O_annual_naturalgas = naturalgas_GJ_annual * bldg.EF_naturalgas.N2O

        # Fuel Oil Emissions (kg)
        CO2_annual_fueloilno2 = (
            fueloilno2_kBtu_annual / 1000 * bldg.EF_naturalgas.CO2
        )  # converting from kBtu to MMBtu
        CH4_annual_fueloilno2 = fueloilno2_kBtu_annual / 1000 * bldg.EF_naturalgas.CH4
        N2O_annual_fueloilno2 = fueloilno2_kBtu_annual / 1000 * bldg.EF_naturalgas.N2O

        # CO2_flux[0:bldg.lifespan] = CO2_annual_electricity + CO2_annual_naturalgas + CO2_annual_fueloilno2
        # CH4_flux[0:bldg.lifespan] = CH4_annual_electricity + CH4_annual_naturalgas + CH4_annual_fueloilno2
        # N2O_flux[0:bldg.lifespan] = N2O_annual_electricity + N2O_annual_naturalgas + N2O_annual_fueloilno2

        # Where to start:
        # Need to fix the unit check on emissions factors.
        # Confirm all unit conversions from emissions factors that are used.
        # Create the flux vector from the initialization (currently it is wrong).

        pass
