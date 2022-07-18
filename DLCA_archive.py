# Script to support the figure for the Science Policy Paper with Francesco, Verena, and Guillame

# Methods adapted from v2.0 of cooper et a. 2020 (https://doi.org/10.15125/BATH-00923)
# The details of the methods are described by the paper: https://doi.org/10.1016/j.biombioe.2020.105778

# Load in appropriate libraries
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns



def create_dyn_inventory_bio(material, ECC_CO2_A, ECC_CH4_A, CO2_bio, rot_period):
    # notes about the function
    #       only including A1-A3 emissions for CO2 and CH4.
    #       assuming biomass will be long stored (end-of-life is outside the scope of the study)

    # Sample inputs to debug function as needed
    material = 'Timber'
    ECC_CO2_A = 0.16    # kg CO2 / kg material
    ECC_CH4_A = 0.01    # kg CH4 / kg material
    CO2_bio = 1.14      # kg CO2 / kg material
    rot_period = 40   # years

    # start and end years
    start_yr = 0
    end_yr = 500
    year_vec = np.linspace(start=start_yr, stop=end_yr, num=(end_yr - start_yr + 1)).astype(int)

    if rot_period > 1:
        # Cherubini et al. 2011 generic method for biomass regrowth
        mu = rot_period / 2
        sigma = mu/2
        growth_biomass = 1/(sigma * np.sqrt(2 * np.pi)) * np.exp(-0.5 * ((year_vec- mu)/ sigma) ** 2) * CO2_bio
    elif rot_period == 1:
        growth_biomass = (year_vec * 0).astype(float)
        growth_biomass[1] = CO2_bio

    # initialize flux vectors
    CO2_flux = np.linspace(start=0, stop=0, num=(end_yr - start_yr + 1))
    CH4_flux = np.linspace(start=0, stop=0, num=(end_yr - start_yr + 1))

    # Add in year 0 fluxes
    CO2_flux[0] = ECC_CO2_A
    CH4_flux[0] = ECC_CH4_A

    # Add in carbon uptake
    CO2_flux = CO2_flux - growth_biomass

    flux_df = pd.DataFrame({'time':year_vec,
                            'CO2_flux':CO2_flux,
                            'CH4_flux':CH4_flux})

    return flux_df

def create_dyn_inventory_conv(material, ECC_CO2_A, ECC_CH4_A):
    # notes about the function
    #       only including A1-A3 emissions for CO2 and CH4.

    # start and end years
    start_yr = 0
    end_yr = 500
    year_vec = np.linspace(start=start_yr, stop=end_yr, num=(end_yr - start_yr + 1)).astype(int)

    # initialize flux vectors
    CO2_flux = np.linspace(start=0, stop=0, num=(end_yr - start_yr + 1))
    CH4_flux = np.linspace(start=0, stop=0, num=(end_yr - start_yr + 1))

    # Add in year 0 fluxes
    CO2_flux[0] = ECC_CO2_A
    CH4_flux[0] = ECC_CH4_A

    # can add in concrete carbonation if desired...


    flux_df = pd.DataFrame({'time':year_vec,
                            'CO2_flux':CO2_flux,
                            'CH4_flux':CH4_flux})

    return flux_df


flux_sawnwood = create_dyn_inventory_bio(material='Sawnwood', ECC_CO2_A=0.1036, ECC_CH4_A=0.0002, CO2_bio=1.83, rot_period=90)
flux_glulam = create_dyn_inventory_bio(material='Glulam', ECC_CO2_A=0.5186, ECC_CH4_A=0.0013, CO2_bio=1.83, rot_period=50)
flux_clt = create_dyn_inventory_bio(material='CLT', ECC_CO2_A=0.365, ECC_CH4_A=0.000714583, CO2_bio=1.83, rot_period=40)
flux_bamboo = create_dyn_inventory_bio(material='Bamboo', ECC_CO2_A=0.9800, ECC_CH4_A=0, CO2_bio=1.83, rot_period=5)
flux_hemp = create_dyn_inventory_bio(material='Hemp', ECC_CO2_A=0.104, ECC_CH4_A=0, CO2_bio=1.83, rot_period=1)
flux_straw = create_dyn_inventory_bio(material='Straw', ECC_CO2_A=0.1020, ECC_CH4_A=0.0001, CO2_bio=1.47, rot_period=1)
flux_cork = create_dyn_inventory_bio(material='Cork', ECC_CO2_A=1.86, ECC_CH4_A=0, CO2_bio=2.01, rot_period=9)
flux_concrete = create_dyn_inventory_conv(material='Concrete', ECC_CO2_A=0.1255, ECC_CH4_A=0.0001)  # Assuming 500 kg CO2e/m3 of concrete
flux_steel = create_dyn_inventory_conv(material='Steel', ECC_CO2_A=1.76, ECC_CH4_A=0.0053)       # GWP from AISC EPD

