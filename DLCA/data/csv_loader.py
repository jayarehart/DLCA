from typing import Any
import pandas as pd
from DLCA.models import *
import csv

def load_AGTP_supp_data():
    return pd.read_csv('../data/AGTP_supp_data.csv')

def load_AGWP_supp_data():
    return pd.read_csv('../data/AGWP_supp_data.csv')

def load_EUI_data():
    return pd.read_csv('../data/DOE_energyuse_fake.csv')

def load_EF_state_data():
    return pd.read_csv('../data/egrid2020_ef_state.csv')

def load_EF_subregion_data():
    return pd.read_csv('../data/egrid2020_ef_subregion.csv')



