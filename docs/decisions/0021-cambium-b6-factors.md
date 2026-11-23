# 0021. Packaged Cambium 2024 grid factors for B6 electricity

- **Status:** Accepted
- **Date:** 2026-11-23
- **Decided by:** Jay Arehart, accepted 2026-11-23 (C0–C6 on #85, 2026-11-20; licence metadata, `year_zero` bounds and CH₄/N₂O tolerance on PR #91, 2026-11-23)

## Context

Record 0019 (#82) gave B6 electricity two packaged factor sources, both
constant over the study: eGRID2023 Rev 2 by subregion and by state. It also
let users pass their own absolute factor series by study year. It left NREL's
Cambium projections to #85.

Cambium 2024, the fifth annual release, gives modelled grid emission rates to
2050 for 8 scenarios and 18 generation and emission assessment (GEA) regions.
The lab is now the National Laboratory of the Rockies (NLR). Jay answered
#85's questions C0–C6 on 2026-11-20
(https://github.com/jayarehart/DLCA/issues/85#issuecomment-7052789620).

## Decision

We will package a Cambium 2024 extract and let an electricity energy line use
it as a year-by-year factor.

**Source and licence (C0, C1).**
- The data comes from the Cambium 2024 project on NLR's Scenario Viewer
  (https://scenarioviewer.nlr.gov/), downloaded 2026-11-20. It uses two
  downloads: "Annual · GEA Regions" and "GEA Historical Intensities".
- The data has no named licence, only a disclaimer: "as is", credit DOE, NLR
  and the Alliance, and users indemnify them. Jay accepted redistributing an
  extract on that basis (C1).
- `dlca/data/CAMBIUM_NOTICE.md` gives the source, NLR's recommended citation
  and the credit. It says the two files are not under DLCA's MIT licence.
- `scripts/build_cambium_extract.py` makes the two packaged files from the
  source CSVs. It copies each value as the source text and stops on any
  unexpected header, unit or count. Run it with `python -I`.

| Packaged file | Source CSV | SHA-256 of the source CSV |
|---|---|---|
| `cambium2024_gea_aer_gen_c.csv` | `Cambium24_allScenarios_annual_gea.csv` | `e5d83c6b31e78d343a6921953da79287928b804073c973ce92c1be909ab947c6` |
| `cambium2024_gea_historical.csv` | `GEA_historical_emissions_intensities 3-17-25.csv` | `62da7f1d652180e035fc739c1fd70de4a8ff3438d034988940c6d55f08ff98be` |

The ZIPs as downloaded have these SHA-256 sums:
- `Cambium24_allScenarios_annual_gea.zip`: `b5438ee16c0cf03054bac62520155cbfdc8e98797aba025e48e793fb1527c189`
- `GEA_historical_emissions_intensities 3-17-25.zip`: `dfee52c63d5f8f6f5c14b01e74e6b12d7867fd74ad90c3ad47e7f1db841568af`

**What is packaged (C2, C3).**
- All 8 scenarios, under the names NLR's files use: `MidCase` (the default),
  `HighDemandGrowth`, `HighNGPrice`, `LowNGPrice`, `HighRECost`, `LowRECost`,
  `HighRECost_LowNGPrice` and `LowRECost_HighNGPrice`.
- All 18 GEA regions. The years are 2025, 2030, …, 2050.
- The rate is `aer_gen_{co2,ch4,n2o}_c`: the average emission rate of in-region
  generation, combustion only, per MWh of generation. It includes no imports
  and no distribution losses (Cambium documentation §5.4). This is eGRID's
  basis and keeps record 0019's scope: combustion and generation only.
- CH₄ goes under `ch4_fossil`, as for the other packaged factors.
- Units: CO₂ in kg/MWh; CH₄ and N₂O in g/MWh, divided by 1000 when read.

**Regions (C4).** The user names one of the 18 GEA regions in
`cambium_gea`. DLCA builds no mapping to eGRID subregions or states. NLR says
the regions differ (documentation §4.2) and publishes only GEA→ZIP and
GEA→county mappings (Scenario Viewer, "GEA Mappings and Shapefiles").

**Joining to measured data (C5).** For each region, scenario and gas, the
calendar-year series is:
1. NLR's eGRID-based historical values for the region, for 2014, 2016 and
   2018–2023, all three gases in kg/MWh;
2. a straight line from the last historical year (2023) to Cambium 2030.
   **Cambium's 2025 point is not used**, following the conservative option in
   the documentation's §4.2. That section names step changes from eGRID 2023
   to Cambium 2025 in NorthernGrid_West, ERCOT, ISONE, NorthernGrid_East,
   NorthernGrid_South, SPP_North and WestConnect_North. For example (DLCA's,
   from the files), CAISO CO₂ goes from 182.5 kg/MWh in 2023 to 132.2 in 2025;
3. Cambium 2030–2050, with a straight line between the 5-year points;
4. the first value held before 2014 and the 2050 value held after 2050.

Gaps (2015, 2017) get a straight line. The series is turned into study years
with `to_study_years` (record 0019).

**Input (C6).** `EnergyUse` gets three optional fields:

| Field | Meaning |
|---|---|
| `cambium_gea` | one of the 18 GEA regions |
| `cambium_scenario` | one of the 8 scenarios; absent means `MidCase` |
| `year_zero` | calendar year of study year 0; required with `cambium_gea` |

- Electricity needs exactly one of `egrid_subregion`, `egrid_state`, `factor`
  or `cambium_gea`.
- `cambium_scenario` and `year_zero` are refused without `cambium_gea`.
  `cambium_gea` is refused on fuels.
- As with a series `factor` (record 0019), a non-constant `trajectory` is
  refused on a Cambium line, so nothing is scaled twice.

B6 in study year *y* (1..RSP) is amount × factor(`year_zero` + *y*).

**Versions.**
- Inventory `schema_version` goes from 5 to 6. Version 1–5 files still load
  but may not use `cambium_gea`.
- `BuildingResult` JSON, which embeds the building, goes from 5 to 6 and
  still reads 1–5.
- `Result` and `Timeline` JSON do not change.

## Alternatives considered

- **Document only, and package nothing.** Lost (C0): users would each have to
  choose scenario, metric and region, and repeat the join. The absolute
  factor series stays available for other data.
- **The CC BY 4.0 workbook (OEDI 8395) as the only source.** Lost (C1): its
  host returned 503 on 2026-11-20, and the Scenario Viewer files hold the
  year-by-year rates per gas.
- **Long-run marginal (`lrmer_*_c`) or `aer_load_*_c`.** Lost (C3): both are
  per MWh of end use with average distribution losses included, which breaks
  record 0019's scope. LRMER is also a consequential measure, and building
  LCA here is attributional.
- **No join (Cambium only, the 2025 value held back).** Lost (C5): it hides
  the 2023→2025 step that NLR flags as possibly too fast.
- **A Cambium ratio laid on the eGRID2023 baseline.** Lost in record 0019; the
  regions and the bases differ.
- **A derived GEA↔eGRID or state mapping.** Lost (C4): it's an invented
  mapping, and it's ambiguous where regions overlap.

## Consequences

- A user can model a declining grid by naming a region, a scenario and the
  construction year.
- **A known method gap at the join (C5, accepted).** NLR's historical
  intensities are eGRID-based, and their CH₄ and N₂O are higher than
  Cambium's. CAISO CH₄ is 9.37 g/MWh in 2023 and 2.1 g/MWh in 2030; N₂O is 1.13
  and 0.21 g/MWh. The joined series shows this change of method as a smooth
  decline to 2030.
  - Across the 18 regions (2023 historical vs Mid-case 2030), the CH₄ ratio
    runs from about 1.2× (SERTP) to 28× (NorthernGrid_West).
  - Valued at AR6 GWP100, the CH₄ and N₂O difference is 0.05–3.5 kg
    CO₂e/MWh, or 0.04–0.72% of the 2023 CO₂ intensity. It is largest in ISONE
    and WestConnect_North. For CAISO it is 0.47 kg, 0.26%.
  - Part of the difference is a real decline in fossil generation, so these
    are upper bounds on the method effect. The historical
  CO₂ also leaves out behind-the-meter PV, storage and Canadian imports, which
  Cambium includes (documentation §4.2: under 10 kg/MWh in most regions).
- Cambium is modelled: NLR says it should not be the sole basis for
  decisions.
- The Cambium rates come from Cambium's own emission factors (documentation
  §6.2), not EPA's. A Cambium line and an eGRID line for the same place will
  not match in 2023.
- The data is redistributed without a named licence, on Jay's decision. If
  NLR objects, the two files and the `cambium_*` fields can be removed without
  touching anything else.
- Cambium is released yearly. A new release needs a new record (or one that
  supersedes this), new source checksums and new check values. The scenario
  and region names may change.

## References

- Issue #85 (C0–C6, Jay's decisions 2026-11-20, the independent check). Issue
  #82 and record 0019 (B6, the absolute factor series, `to_study_years`).
  Record 0018 (`Trajectory`).
- Gagnon, Pieter; Pedro Andres Sanchez Perez; Julian Florez; James Morris;
  Marck Llerena Velasquez; and Jordan Eisenman. Cambium 2024 Data. National
  Renewable Energy Laboratory. https://scenarioviewer.nrel.gov (now
  https://scenarioviewer.nlr.gov/).
- Gagnon, P., et al. (2025). *Cambium 2024 Scenario Descriptions and
  Documentation*. National Renewable Energy Laboratory.
  https://docs.nlr.gov/docs/fy25osti/93005.pdf. §3 scenarios; §4.2 eGRID
  comparison and the 2025 step; §5.1 busbar and end use; §5.4 emission
  metrics; §6.2 emission factors.
- Workbooks for Cambium 2024 Data (CC BY 4.0; not used):
  https://data.openei.org/submissions/8395
