import unittest
from DLCA import DLCA

class MyTestCase(unittest.TestCase):

    def test_AnalysisPeriod(self):
        print('Checking analysis period creation..')
        test_analysisperiod = DLCA.AnaysisPeriod(0,500)
        start_of_vec = test_analysisperiod.year_vec[0]
        end_of_vec = test_analysisperiod.year_vec[-1]
        print('Start of analysis period ..', str(start_of_vec))
        print('Start of analysis period ..', str(end_of_vec))
        self.assertEqual(start_of_vec, 0)
        self.assertEqual(end_of_vec, 500)

    def test_create_fux_mat(self):

        my_emissions_CO2 = DLCA.EmissionsInventoryGHGi(material=DLCA.MaterialTypes.TEST,
                                                       ghg=DLCA.GHGTypes.CO2,
                                                       emissions_A=1,
                                                       emissions_B=0,
                                                       emissions_C=0)
        my_emissions_CH4 = DLCA.EmissionsInventoryGHGi(material=DLCA.MaterialTypes.TEST,
                                                       ghg=DLCA.GHGTypes.CH4,
                                                       emissions_A=1/25,
                                                       emissions_B=0,
                                                       emissions_C=0)
        my_emissions_NO2 = DLCA.EmissionsInventoryGHGi(material=DLCA.MaterialTypes.TEST,
                                                       ghg=DLCA.GHGTypes.N2O,
                                                       emissions_A=1/298,
                                                       emissions_B=0,
                                                       emissions_C=0)
        my_emissions_all = DLCA.EmissionsInventoryAllGHG(CO2=my_emissions_CO2, CH4=my_emissions_CH4, N2O=my_emissions_NO2)

        my_EmissionsFluxEngine = DLCA.EmissionsFluxEngine()
        my_EmissionsFluxEngine = my_EmissionsFluxEngine.create_flux_mat(material=DLCA.MaterialTypes.STEEL,
                                               time=DLCA.AnaysisPeriod(0,500),
                                               timing=DLCA.EmissionsTiming(bldg_lifespan=60),
                                               emissions_inv=my_emissions_all)



        self.assertEqual(True, False)  # add assertion here


if __name__ == '__main__':
    unittest.main()
