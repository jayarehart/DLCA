from enum import Enum
from dataclasses import dataclass
import numpy as np
import pandas as pd


class EoLScenario(Enum):
    S1 = "Scenario 1"
    S2 = "Scenario 2"
    S3 = "Scenario 3"
    S4 = "Scenario 4"


class MaterialTypes(Enum):
    STEEL = "Steel"
    CONCRETE = "Concrete"
    CLT = "CLT"
    STRAW = "Straw"
    NA = "NA"
    TEST = "Test"


class Units(Enum):
    US = 'US'
    SI = 'SI'


class SCMType(Enum):
    FLYASH_C = "Fly Ash Class C"
    FLYASH_F = "Fly Ash Class F"
    SLAG = "Slag"
    SILICAFUME = "Silica Fume"
    METAKAOLIN = "Metakaolin"
    NONE = "None"


class CementType(Enum):
    I = "I"
    II = "II"
    III = "III"
    IV = "IV"
    V = "V"
    White = "White"


class Shape(Enum):
    REC = 'Rectangle'
    CYLINDER = 'Cylinder'
    SPHERE = 'Sphere'


class XC(Enum):
    I = "I"
    II = "II"
    III = "III"
    IV = "IV"

class Faces(Enum):
    ALL = "ALL"
    WIDTH_ONLY = "WIDTH ONLY"
    LENGTH_ONLY = "LENGTH ONLY"
    THREE_FACES = "THREE FACES"
    ONE_FACE = "ONE FACE"

# analysis period
class ServiceLife:
    def __init__(self, start_year, end_year):
        self.start_year = start_year
        self.end_year = end_year
        self.years_vec = np.linspace(start=start_year, stop=end_year, num=(end_year - start_year + 1)).astype(int)


@dataclass
class EoLTime:
    start_year: int = 1
    end_year: int = 15
    years_vec = np.linspace(start=start_year, stop=end_year, num=(end_year - start_year + 1)).astype(int)


# geometry
@dataclass
class Geometry:
    shape: Shape
    length: float = None
    width: float = None
    height: float = None
    radius: float = None
    faces_exposed: Faces = None

# mix
@dataclass
class ConcreteComponents:
    units: Units
    scm_type: SCMType
    name: str
    fc: float = None
    cement_type: CementType = CementType.I
    cement_kg: float = None
    water_kg: float = None
    crushed_coarse_agg_kg: float = None
    nat_coarse_agg_kg: float = None
    crushed_fine_agg_kg: float = None
    nat_fine_agg_kg: float = None
    percent_replacement: float = 0
    fly_ash_kg: float = 0
    slag_kg: float = 0
    m_binder: float = None
    mix:{} = None
    def __post_init__(self):

        if self.units == Units.US:
            self.fc = self.fc / 145
            self.cement_kg = self.cement_kg / 2.205
            self.water_kg = self.water_kg / 2.205
            self.crushed_coarse_agg_kg = self.crushed_coarse_agg_kg / 2.205
            self.nat_coarse_agg_kg = self.nat_coarse_agg_kg / 2.205
            self.crushed_fine_agg_kg = self.crushed_fine_agg_kg / 2.205
            self.nat_fine_agg_kg = self.nat_fine_agg_kg / 2.205
            self.fly_ash_kg = self.fly_ash_kg / 2.205
            self.slag_kg = self.slag_kg / 2.205
        else:
            pass

        if self.fly_ash_kg == None and self.slag_kg == None:
            rho_FA = 700  # kg / m3
            rho_SL = 1150  # kg / m3
            rho_cement = 1440  # kg / m3
            if self.scm_type == SCMType.SLAG:
                self.m_binder = self.cement_kg + self.cement_kg * self.percent_replacement * (rho_SL / rho_cement)
            elif self.scm_type == SCMType.FLYASH_C:
                self.m_binder = self.cement_kg + self.cement_kg * self.percent_replacement * (rho_FA / rho_cement)
            elif self.scm_type == SCMType.NONE:
                self.m_binder = self.cement_kg
        else:
            self.m_binder = self.cement_kg + self.slag_kg + self.fly_ash_kg
        self.create_design_dict()

    def create_design_dict(self):
        self.mix = {'Name': self.name,
                    'Compressive Strength': self.fc,
                    'Cement Type': self.cement_type,
                    'Cement (kg / m3 of concrete)': self.cement_kg,
                    'Water (kg / m3 of concrete)': self.water_kg,
                    'Crushed Coarse Agg. (kg / m3 of concrete)': self.crushed_coarse_agg_kg,
                    'Natural Coarse Agg. (kg / m3 of concrete)': self.nat_coarse_agg_kg,
                    'Crushed Fine Agg. (kg / m3 of concrete)': self.crushed_fine_agg_kg,
                    'Natural Fine Agg. (kg / m3 of concrete)': self.nat_fine_agg_kg,
                    'SCM Type': self.scm_type,
                    'SCM % Replacement': self.percent_replacement,
                    'Slag (kg / m3 of concrete)': self.slag_kg,
                    'Fly Ash (kg / m3 of concrete)': self.fly_ash_kg,
                    'Total Mass of Binder (kg / m3 of concrete)': self.m_binder}
        return self.mix


