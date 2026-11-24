# Notice for the eGRID2023 files

This notice covers two data files in this folder:

- `egrid2023_rev2_state.csv`
- `egrid2023_rev2_subregion.csv`

Unlike the Cambium files (see `CAMBIUM_NOTICE.md`), these carry no licence
restriction. They are US EPA data, and EPA publishes eGRID in the public
domain (eGRID FAQ, Q25). They are shipped here under no extra terms.

## Source

US EPA (2025). Emissions & Generation Resource Integrated Database (eGRID),
2023, Revision 2, released 12 June 2025. https://www.epa.gov/egrid

The values come from EPA's workbook `egrid2023_data_rev2.xlsx`: the annual
total output emission rates in the `SRL23` sheet (by eGRID subregion) and the
`ST23` sheet (by state).

## What DLCA changed

Nothing numerical. Each file keeps only the CO₂, CH₄ and N₂O output emission
rates, in lb/MWh at EPA's three-decimal precision. DLCA converts them to kg
when it uses them (1 lb = 0.45359237 kg). The choice of eGRID2023 and the
scope (combustion only, no transmission losses or upstream emissions) are in
`docs/decisions/0019-operational-energy-b6.md`.
