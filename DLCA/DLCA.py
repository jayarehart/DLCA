# import libraries
from DLCA.models import *
from DLCA.data.csv_loader import *
import numpy as np

class EmissionsFluxEngine():
    # Engine to create the emissions inventory for a given material over a given analysis period
    @staticmethod
    def create_flux_mat(material:MaterialTypes, time:AnalysisPeriod, timing:MatEmissionsTiming, emissions_inv:EmissionsInventoryAllGHG, ) -> EmissionsFluxMat:
        # initialize flux vectors
        CO2_flux = np.linspace(start=0, stop=0, num=(time.end_year - time.start_year + 1))
        CH4_flux = np.linspace(start=0, stop=0, num=(time.end_year - time.start_year + 1))
        N2O_flux = np.linspace(start=0, stop=0, num=(time.end_year - time.start_year + 1))

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
            emissions_inv.CO2bio.growth_biomass = 1 / (emissions_inv.CO2bio.sigma * np.sqrt(2 * np.pi)) * np.exp(-0.5 * ((time.years_vec - emissions_inv.CO2bio.mu) / emissions_inv.CO2bio.sigma) ** 2) * emissions_inv.CO2bio.CO2_bio
        elif emissions_inv.CO2bio.rot_period == 1:
            emissions_inv.CO2bio.growth_biomass = (time.years_vec * 0).astype(float)
        elif emissions_inv.CO2bio.rot_period < 1:
            emissions_inv.CO2bio.growth_biomass = (time.years_vec * 0).astype(float)

        # Add in the carbon uptake
        CO2_flux = CO2_flux - emissions_inv.CO2bio.growth_biomass

        # Create and return the result
        res = EmissionsFluxMat(time.years_vec, CO2_flux, CH4_flux, N2O_flux, material)
        return res

    @staticmethod
    def flux_total(flux_list:[EmissionsFluxMat]) -> EmissionsFluxTotal:
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

    # @staticmethod
    # def create_flux_operational(bldg:BldgDetails,time:AnalysisPeriod,Scenario:) -> EmissionsFluxMat:):

