# 0013. Inventory input schemas: `BuildingTotals` and `BuildingInventory`

- **Status:** Accepted
- **Date:** 2026-11-19
- **Decided by:** Jay Arehart, 2026-11-19 (decisions S1–S15 on #57)
- **Supersedes:** 0003, in part: its module D and its service-life and
  replacement-interval sentences. The rest of 0003 stands.

## Context

M2 needs an input that says what a building emits, by EN 15978 module, so the
timing engine (#58) can turn it into the yearly series `assess()` takes (kg
per year under `co2`, `ch4`, `ch4_fossil`, `n2o`; record 0008). Inputs must be
JSON-serialisable (record 0005). Issue #57 holds the proposal and Jay's
decisions S1–S15 (2026-11-19). Jay changed the proposal in three ways that
depart from accepted record 0003. The tool drops module D. Replacements are
entered as dated events instead of derived from service life. There are two
schemas, for whole-building totals and for a detailed inventory.

## Decision

We will accept building input in one of two pydantic v2 schemas in
`dlca.inventory`. Both refuse unknown fields (`extra="forbid"`) and use strict
types, so `"60"` or `60.5` is not a year.

**Shared parts.**

| Field | Type | Unit |
|---|---|---|
| `schema` | `"dlca.building_totals"` or `"dlca.building_inventory"`, required | - |
| `schema_version` | the integer `1` | - |
| `name` | non-empty string, no leading or trailing whitespace | - |
| `study_period` | whole number ≥ 1 | years |
| `GasAmounts` | `co2`, `ch4` (non-fossil), `ch4_fossil`, `n2o`; finite floats, default 0, negative allowed | kg of each gas (see the unit of the field that holds it) |
| `Event` | `year` (whole number, 1 ≤ year ≤ `study_period`), `amounts: GasAmounts` | year of the study period |

Module names: one-off `A1-A3`, `A4`, `A5`, `C1`, `C2`, `C3`, `C4`. Per year
`B1`, `B2`, `B3`, `B6`, `B7`, constant each year (S12). B4 (replacement) and
B5 (refurbishment) are lists of `Event`s, never plain amounts (S4, S15).

**`BuildingTotals`** holds whole-building amounts.

| Field | Unit |
|---|---|
| `modules: {one-off module: GasAmounts}` | kg |
| `per_year: {B1, B2, B3, B6, B7: GasAmounts}` | kg per year |
| `b4`, `b5: list[Event]` | kg per event |

**`BuildingInventory`** holds `assemblies` (at least one, unique names), each
with `materials` (at least one, unique names). The building has
`per_year: {B6, B7: GasAmounts}` in kg per year. A `Material` has:

| Field | Unit |
|---|---|
| `quantity`: finite, > 0 | in `unit` |
| `unit`: one of `m3`, `m2`, `m`, `kg`, `t`, `item` | the declared unit |
| `modules: {one-off module: GasAmounts}` | kg per declared unit |
| `per_year: {B1, B2, B3: GasAmounts}` | kg per declared unit per year |
| `b4`, `b5: list[Event]` | kg per declared unit per event (S14) |

The emitted amount is `quantity` × the per-unit amount. There is no unit
conversion. A building is all totals or all inventory, never mixed (S13).

**Rules.**
- A B4 amount is the whole replacement: the new item's A1–A5 plus the old
  item's C1–C4. The tool adds nothing to it.
- Two events in the same year add together.
- `ch4` is non-fossil CH₄ with no carbon credit (record 0010, C8). There is no
  biogenic field until M3 (S7).
- Module D, `service_life` and `replacement_interval` are refused.
- A B4 event may not fall in the end-of-life year. That check waits for #58's
  end-of-life rule.

**Supersedes 0003 on two points.**
- "Module D … is reported separately and not added to the modules A–C total."
  Replaced by: module D is not part of the tool, and D input is refused.
- "Each item also takes a service life and a replacement interval, so that
  emissions can be placed on the time axis." Replaced by: replacements (B4)
  and refurbishments (B5) are dated events that the user enters.

0003's module list (A1–A3, A4–A5, B1–B7, C1–C4) and its call for a timing
record per module stand.

## Alternatives considered

- **One three-level schema only** (the first proposal). Lost: Jay wants to
  enter whole-building totals without inventing quantities (S1).
- **B4 derived from service life and replacement interval** (the first
  proposal, S4). Lost: Jay chose user-given dated events. They state the year
  and amount outright, and avoid a derivation rule whose end-of-study-period
  handling is itself a choice.
- **Module D in its own field, never summed** (S8 as first proposed). Lost:
  Jay dropped D from the tool's scope.
- **One `ch4` amount with a `fossil` flag.** Lost: one module often has both
  kinds, and record 0008 already rejected a flag on `assess()` (S5).
- **A reserved, unused `biogenic` field.** Lost: a field that is accepted but
  ignored is a silent trap. M3 adds one with a `schema_version` bump (S7).
- **A1, A2 and A3 as separate modules.** Lost for now: most EPDs declare
  A1–A3 together (S2). It can be added later without breaking files.

## Consequences

- #58 reduces either schema to one internal form, so #59 and `assess()` see
  one type. #58 places events in the year given, so it needs no replacement
  rule, but it must fix the end-of-life year. Record 0014 puts end of life in
  year RSP + 1, so the 1..`study_period` range already keeps every B4 and B5
  event out of the end-of-life year; no separate check is needed.
  `test_event_in_end_of_life_year_refused` confirms it (#58).
- Replacement counts are the user's job. A file with too few B4 events is not
  caught.
- The JSON Schemas are committed as `src/dlca/data/building_totals.schema.json`
  and `src/dlca/data/building_inventory.schema.json`, and a test keeps each in
  sync with its model. Any change to either schema bumps `schema_version`.
- The JSON Schema files are weaker than the models: they cannot say "event
  year ≤ `study_period`" or "names unique among siblings". An outside
  validator that passes a file is not enough; load it with the models.
- JSON text with a repeated key (for example `"A4"` twice) is read with the
  last value winning, as Python's `json` does. Refusing it needs a loader
  around the models, which is not part of this record.
- Adds pydantic (≥ 2.11) as a runtime dependency.

## References

- Issue #57 (proposal, updates and decisions S1–S15); #58, #59, #60.
- Records 0003 (partly superseded), 0005, 0008, 0010.
- EN 15978:2011, *Sustainability of construction works: assessment of
  environmental performance of buildings, calculation method*. Clause numbers
  and titles were checked against the table of contents in the public preview
  (SIST EN 15978:2011, pages 2–3). The clause bodies and the module figure
  were not checked, because the preview stops before clause 7.
  - 7.3 Reference study period (`study_period`).
  - 7.4 System boundary: 7.4.2 product stage, modules A1 to A3 (`A1-A3`);
    7.4.3 construction process stage, modules A4 and A5; 7.4.4 use stage,
    modules B1–B7; 7.4.5 end of life stage, modules C1–C4; 7.4.6 benefits and
    loads beyond the system boundary, module D (out of scope here).
  - 8.6.2–8.6.6 name the use-stage modules: B1 use; B2, B3, B4 maintenance,
    repair, replacement; B5 refurbishment; B6 operational energy use; B7
    operational water use.
  - 9.3.3 Replaceable components and number of replacements. Under this
    record, the user applies that rule when writing B4 events. The tool does
    not apply it.
