# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Planned as v0.2.0 (milestone M1, "Climate core"): the climate engine is rebuilt
as pure NumPy functions with cited AR5 and AR6 parameter sets.

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

### Fixed

- `gwi()`, `gtp()`, `static_gwp()` and `assess()` now raise `ValueError` for a
  horizon below `dlca.climate.MIN_HORIZON` (1e-6 yr). Before, a tiny horizon
  such as 2.22e-16 raised `ZeroDivisionError` in `gtp()` or returned wrong
  values without an error (#47, decision record 0011, Proposed).
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