class DLCAEngine():

    def __init__(self) -> None:
        self.load_data()

    def load_data(self):
        self._inputdata = DLCAInputData()
        self.Results = DLCAResults()

    def calc_decay(self, input_flux:EmissionsFluxTotal) -> DLCAResults:
        self.years_vec = input_flux.time
        # Initialize mass in atmosphere dataframe
        mass_in_atm_df = pd.DataFrame(0, index=self.years_vec, columns=['CO2', 'CH4'])
        # Initialize CO2 atmospheric decay components dataframe
        CO2_mass_df = pd.DataFrame(0, index=self.years_vec, columns=['mass0', 'mass1', 'mass2', 'mass3', 'CH4_to_CO2'])

        CO2_flux = input_flux.flux_df['CO2_flux']
        CH4_flux = input_flux.flux_df['CH4_flux']
        N20_flux = input_flux.flux_df['N20_flux']

        # Calculate the Mass Decay
        for index, row in mass_in_atm_df.iterrows():
            # Calculation for the first timestep
            if index == 0:
                mass_in_atm_df.loc[index, 'CH4'] = CH4_flux[index]
                CO2_mass_df.loc[index, 'mass0'] = self._inputdata.p_0 * CO2_flux[index]
                CO2_mass_df.loc[index, 'mass1'] = self._inputdata.p_1 * CO2_flux[index]
                CO2_mass_df.loc[index, 'mass2'] = self._inputdata.p_2 * CO2_flux[index]
                CO2_mass_df.loc[index, 'mass3'] = self._inputdata.p_3 * CO2_flux[index]
                CO2_mass_df.loc[index, 'CH4_to_CO2'] = 0
            # Calculation for the start + 1 to end timesteps
            else:
                mass_in_atm_df.loc[index, 'CH4'] = CH4_flux[index] + mass_in_atm_df.loc[index - 1, 'CH4'] * np.exp(
                    -1 / self._inputdata.life_CH4)
                CO2_mass_df.loc[index, 'mass0'] = self._inputdata.p_0 * (
                            CO2_flux[index] + CO2_mass_df.loc[index, 'CH4_to_CO2']) + CO2_mass_df.loc[
                                                      index - 1, 'mass0']
                CO2_mass_df.loc[index, 'mass1'] = self._inputdata.p_1 * (
                            CO2_flux[index] + CO2_mass_df.loc[index, 'CH4_to_CO2']) + CO2_mass_df.loc[
                                                      index - 1, 'mass1'] * np.exp(-1 / self._inputdata.life1_CO2)
                CO2_mass_df.loc[index, 'mass2'] = self._inputdata.p_2 * (
                            CO2_flux[index] + CO2_mass_df.loc[index, 'CH4_to_CO2']) + CO2_mass_df.loc[
                                                      index - 1, 'mass2'] * np.exp(-1 / self._inputdata.life2_CO2)
                CO2_mass_df.loc[index, 'mass3'] = self._inputdata.p_3 * (
                            CO2_flux[index] + CO2_mass_df.loc[index, 'CH4_to_CO2']) + CO2_mass_df.loc[
                                                      index - 1, 'mass3'] * np.exp(-1 / self._inputdata.life3_CO2)
                if self._inputdata.fossil_CH4 == True:
                    CO2_mass_df.loc[index, 'CH4_to_CO2'] = mass_in_atm_df.loc[index - 1, 'CH4'] * (
                                1 - np.exp(-1 / self._inputdata.life_CH4)) * self._inputdata.CH4_to_CO2
                elif self._inputdata.fossil_CH4 == False:
                    CO2_mass_df.loc[index, 'CH4_to_CO2'] = 0
            mass_in_atm_df.loc[index, 'CO2'] = CO2_mass_df.loc[index, 'mass0'] + CO2_mass_df.loc[index, 'mass1'] + \
                                               CO2_mass_df.loc[index, 'mass2'] + CO2_mass_df.loc[index, 'mass3']


        # Cumulative net emissions [kg]
        cum_net_emissions = pd.DataFrame(0, index=self.years_vec, columns=['CO2_net', 'CH4_net', 'gas1_net', 'gas2_net', 'gas3_net'])
        for index, row in cum_net_emissions.iterrows():
            if index == 0:
                cum_net_emissions.loc[index, 'CO2_net'] = CO2_flux[index]
                cum_net_emissions.loc[index, 'CH4_net'] = CH4_flux[index]
                # Add in new gases too here
            else:
                cum_net_emissions.loc[index, 'CO2_net'] = cum_net_emissions.loc[index - 1, 'CO2_net'] + CO2_flux[index]
                cum_net_emissions.loc[index, 'CH4_net'] = cum_net_emissions.loc[index - 1, 'CH4_net'] + CH4_flux[index]
                # Add in new gases too here

        self.Results.mass_in_atm_df = mass_in_atm_df
        self.Results.CO2_mass_df = CO2_mass_df
        self.Results.cum_net_emissions = cum_net_emissions

        return self.Results

    def calc_AGWP(self, time_horizon=100) -> DLCAResults:

        self._inputdata.time_horizon = time_horizon

        # Specific radiative forcing [W m-2 kg-1]
        # Forcing parameters from [ref 5]
        self._inputdata.A_CO2 = self._inputdata.CO2_RE * self._inputdata.adj_factor_CO2 * self._inputdata.mol_mass_air * 1000000000 / self._inputdata.mass_atm / self._inputdata.mol_mass_CO2
        self._inputdata.A_CH4 = self._inputdata.CH4_RE * self._inputdata.adj_factor_CH4 * self._inputdata.mol_mass_air * 1000000000 / self._inputdata.mass_atm / self._inputdata.mol_mass_CH4

        self._inputdata.AGWP_CO2 = self._inputdata.A_CO2 * (self._inputdata.p_0 * time_horizon
                            + self._inputdata.p_1 * self._inputdata.life1_CO2 * (1 - np.exp(-time_horizon / self._inputdata.life1_CO2))
                            + self._inputdata.p_2 * self._inputdata.life2_CO2 * (1 - np.exp(-time_horizon / self._inputdata.life2_CO2))
                            + self._inputdata.p_3 * self._inputdata.life3_CO2 * (1 - np.exp(-time_horizon / self._inputdata.life3_CO2)))

        self._inputdata.AGWP_CH4 = self._inputdata.A_CH4 * self._inputdata.life_CH4 * (1 - np.exp(-time_horizon / self._inputdata.life_CH4))

        # Normalize AGWP to GWP
        self._inputdata.GWP_CH4 = self._inputdata.AGWP_CH4 / self._inputdata.AGWP_CO2

        # Initialize radiative forcing dataframe
        irf_df = pd.DataFrame(0, index=self.years_vec, columns=['CO2_radfor', 'CH4_radfor', 'CO2_IRF', 'CH4_IRF', 'IRF_all'])



        # Calculate the radiative forcing (instantaneous just after start of year), [W m^-2]
        irf_df['CO2_radfor'] = self._inputdata.A_CO2 * self.Results.mass_in_atm_df['CO2']
        irf_df['CH4_radfor'] = self._inputdata.A_CH4 * self.Results.mass_in_atm_df['CH4']

        # Calculate integrated radiative forcing [W-year m^-2]
        for index, row in irf_df.iterrows():
            if index == 0:
                irf_df.loc[index, 'CO2_IRF'] = 0
                irf_df.loc[index, 'CH4_IRF'] = 0
            else:
                irf_df.loc[index, 'CO2_IRF'] = irf_df.loc[index - 1, 'CO2_IRF'] + self._inputdata.A_CO2 * (
                        self.Results.CO2_mass_df.loc[index - 1, 'mass0'] +
                        self.Results.CO2_mass_df.loc[index - 1, 'mass1'] * self._inputdata.life1_CO2 * (1 - np.exp(-1 / self._inputdata.life1_CO2)) +
                        self.Results.CO2_mass_df.loc[index - 1, 'mass2'] * self._inputdata.life2_CO2 * (1 - np.exp(-1 / self._inputdata.life2_CO2)) +
                        self.Results.CO2_mass_df.loc[index - 1, 'mass3'] * self._inputdata.life3_CO2 * (1 - np.exp(-1 / self._inputdata.life3_CO2))
                )
                irf_df.loc[index, 'CH4_IRF'] = irf_df.loc[index - 1, 'CH4_IRF'] + self.Results.mass_in_atm_df.loc[
                    index - 1, 'CH4'] * self._inputdata.A_CH4 * self._inputdata.life_CH4 * (1 - np.exp(-1 / self._inputdata.life_CH4))

        irf_df['IRF_all'] = irf_df['CO2_IRF'] + irf_df['CH4_IRF']



        # load in supporting data

        AGWP_df_sup = load_AGWP_supp_data()


        # AGWP and AGTP in reverse-order from year X (the time-horizon)
        AGWP_rev = pd.DataFrame(0, index=self.years_vec, columns=['CO2_AGWP_rev', 'CH4_AGWP_rev'])
        AGWP_rev['CO2_AGWP_rev'] = pd.concat((AGWP_df_sup.loc[0:time_horizon, 'CO2_AGWP'][::-1], pd.Series(self.years_vec[time_horizon + 1:] * 0))).reset_index(drop=True)
        AGWP_rev['CH4_AGWP_rev'] = pd.concat((AGWP_df_sup.loc[0:time_horizon, 'CH4_AGWP'][::-1], pd.Series(self.years_vec[time_horizon + 1:] * 0))).reset_index(drop=True)


        # Equivalency summary dataframe
        # equiv_df = pd.DataFrame(0, index=self.years_vec, columns=['irf_GWP_slidingTH', 'GTP_slidingTH', 'CO2_AGTP_rev', 'CH4_AGTP_rev'])

        equiv_df = pd.DataFrame(0, index=self.years_vec, columns=['LCA_dyn', 'LCA_static'])
        equiv_df['LCA_dyn'] = irf_df['IRF_all'] / self._inputdata.AGWP_CO2
        equiv_df['LCA_static'] = self.Results.cum_net_emissions['CO2_net'] + self.Results.cum_net_emissions['CH4_net'] * self._inputdata.GWP_CH4  # add in more gasses here if desired

        self.Results.irf_df = irf_df
        self.Results.equiv_df = equiv_df

        return self.Results

    def calc_AGTP(self, time_horizon=100) -> DLCAResults:

        AGTP_CO2 = self._inputdata.A_CO2 * (self._inputdata.p_0 * (self._inputdata.clim_sens1 * (1 - np.exp(-time_horizon / self._inputdata.clim_time1)) + self._inputdata.clim_sens2 * (1 - np.exp(-time_horizon / self._inputdata.clim_time2)))
                                            + self._inputdata.p_1 * self._inputdata.life1_CO2 * (self._inputdata.clim_sens1 / (self._inputdata.life1_CO2 - self._inputdata.clim_time1) * (np.exp(-time_horizon / self._inputdata.life1_CO2) - np.exp(-time_horizon / self._inputdata.clim_time1)) + self._inputdata.clim_sens2 / (self._inputdata.life1_CO2 - self._inputdata.clim_time2) * (np.exp(-time_horizon / self._inputdata.life1_CO2) - np.exp(-time_horizon / self._inputdata.clim_time2))) + self._inputdata.p_2 * self._inputdata.life2_CO2 * (self._inputdata.clim_sens1 / (self._inputdata.life2_CO2 - self._inputdata.clim_time1) * (
                        np.exp(-time_horizon / self._inputdata.life2_CO2) - np.exp(-time_horizon / self._inputdata.clim_time1)) + self._inputdata.clim_sens2 / (self._inputdata.life2_CO2 - self._inputdata.clim_time2) * (np.exp(-time_horizon / self._inputdata.life2_CO2) - np.exp(-time_horizon / self._inputdata.clim_time2))) + self._inputdata.p_1 * self._inputdata.life3_CO2 * (self._inputdata.clim_sens1 / (self._inputdata.life3_CO2 - self._inputdata.clim_time1) * (
                        np.exp(-time_horizon / self._inputdata.life3_CO2) - np.exp(-time_horizon / self._inputdata.clim_time1)) + self._inputdata.clim_sens2 / (self._inputdata.life3_CO2 - self._inputdata.clim_time2) * (np.exp(-time_horizon / self._inputdata.life3_CO2) - np.exp(-time_horizon / self._inputdata.clim_time2))))

        AGTP_CH4 = self._inputdata.A_CH4 * (self._inputdata.life_CH4 * self._inputdata.clim_sens1 / (self._inputdata.life_CH4 - self._inputdata.clim_time1) * (
                np.exp(-time_horizon / self._inputdata.life_CH4) - np.exp(-time_horizon / self._inputdata.clim_time1))
                                            + self._inputdata.life_CH4 * self._inputdata.clim_sens2 / (self._inputdata.life_CH4 - self._inputdata.clim_time2) * (
                                                    np.exp(-time_horizon / self._inputdata.life_CH4) - np.exp(-time_horizon / self._inputdata.clim_time2)))

        GTP_CH4 = AGTP_CH4 / AGTP_CO2

        # Temperature change components (two-part climate response model)
        # Initialize the temperature change dataframe
        temp_change_df = pd.DataFrame(0, index=self.years_vec,columns=['CO2_temp_s1', 'CO2_temp_s2', 'CH4_temp_s1', 'CH4_temp_s2', 'CO2_temp', 'CH4_temp', 'temp_change'])
        for index, row in temp_change_df.iterrows():
            if index == 0:
                temp_change_df.loc[index, 'CO2_temp_s1'] = 0
                temp_change_df.loc[index, 'CO2_temp_s2'] = 0
                temp_change_df.loc[index, 'CH4_temp_s1'] = 0
                temp_change_df.loc[index, 'CH4_temp_s2'] = 0
                temp_change_df.loc[index, 'CO2_temp'] = 0
                temp_change_df.loc[index, 'CH4_temp'] = 0
            else:
                temp_change_df.loc[index, 'CO2_temp_s1'] = self._inputdata.A_CO2 * (self.Results.CO2_mass_df.loc[index - 1, 'mass0'] * self._inputdata.clim_sens1 * (1 - np.exp(-1 / self._inputdata.clim_time1))
                                                                                    + self.Results.CO2_mass_df.loc[index - 1, 'mass1'] * self._inputdata.clim_sens1 * self._inputdata.life1_CO2 / (self._inputdata.life1_CO2 - self._inputdata.clim_time1) * (np.exp(-1 / self._inputdata.life1_CO2) - np.exp(-1 / self._inputdata.clim_time1))
                                                                                    + self.Results.CO2_mass_df.loc[index - 1, 'mass2'] * self._inputdata.clim_sens1 * self._inputdata.life2_CO2 / (self._inputdata.life2_CO2 - self._inputdata.clim_time1) * (np.exp(-1 / self._inputdata.life2_CO2) - np.exp(-1 / self._inputdata.clim_time1))
                                                                                    + self.Results.CO2_mass_df.loc[index - 1, 'mass3'] * self._inputdata.clim_sens1 * self._inputdata.life3_CO2 / (self._inputdata.life3_CO2 - self._inputdata.clim_time1) * (np.exp(-1 / self._inputdata.life3_CO2) - np.exp(-1 / self._inputdata.clim_time1))) \
                                                           + temp_change_df.loc[index - 1, 'CO2_temp_s1'] * np.exp(-1 / self._inputdata.clim_time1)
                temp_change_df.loc[index, 'CO2_temp_s2'] = self._inputdata.A_CO2 * (self.Results.CO2_mass_df.loc[index - 1, 'mass0'] * self._inputdata.clim_sens2 * (1 - np.exp(-1 / self._inputdata.clim_time2))
                                                                                    + self.Results.CO2_mass_df.loc[index - 1, 'mass1'] * self._inputdata.clim_sens2 * self._inputdata.life1_CO2 / (self._inputdata.life1_CO2 - self._inputdata.clim_time2) * (np.exp(-1 / self._inputdata.life1_CO2) - np.exp(-1 / self._inputdata.clim_time2))
                                                                                    + self.Results.CO2_mass_df.loc[index - 1, 'mass2'] * self._inputdata.clim_sens2 * self._inputdata.life2_CO2 / (self._inputdata.life2_CO2 - self._inputdata.clim_time2) * (np.exp(-1 / self._inputdata.life2_CO2) - np.exp(-1 / self._inputdata.clim_time2))
                                                                                    + self.Results.CO2_mass_df.loc[index - 1, 'mass3'] * self._inputdata.clim_sens2 * self._inputdata.life3_CO2 / (self._inputdata.life3_CO2 - self._inputdata.clim_time2) * (np.exp(-1 / self._inputdata.life3_CO2) - np.exp(-1 / self._inputdata.clim_time2))) \
                                                           + temp_change_df.loc[index - 1, 'CO2_temp_s2'] * np.exp(-1 / self._inputdata.clim_time2)
                temp_change_df.loc[index, 'CH4_temp_s1'] = self._inputdata.A_CH4 * self.Results.mass_in_atm_df.loc[index - 1, 'CH4'] * self._inputdata.clim_sens1 * self._inputdata.life_CH4 / (self._inputdata.life_CH4 - self._inputdata.clim_time1) * (np.exp(-1 / self._inputdata.life_CH4) - np.exp(-1 / self._inputdata.clim_time1)) + temp_change_df.loc[index - 1, 'CH4_temp_s1'] * np.exp(-1 / self._inputdata.clim_time1)
                temp_change_df.loc[index, 'CH4_temp_s2'] = self._inputdata.A_CH4 * self.Results.mass_in_atm_df.loc[index - 1, 'CH4'] * self._inputdata.clim_sens2 * self._inputdata.life_CH4 / (self._inputdata.life_CH4 - self._inputdata.clim_time2) * (np.exp(-1 / self._inputdata.life_CH4) - np.exp(-1 / self._inputdata.clim_time2)) + temp_change_df.loc[index - 1, 'CH4_temp_s2'] * np.exp(-1 / self._inputdata.clim_time2)
                temp_change_df.loc[index, 'CO2_temp'] = temp_change_df.loc[index, 'CO2_temp_s1'] + temp_change_df.loc[index, 'CO2_temp_s2']
                temp_change_df.loc[index, 'CH4_temp'] = temp_change_df.loc[index, 'CH4_temp_s1'] + temp_change_df.loc[index, 'CH4_temp_s2']

        temp_change_df['temp_change'] = temp_change_df['CO2_temp'] + temp_change_df['CH4_temp'].fillna(0)

        AGTP_df_sup = load_AGTP_supp_data()
        AGTP_rev = pd.DataFrame(0, index=self.years_vec, columns=['CO2_AGTP_rev', 'CH4_AGTP_rev'])
        AGTP_rev['CO2_AGTP_rev'] = pd.concat((AGTP_df_sup.loc[0:time_horizon, 'CO2_AGTP'][::-1], pd.Series(self.years_vec[time_horizon + 1:] * 0))).reset_index(drop=True)
        AGTP_rev['CH4_AGTP_rev'] = pd.concat((AGTP_df_sup.loc[0:time_horizon, 'CH4_AGTP'][::-1], pd.Series(self.years_vec[time_horizon + 1:] * 0))).reset_index(drop=True)

        self.Results.temp_change_df = temp_change_df

        return self.Results







