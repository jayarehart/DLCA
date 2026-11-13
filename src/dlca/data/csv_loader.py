from importlib.resources import files

import pandas as pd


def _read(name):
    # Read a CSV shipped inside the dlca.data package, independent of the
    # current working directory.
    with files("dlca.data").joinpath(name).open("r") as f:
        return pd.read_csv(f)


def load_AGTP_supp_data():
    return _read("AGTP_supp_data.csv")


def load_AGWP_supp_data():
    return _read("AGWP_supp_data.csv")


def load_EUI_data():
    return _read("DOE_energyuse_fake.csv")


def load_EF_state_data():
    return _read("egrid2020_ef_state.csv")


def load_EF_subregion_data():
    return _read("egrid2020_ef_subregion.csv")
