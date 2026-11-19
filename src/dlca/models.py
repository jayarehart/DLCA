# import libraries
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

from dlca.data.csv_loader import *


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


class USState(Enum):
    AK = "Alaska"
    AL = "Alabamba"
    AR = "Arkansas"
    AZ = "Arizona"
    CA = "California"
    CO = "Colorado"
    CT = "Connecticut"
    DC = "District of Columbia"
    DE = "Delaware"
    FL = "Florida"
    GA = "Georgia"
    HI = "Hawaii"
    IA = "Iowa"
    ID = "Idaho"
    IL = "Illinois"
    IN = "Indiana"
    KS = "Kansas"
    KY = "Kentucky"
    LA = "Louisiana"
    MA = "massachusetts"
    MD = "Maryland"
    ME = "Maine"
    MI = "Michigan"
    MN = "Minnesota"
    MO = "Missouri"
    MS = "Mississippi"
    MT = "Montana"
    NC = "North Carolina"
    ND = "North Dakota"
    NE = "Nebraska"
    NH = "New Hampshire"
    NJ = "New Jersey"
    NM = "New Mexico"
    NV = "Nevada"
    NY = "New York"
    OH = "Ohio"
    OK = "Oklahoma"
    OR = "Oregon"
    PA = "Pennsylvania"
    PR = "Puerto Rico"
    RI = "Rhode Island"
    SC = "South Carolina"
    SD = "South Dakota"
    TN = "Tennessee"
    TX = "Texas"
    UT = "Utah"
    VA = "Virginia"
    VT = "Vermont"
    WA = "Washington"
    WI = "Wisconsin"
    WV = "West Virginia"
    WY = "Wyoming"
    USA = "United States of America"


class USSubgrid(Enum):
    AKGD = "ASCC Alaska Grid"
    AKMS = "ASCC Miscellaneous"
    AZNM = "WECC Southwest"
    CAMX = "WECC California"
    ERCT = "ERCOT All"
    FRCC = "FRCC All"
    HIMS = "HICC Miscellaneous"
    HIOA = "HICC Oahu"
    MROE = "MRO East"
    MROW = "MRO West"
    NEWE = "NPCC New England"
    NWPP = "WECC Northwest"
    NYCW = "NPCC NYC / Westchester"
    NYLI = "NPCC Long Island"
    NYUP = "NPCC Upstate NY"
    PRMS = "Puerto Rico Miscellaneous"
    RFCE = "RFC East"
    RFCM = "RFC Michigan"
    RFCW = "RFC West"
    RMPA = "WECC Rockies"
    SPNO = "SPP North"
    SPSO = "SPP South"
    SRMV = "SERC Mississippi Valley"
    SRMW = "SERC Midwest"
    SRSO = "SERC South"
    SRTV = "SERC Tennessee Valley"
    SRVC = "SERC Virginia / Carolina"
    USA = "United States of America"


class Unit(Enum):
    MMBtu = "1 Million British Thermal Units"
    kBtu = "1 Thousand British Thermal Units"
    # 1 Million BTU [MMBtu] = 1055.05585262 # Megajoule [MJ]
    MJ = "Megajoule"
    GJ = "Gigajoule"
    KG_KWH = "kg of GHG per kwh"
    KG_MMBTU = "kg of GHG per mmBtu"
    KG_GJ = "kg of GGH per GJ"


class FuelType(Enum):
    ELECTRICITY_SITE = "Electricity - Site"
    NATURALGAS_SITE = "Natural Gas - Site"
    FUELOILNO2_SITE = "Fuel Oil No2 - Site"


class ComOrRes(Enum):
    COM = "Commercial"
    RES = "Residential"


class Scenario(Enum):
    S1 = "Scenario 1"
    S2 = "Secneario 2"


class BldgUseType(Enum):
    # ASHRAE 90.1-2019
    # https://www.energycodes.gov/prototype-building-models
    SMALLOFFICE = "Small Office"
    MEDIUMOFFICE = "Medium Office"
    LARGEOFFICE = "Large Office"
    WAREHOUSE = "Warehouse"
    STANDALONERETAIL = "Stand-Alone Retail"
    STRIPMALL = "Strip Mall"
    PRIMARYSCHOOL = "Primary School"
    SECONDARYSCHOOL = "Secondary School"
    SUPERMARKET = "Supermarket"
    QUICKSERVICERESTAURANT = "Quick Service Restaurant"
    FULLSERVICERESTAURANT = "Full Service Restaurant"
    HOSPITAL = "Hospital"
    OUTPATIENTHEALTHCARE = "Outpatient Health Care"
    SMALLHOTEL = "Small Hotel"
    LARGEHOTEL = "Large Hotel"
    MIDRISEAPT = "Midrise Apartment"
    HIGHRISEAPT = "Highrise Apartment"

    # Residential
    SF_CRAWLSPACE = "Single-Family & Crawlspace"
    SF_HTDBASEMENT = "Single-Family & Heated Basement"
    SF_SLAB = "Single-Family & Slab"
    SF_UNHTDBASEMENT = "Single-Family & Unheated Basement"
    MF_CRAWLSPACE = "Multi-Family & Crawlspace"
    MF_HTDBASEMENT = "Multi-Family & Heated Basement"
    MF_SLAB = "Multi-Family & Slab"
    MF_UNHTDBASEMENT = "Multi-Family & Unheated Basement"