@dataclass
class EnvironmentalInputs:
    # mix: Design
    k0: float = 1.0
    k1: float = None
    k2: float = 1.0
    n: float = None
    exposure_class: XC = None
    carb_atm_conc: float = None
    R: float = None
    phi_c = float = 1

    # convert to units used in model
    def __post_init__(self):

        if self.carb_atm_conc > 10:
            self.carb_atm_conc = self.carb_atm_conc / (516 * (10 ** 3))
        if self.exposure_class == self.exposure_class.I:
            self.k1 = 1
            self.n = 0
        elif self.exposure_class == self.exposure_class.II:
            self.k1 = 0.2
            self.n = 0.183
        elif self.exposure_class == self.exposure_class.III:
            self.k1 = 0.77
            self.n = 0.02
        elif self.exposure_class == self.exposure_class.IV:
            self.k1 = 0.41
            self.n = 0.085

        self.create_inputs()

    def create_inputs(self):
        self.en_inputs = {'XC': self.exposure_class, 'k0': self.k0, 'k1': self.k1, 'k2': self.k2, 'n': self.n, 'R': self.R,
             'CO2 Concentration': self.carb_atm_conc, 'phi_c': self.phi_c}
        return self


# store results

@dataclass
class StructureDim:
    structure: Geometry
    vol: [] = None
    surf_area: [] = None
    structure_df:{}=None
    def __post_init__(self):
        self.create_structure_df()

    def create_structure_df(self):
        if self.structure.shape == Shape.REC:
            self.structure_df = {'Geometry': self.structure.shape, 'Length (m)': self.structure.length,
                                              'Width (m)': self.structure.width, 'Height (m)': self.structure.height,
                                              'Volume (m3)': self.vol, 'Surface Area (m2)': self.surf_area,
                                              'Faces Exposed': self.structure.faces_exposed}
        elif self.structure.shape == Shape.CYLINDER:
            self.structure_df = {'Geometry': self.structure.shape, 'Radius (m)': self.structure.radius,
                                              'Height (m)': self.structure.height, 'Volume (m3)': self.vol,
                                              'Surface Area (m2)': self.surf_area}
        elif self.structure.shape == Shape.SPHERE:
            self.structure_df = {'Geometry': self.structure.shape, 'Radius (m)': self.structure.radius,
                                              'Volume (m3)': self.vol, 'Surface Area (m2)': self.surf_area}
        return self.structure_df


@dataclass
class Inputs:
    time: ServiceLife
    mix: ConcreteComponents = None
    structure: {} = None
    envi_inputs: {} = None

    def __post_init__(self):
        self.create_inputs()

    def create_inputs(self):
        self.inputs_df = {}
        for i in [self.structure,self.mix.mix,self.envi_inputs]:
            self.inputs_df.update(i)
        return self.inputs_df


@dataclass
class ModelResults:
    name: [] = None
    time: [] = None
    carb_depth: [] = None
    uncarb_vol: [] = None
    carb_vol: [] = None
    carb_seq_CH: [] = None
    carb_seq_CSH: [] = None
    carb_seq_Lagerblad: [] = None
    carb_seq: [] = None
    pulses: [] = None
    results:{} = None

    def __post_init__(self):
        self.Results()

    def Results(self):
        self.results = {'Name': self.name, 'time': self.time,
                        'x': self.carb_depth, 'volume left': self.uncarb_vol,
                        'Vc': self.carb_vol,'Cs CH':self.carb_seq_CH,
                        'Cs CSH':self.carb_seq_CSH,'Cs Lagerblad': self.carb_seq_Lagerblad,
                        'Cs': self.carb_seq,
                        'pulses': self.pulses}
        return self

@dataclass
class EoLResults:
    eol_scenario: EoLScenario = None
    service:{} = None
    eol_seq_CH: [] = None
    eol_seq_CSH: [] = None
    eol_seq: [] = None
    eol_pulses: [] = None
    results:{}=None
    all_seq:[]=None
    all_pulses:[]=None
    def __post_init__(self):
        self.Results()
    def Results(self):
        self.results = self.service.update({'EoL CH':self.eol_seq_CH,
                        'EoL CSH':self.eol_seq_CSH,
                        'EoL Cs': self.eol_seq,
                        'EoL pulses': self.eol_pulses})
        if self.eol_scenario != EoLScenario.S2:
            self.all_seq = np.append(self.service['Cs'], self.eol_seq + self.service['Cs'][-1])
            self.all_pulses = np.append(self.service['pulses'], self.eol_pulses + self.service['pulses'][-1])
        else:
            pass
        return self