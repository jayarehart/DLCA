# 0014. Module timing: when each EN 15978 module's emissions happen

- **Status:** Proposed
- **Date:** 2026-11-19
- **Decided by:**

## Context

`assess()` takes kg per year of each gas, index 0 = year 0 (record 0008). The
inventory schemas (record 0013) give amounts per EN 15978 module, with B4 and
B5 as dated events, but say nothing about the year of the other modules.
Record 0003 calls for a timing rule per module. EN 15978 is a static method;
as far as we could check (clause titles only, see References) it gives no
calendar year to any module, so the years below are our convention. The old
builder `create_flux_mat` assigned instead of adding amounts and spread C over
15 years (strict xfail `test_building_lifecycle_flux_builder`). Issue #58 holds
the proposal (T1–T6); Jay decided on 2026-11-19: T1 changed so C falls in
RSP + 1, T2–T6 as recommended.

## Decision

We will place a building's emissions with `dlca.inventory.timeline(building,
*, horizon=100, years=None) -> Timeline`, a pure function. With RSP the
`study_period`:

| Module | Year(s) |
|---|---|
| A1-A3, A4, A5 | 0 |
| B1, B2, B3, B6, B7 | each of 1..RSP (RSP years in all) |
| B4, B5 events | the event's year, 1..RSP |
| C1, C2, C3, C4 | RSP + 1 (the end-of-life year), one pulse |

- Amounts in the same year add (part by part, and in every sum).
- No event can fall in the end-of-life year, because the schema keeps events
  in 1..RSP. So the last allowed B4 (and B5) year is RSP (T1, T2).
- The series has `RSP + H + 2` years (0..RSP + 1 + H), so the end-of-life pulse
  gets a full horizon H. `years` can make it longer (zeros), never shorter.
  H is a whole number ≥ 1; pass the same H to `assess()` (T3).
- `Timeline` holds one read-only series per `(assembly, material, module)`.
  `BuildingTotals` amounts and an inventory's B6/B7 use `(None, None,
  module)`. A material's amounts are multiplied by its `quantity`. B4 and B5
  are one part each, all events added. `emissions()` gives the summed mapping
  for `assess()`; `by_module()` and `by_material()` give breakdowns (T4).
- JSON for `Timeline` is left to #59 (T5).

## Alternatives considered

- **C1–C4 in year RSP** (the proposal, and the Cooper `building_lifecycle`
  case, which puts B + C in year 60 of 60). Lost: Jay chose RSP + 1, so the
  building is used through year RSP and demolished the year after. The new
  engine therefore differs from that spreadsheet case by one year for C.
- **B modules in years 0..RSP − 1.** Lost: it puts use in the construction
  year.
- **A fixed series length** (Cooper uses 0..500). Lost: it ignores H and is too
  short when RSP + 1 + H > 500.
- **`assess()` pads the series itself.** Lost: it changes record 0008's entry
  point for a convenience.
- **Return only the summed mapping.** Lost: #59 would rebuild per-part series,
  so the timing logic would exist twice.

## Consequences

- Strict xfail `test_b4_in_end_of_life_year_refused` (record 0013) is replaced
  by an active test for year RSP + 1; record 0013's pending check is met by the
  existing 1..RSP range.
- End of life falls outside the study period, one year after it. Totals over
  the series include it; a user summing "emissions within the study period"
  would miss C.
- `gwi().sliding` and `gtp().sliding` weight each emission by the time left to
  year H counted from year 0, so with RSP + 1 ≥ H the C pulse counts zero in
  those two series whatever the length. That is a metric choice, for #59 to
  report, not a timing rule.
- Time-varying factors (M4) and biogenic uptake (M3) will change amounts, not
  these years. A new module or a per-year profile needs a new record.

## References

- Issue #58 (proposal T1–T6 and Jay's decision); #57 (S11, S12); #59, #61.
- Records 0003, 0008, 0013.
- EN 15978:2011, 7.3 (reference study period) and 7.4.2–7.4.5 (modules A–C),
  checked by title only in the public table of contents; the clause bodies
  were not read.
- Cooper et al. (2020) spreadsheet, case `building_lifecycle`
  (`tests/reference/README.md`).
