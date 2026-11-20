# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Decision records 0013 (inventory input schemas), 0014 (module timing) and
  0015 (building roll-up and breakdown) are now Accepted. Record 0003 is now
  "Superseded in part by 0013": module D, and service life and replacement
  interval, no longer apply. No code or output changes.

## [0.3.0] - 2026-11-20

Milestone M2, "Inventory and timing": a building inventory now goes from
EN 15978 modules to yearly emissions, climate results, and a breakdown by
part.

### Added

- `dlca.inventory.BuildingTotals` and `dlca.inventory.BuildingInventory`, two
  pydantic input schemas (#57, decision record 0013, Proposed).
  `BuildingTotals` holds whole-building kg per module. `BuildingInventory`
  holds assemblies of materials, each a quantity in a declared unit times kg
  per unit. Modules are A1-A3, A4, A5, B1–B3, B6, B7 and C1–C4, in kg of each
  gas under the `assess()` keys. B4 (replacement) and B5 (refurbishment) are
  dated events the user enters. There is no module D and no service life.
  Each file carries a `schema` tag and `schema_version` 1, and the JSON Schema
  for each ships in `dlca/data/`.
- `dlca.inventory.timeline(building, *, horizon=100, years=None)` returns a
  `Timeline` of yearly series per assembly, material and module (#58, record
  0014, Proposed). A1–A5 fall in year 0, B1–B3, B6 and B7 in each of years 1
  to the study period (RSP), B4 and B5 in their event years, and C1–C4 in
  year RSP + 1. Amounts in the same year add. The series runs RSP + H + 2
  years. `Timeline.emissions()` gives the input `dlca.assess()` takes.
- `dlca.assess_building(building, *, parameters="AR6", horizon=100)` returns a
  `BuildingResult`: the whole-building `Result` plus GWI and GTP (dynamic,
  sliding and static) for each module, gas, material and assembly (#59, record
  0015, Proposed). The rows of each breakdown add up to the total. Rows with
  emissions in year H or later, which the sliding series cannot count, are
  listed in `sliding_incomplete` and raise one `UserWarning`. `BuildingResult`
  and `Timeline` round-trip through JSON (`dlca.building_result` and
  `dlca.timeline`, schema version 1). `Result` stays at schema version 4.
- Illustrative example inventories for tests (timber, steel and concrete
  floors, and one `BuildingTotals` file) with pytest fixtures (#60). The
  numbers are made up but plausible, and labelled as such.
- `pydantic>=2.11` as a runtime dependency.

### Changed

- Record 0013 proposes to supersede accepted record 0003 on two points: module
  D is no longer part of DLCA, and B4 and B5 are dated events instead of being
  derived from a service life and replacement interval. Record 0003's status
  changes when 0013 is accepted.

### Removed

- The old inventory code (#61): `dlca.engine` (`EmissionsFluxEngine` with
  `create_flux_mat`, `flux_total` and `create_flux_operational`) and, from
  `dlca.models`, `AnalysisPeriod`, `MatEmissionsTiming`,
  `EmissionsInventoryGHGi`, `EmissionInventoryBio`, `EmissionsInventoryAllGHG`,
  `EmissionsFluxMat`, `EmissionsFluxOperational`, `EmissionsFluxTotal`,
  `MaterialTypes` and `GHGTypes`. None of them were in `dlca.__all__`.
  Use `dlca.inventory.BuildingTotals` or `BuildingInventory` for the input and
  `dlca.inventory.timeline(...).emissions()` for the yearly series that
  `dlca.assess()` takes. The removed builder had two bugs that the new one does not have:
  module amounts in the same year overwrote each other, and C was repeated over
  15 years.
- Biogenic regrowth uptake (the Cherubini Gaussian in `create_flux_mat`). DLCA
  has no regrowth model until M3. Until then, pass uptake as negative `co2`.
  The old code is at `git show v0.2.0:src/dlca/engine.py`.

## [0.2.0] - 2026-11-19

Milestone M1, "Climate core": the climate engine is rebuilt as pure NumPy
functions with cited AR5 and AR6 parameter sets.

### Added

- `dlca.assess(emissions, *, parameters="AR6", horizon=100)` returns a
  `dlca.Result`. The result is frozen, its arrays are read-only, and it
  round-trips through JSON exactly (`to_dict()` / `from_dict()`). It records the
  parameter set: its name, full values, `fingerprint()` and the CCF flag
  (#31, decision record 0008, Proposed).
- `dlca.climate`, the climate engine as pure functions:
  - `burden()` (#27);
  - `forcing()`, `agwp()` and `gwi()` (#28);
  - `temperature()`, `agtp()` and `gtp()` (#29);
  - `static_gwp()` and the `ch4_fossil` emissions key (#30).

  Each result type has `to_dict()` and `from_dict()`.
- Cited AR5 and AR6 parameter sets: `ClimateParameters`, `get_parameters()`
  and `available_parameter_sets()`. AR6 is the default (#26, records 0002 and
  0007).
- Reference tests against the corrected Cooper et al. (2020) spreadsheet. The
  tests also include analytic checks against the IPCC tables and property
  tests. Each reference case now names its parameter set in `settings.csv`.
- MIT `LICENSE`, `CITATION.cff`, `SECURITY.md` and a project `README.md`.
- This changelog.

### Changed

- Fossil CH₄ is given as the `ch4_fossil` emissions key, not as a flag (#30).
- `Burden`, `Forcing` and `Temperature` record `parameter_fingerprint`, also in
  `to_dict()`. `forcing()` and `temperature()` raise `ValueError` for a burden
  made with another parameter set, or with a variant of the same one. `Result`
  refuses a burden, forcing or temperature of another set, and its schema version is now 2 (#37,
  decision record 0009, Proposed).
- **AR6 CH₄ and N₂O now include the carbon-cycle feedback (CCF)** of Gasser et
  al. (2017), computed exactly (#33, decision record 0010, Proposed). AR6 CH₄
  GWP₁₀₀ goes from 26.37 to 28.02, CH₄ GWP₂₀ from 79.15 to 81.27, CH₄ GTP₁₀₀
  from 4.90 to 5.58, and N₂O GWP₁₀₀ from 260.6 to 274.4; CO₂ and all AR5 results
  are unchanged. The printed Table 7.SM.7 values (27.9, 273) carry the IPCC
  code's 0.1-year step error in the CCF term. `Burden` has a new `ccf_co2`
  series; `ClimateParameters` has `ccf_gamma`, `ccf_weights`, `ccf_timescales`
  and `molar_mass_c`; the `Result` schema version is now 3. For the old
  behaviour use `dataclasses.replace(get_parameters("AR6"),
  carbon_cycle_feedback=False)`; AR5 refuses CCF.
- `GWI`, `GTP` and `StaticGWP` also record `parameter_fingerprint`, in
  `to_dict()` too, and `from_dict()` requires it. `Result` now refuses any of
  its six components made with another parameter set, and its schema version is
  now 4. No output value changes (#46, decision record 0009, Proposed).

### Fixed

- `gwi()`, `gtp()`, `static_gwp()` and `assess()` now raise `ValueError` for a
  horizon below `dlca.climate.MIN_HORIZON` (1e-6 yr). Before, a tiny horizon
  such as 2.22e-16 raised `ZeroDivisionError` in `gtp()` or returned wrong
  values without an error (#47, decision record 0012).
- `EmissionsInventoryAllGHG` raised on matching materials and accepted
  mismatched ones. It now raises when the CO₂, CH₄, N₂O and biogenic-CO₂
  materials differ (#31).
- The fossil CH₄ oxidation order in the burden (#27).
- The AGTP of CO₂ third-pool slip in the reference spreadsheet, and the CH₄
  tables made with 16.00 g/mol (#15).

### Removed

- `DLCAEngine`, `DLCAInputData` and `DLCAResults`. Use `dlca.assess()`,
  `dlca.get_parameters()` and `dlca.Result` instead (#31).
- The pasted `AGWP_supp_data.csv` and `AGTP_supp_data.csv` tables and their
  `csv_loader` functions. `agwp()` and `agtp()` compute these values in closed
  form (#31).
- Empty `LICENSE.txt` and `CHANGES.txt` placeholders.

[Unreleased]: https://github.com/jayarehart/DLCA/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/jayarehart/DLCA/releases/tag/v0.3.0
[0.2.0]: https://github.com/jayarehart/DLCA/releases/tag/v0.2.0
