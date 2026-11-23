# 0019. Operational energy (B6) from energy use by fuel

- **Status:** Accepted
- **Date:** 2026-11-20
- **Decided by:** Jay Arehart, accepted 2026-11-23 (O1–O4 on #82, 2026-11-20; rounded eGRID CH₄/N₂O rates accepted after review, PR #89)

## Context

Until now, B6 (operational energy use) could only be entered as kg of each gas
per year (`per_year["B6"]`, constant over years 1..RSP, record 0014). Users
usually know energy use by fuel instead: kWh of electricity, therms of gas.
The package shipped eGRID2020 electricity factors, which were unused. It also
shipped an old `BldgDetails` model that read **fake** DOE energy-use data and
hard-coded EPA 2014 fuel factors, one of them wrong: natural gas at 54.06 kg
CO₂/mmBtu, where the EPA table it cites gives 53.06. Issue #82 holds the
questions (O1–O4) and Jay's decisions of 2026-11-20. Record 0018 (#81) defines
the shared `Trajectory` type that B6 reuses.

## Decision

We will accept B6 as energy use by fuel, convert it with packaged or
user-supplied factors, and place it in years 1..RSP.

**Input.** `BuildingTotals` and `BuildingInventory` get the same optional
building-level field `energy: list[EnergyUse]`. A building gives `energy` or
`per_year["B6"]`, never both, so nothing is counted twice. Each `EnergyUse`
line has:

| Field | Meaning |
|---|---|
| `fuel` | `"electricity"`, `"natural_gas"` or `"fuel_oil_2"` |
| `amount` | energy used per year, finite, ≥ 0 |
| `unit` | an energy unit from the #80 table: `kWh`, `MJ`, `GJ`, `MMBtu`, `kBtu`, `therm` |
| factor source | electricity: exactly one of `egrid_subregion`, `egrid_state` or `factor`; fuels: `factor`, or none for the packaged Hub factor |
| `trajectory` | optional `Trajectory` (record 0018); `constant` when absent |

- `factor` is kg of each gas (`co2`, `ch4`, `ch4_fossil`, `n2o`) per one
  `unit` of energy (the line's own unit). It is either one `GasAmounts`, constant, or an
  **absolute series**: a list of `GasAmounts`, where entry *i* is study year
  *i*. B6 uses entries 1..RSP, and a short series holds its last value
  (Jay, 2026-11-20). A series factor may not have a non-constant
  `trajectory`, so nothing is scaled twice.
- Subregion and state codes are separate fields and are looked up only in
  their own table.

**Factors (O1, O2).**
- Electricity: eGRID2023 Rev 2 (data year 2023, released 2025-06-12), annual
  total output emission rates of CO₂, CH₄ and N₂O by subregion (`SRL23`
  sheet) and by state (`ST23`), as EPA publishes them in
  `egrid2023_data_rev2.xlsx` (lb/MWh, three decimals). The package stores
  lb/MWh and converts with 1 lb = 0.45359237 kg and 1 MWh = 3 600 MJ.
- Fuels: EPA GHG Emission Factors Hub 2025, Table 1 (from 40 CFR 98 Tables
  C-1 and C-2): natural gas 53.06 kg CO₂, 1.0 g CH₄ and 0.10 g N₂O per mmBtu;
  fuel oil No. 2 73.96 kg CO₂, 3.0 g CH₄ and 0.60 g N₂O per mmBtu.
- Scope: combustion and generation only, as EPA publishes it. No
  transmission and distribution losses, no upstream (fuel supply) emissions.
- CH₄ from the packaged factors goes under `ch4_fossil`. A user factor names
  its own keys.

**Trajectory (O3).** Each energy line may carry its own `Trajectory`
(constant, linear or series, as record 0018 defines them). B6 in year *y*
(1..RSP) is amount × factor(*y*) × m(*y*). Like record 0018's E2, m scales
only the fossil gases (`co2`, `ch4_fossil`, `n2o`). The base factor is used as
published, with no shift from the 2023 data year to study year 0.

**Calendar years.** `dlca.inventory.to_study_years(values, year_zero,
n_years)` turns `{calendar year: value}` into a list indexed by study year
(0..n_years − 1): a straight line between given years, the first value held
before the first given year, and the last value held after the last. It
refuses years that are not whole numbers, values that are not finite or are
negative, and an empty mapping. It works on plain numbers, so one call per
gas builds an absolute factor series or a trajectory series, for example from
NREL Cambium data, which is not packaged (#85).

**Timeline.** Energy lines add into the one `(None, None, "B6")` part, the same
part `per_year["B6"]` uses, so breakdowns and the roll-up do not change form.
Inventory `schema_version` goes from 4 (record 0018) to 5, and version 1–4
files still load and may not use `energy`. `BuildingResult` JSON, which
embeds the building, goes from 4 to 5 and still reads 1–4. `Result` and
`Timeline` JSON do not change. A series `factor` together with a non-constant
`trajectory` is refused.

**Removed.** `dlca.models` (the old building and energy models),
`DOE_energyuse_fake.csv`, `dlca.data.csv_loader` and the eGRID2020 files, with
their test.

## Alternatives considered

- **Keep eGRID2020.** Lost: eGRID2023 is EPA's latest release, and EPA
  advises using the latest factors. CAMX CO₂ moves from 513.45 to 428.464
  lb/MWh (−17%).
- **Add T&D losses (eGRID grid gross loss) or upstream emissions.** Lost for
  now. EPA advises against applying grid gross loss to an end user's
  emissions, and upstream emissions need a second, non-EPA source. Users can
  pass their own factor.
- **One trajectory for all of B6.** Lost: it would scale gas with the grid.
- **A Cambium projection as a ratio laid on the eGRID baseline.** Lost: it
  mixes measured and modelled data, different regions and possibly
  different emission scopes. The absolute factor series covers this case.
- **Allow `energy` and `per_year["B6"]` together, adding them.** Lost: it
  invites double counting.
- **Recompute CH₄ and N₂O rates from annual emissions ÷ net generation, for
  more digits.** Lost: they would no longer be the values EPA publishes.
  The published N₂O rates have one or two significant figures (CAMX 0.003
  lb/MWh). For CAMX this is 0.2% of CO₂e at most.

## Consequences

- Users can enter B6 as kWh, therms and so on, and choose a grid region.
- Results for buildings without `energy` do not move.
- The packaged CH₄ and N₂O rates keep EPA's published rounding. Some are
  coarse: NYUP's N₂O rate (0.001 lb/MWh) could be off by up to ±50%, which is
  small in CO₂e terms. Jay accepted this for now (2026-11-20, after review).
- The packaged scope (no losses, no upstream) understates B6, most of all for
  natural gas. Docs must say so.
- `pandas` is no longer used by the package itself; dropping it from the
  runtime dependencies is left to a follow-up.
- A new eGRID release needs a new record (or a superseding one) and new
  check values.

## References

- Issue #82 (O1–O4, Jay's decisions 2026-11-20); #80 (unit table); #81 and
  record 0018 (`Trajectory`); #85 (Cambium follow-up).
- Records 0005, 0010, 0011, 0013, 0014, 0015, 0018.
- US EPA (2025). Emissions & Generation Resource Integrated Database (eGRID),
  2023, Revision 2, 12 June 2025. https://www.epa.gov/egrid. Public domain
  (eGRID FAQ, Q25). File `egrid2023_data_rev2.xlsx`, SHA-256
  `895cd81dd8662406189ad8adf5a2578dcb362cdb5cff7cca81b10ee6bd2447c6`.
- US EPA (2025). GHG Emission Factors Hub, January 2025, Tables 1 and 6.
  https://www.epa.gov/system/files/documents/2025-01/ghg-emission-factors-hub-2025.pdf
- US EPA (2014). Emission Factors for Greenhouse Gas Inventories, 4 April
  2014, Table 1 (natural gas 53.06).
