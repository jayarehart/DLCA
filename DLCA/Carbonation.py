from DLCA.carb_models import *

#Establish the structure of the concrete element being studied and some inputs for the carbonation model
class StructureEngine:
    @staticmethod
    def create_structure(dim: Geometry) -> StructureDim:
        if dim.shape == Shape.REC:
            volume = dim.width * dim.length * dim.height
        elif dim.shape == Shape.CYLINDER:
            volume = np.pi * (dim.radius ** 2) * dim.height
        elif dim.shape == Shape.SPHERE:
            volume = (4 / 3) * np.pi * dim.radius ** 3

        if dim.shape == Shape.REC:
            SA = 2 * (dim.width + dim.length * dim.height + dim.width * dim.height)
        elif dim.shape == Shape.CYLINDER:
            SA = 2 * np.pi * dim.radius * dim.height + 2 * np.pi * dim.radius ** 2
        elif dim.shape == Shape.SPHERE:
            SA = 4 * np.pi * dim.radius ** 2

        res = StructureDim(dim, volume, SA)
        return res

    @staticmethod
    def model_inputs(time: ServiceLife, mix: ConcreteComponents, structure: StructureDim, enviro: EnvironmentalInputs)->Inputs:
        if mix.mix['Cement Type'] == CementType.I or mix.mix['Cement Type'] == CementType.II:
            R = 0.0016 * mix.mix['Compressive Strength'] ** 3.106
        else:
            R = 0.0018 * mix.mix['Compressive Strength'] ** 2.862

        enviro.en_inputs['R'] = R
        res = Inputs(time, mix, structure.structure_df, enviro.en_inputs)
        return (res)

# carbonation engine that runs the carbonation model; considering both CH and CSH as well as an updated way for calculating the carbonated volume
class CarbonationEngine:

    @staticmethod
    def calc_carbonation(inputs: Inputs) -> ModelResults:

        x = np.sqrt(2 * inputs.inputs_df['CO2 Concentration']* inputs.time.years_vec / inputs.inputs_df['R']) * (
                np.sqrt(inputs.inputs_df['k0'] * inputs.inputs_df['k1'] * inputs.inputs_df['k2']) * (
                1 / inputs.time.years_vec) ** inputs.inputs_df['n'])

        if inputs.inputs_df['Geometry'] == Shape.REC:
            if inputs.inputs_df['Faces Exposed'] == Faces.ALL:
                uncarb_volume = (inputs.inputs_df['Length (m)'] - 2 * x) * (inputs.inputs_df['Width (m)'] - 2 * x) * \
                                inputs.inputs_df['Height (m)']
            elif inputs.inputs_df['Faces Exposed'] == Faces.LENGTH_ONLY:
                uncarb_volume = (inputs.inputs_df['Length (m)']) * (inputs.inputs_df['Width (m)'] - 2 * x) * \
                                inputs.inputs_df['Height (m)']
            elif inputs.inputs_df['Faces Exposed'] == Faces.WIDTH_ONLY:
                uncarb_volume = (inputs.inputs_df['Length (m)'] - 2 * x) * (inputs.inputs_df['Width (m)']) * \
                                inputs.inputs_df['Height (m)']
            elif inputs.inputs_df['Faces Exposed'] == Faces.ONE_FACE:
                uncarb_volume = (inputs.inputs_df['Length (m)'] - x) * (inputs.inputs_df['Width (m)']) * \
                                inputs.inputs_df['Height (m)']
        elif inputs.inputs_df['Geometry'] == Shape.CYLINDER:
            uncarb_volume = (np.pi * (
                    inputs.inputs_df['Radius (m)'] - x) ** 2) * inputs.inputs_df['Height (m)']
        elif inputs.inputs_df['Geometry'] == Shape.SPHERE:
            uncarb_volume = (4 / 3) * np.pi * (inputs.inputs_df['Radius (m)'] - x) ** 3

        carbonated_volume = np.where(
            inputs.inputs_df['Volume (m3)'] - uncarb_volume > inputs.inputs_df['Volume (m3)'],
            inputs.inputs_df['Volume (m3)'],
            inputs.inputs_df['Volume (m3)'] - uncarb_volume)

        if inputs.inputs_df['Cement Type'] == CementType.I:
            alpha__CH = 0.165
            alpha__CSH = 0.225
        elif inputs.inputs_df['Cement Type'] == CementType.II:
            alpha__CH = 0.163
            alpha__CSH = 0.240
        elif inputs.inputs_df['Cement Type'] == CementType.III:
            alpha__CH = 0.166
            alpha__CSH = 0.224
        elif inputs.inputs_df['Cement Type'] == CementType.IV:
            alpha__CH = 0.135
            alpha__CSH = 0.244
        elif inputs.inputs_df['Cement Type'] == CementType.V:
            alpha__CH = 0.161
            alpha__CSH = 0.240
        elif inputs.inputs_df['Cement Type'] == CementType.White:
            alpha__CH = 0.203
            alpha__CSH = 0.251

        if inputs.inputs_df['SCM Type'] == SCMType.NONE:
            S = 0
        elif inputs.inputs_df['SCM Type'] == SCMType.FLYASH_F:
            S = 50 / 100
        elif inputs.inputs_df['SCM Type'] == SCMType.FLYASH_C:
            S = 25 / 100
        elif inputs.inputs_df['SCM Type'] == SCMType.SLAG:
            S = 35 / 100
        elif inputs.inputs_df['SCM Type'] == SCMType.SILICAFUME:
            S = 90 / 100
        elif inputs.inputs_df['SCM Type'] == SCMType.METAKAOLIN:
            S = 50 / 100

        K_s = S * inputs.inputs_df['SCM % Replacement']
        M_CH = 74.09
        M_CO2 = 44.01
        M_CaO = 56.0774  # g/mol
        Q = S / (alpha__CH * (M_CH / M_CO2))

        if Q >= 0.5406:
            beta__CH = alpha__CH
            beta__CSH = 0.594 * alpha__CH * (M_CH / M_CO2)
        elif Q < 0.5406:
            beta__CH = 1.099 * K_s
            beta__CSH = 1.099 * K_s
        elif Q == 0:
            beta__CH = 0
            beta__CSH = 0

        C_m_CH = alpha__CH - beta__CH * inputs.inputs_df['SCM % Replacement']
        C_m_CSH = alpha__CSH + beta__CSH * inputs.inputs_df['SCM % Replacement']

        cs_ch = inputs.inputs_df['phi_c'] * C_m_CH * inputs.inputs_df[
            'Total Mass of Binder (kg / m3 of concrete)'] * carbonated_volume

        cs_csh = inputs.inputs_df['phi_c'] *C_m_CSH * inputs.inputs_df[
                                 'Total Mass of Binder (kg / m3 of concrete)'] * carbonated_volume

        carbon_sequestered = inputs.inputs_df['phi_c'] * (C_m_CH * inputs.inputs_df[
            'Total Mass of Binder (kg / m3 of concrete)'] * carbonated_volume + C_m_CSH * inputs.inputs_df[
                                 'Total Mass of Binder (kg / m3 of concrete)'] * carbonated_volume)
        cs_lagerblad = 0.75 * inputs.inputs_df['Total Mass of Binder (kg / m3 of concrete)'] * carbonated_volume * (
                    M_CO2 / M_CaO)
        cs_pulses = np.diff(carbon_sequestered)
        cs_pulses = np.append(carbon_sequestered[0], cs_pulses)
        cs_pulses = cs_pulses * (-1)
        res = ModelResults(inputs.inputs_df['Name'], inputs.time.years_vec, x, uncarb_volume, carbonated_volume,cs_ch,cs_csh,
                           cs_lagerblad, carbon_sequestered, cs_pulses)

        return res