def DLCA_calc(input_flux, time_horizon=100):

    ## Inputs
    fossil_CH4 = False
    CH4_to_CO2 = 0.5 * (12 + 16 * 2) / (12 + 1 * 4)

    Other_forcing_efficacy = 1

    # climate sensitivity [K (W m-2)-1]
    clim_sens1 = 0.631
    clim_sens2 = 0.429
    # climate time response [years]
    clim_time1 = 8.4
    clim_time2 = 409.5

    mol_mass_air = 28.97  # g/mol
    earth_area = 5.10E+14  # m2
    mass_atm = 5.14E+18  # kg

    # Lifetime Parameters
    life1_CO2 = 394.4
    life2_CO2 = 36.54
    life3_CO2 = 4.304
    life_CH4 = 12.4
    # Proportion lifetime applies to
    p_0 = 0.2173
    p_1 = 0.224
    p_2 = 0.2824
    p_3 = 0.2763

    # Radiative efficiency [W m-2 ppb-1]
    CO2_RE = 1.37E-05
    CH4_RE = 0.000363
    # molar mass of CO2
    mol_mass_CO2 = 44.01
    mol_mass_CH4 = 16.05

    # adjustment factor
    adj_factor_CO2 = 0.99746898064295
    adj_factor_CH4 = 1 + 0.15 + 0.5

    # Specific radiative forcing [W m-2 kg-1]
    # Forcing parameters from [ref 5]
    A_CO2 = CO2_RE * adj_factor_CO2 * mol_mass_air * 1000000000 / mass_atm / mol_mass_CO2
    A_CH4 = CH4_RE * adj_factor_CH4 * mol_mass_air * 1000000000 / mass_atm / mol_mass_CH4

    AGWP_CO2 = A_CO2 * (p_0 * time_horizon
                        + p_1 * life1_CO2 * (1 - np.exp(-time_horizon / life1_CO2))
                        + p_2 * life2_CO2 * (1 - np.exp(-time_horizon / life2_CO2))
                        + p_3 * life3_CO2 * (1 - np.exp(-time_horizon / life3_CO2)))

    AGTP_CO2 = A_CO2 * (p_0 * (clim_sens1 * (1 - np.exp(-time_horizon / clim_time1)) + clim_sens2 * (
            1 - np.exp(-time_horizon / clim_time2)))
                        + p_1 * life1_CO2 * (clim_sens1 / (life1_CO2 - clim_time1) * (
                    np.exp(-time_horizon / life1_CO2) - np.exp(-time_horizon / clim_time1)) + clim_sens2 / (
                                                     life1_CO2 - clim_time2) * (
                                                     np.exp(-time_horizon / life1_CO2) - np.exp(
                                                 -time_horizon / clim_time2)))
                        + p_2 * life2_CO2 * (clim_sens1 / (life2_CO2 - clim_time1) * (
                    np.exp(-time_horizon / life2_CO2) - np.exp(-time_horizon / clim_time1)) + clim_sens2 / (
                                                     life2_CO2 - clim_time2) * (
                                                     np.exp(-time_horizon / life2_CO2) - np.exp(
                                                 -time_horizon / clim_time2)))
                        + p_1 * life3_CO2 * (clim_sens1 / (life3_CO2 - clim_time1) * (
                    np.exp(-time_horizon / life3_CO2) - np.exp(-time_horizon / clim_time1)) + clim_sens2 / (
                                                     life3_CO2 - clim_time2) * (
                                                     np.exp(-time_horizon / life3_CO2) - np.exp(
                                                 -time_horizon / clim_time2))))

    AGWP_CH4 = A_CH4 * life_CH4 * (1 - np.exp(-time_horizon / life_CH4))

    AGTP_CH4 = A_CH4 * (life_CH4 * clim_sens1 / (life_CH4 - clim_time1) * (
            np.exp(-time_horizon / life_CH4) - np.exp(-time_horizon / clim_time1))
                        + life_CH4 * clim_sens2 / (life_CH4 - clim_time2) * (
                                np.exp(-time_horizon / life_CH4) - np.exp(-time_horizon / clim_time2)))

    GWP_CH4 = AGWP_CH4 / AGWP_CO2
    GTP_CH4 = AGTP_CH4 / AGTP_CO2

    # years to consider in the analysis
    year_vec = input_flux['time']

    CO2_flux = input_flux['CO2_flux']
    CH4_flux = input_flux['CH4_flux']

    # Cumulative net emissions [kg]
    cum_net_emissions = pd.DataFrame(0, index=year_vec,
                                     columns=['CO2_net', 'CH4_net', 'gas1_net', 'gas2_net', 'gas3_net'])
    for index, row in cum_net_emissions.iterrows():
        if index == 0:
            cum_net_emissions.loc[index, 'CO2_net'] = CO2_flux[index]
            cum_net_emissions.loc[index, 'CH4_net'] = CH4_flux[index]
            # Add in new gases too here
        else:
            cum_net_emissions.loc[index, 'CO2_net'] = cum_net_emissions.loc[index - 1, 'CO2_net'] + CO2_flux[index]
            cum_net_emissions.loc[index, 'CH4_net'] = cum_net_emissions.loc[index - 1, 'CH4_net'] + CH4_flux[index]
            # Add in new gases too here

        # Initialize mass in atmosphere dataframe
    mass_in_atm_df = pd.DataFrame(0, index=year_vec, columns=['CO2', 'CH4'])
    # Initialize CO2 atmospheric decay components dataframe
    CO2_mass_df = pd.DataFrame(0, index=year_vec, columns=['mass0', 'mass1', 'mass2', 'mass3', 'CH4_to_CO2'])
    # Initialize radiative forcing dataframe
    irf_df = pd.DataFrame(0, index=year_vec, columns=['CO2_radfor', 'CH4_radfor', 'CO2_IRF', 'CH4_IRF', 'IRF_all'])

    # Calculate the Mass Decay
    for index, row in mass_in_atm_df.iterrows():
        # Calculation for the first timestep
        if index == 0:
            mass_in_atm_df.loc[index, 'CH4'] = CH4_flux[index]
            CO2_mass_df.loc[index, 'mass0'] = p_0 * CO2_flux[index]
            CO2_mass_df.loc[index, 'mass1'] = p_1 * CO2_flux[index]
            CO2_mass_df.loc[index, 'mass2'] = p_2 * CO2_flux[index]
            CO2_mass_df.loc[index, 'mass3'] = p_3 * CO2_flux[index]
            CO2_mass_df.loc[index, 'CH4_to_CO2'] = 0
        # Calculation for the start + 1 to end timesteps
        else:
            mass_in_atm_df.loc[index, 'CH4'] = CH4_flux[index] + mass_in_atm_df.loc[index - 1, 'CH4'] * np.exp(
                -1 / life_CH4)
            CO2_mass_df.loc[index, 'mass0'] = p_0 * (CO2_flux[index] + CO2_mass_df.loc[index, 'CH4_to_CO2']) + \
                                              CO2_mass_df.loc[index - 1, 'mass0']
            CO2_mass_df.loc[index, 'mass1'] = p_1 * (CO2_flux[index] + CO2_mass_df.loc[index, 'CH4_to_CO2']) + \
                                              CO2_mass_df.loc[index - 1, 'mass1'] * np.exp(-1 / life1_CO2)
            CO2_mass_df.loc[index, 'mass2'] = p_2 * (CO2_flux[index] + CO2_mass_df.loc[index, 'CH4_to_CO2']) + \
                                              CO2_mass_df.loc[index - 1, 'mass2'] * np.exp(-1 / life2_CO2)
            CO2_mass_df.loc[index, 'mass3'] = p_3 * (CO2_flux[index] + CO2_mass_df.loc[index, 'CH4_to_CO2']) + \
                                              CO2_mass_df.loc[index - 1, 'mass3'] * np.exp(-1 / life3_CO2)
            if fossil_CH4 == True:
                CO2_mass_df.loc[index, 'CH4_to_CO2'] = mass_in_atm_df.loc[index - 1, 'CH4'] * (
                        1 - np.exp(-1 / life_CH4)) * CH4_to_CO2
            elif fossil_CH4 == False:
                CO2_mass_df.loc[index, 'CH4_to_CO2'] = 0
        mass_in_atm_df.loc[index, 'CO2'] = CO2_mass_df.loc[index, 'mass0'] + CO2_mass_df.loc[index, 'mass1'] + \
                                           CO2_mass_df.loc[index, 'mass2'] + CO2_mass_df.loc[index, 'mass3']

    # Calculate the radiative forcing (instantaneous just after start of year), [W m^-2]
    irf_df['CO2_radfor'] = A_CO2 * mass_in_atm_df['CO2']
    irf_df['CH4_radfor'] = A_CH4 * mass_in_atm_df['CH4']

    # Calculate integrated radiative forcing [W-year m^-2]
    for index, row in irf_df.iterrows():
        if index == 0:
            irf_df.loc[index, 'CO2_IRF'] = 0
            irf_df.loc[index, 'CH4_IRF'] = 0
        else:
            irf_df.loc[index, 'CO2_IRF'] = irf_df.loc[index - 1, 'CO2_IRF'] + A_CO2 * (
                    CO2_mass_df.loc[index - 1, 'mass0'] +
                    CO2_mass_df.loc[index - 1, 'mass1'] * life1_CO2 * (1 - np.exp(-1 / life1_CO2)) +
                    CO2_mass_df.loc[index - 1, 'mass2'] * life2_CO2 * (1 - np.exp(-1 / life2_CO2)) +
                    CO2_mass_df.loc[index - 1, 'mass3'] * life3_CO2 * (1 - np.exp(-1 / life3_CO2))
            )
            irf_df.loc[index, 'CH4_IRF'] = irf_df.loc[index - 1, 'CH4_IRF'] + mass_in_atm_df.loc[
                index - 1, 'CH4'] * A_CH4 * life_CH4 * (1 - np.exp(-1 / life_CH4))

    irf_df['IRF_all'] = irf_df['CO2_IRF'] + irf_df['CH4_IRF']

    # Temperature change components (two-part climate response model)
    # Initialize the temperature change dataframe
    temp_change_df = pd.DataFrame(0, index=year_vec,
                                  columns=['CO2_temp_s1', 'CO2_temp_s2', 'CH4_temp_s1', 'CH4_temp_s2', 'CO2_temp',
                                           'CH4_temp', 'temp_change'])
    for index, row in temp_change_df.iterrows():
        if index == 0:
            temp_change_df.loc[index, 'CO2_temp_s1'] = 0
            temp_change_df.loc[index, 'CO2_temp_s2'] = 0
            temp_change_df.loc[index, 'CH4_temp_s1'] = 0
            temp_change_df.loc[index, 'CH4_temp_s2'] = 0
            temp_change_df.loc[index, 'CO2_temp'] = 0
            temp_change_df.loc[index, 'CH4_temp'] = 0
        else:
            temp_change_df.loc[index, 'CO2_temp_s1'] = A_CO2 * (
                    CO2_mass_df.loc[index - 1, 'mass0'] * clim_sens1 * (1 - np.exp(-1 / clim_time1))
                    + CO2_mass_df.loc[index - 1, 'mass1'] * clim_sens1 * life1_CO2 / (life1_CO2 - clim_time1) * (
                            np.exp(-1 / life1_CO2) - np.exp(-1 / clim_time1))
                    + CO2_mass_df.loc[index - 1, 'mass2'] * clim_sens1 * life2_CO2 / (life2_CO2 - clim_time1) * (
                            np.exp(-1 / life2_CO2) - np.exp(-1 / clim_time1))
                    + CO2_mass_df.loc[index - 1, 'mass3'] * clim_sens1 * life3_CO2 / (life3_CO2 - clim_time1) * (
                            np.exp(-1 / life3_CO2) - np.exp(-1 / clim_time1))) + \
                                                       temp_change_df.loc[index - 1, 'CO2_temp_s1'] * np.exp(
                -1 / clim_time1)
            temp_change_df.loc[index, 'CO2_temp_s2'] = A_CO2 * (
                    CO2_mass_df.loc[index - 1, 'mass0'] * clim_sens2 * (1 - np.exp(-1 / clim_time2))
                    + CO2_mass_df.loc[index - 1, 'mass1'] * clim_sens2 * life1_CO2 / (life1_CO2 - clim_time2) * (
                            np.exp(-1 / life1_CO2) - np.exp(-1 / clim_time2))
                    + CO2_mass_df.loc[index - 1, 'mass2'] * clim_sens2 * life2_CO2 / (life2_CO2 - clim_time2) * (
                            np.exp(-1 / life2_CO2) - np.exp(-1 / clim_time2))
                    + CO2_mass_df.loc[index - 1, 'mass3'] * clim_sens2 * life3_CO2 / (life3_CO2 - clim_time2) * (
                            np.exp(-1 / life3_CO2) - np.exp(-1 / clim_time2))) + \
                                                       temp_change_df.loc[index - 1, 'CO2_temp_s2'] * np.exp(
                -1 / clim_time2)
            temp_change_df.loc[index, 'CH4_temp_s1'] = A_CH4 * mass_in_atm_df.loc[
                index - 1, 'CH4'] * clim_sens1 * life_CH4 / (life_CH4 - clim_time1) * (
                                                               np.exp(-1 / life_CH4) - np.exp(-1 / clim_time1)) + \
                                                       temp_change_df.loc[index - 1, 'CH4_temp_s1'] * np.exp(
                -1 / clim_time1)
            temp_change_df.loc[index, 'CH4_temp_s2'] = A_CH4 * mass_in_atm_df.loc[
                index - 1, 'CH4'] * clim_sens2 * life_CH4 / (life_CH4 - clim_time2) * (
                                                               np.exp(-1 / life_CH4) - np.exp(-1 / clim_time2)) + \
                                                       temp_change_df.loc[index - 1, 'CH4_temp_s2'] * np.exp(
                -1 / clim_time2)
            temp_change_df.loc[index, 'CO2_temp'] = temp_change_df.loc[index, 'CO2_temp_s1'] + temp_change_df.loc[
                index, 'CO2_temp_s2']
            temp_change_df.loc[index, 'CH4_temp'] = temp_change_df.loc[index, 'CH4_temp_s1'] + temp_change_df.loc[
                index, 'CH4_temp_s2']

    temp_change_df['temp_change'] = temp_change_df['CO2_temp'] + temp_change_df['CH4_temp'].fillna(0)

    # load in supporting data
    AGWP_df_sup = pd.read_csv('DLCA/data/AGWP_supp_data.csv')
    AGTP_df_sup = pd.read_csv('DLCA/data/AGTP_supp_data.csv')
    # AGWP_df_sup = pd.read_excel('./DLCA_supp_data.xlsx', sheet_name='AGWP', index_col='year')  # [W yr m^-2]
    # AGTP_df_sup = pd.read_excel('./DLCA_supp_data.xlsx', sheet_name='AGTP', index_col='year')  # [delta-K]

    # AGWP and AGTP in reverse-order from year X (the time-horizon)
    AGWP_AGTP_rev = pd.DataFrame(0, index=year_vec,
                                 columns=['CO2_AGWP_rev', 'CH4_AGWP_rev', 'CO2_AGTP_rev', 'CH4_AGTP_rev'])
    AGWP_AGTP_rev['CO2_AGWP_rev'] = pd.concat(
        (AGWP_df_sup.loc[0:time_horizon, 'CO2_AGWP'][::-1], pd.Series(year_vec[time_horizon + 1:] * 0))).reset_index(
        drop=True)
    AGWP_AGTP_rev['CH4_AGWP_rev'] = pd.concat(
        (AGWP_df_sup.loc[0:time_horizon, 'CH4_AGWP'][::-1], pd.Series(year_vec[time_horizon + 1:] * 0))).reset_index(
        drop=True)
    AGWP_AGTP_rev['CO2_AGTP_rev'] = pd.concat(
        (AGTP_df_sup.loc[0:time_horizon, 'CO2_AGTP'][::-1], pd.Series(year_vec[time_horizon + 1:] * 0))).reset_index(
        drop=True)
    AGWP_AGTP_rev['CH4_AGTP_rev'] = pd.concat(
        (AGTP_df_sup.loc[0:time_horizon, 'CH4_AGTP'][::-1], pd.Series(year_vec[time_horizon + 1:] * 0))).reset_index(
        drop=True)

    # Equivalency summary dataframe
    # equiv_df = pd.DataFrame(0, index=year_vec, columns=['irf_GWP_slidingTH', 'GTP_slidingTH', 'CO2_AGTP_rev', 'CH4_AGTP_rev'])

    equiv_df = pd.DataFrame(0, index=year_vec, columns=['LCA_dyn', 'LCA_static'])
    equiv_df['LCA_dyn'] = irf_df['IRF_all'] / AGWP_CO2
    equiv_df['LCA_static'] = cum_net_emissions['CO2_net'] + cum_net_emissions[
        'CH4_net'] * GWP_CH4  # add in more gasses here if desired

    return mass_in_atm_df, irf_df, temp_change_df, equiv_df


