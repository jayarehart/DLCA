# import libraries
from dataclasses import dataclass
import numpy as np
import pandas as pd
from enum import Enum

class MaterialTypes(Enum):
    STEEL = "Steel"
    CONCRETE = "Concrete"
    CLT = "CLT"
    STRAW = "Straw"
    NA = "NA"
    TEST = "Test"

class GHGTypes(Enum):
    CO2 = "CO2"
    CH4 = "CH4"
    N2O = "N2O"

@dataclass
class AnalysisPeriod:
    start_year: int = 0
    end_year: int = 500
    years_vec = np.linspace(start=start_year, stop=end_year, num=(end_year - start_year + 1)).astype(int)

@dataclass
class EmissionsTiming:
    bldg_lifespan: int = 60
    def __post_init__(self):
        # For now, assume emissions from B come from
        self.A_time = 0
        self.B_time = int(self.bldg_lifespan/2)
        self.C_time = int(self.bldg_lifespan)


@dataclass
class EmissionsInventoryGHGi:
    material: MaterialTypes
    ghg: GHGTypes
    emissions_A: float
    emissions_B: float
    emissions_C: float
    # Emissions of a single greenhouse gas for a material in each life cycle stage (modules A, B, and C)
    # def __int__(self):
    #     self.material = material
    #     self.ghg = ghg
    #     self.emissions_A = emissions_A
    #     self.emissions_B = emissions_B
    #     self.emissions_C = emissions_C


@dataclass
class EmissionInventoryBio:
    # Emissions inventory for biogenic carbon
    material: MaterialTypes
    CO2_bio: float
    rot_period: float
    growth_biomass: float = None
    def __post_init__(self):
        # mu and sigma are used for the generic method for biomass regrowth
        # (Cherubini et al. 2011, https://doi.org/10.1111/j.1757-1707.2011.01102.x)
        self.mu = self.rot_period / 2   # mean
        self.sigma = self.mu / 2        # variance


@dataclass
class EmissionsInventoryAllGHG:
    # All GHGs for a material
    CO2: EmissionsInventoryGHGi = EmissionsInventoryGHGi(MaterialTypes.NA,GHGTypes.CO2,0,0,0)
    CH4: EmissionsInventoryGHGi = EmissionsInventoryGHGi(MaterialTypes.NA,GHGTypes.CH4,0,0,0)
    N2O: EmissionsInventoryGHGi = EmissionsInventoryGHGi(MaterialTypes.NA,GHGTypes.N2O,0,0,0)
    CO2bio: EmissionInventoryBio = EmissionInventoryBio(MaterialTypes.NA, 0,0)
    def __post_init__(self):
        self.material = self.CO2.material
        # Check to see if materials match in each GHG inventory
        if self.material == self.CO2.material == self.CH4.material == self.N2O.material == self.CO2bio.material:
            raise ValueError("GHG inventory is created with mismatched materials. Check the emissions inventory")

@dataclass
class EmissionsFluxMat:
    time: []
    CO2_flux: []
    CH4_flux: []
    N2O_flux: []
    material: MaterialTypes

    def __post_init__(self):
        self.flux_df = pd.DataFrame({'time': self.time, 'CO2_flux':self.CO2_flux, 'CH4_flux':self.CH4_flux, 'N20_flux':self.N2O_flux})
@dataclass
class EmissionsFluxTotal:
    time: []
    CO2_flux: []
    CH4_flux: []
    N2O_flux: []

    def __post_init__(self):
        # self.flux_df = pd.DataFrame({'time': self.time, 'CO2_flux':self.CO2_flux, 'CH4_flux':self.CH4_flux, 'N20_flux':self.N2O_flux})
        self.create_flux_df()

    def create_flux_df(self):
        self.flux_df = pd.DataFrame({'time': self.time, 'CO2_flux': self.CO2_flux, 'CH4_flux': self.CH4_flux, 'N20_flux': self.N2O_flux})
        return self

    def zeros(self, time:[]):
        self.time = time
        self.CO2_flux = len(time) * [0]
        self.CH4_flux = len(time) * [0]
        self.N2O_flux = len(time) * [0]
        self.flux_df = None
        return self

@dataclass
class DLCAInputData:
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

    # Inputs based upon time horizon
    time_horizon: float = None
    A_CO2: float = None
    A_CH4: float = None
    AGWP_CO2: float = None
    AGWP_CH4: float = None
    GWP_CH4: float = None



@dataclass
class DLCAResults:
    mass_in_atm_df: pd.DataFrame = None
    CO2_mass_df: pd.DataFrame = None
    cum_net_emissions: pd.DataFrame = None
    irf_df: pd.DataFrame = None
    equiv_df: pd.DataFrame = None
    temp_change_df: pd.DataFrame = None