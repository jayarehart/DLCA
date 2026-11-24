# DLCA

[![CI](https://github.com/jayarehart/DLCA/actions/workflows/ci.yml/badge.svg)](https://github.com/jayarehart/DLCA/actions/workflows/ci.yml)

Dynamic life cycle assessment (DLCA) for buildings.

DLCA models the greenhouse-gas emissions of buildings, assemblies and
materials as they occur over time, rather than lumping them into a single
point in time. It reports cumulative global warming impact (GWI) and global
temperature change potential (GTP) over the chosen study period.

## Status

Version 0.5.0, working towards 1.0. The climate engine, building inventory,
biogenic carbon, concrete carbonation and operational energy are in place.
The public API may still change before 1.0; the [changelog](CHANGELOG.md)
lists every change, and [`docs/roadmap.md`](docs/roadmap.md) shows what is
left.

Releases are published on [GitHub](https://github.com/jayarehart/DLCA/releases)
only. DLCA is not on PyPI, so `pip install dlca` will not find it.

## Installation

Python 3.10 or newer is required.

**From a tag.** This builds the package from source and works for any
release tag, for example `v0.5.0`:

```bash
pip install "git+https://github.com/jayarehart/DLCA.git@v0.5.0"
```

**From a release wheel.** Releases made by the release workflow (after
v0.5.0) have a wheel attached. Take its link from the release page, or use
the pattern below (replace `X.Y.Z` with the release you want):

```bash
pip install https://github.com/jayarehart/DLCA/releases/download/vX.Y.Z/dlca-X.Y.Z-py3-none-any.whl
```

**From source**, for development:

```bash
git clone https://github.com/jayarehart/DLCA.git
cd DLCA
uv sync          # or: pip install .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how releases are made and for the
development workflow.

## Quick example

Emissions go in as kilograms of each gas per year, with index 0 as year 0.
This assesses 1000 kg of CO2 emitted in year 0 and 5 kg of (non-fossil)
methane emitted in year 1, over a 100-year horizon, with the AR6 parameters:

```python
from dlca import assess

result = assess(
    {"co2": [1000, 0, 0], "ch4": [0, 5, 0]},
    parameters="AR6",
    horizon=100,
)

print(result.gwi.dynamic)  # global warming impact by year [kg CO2e]
print(result.gtp.dynamic)  # global temperature change potential by year [kg CO2e]
print(result.static_gwp.total)  # the same emissions with no timing [kg CO2e]
```

For a whole building, `dlca.assess_building()` takes an inventory (see the
example files in `tests/data/inventories/`).

## License

DLCA's code is released under the [MIT License](LICENSE).

**Exception:** two packaged data files, `cambium2024_gea_aer_gen_c.csv` and
`cambium2024_gea_historical.csv`, are extracts of the Cambium 2024 data from
the National Laboratory of the Rockies (formerly NREL). They are not under the
MIT License. They carry NLR's own terms, including a credit requirement. Read
[the notice](src/dlca/data/CAMBIUM_NOTICE.md) before you redistribute them or
use them in a publication.

## Citing

If you use DLCA in your work, please cite it. Citation metadata is in
[CITATION.cff](CITATION.cff); GitHub's "Cite this repository" button reads it.