mass_in_atm_sawnwood, irf_sawnwood, temp_change_sawnwood, equiv_sawnwood = DLCA_calc(input_flux=flux_sawnwood, time_horizon=100)
mass_in_atm_glulam, irf_glulam, temp_change_glulam, equiv_glulam = DLCA_calc(input_flux=flux_glulam, time_horizon=100)
mass_in_atm_clt, irf_clt, temp_change_clt, equiv_clt = DLCA_calc(input_flux=flux_clt, time_horizon=100)
mass_in_atm_bamboo, irf_bamboo, temp_change_bamboo, equiv_bamboo = DLCA_calc(input_flux=flux_bamboo, time_horizon=100)
mass_in_atm_hemp, irf_hemp, temp_change_hemp, equiv_hemp = DLCA_calc(input_flux=flux_hemp, time_horizon=100)
mass_in_atm_straw, irf_straw, temp_change_straw, equiv_straw = DLCA_calc(input_flux=flux_straw, time_horizon=100)
mass_in_atm_cork, irf_cork, temp_change_cork, equiv_cork = DLCA_calc(input_flux=flux_cork, time_horizon=100)
mass_in_atm_concrete, irf_concrete, temp_change_concrete, equiv_concrete = DLCA_calc(input_flux=flux_concrete, time_horizon=100)
mass_in_atm_steel, irf_steel, temp_change_steel, equiv_steel = DLCA_calc(input_flux=flux_steel, time_horizon=100)