#HAS THE DIFFERENT END OF LIFE SCENARIOS
# ADD A NEW SCNARIO FOR ANAEROBIC LANDFILL (OXYGEN REMOVED)
class EoLEngine:

    @staticmethod
    def choose_scenario(eol: EoLScenario, carb: ModelResults, same_input: Inputs, time: EoLTime)-> EoLResults:
        if eol == EoLScenario.S1:
            #crush and stockpile
            geometry = Geometry(shape=Shape.SPHERE, radius=0.05)
            structures = StructureEngine.create_structure(geometry)
            S1_envi_inputs = EnvironmentalInputs(exposure_class=XC.III, carb_atm_conc=400)
            eol_input = StructureEngine.model_inputs(time, same_input.mix, structures, S1_envi_inputs)
            # eol_input = Inputs(time, same_input.mix, structures.structure_df, S1_envi_inputs.en_inputs)
            num_of_spheres = (carb.results['volume left'][-1] / eol_input.inputs_df['Volume (m3)'])
            eol_carb = CarbonationEngine.calc_carbonation(eol_input)
            sphere_pulse = eol_carb.pulses * num_of_spheres
            sphere_carb = eol_carb.carb_seq * num_of_spheres

            res = EoLResults(eol,carb.results,eol_carb.carb_seq_CH,eol_carb.carb_seq_CSH, sphere_carb, sphere_pulse)
        elif eol == EoLScenario.S2:
            #leave as is
            S2_inputs = Inputs(ServiceLife(1,(same_input.time.end_year + time.end_year)), same_input.mix, same_input.structure, same_input.envi_inputs)
            S2_carb = CarbonationEngine.calc_carbonation(S2_inputs)
            landfill_pulse = S2_carb.pulses[60:]
            res = EoLResults(eol,S2_carb.results,eol_pulses=landfill_pulse)
        elif eol == EoLScenario.S3:
            #crush and bury
            geometry = Geometry(shape=Shape.SPHERE, radius=0.05)
            structures = StructureEngine.create_structure(geometry)
            S3_envi_inputs = EnvironmentalInputs(exposure_class=XC.II,carb_atm_conc=260)
            eol_input = StructureEngine.model_inputs(time,same_input.mix,structures,S3_envi_inputs)
            num_of_spheres = (carb.results['volume left'][-1] / eol_input.inputs_df['Volume (m3)'])
            eol_carb = CarbonationEngine.calc_carbonation(eol_input)
            sphere_pulse = eol_carb.pulses * num_of_spheres
            sphere_carb = eol_carb.carb_seq * num_of_spheres
            res = EoLResults(eol,carb.results, eol_carb.carb_seq_CH, eol_carb.carb_seq_CSH, sphere_carb, sphere_pulse)
        else:
            pass
        return res