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

### Fixed

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