class ResHeatSystem(Enum):
    ELECRES = "Electric Resistant"
    GASFURNACE = "Gas Furnace"
    OILFURNACE = "Oil Furnace"
    HP = "Heat Pump"
    NONE = "NONE"


class ClimateZone(Enum):
    _1A = "1A - Miami"
    _1A_TROPICAL = "1A Tropical - Honolulu"
    _2A = "2A - Tampa"
    _2B = "2B - Tucson"
    _3A = "3A - Atlanta"
    _3AWH = "3AWH - Montgomery"
    _4A = "4A - New York"
    _4B = "4B - Albuquerque"
    _4C = "4C - Seattle"
    _5A = "5A - Buffalo"
    _5B = "5B - Denver"
    _5C = "5C - Port Angeles"
    _6A = "6A - Rochester"
    _6B = "6B - Great Falls"
    _7 = "7 - International Falls"
    _8 = "8 - Fairbanks"


@dataclass
class AnalysisPeriod:
    start_year: int = 0
    end_year: int = 500
    years_vec = np.linspace(
        start=start_year, stop=end_year, num=(end_year - start_year + 1)
    ).astype(int)


@dataclass
class MatEmissionsTiming:
    bldg_lifespan: int = 60

    def __post_init__(self):
        # For now, assume emissions from B come from
        self.A_time = 0
        self.B_time = np.arange(1, self.bldg_lifespan + 1)
        self.C_time = np.arange(
            self.bldg_lifespan, self.bldg_lifespan + 15
        )  # int(self.bldg_lifespan)#


###NEED TO FIX ABOVE TO WORK FOR A SINGLE INPUT AT [0] OF C, AND A LIST INPUT THROUGH X YEARS


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
        self.mu = self.rot_period / 2  # mean
        self.sigma = self.mu / 2  # variance


@dataclass
class EmissionsInventoryAllGHG:
    # All GHGs for a material
    CO2: EmissionsInventoryGHGi = field(
        default_factory=lambda: EmissionsInventoryGHGi(MaterialTypes.NA, GHGTypes.CO2, 0, 0, 0)
    )
    CH4: EmissionsInventoryGHGi = field(
        default_factory=lambda: EmissionsInventoryGHGi(MaterialTypes.NA, GHGTypes.CH4, 0, 0, 0)
    )
    N2O: EmissionsInventoryGHGi = field(
        default_factory=lambda: EmissionsInventoryGHGi(MaterialTypes.NA, GHGTypes.N2O, 0, 0, 0)
    )
    CO2bio: EmissionInventoryBio = field(
        default_factory=lambda: EmissionInventoryBio(MaterialTypes.NA, 0, 0)
    )

    def __post_init__(self):
        self.material = self.CO2.material
        # Every part of the inventory must be for the same material (strict; decision
        # A8 on #31). CO2bio defaults to MaterialTypes.NA, so pass it explicitly.
        parts = (self.CO2, self.CH4, self.N2O, self.CO2bio)
        if len({part.material for part in parts}) != 1:
            raise ValueError(
                "GHG inventory is created with mismatched materials. Check the emissions inventory"
            )


@dataclass
class EmissionsFluxMat:
    time: []
    CO2_flux: []
    CH4_flux: []
    N2O_flux: []
    material: MaterialTypes

    def __post_init__(self):
        self.flux_df = pd.DataFrame(
            {
                "time": self.time,
                "CO2_flux": self.CO2_flux,
                "CH4_flux": self.CH4_flux,
                "N2O_flux": self.N2O_flux,
            }
        )


@dataclass
class EmissionsFluxOperational:
    time: []
    CO2_flux: []
    CH4_flux: []
    N2O_flux: []

    def __post_init__(self):
        self.flux_df = pd.DataFrame(
            {
                "time": self.time,
                "CO2_flux": self.CO2_flux,
                "CH4_flux": self.CH4_flux,
                "N2O_flux": self.N2O_flux,
            }
        )


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
        self.flux_df = pd.DataFrame(
            {
                "time": self.time,
                "CO2_flux": self.CO2_flux,
                "CH4_flux": self.CH4_flux,
                "N2O_flux": self.N2O_flux,
            }
        )
        return self

    def zeros(self, time: []):
        self.time = time
        self.CO2_flux = len(time) * [0]
        self.CH4_flux = len(time) * [0]
        self.N2O_flux = len(time) * [0]
        self.flux_df = None
        return self


