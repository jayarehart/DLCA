# 0003. Inventory input uses EN 15978 modules

- **Status:** Accepted
- **Date:** 2026-11-12
- **Decided by:** Jay Arehart

## Context

DLCA turns a building's emissions over time into cumulative GWI and GTP. The
inventory must say when each emission happens. Building LCA practice labels the
life cycle in stages, and a building's parts are replaced during its life.

## Decision

The inventory input will use the EN 15978 life cycle modules: A1–A3 (product),
A4–A5 (construction), B1–B7 (use), and C1–C4 (end of life). Module D (benefits
beyond the system boundary) is reported separately and not added to the
modules A–C total. Each item also takes a service life and a replacement
interval, so that emissions can be placed on the time axis.

## Alternatives considered

- **One emissions series per year with no module labels.** Lost: it throws away
  the stage structure that LCA users and EPDs already report in, and makes
  results harder to compare with other studies. (Rationale to confirm)
- **Fewer, custom stages** (for example build, use, end of life). Lost: it would
  not map onto EPD data. (Rationale to confirm)
- **Fold module D into the total.** Lost: D is a different kind of quantity
  (credits outside the system boundary) and EN 15978 reports it separately.
  (Rationale to confirm)

## Consequences

- Timing rules for each module (for example when A1–A3 occur, and how
  replacements repeat) are `science` decisions and need their own records.
- The input models in `src/dlca/models.py` will change to carry module labels,
  service life and replacement interval (a later change, not this record).

## References

- EN 15978, *Sustainability of construction works: assessment of environmental
  performance of buildings*.
