"""Build DLCA's packaged Cambium 2024 extract from NLR's source files (#85, record 0021).

The source files come from the Download tab of the Cambium 2024 project on
NLR's Scenario Viewer (https://scenarioviewer.nlr.gov/):

- "Annual - GEA Regions": ``Cambium24_allScenarios_annual_gea.zip``, holding
  ``Cambium24_allScenarios_annual_gea.csv``.
- "GEA Historical Intensities": ``GEA_historical_emissions_intensities 3-17-25.zip``,
  holding ``GEA_historical_emissions_intensities 3-17-25.csv``.

Treat them as untrusted input: unzip them in a scratch directory and run this
script with ``python -I``, passing the two CSV paths::

    python -I scripts/build_cambium_extract.py ANNUAL_CSV HISTORICAL_CSV [OUT_DIR]

It writes two files to OUT_DIR (default ``src/dlca/data``), copying each value
as the source text, without rounding or recomputing:

- ``cambium2024_gea_aer_gen_c.csv``: scenario, gea, year and the three
  ``aer_gen_*_c`` columns (CO2 kg/MWh, CH4 and N2O g/MWh) for every row.
- ``cambium2024_gea_historical.csv``: year, gea and the three intensities
  (kg/MWh).

It stops if a header, unit or count is not what record 0021 describes.
"""

from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

ANNUAL_OUT = "cambium2024_gea_aer_gen_c.csv"
HISTORICAL_OUT = "cambium2024_gea_historical.csv"

AER_GEN_C = {"aer_gen_co2_c": "kg/MWh", "aer_gen_ch4_c": "g/MWh", "aer_gen_n2o_c": "g/MWh"}
HISTORICAL_COLUMNS = ("co2_kg_per_mwh", "ch4_kg_per_mwh", "n2o_kg_per_mwh")
N_SCENARIOS, N_GEAS, N_YEARS = 8, 18, 6


def _stop(message: str) -> None:
    sys.exit(f"build_cambium_extract: {message}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _annual(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    # Rows 0-1: project metadata; 2: documentation link; 3: groups; 4: units; 5: names.
    if not rows[1] or rows[1][0] != "Cambium24":
        _stop(f"{path.name}: not a Cambium24 file (row 2 starts {rows[1][:1]})")
    units, names = rows[4], rows[5]
    index = {name: i for i, name in enumerate(names)}
    for key in ("scenario", "gea", "t", *AER_GEN_C):
        if key not in index:
            _stop(f"{path.name}: no column {key!r}")
    for key, unit in AER_GEN_C.items():
        if units[index[key]] != unit:
            _stop(f"{path.name}: {key} is in {units[index[key]]!r}, expected {unit!r}")
    out = [["scenario", "gea", "year", "co2_kg_per_mwh", "ch4_g_per_mwh", "n2o_g_per_mwh"]]
    for row in rows[6:]:
        if not row:
            continue
        out.append(
            [row[index["scenario"]], row[index["gea"]], row[index["t"]]]
            + [row[index[key]] for key in AER_GEN_C]
        )
    data = out[1:]
    counts = (len({r[0] for r in data}), len({r[1] for r in data}), len({r[2] for r in data}))
    if counts != (N_SCENARIOS, N_GEAS, N_YEARS) or len(data) != N_SCENARIOS * N_GEAS * N_YEARS:
        _stop(f"{path.name}: {len(data)} rows, (scenarios, geas, years) = {counts}")
    return out


def _historical(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    # Rows 0-2: notes; 3: names.
    names = rows[3]
    index = {name: i for i, name in enumerate(names)}
    for key in ("year", "gea", *HISTORICAL_COLUMNS):
        if key not in index:
            _stop(f"{path.name}: no column {key!r}")
    out = [["year", "gea", *HISTORICAL_COLUMNS]]
    for row in rows[4:]:
        if not row or not row[0].strip():
            continue
        out.append([row[index["year"]], row[index["gea"]]] + [row[index[k]] for k in HISTORICAL_COLUMNS])
    if len({r[1] for r in out[1:]}) != N_GEAS:
        _stop(f"{path.name}: expected {N_GEAS} GEA regions")
    return out


def main(argv: list[str]) -> None:
    if len(argv) not in (2, 3):
        _stop("usage: build_cambium_extract.py ANNUAL_CSV HISTORICAL_CSV [OUT_DIR]")
    annual, historical = Path(argv[0]), Path(argv[1])
    out_dir = Path(argv[2]) if len(argv) == 3 else Path(__file__).resolve().parents[1] / "src/dlca/data"
    a_rows, h_rows = _annual(annual), _historical(historical)
    for name, rows in ((ANNUAL_OUT, a_rows), (HISTORICAL_OUT, h_rows)):
        with (out_dir / name).open("w", newline="", encoding="utf-8") as f:
            csv.writer(f, lineterminator="\n").writerows(rows)
    print(f"{annual.name}: sha256 {_sha256(annual)}, {len(a_rows) - 1} rows -> {ANNUAL_OUT}")
    print(f"{historical.name}: sha256 {_sha256(historical)}, {len(h_rows) - 1} rows -> {HISTORICAL_OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
