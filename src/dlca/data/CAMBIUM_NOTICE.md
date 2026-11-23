# Notice for the Cambium 2024 files

This notice covers two data files in this folder:

- `cambium2024_gea_aer_gen_c.csv`
- `cambium2024_gea_historical.csv`

**These two files are not under DLCA's MIT licence.** They are extracts of
data made by the National Laboratory of the Rockies (NLR, formerly the
National Renewable Energy Laboratory, NREL) for the U.S. Department of Energy
(DOE). They carry the terms NLR gives for that data, as set out below. The
rest of DLCA stays under its MIT licence.

## Source

The files come from the Cambium 2024 project on NLR's Scenario Viewer,
https://scenarioviewer.nlr.gov/, Download tab. Both were downloaded on
2026-11-20.

| DLCA file | Source download | Source file | SHA-256 of the source CSV |
|---|---|---|---|
| `cambium2024_gea_aer_gen_c.csv` | "Annual · GEA Regions" (`Cambium24_allScenarios_annual_gea.zip`) | `Cambium24_allScenarios_annual_gea.csv` | `e5d83c6b31e78d343a6921953da79287928b804073c973ce92c1be909ab947c6` |
| `cambium2024_gea_historical.csv` | "GEA Historical Intensities" (`GEA_historical_emissions_intensities 3-17-25.zip`) | `GEA_historical_emissions_intensities 3-17-25.csv` | `62da7f1d652180e035fc739c1fd70de4a8ff3438d034988940c6d55f08ff98be` |

`scripts/build_cambium_extract.py` makes the DLCA files. It keeps these
columns, all rows, and copies each value as the source text:

- **Annual file:** `scenario`, `gea`, `t` (as `year`), `aer_gen_co2_c`
  (kg/MWh), `aer_gen_ch4_c` and `aer_gen_n2o_c` (g/MWh). These are average
  emission rates of in-region generation, combustion only, per MWh of
  generation.
- **Historical file:** `year`, `gea`, `co2_kg_per_mwh`, `ch4_kg_per_mwh` and
  `n2o_kg_per_mwh`. NLR made these from US EPA eGRID plant-level data,
  summed to the Cambium GEA regions.

## Citation and credit

Cite the data as NLR recommends:

> Gagnon, Pieter; Pedro Andres Sanchez Perez; Julian Florez; James Morris;
> Marck Llerena Velasquez; and Jordan Eisenman. Cambium 2024 Data. National
> Renewable Energy Laboratory. https://scenarioviewer.nrel.gov

The methods and definitions are documented in:

> Gagnon, P., et al. (2025). *Cambium 2024 Scenario Descriptions and
> Documentation*. National Renewable Energy Laboratory.
> https://docs.nlr.gov/docs/fy25osti/93005.pdf

Credit: the data was produced by the National Laboratory of the Rockies,
formerly NREL. NLR is operated by the Alliance for Energy Innovation LLC for
the U.S. Department of Energy. Under the Scenario Viewer's disclaimer, anyone
who uses this data in a publication agrees to credit DOE, NLR and the
Alliance. Those names may not be used to endorse any results.

## Terms

The Scenario Viewer data has no named licence. Its disclaimer says the data
is provided by NLR "as is" and for reference only. Any express or implied
warranties are disclaimed. DOE, NLR and the Alliance do not guarantee or
endorse any results. Users agree to credit DOE, NLR and the Alliance in any
publication and to indemnify them against claims arising from use. Read the
full disclaimer on https://scenarioviewer.nlr.gov/ before using the data.

NLR advises that Cambium data are modelled projections and "should not be
used as the sole basis for making decisions". Section 4 of the documentation
describes the limits.

DLCA's reasons for redistributing the data are in decision record 0021
(`docs/decisions/0021-cambium-b6-factors.md`, issue #85).