@dataclass
class EF:
    # Emissons factor for a given fuel source
    fuel: FuelType
    CO2: int
    CH4: int
    N2O: int
    unit: Unit


@dataclass
class RefBldgDetails:
    ref_bldg_area_m2: int = None
    electricity_site_GJ: float = None
    naturalgas_site_GJ: float = None
    fueloilno2_kBtu: float = None

    electricity_UI_GJm2: float = None
    naturalgas_UI_GJm2: float = None
    fueloilno2_UI_kBtum2: float = None


# @dataclass
# class BldgEF:
#     EF_naturalgas: EF = None
#     EF_fueloilno2: EF = None
#     EF_electricity: EF = None


@dataclass
class BldgDetails:
    use_type: BldgUseType
    heating_system: ResHeatSystem
    climate_zone: ClimateZone
    eGrid: USSubgrid
    area_m2: float
    lifespan: float
    scenario: Scenario

    # Emissions factors
    EF_naturalgas: EF = None
    EF_fueloilno2: EF = None
    EF_electricity: EF = None

    def __post_init__(self):
        # create empty reference building properties
        self.ref_bldg = RefBldgDetails()
        # load EUI data
        self.load_EUI()

        # add property for res or com
        Com_Res: ComOrRes = None
        res_list = [
            "SF_CRAWLSPACE",
            "SF_HTDBASEMENT",
            "SF_SLAB",
            "SF_UNHTDBASEMENT",
            "MF_CRAWLSPACE",
            "MF_HTDBASEMENT",
            "MF_SLAB",
            "MF_UNHTDBASEMENT",
        ]
        if self.use_type.name in res_list:
            self.Com_Res = ComOrRes.RES
        else:
            self.Com_Res = ComOrRes.COM

        # load emissions factors
        self.load_EF()

    def load_EUI(self):
        if self.ref_bldg.ref_bldg_area_m2 != None:
            raise Warning("EUI data already loaded.. Overwritting..")
        df_EUI = load_EUI_data()
        # Filter EUI datafram based upon BldgDetails
        df_EUI_filtered = df_EUI.query(
            "BldgUseType == @self.use_type.name and ResHeatSystem == @self.heating_system.value and ClimateZone == @self.climate_zone.name"
        )
        # Throw error if more than one building is returned
        if len(df_EUI_filtered.index) != 1:
            raise Exception("Multiple types of buildings were returend from the queried")

        # Write new attributes to the bldg input and return
        self.ref_bldg.ref_bldg_area_m2 = df_EUI_filtered["Area_m2"].iloc[0]
        self.ref_bldg.electricity_site_GJ = df_EUI_filtered["ElectricitySite_GJ"].iloc[0]
        self.ref_bldg.naturalgas_site_GJ = df_EUI_filtered["NaturalGasSite_GJ"].iloc[0]
        self.ref_bldg.fueloilno2_kBtu = df_EUI_filtered["FuelOilNo2_kBtu"].iloc[0]
        self.ref_bldg.electricity_UI_GJm2 = (
            self.ref_bldg.electricity_site_GJ / self.ref_bldg.ref_bldg_area_m2
        )
        self.ref_bldg.naturalgas_UI_GJm2 = (
            self.ref_bldg.naturalgas_site_GJ / self.ref_bldg.ref_bldg_area_m2
        )
        self.ref_bldg.fueloilno2_UI_kBtum2 = (
            self.ref_bldg.fueloilno2_kBtu / self.ref_bldg.ref_bldg_area_m2
        )

        return self

    def load_EF(self):
        if self.EF_electricity != None:
            raise Warning("EUI data already loaded.. Overwritting..")
        df_subregion = load_EF_subregion_data()
        df_subregion_filtered = df_subregion.query("eGRID_subregion_acronym == @self.eGrid.name")
        # Throw error if more than one building is returned
        if len(df_subregion_filtered.index) != 1:
            raise Exception("Multiple types of buildings were returend from the queried")

        # Emissions factors from eGrid: https://www.epa.gov/egrid
        self.EF_electricity = EF(
            FuelType.ELECTRICITY_SITE,
            CO2=df_subregion_filtered["CO2_kgperkwh"].iloc[0],
            CH4=df_subregion_filtered["CH4_kgperkwh"].iloc[0],
            N2O=df_subregion_filtered["N2O_kgperkwh"].iloc[0],
            unit=Unit.KG_KWH,
        )
        # Emissions factors from: https://www.epa.gov/sites/default/files/2015-07/documents/emission-factors_2014.pdf
        self.EF_naturalgas = EF(
            fuel=FuelType.NATURALGAS_SITE, CO2=54.06, CH4=0.001, N2O=0.0001, unit=Unit.KG_MMBTU
        )
        self.EF_fueloilno2 = EF(
            fuel=FuelType.FUELOILNO2_SITE, CO2=73.96, CH4=0.003, N2O=0.0006, unit=Unit.KG_MMBTU
        )

        return self