# Plot all of the scenarios together

SUMMARY_temp = pd.DataFrame({'Sawnwood':temp_change_sawnwood['temp_change'],
                             'Glulam':temp_change_glulam['temp_change'],
                             'CLT':temp_change_clt['temp_change'],
                             'Bamboo':temp_change_bamboo['temp_change'],
                             'Hemp':temp_change_hemp['temp_change'],
                             'Straw':temp_change_straw['temp_change'],
                             'Cork':temp_change_cork['temp_change'],
                             'Concrete':temp_change_concrete['temp_change'],
                             'Steel':temp_change_steel['temp_change'],
                             })

SUMMARY_equiv = pd.DataFrame({'Sawnwood':equiv_sawnwood['LCA_dyn'],
                              'Glulam':equiv_glulam['LCA_dyn'],
                              'CLT': equiv_clt['LCA_dyn'],
                              'Bamboo':equiv_bamboo['LCA_dyn'],
                              'Hemp':equiv_hemp['LCA_dyn'],
                              'Straw':equiv_straw['LCA_dyn'],
                              'Cork':equiv_cork['LCA_dyn'],
                              'Concrete':equiv_concrete['LCA_dyn'],
                              'Steel':equiv_steel['LCA_dyn'],
                              })

# Plot the temperature change effect
year_to_end_plot = 81
SUMMARY_temp_plot = SUMMARY_temp[0:year_to_end_plot]
SUMMARY_temp_plot = SUMMARY_temp_plot.assign(year = np.linspace(start=2020, stop=(2020+year_to_end_plot-1), num=(year_to_end_plot)))
SUMMARY_temp_plot = SUMMARY_temp_plot.set_index('year')

