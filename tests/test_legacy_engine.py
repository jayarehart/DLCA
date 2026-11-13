import unittest
from dlca import engine as DLCA
from dlca.models import *


class MyTestCase(unittest.TestCase):

    def test_AnalysisPeriod(self):
        print('Checking analysis period creation..')
        test_analysisperiod = DLCA.AnalysisPeriod(0, 500)
        start_of_vec = test_analysisperiod.years_vec[0]
        end_of_vec = test_analysisperiod.years_vec[-1]
        print('Start of analysis period ..', str(start_of_vec))
        print('Start of analysis period ..', str(end_of_vec))
        self.assertEqual(start_of_vec, 0)
        self.assertEqual(end_of_vec, 500)

    def test_create_flux_mat(self):
        print('Checking the creation of a carbon flux for a set of materials..')
        my_mat_emissions_CO2 = DLCA.EmissionsInventoryGHGi(material=DLCA.MaterialTypes.TEST,
                                                       ghg=DLCA.GHGTypes.CO2,
                                                       emissions_A=1,
                                                       emissions_B=0,
                                                       emissions_C=1)
        my_mat_emissions_CH4 = DLCA.EmissionsInventoryGHGi(material=DLCA.MaterialTypes.TEST,
                                                       ghg=DLCA.GHGTypes.CH4,
                                                       emissions_A=1/25,
                                                       emissions_B=0,
                                                       emissions_C=1/25)
        my_mat_emissions_N2O = DLCA.EmissionsInventoryGHGi(material=DLCA.MaterialTypes.TEST,
                                                       ghg=DLCA.GHGTypes.N2O,
                                                       emissions_A=1/298,
                                                       emissions_B=0,
                                                       emissions_C=1/298)
        my_emissions_all = DLCA.EmissionsInventoryAllGHG(CO2=my_mat_emissions_CO2, CH4=my_mat_emissions_CH4, N2O=my_mat_emissions_N2O)

        flux_mat_1 = DLCA.EmissionsFluxEngine.create_flux_mat(material=DLCA.MaterialTypes.TEST,
                                                              time=DLCA.AnalysisPeriod(0, 500),
                                                              timing=DLCA.MatEmissionsTiming(bldg_lifespan=60),
                                                              emissions_inv=my_emissions_all)
        self.assertEqual(flux_mat_1.flux_df['CO2_flux'][0], 1, msg='.. Creation of single material ghg flux incorrect')

        flux_mat_2 = DLCA.EmissionsFluxEngine.create_flux_mat(material=DLCA.MaterialTypes.TEST,
                                                              time=DLCA.AnalysisPeriod(0, 500),
                                                              timing=DLCA.MatEmissionsTiming(bldg_lifespan=60),
                                                              emissions_inv=my_emissions_all)
        flux_total = DLCA.EmissionsFluxEngine.flux_total([flux_mat_1, flux_mat_2])

        self.assertEqual(2, flux_total.flux_df["CO2_flux"][0], msg='.. Creation of total flux object incorrect')


    def test_DLCAEngine_calc_decay(self):
        print('Checking the decay function..')
        my_mat_emissions_CO2 = DLCA.EmissionsInventoryGHGi(material=DLCA.MaterialTypes.TEST, ghg=DLCA.GHGTypes.CO2, emissions_A=1,emissions_B=0, emissions_C=0)
        my_mat_emissions_CH4 = DLCA.EmissionsInventoryGHGi(material=DLCA.MaterialTypes.TEST, ghg=DLCA.GHGTypes.CH4, emissions_A=1/25,emissions_B=0, emissions_C=0)
        my_mat_emissions_NO2 = DLCA.EmissionsInventoryGHGi(material=DLCA.MaterialTypes.TEST, ghg=DLCA.GHGTypes.N2O, emissions_A=1 / 298, emissions_B=0, emissions_C=0)
        my_emissions_all = DLCA.EmissionsInventoryAllGHG(CO2=my_mat_emissions_CO2, CH4=my_mat_emissions_CH4, N2O=my_mat_emissions_NO2)

        flux_mat_test = DLCA.EmissionsFluxEngine.create_flux_mat(material=DLCA.MaterialTypes.TEST,
                                                                 time=DLCA.AnalysisPeriod(0, 500),
                                                                 timing=DLCA.MatEmissionsTiming(bldg_lifespan=60),
                                                                 emissions_inv=my_emissions_all)

        my_DLCAEngine = DLCA.DLCAEngine()
        my_DLCAEngine.calc_decay(input_flux=flux_mat_test)

        self.assertAlmostEqual(sum(my_DLCAEngine.Results.mass_in_atm_df['CO2']), 184.2837146985627, places=9, msg='.. Decay of CO2 is calculated incorrectly')
        self.assertAlmostEqual(sum(my_DLCAEngine.Results.mass_in_atm_df['CH4']), 0.5162687880706308, places=9, msg='.. Decay of CH4 is calculated incorrectly')
        self.assertAlmostEqual(sum(my_DLCAEngine.Results.mass_in_atm_df['N2O']), 0.40123157841290424, places=9, msg='.. Decay of N2O is calculated incorrectly')


    def test_DLCAEngine_calc_warming(self):
        print('Checking the calculation of AGTP and AGWP..')
        my_mat_emissions_CO2 = DLCA.EmissionsInventoryGHGi(material=DLCA.MaterialTypes.TEST, ghg=DLCA.GHGTypes.CO2,
                                                           emissions_A=1, emissions_B=0, emissions_C=0)
        my_mat_emissions_CH4 = DLCA.EmissionsInventoryGHGi(material=DLCA.MaterialTypes.TEST, ghg=DLCA.GHGTypes.CH4,
                                                           emissions_A=1 / 25, emissions_B=0, emissions_C=0)
        my_mat_emissions_N2O = DLCA.EmissionsInventoryGHGi(material=DLCA.MaterialTypes.TEST, ghg=DLCA.GHGTypes.N2O,
                                                           emissions_A=1 / 298, emissions_B=0, emissions_C=0)
        my_emissions_all = DLCA.EmissionsInventoryAllGHG(CO2=my_mat_emissions_CO2, CH4=my_mat_emissions_CH4,
                                                         N2O=my_mat_emissions_N2O)

        flux_mat_test = DLCA.EmissionsFluxEngine.create_flux_mat(material=DLCA.MaterialTypes.TEST,
                                                                 time=DLCA.AnalysisPeriod(0, 500),
                                                                 timing=DLCA.MatEmissionsTiming(bldg_lifespan=60),
                                                                 emissions_inv=my_emissions_all)

        my_DLCAEngine = DLCA.DLCAEngine()
        my_DLCAEngine.calc_decay(input_flux=flux_mat_test)
        my_DLCAEngine.calc_AGWP(time_horizon=100)
        my_DLCAEngine.calc_AGTP(time_horizon=100)

        # N2O has not been added to the AGTP or the AGWP calculations

        self.assertAlmostEqual(my_DLCAEngine.Results.temp_change_df['temp_change'][100], 1.0700561631626676E-15, delta=1e-12 * abs(1.0700561631626676E-15), msg='.. AGTP is calculated incorrectly')
        self.assertAlmostEqual(my_DLCAEngine.Results.equiv_df['LCA_dyn'][100], 3.0267395007015145, places=9, msg='.. AGWP is calculated incorrectly')


    def test_loadEUI_loadEF(self):
        print('Testing the cvs lookup for getting the EUI and EFs')
        my_bldg = BldgDetails(use_type=BldgUseType.SMALLOFFICE,
                              heating_system=ResHeatSystem.NONE,
                              climate_zone=ClimateZone._2B,
                              eGrid=USSubgrid.RMPA,
                              area_m2=15000,
                              lifespan=60,
                              scenario=Scenario.S1)

        # my_bldg.load_EUI()
        self.assertNotEqual(my_bldg.ref_bldg.naturalgas_site_GJ,None,msg='No EUI looked up')
        self.assertNotEqual(my_bldg.ref_bldg.electricity_site_GJ, None, msg='No EUI looked up')
        self.assertNotEqual(my_bldg.ref_bldg.fueloilno2_kBtu, None, msg='No EUI looked up')

        # my_bldg.load_EF()
        self.assertNotEqual(my_bldg.EF_electricity, None, msg='No EF looked up')
        self.assertNotEqual(my_bldg.EF_naturalgas, None, msg='No EF looked up')
        self.assertNotEqual(my_bldg.EF_fueloilno2, None, msg='No EF looked up')


if __name__ == '__main__':
    unittest.main()
