from importlib.resources import files

import pandas as pd


def _read(name):
    # Read a CSV shipped inside the dlca.data package, independent of the
    # current working directory. The files carry a UTF-8 BOM; utf-8-sig strips it and
    # avoids the platform default encoding (cp1252 on Windows).
    with files("dlca.data").joinpath(name).open("r", encoding="utf-8-sig") as f:
        return pd.read_csv(f)


def load_EUI_data():
    return _read("DOE_energyuse_fake.csv")


def load_EF_state_data():
    return _read("egrid2020_ef_state.csv")


def load_EF_subregion_data():
    return _read("egrid2020_ef_subregion.csv")
