import unittest
from DLCA import DLCA

class MyTestCase(unittest.TestCase):

    def test_AnalysisPeriod(self):
        print('Checking analysis period creation..')
        test_analysisperiod = DLCA.AnalysisPeriod(0, 500)
        start_of_vec = test_analysisperiod.year_vec[0]
        end_of_vec = test_analysisperiod.year_vec[-1]
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
        my_mat_emissions_NO2 = DLCA.EmissionsInventoryGHGi(material=DLCA.MaterialTypes.TEST,
                                                       ghg=DLCA.GHGTypes.N2O,
                                                       emissions_A=1/298,
                                                       emissions_B=0,
                                                       emissions_C=1/298)
        my_emissions_all = DLCA.EmissionsInventoryAllGHG(CO2=my_mat_emissions_CO2, CH4=my_mat_emissions_CH4, N2O=my_mat_emissions_NO2)

        flux_mat_1 = DLCA.EmissionsFluxEngine.create_flux_mat(material=DLCA.MaterialTypes.TEST,
                                                                        time=DLCA.AnalysisPeriod(0, 500),
                                                                        timing=DLCA.EmissionsTiming(bldg_lifespan=60),
                                                                        emissions_inv=my_emissions_all)
        self.assertEqual(flux_mat_1.flux_df['CO2_flux'][0], 1, msg='.. Creation of single material ghg flux incorrect')

        flux_mat_2 = DLCA.EmissionsFluxEngine.create_flux_mat(material=DLCA.MaterialTypes.TEST,
                                                                        time=DLCA.AnalysisPeriod(0, 500),
                                                                        timing=DLCA.EmissionsTiming(bldg_lifespan=60),
                                                                        emissions_inv=my_emissions_all)
        flux_total = DLCA.EmissionsFluxEngine.flux_total([flux_mat_1, flux_mat_2])

        self.assertEqual(2, flux_total.flux_df["CO2_flux"][0], msg='.. Creation of total flux object incorrect')


    def test_

if __name__ == '__main__':
    unittest.main()
