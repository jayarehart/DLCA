# 0015. Building roll-up and breakdown: `assess_building()` and `BuildingResult`

- **Status:** Proposed
- **Date:** 2026-11-19
- **Decided by:**

## Context

Users need a building's climate result as a whole and also broken down by
module, gas and material (M2 roadmap item 3). `assess()` takes yearly
emissions and returns a `Result` (record 0008, JSON schema 4). `timeline()`
places a building's modules in time, one series per `(assembly, material,
module)` (record 0014). It left `Timeline`'s JSON form to #59 (T5). The engine
is linear in the emissions (property tests), so results for parts add up to
the whole. The sliding GWI and GTP give an emission in year k the horizon
`max(H − k, 0)`, so anything emitted in year H or later counts zero there. With
end of life in year RSP + 1, that happens whenever RSP + 1 ≥ H. Issue #59 holds
the proposal (R1–R8). Jay approved it as recommended on 2026-11-19.

## Decision

We will add `dlca.assess_building(building, *, parameters="AR6", horizon=100,
years=None) -> BuildingResult` (R1). It calls `timeline()` and then `assess()`.
`horizon` is a whole number. `assess()` is unchanged.

- **Breakdowns (R2).**
  - By module, in EN 15978 order, with B4 and B5 as one row each.
  - By gas, by input key (`co2`, `ch4`, `ch4_fossil`, `n2o`). A row holds what
    its key causes: `ch4_fossil` includes its oxidised CO₂, and the CH₄ and N₂O
    rows include the CO₂ their carbon-cycle feedback releases.
  - By material `(assembly, material)` and by assembly, for a
    `BuildingInventory` only. The building's own B6/B7 form one more row so
    that the rows add up to the total. That row is keyed `None` (JSON `null`),
    so it cannot clash with an assembly the user named "building".
  - There is no module × material table.
- **Metrics (R3).** Each row is a `Metrics` holding six read-only series over
  the whole timeline: GWI and GTP, each dynamic, sliding and static.
- **Format (R4).** `BuildingResult` holds the building input, `total` (a
  schema-4 `Result`), the four breakdowns, `horizon`, `years`,
  `sliding_cutoff_year` and `sliding_incomplete`. Its JSON is
  `schema: "dlca.building_result"`, `schema_version: 1`, and `from_dict()` is
  its exact inverse. `Result` stays at schema 4.
- **Cost (R5).** One `assess()` per breakdown row plus one for the total. There
  is no convolution shortcut.
- **Sliding cut-off (R6).** Every row keeps all six series.
  `sliding_cutoff_year` is H. `sliding_incomplete` maps each breakdown to the
  keys of its rows that have a non-zero emission in year H or later. If any row
  is listed, `assess_building()` gives one `UserWarning` that names the rows.
  Nothing is refused.
- **`Timeline` JSON (R7).** `Timeline.to_dict()`/`from_dict()` under
  `schema: "dlca.timeline"`, `schema_version: 1`. Parts are a list of
  `{assembly, material, module, co2, ch4, ch4_fossil, n2o}`. The timeline is
  not embedded in `BuildingResult`, since the stored building input rebuilds
  it.
- **Tolerance (R8).** In each breakdown, the rows equal the total to within
  `1e-9 × Σ|row|` in every year and series.

## Alternatives considered

- **`assess()` also accepts a building.** Lost: record 0008 fixes it as
  emissions in, `Result` out. Two input types would need two result shapes.
- **Breakdowns inside `Result` (schema 5).** Lost: they would sit empty for
  plain `assess()` calls.
- **One full `Result` per row.** Lost on size: about 110 kB of JSON per row at
  162 years (measured), mostly burden and forcing.
- **Only the values at the horizon.** Lost: it throws away the time profile,
  which is the point of a dynamic LCA.
- **Convolve each gas's impulse response with each part.** Lost for now: it is
  faster, but it would be a second copy of the climate maths. Measured: one
  `assess()` takes about 6.5 ms, so a 200-material building takes roughly 1.5 s
  (estimated from that rate, not timed).
- **Refuse when RSP + 1 ≥ H, or drop sliding then.** Lost: refusing blocks a
  common case (RSP = H = 100), and dropping sliding makes the format depend on
  the input. Documenting the gap alone leaves a zero C row that reads as "no
  impact".
- **A `"building"` string key for the B6/B7 row** (as first proposed). Changed
  to `None` during the work, because an assembly may be called "building".
  (Not a separate decision by Jay; flagged in the PR.)

## Consequences

- One call gives the whole building and every breakdown. A web backend can
  store `to_dict()` as it is.
- A breakdown row with a zero sliding value can be checked against
  `sliding_incomplete`. A zero there is a property of the metric, not "no
  impact".
- Any change to the `BuildingResult` or `Timeline` JSON must bump its own
  schema version.
- Run time grows with the number of rows: about 13 modules, 4 gases, M
  materials and A assemblies. A module × material table, or a faster path,
  needs a new record.
- Gas rows follow input keys, not gases in the air. A reader who wants "all
  CO₂ in the air" must add the CO₂ from fossil CH₄ and from the carbon-cycle
  feedback, which sit in the CH₄ and N₂O rows.

## References

- Issue #59 (proposal R1–R8 and Jay's approval); #57, #58 (T5), #65.
- Records 0005, 0008, 0013, 0014.