SUMMARY_equiv_plot = SUMMARY_equiv[0:year_to_end_plot]
SUMMARY_equiv_plot = SUMMARY_equiv_plot.assign(year = np.linspace(start=2020, stop=(2020+year_to_end_plot-1), num=(year_to_end_plot)))
SUMMARY_equiv_plot = SUMMARY_equiv_plot.set_index('year')

plt.figure(figsize=(8, 6))
plt.plot(SUMMARY_temp_plot['Sawnwood'], color='#3C1642', label='Sawnwood')
plt.plot(SUMMARY_temp_plot['Glulam'], color='#223D5C', label='Glulam')
plt.plot(SUMMARY_temp_plot['CLT'], color='#086375', label='CLT')
plt.plot(SUMMARY_temp_plot['Cork'], color='#29CC00', label='Cork')
plt.plot(SUMMARY_temp_plot['Bamboo'], color='#139B93', label='Bamboo', linestyle='--')
plt.plot(SUMMARY_temp_plot['Hemp'], color='#117E68', label='Hemp', linestyle='--')
plt.plot(SUMMARY_temp_plot['Straw'], color='#8EF104', label='Straw', linestyle='--')
# plt.plot(SUMMARY_temp_plot['Concrete'], color='gray', label='Concrete')
# plt.plot(SUMMARY_temp_plot['Steel'], color='purple', label='Steel')
plt.axhline(y=0, color='black', linestyle='--')
plt.legend()
plt.ylabel('$\Delta K$', fontsize=14)
plt.xlabel('Time', fontsize=14)
plt.savefig('Temp_Change.png', dpi=440)


plt.figure()
plt.plot(SUMMARY_equiv_plot['Sawnwood'], color='#3C1642', label='Sawnwood')
plt.plot(SUMMARY_equiv_plot['Glulam'], color='#223D5C', label='Glulam', linestyle='--')
plt.plot(SUMMARY_equiv_plot['CLT'], color='#086375', label='CLT')
plt.plot(SUMMARY_equiv_plot['Bamboo'], color='#139B93', label='Bamboo')
plt.plot(SUMMARY_equiv_plot['Hemp'], color='#117E68', label='Hemp', linestyle='--')
plt.plot(SUMMARY_equiv_plot['Straw'], color='#8EF104', label='Straw')
plt.plot(SUMMARY_equiv_plot['Cork'], color='#29CC00', label='Cork', linestyle='--')
# plt.plot(SUMMARY_equiv_plot['Concrete'], color='gray', label='Concrete')
# plt.plot(SUMMARY_equiv_plot['Steel'], color='purple', label='Steel')
plt.axhline(y=0, color='black', linestyle='--')
plt.legend()
plt.ylabel('$kg CO_2 e$', fontsize=14)
plt.xlabel('Time', fontsize=14)
# plt.savefig('LCA_dyn.png', dpi=440)


