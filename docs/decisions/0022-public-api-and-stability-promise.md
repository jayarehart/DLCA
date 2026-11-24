# 0022. The v1.0 public API and its stability promise

- **Status:** Proposed
- **Date:** 2026-11-24
- **Decided by:**

## Context

v1.0.0 (milestone M5) is a semantic-versioning promise, but no record says what
it covers. At v0.5.0, `dlca.__all__` has eight names and `dlca.inventory.__all__`
has 35. `dlca.climate`, `dlca.parameters` and `dlca.result` each have an
`__all__`; the inventory submodules (`aggregate`, `biogenic`, `carbonation`,
`operational`, `schema`, `timing`, `units`) and `dlca.data` have none. Three
JSON formats are written with version numbers: the input schemas
(`schema_version` 6), `Result` (4) and `BuildingResult` (6), plus `Timeline`
(3). Issue #107 proposes a non-building entry point, `assess_inventory()`, for
a v1.x minor release, and names three things this record should not freeze
carelessly: `Timeline`, what `dlca.inventory` means, and `Metrics`. The API
reference of the docs site (#97) will show only the names listed here.

## Decision

We will treat the names below as the public API from v1.0.0, and follow
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) for them,
for the JSON formats and for the numbers, as set out here.

### 1. Public names (P1)

A name is public only if it is listed here. Everything else is internal and
may change in any release, even if it can be imported: every name that starts
with `_`, every module not listed below (the seven inventory submodules and
`dlca.data`), and names such as `MODULE_ORDER`, `BREAKDOWNS`,
`uptake_shares()` or `electricity_factor_per_mj()`. The public import path is
the one given; importing the same object from a submodule is not covered.

| Import from | Names |
|---|---|
| `dlca` (8) | `assess`, `Result`, `assess_building`, `BuildingResult`, `ClimateParameters`, `get_parameters`, `available_parameter_sets`, `DEFAULT_PARAMETER_SET` |
| `dlca.inventory`: input (15) | `BuildingTotals`, `BuildingInventory`, `Assembly`, `Material`, `GasAmounts`, `Event`, `Biogenic`, `Carbonation`, `Surface`, `Stockpile`, `EnergyUse`, `Trajectory`, `ConstantTrajectory`, `LinearTrajectory`, `SeriesTrajectory` |
| `dlca.inventory`: functions and results (10) | `assess_building`, `BuildingResult`, `Metrics`, `biogenic_balance`, `BiogenicBalance`, `timeline`, `Timeline`, `to_study_years`; warnings `BiogenicCarbonWarning`, `CarbonationWarning` |
| `dlca.inventory`: constants (10) | `SCHEMA_VERSION`, `TOTALS_TAG`, `INVENTORY_TAG`, `BUILDING_RESULT_SCHEMA`, `BUILDING_RESULT_SCHEMA_VERSION`, `TIMELINE_SCHEMA`, `TIMELINE_SCHEMA_VERSION`, `UPTAKE_MODULE`, `CARBONATION_UPTAKE_MODULE`, `CARBONATION_EOL_MODULE` |
| `dlca.climate` (19) | `burden`, `forcing`, `temperature`, `gwi`, `gtp`, `static_gwp`, `agwp`, `agtp`, `specific_forcing`; `Burden`, `Forcing`, `Temperature`, `GWI`, `GTP`, `StaticGWP`; `GASES`, `EMISSION_KEYS`, `MIN_HORIZON`, `CO2_PER_CH4_MASS_RATIO` |
| `dlca.parameters` (5) | the four in `dlca`, and `Source` |
| `dlca.result` (4) | `assess`, `Result`, `RESULT_SCHEMA`, `RESULT_SCHEMA_VERSION` |

The three `dlca.inventory` rows are exactly its 35-name `__all__` at v0.5.0,
and each other row is exactly that module's `__all__`, so no export has to
change. Step 2 adds a test that
fails if any of these sets changes without the test changing.

Within a public class, public means its non-underscore attributes, methods,
properties and pydantic fields. Dataclasses are promised for keyword
construction and attribute access, not field order. Exception *types*
(`ValueError`, `TypeError`, the two warning classes) are covered; message text
is not.

`dlca.climate` is public because `Result.burden`, `.gwi` and the rest are its
types, so their fields are reachable anyway, and record 0008 already points
users to its functions for a single series.

### 2. What counts as major, minor or patch (P2)

| Change | Release |
|---|---|
| Remove or rename a public name, argument or field; change a default; refuse an input that was valid; change a unit, sign, key or what a value means | **major** |
| Stop reading a JSON version that a 1.x release wrote | **major** |
| Change the default parameter set, or what a packaged set name means beyond the row below | **major** |
| Add a name, an optional argument or field, an entry point, a schema, a result type, a packaged data option (for example a new grid dataset or scenario) | minor |
| Add a module key, breakdown row type or field to a result, with a new JSON version that still reads the old ones | minor |
| Change any output number for an input that was valid before (a science change or a bug fix that moves numbers), always with a decision record or issue and a "Numbers changed" changelog entry stating which outputs, by how much and why | minor |
| Correct a packaged value that differs from its cited source (parameter set, eGRID, Cambium, Hub factors) | minor, as above |
| Drop a Python version past its end of life, or raise a dependency floor | minor |
| A fix, doc or speed change that leaves every output within rounding (relative 1e-12) and changes no public name | patch |

