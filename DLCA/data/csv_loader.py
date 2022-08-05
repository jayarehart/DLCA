import pandas as pd

def load_AGTP_supp_data():
    return pd.read_csv('../data/AGTP_supp_data.csv')

def load_AGWP_supp_data():
    return pd.read_csv('../data/AGWP_supp_data.csv')