So a patch release never moves a number: `dlca ~= 1.N.0` gives fixes with
the same results. Results already carry `dlca_version` and the parameter
fingerprint, so a stored result says which release made it.

### 3. JSON formats (P3)

- **Input** (`dlca.building_totals`, `dlca.building_inventory`): a file
  valid at any 1.x `schema_version` keeps loading, with the same meaning,
  in every later 1.x. Any schema change bumps `schema_version` (record 0013)
  and is minor. Files written for a newer version need not load in an older
  release.
- **Results** (`Result` 4, `BuildingResult` 6, `Timeline` 3 at v0.5.0): the
  same rule. A new version is minor only if `from_dict()` still reads every
  earlier 1.x version. `Result.from_dict()` today reads only 4; that is
  correct at v1.0, and a later `Result` version must add 4 to what it reads.
- The packaged JSON Schema files are part of the input format; where they sit
  inside the package is internal.

### 4. Deprecation (P4)

Before anything public is removed or changed incompatibly, a minor release
marks it deprecated: it still works, raises `DeprecationWarning` with the
replacement and the earliest removal version, and the changelog lists it
under "Deprecated". It stays for at least one minor release and is removed
only in a major release. Reading an old JSON version is never deprecated
within 1.x.

### 5. The three points from #107

- **`dlca.inventory` (N1).** We promise its names, not that the namespace is
  building-only. New entry points, schemas and result types in it (for
  example `assess_inventory()`, `dlca.timed_inventory` and `InventoryResult`)
  are minor changes.
- **`Timeline` (N2).** `timeline()` and `Timeline` are public and
  **building-only**: their parts are keyed `(assembly, material, module)` over
  EN 15978 modules. A generic entry point gets its own timing type; it does not
  widen `Timeline`. New module keys stay possible as minor changes (rule
  P3), as carbonation was. `Timeline.from_dict()` refusing unknown modules is
  kept: it guards against misread files, and readers of newer files are not
  promised.
- **`Metrics` (N3).** `Metrics` is public for reading: its six series, `years`,
  `to_dict()` and `from_dict()` of dlca-written data. Adding a field is a
  minor change, provided the new field has a default and `from_dict()` still
  reads the old six-field form (the enclosing `BuildingResult` version tells
  which). Constructing `Metrics` by hand is allowed but only the six fields
  are promised. `from_dict()` keeps refusing unknown fields at v1.0.

## Alternatives considered

- **P1: only the eight `dlca` names are public; all submodules internal.**
  Lost: the input schema classes, `Metrics` and the `dlca.climate` result types
  are reached through public objects anyway, so hiding their names would not
  free us to change them. *Shows it wrong:* if the docs (#97–#99) need none of
  the submodule names, the smaller list costs nothing.
- **P1: move the input schemas to `dlca`.** Lost: two paths to the same name
  doubles what the reference and the test track; `dlca.inventory` is already
  where 0013 put them. (Judgement call.)
- **P1: `dlca.climate` internal.** Lost for the reachability reason above.
  *Shows it wrong:* a planned change to a climate function's signature (for
  example new gases) that would otherwise be a minor change.
- **P2: any number change is major.** Lost: every bug fix or source correction
  would need 2.0, which pushes fixes to wait or be skipped. *Shows it wrong:*
  users citing "DLCA 1.x" in papers and expecting the same numbers across
  minors. The "Numbers changed" entry and `dlca_version` in every result are
  the guard.
- **P2: number-moving bug fixes are patch.** Lost: a researcher who pins
  `~=1.N.0` would see numbers change without a minor bump.
- **N2: `Timeline` internal.** It keeps the most freedom for #107. Lost
  because `timeline()` is the only way to see when emissions happen (record
  0014), which the methodology docs (#98) and reviewers need. *Shows it
  wrong:* if #107's work finds that sharing one timing type would save
  substantial code, or if no doc or tutorial uses `timeline()`.
- **N2: a "provisional" label outside semver.** Lost: a second tier of
  promise is harder to explain than "building-only".
- **N3: `from_dict()` ignores unknown fields.** Lost: it drops data silently,
  against the strict style of 0013 (`extra="forbid"`) and the exact-inverse
  rule of 0008/0015.
- **N3: `Metrics` internal.** Lost: every `BuildingResult` breakdown row is
  a `Metrics`, so its fields are public whatever its name.

## Consequences

- At v1.0 no name needs to move: every existing `__all__` already matches P1
  (checked against `dir()` at v0.5.0). Step 2 of #96 adds
  `tests/unit/test_public_api.py`.
- Every PR that changes a public name, a JSON version or an output number has
  to say which release kind it needs; the PR template's "Numbers changed"
  heading already asks for the last.
- `assess_inventory()` (#107, M6) can land in a 1.x minor with its own types.
- Results stay reproducible within a minor line, not across minors. Numbers
  may move in a minor, always recorded.
- Not decided here: a `dlca.__version__` attribute (use
  `importlib.metadata.version("dlca")`), and which Python versions v1.0
  supports.

## References

- Issue #96 (this record), #107 (section 5), #97–#99, #102.
- Records 0005, 0007, 0008 (as amended by #95), 0009, 0010, 0013–0021.
- Semantic Versioning 2.0.0, https://semver.org/spec/v2.0.0.html.
