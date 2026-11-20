# Decision records

A decision record keeps the reason for a science or architecture choice beside
the code, so it does not live only in chat history. The records also feed the
methods paper and the JOSS review. The approach is adapted from
[MSUHydrogeology/cairn](https://github.com/MSUHydrogeology/cairn), in a lighter
form: records cover science and architecture decisions only, not every change.

## When to write one

Write a record for any decision that is:

- labelled `science` (equations, parameters, timing, reference data), or
- about the public API (function names, inputs, outputs, units), or
- an architecture choice that would be costly to reverse (licence, layout,
  tooling that shapes how people contribute).

Do not write one for typos, renames with no behaviour change, or routine
features that follow an agreed issue spec.

## How

1. Copy [`0000-template.md`](0000-template.md) to `NNNN-short-title.md`, using
   the next free four-digit number and a short lowercase hyphenated title.
2. Fill in every heading. Keep it to about one page. Link to longer material
   instead of pasting it.
3. Set Status to `Proposed`. Agents only ever propose. Jay Arehart sets
   `Accepted` and fills in "Decided by" and the date.
4. Link the record from the issue or PR it belongs to.

## Records are append-only

Once a record is `Accepted`, do not rewrite its Decision. If the decision
changes, write a new record that says which one it supersedes, and change only
the old record's Status line to `Superseded by NNNN`. Fixing a typo or a broken
link is fine.

## Index

| No. | Title | Status |
|-----|-------|--------|
| [0001](0001-rebuild-from-main-validate-against-cooper.md) | Rebuild from `main`; validate against the Cooper et al. spreadsheet | Accepted |
| [0002](0002-ar5-and-ar6-parameter-sets.md) | Ship AR5 and AR6 parameter sets; AR6 is the default | Accepted |
| [0003](0003-en-15978-inventory-modules.md) | Inventory input uses EN 15978 modules | Superseded in part by 0013 |
| [0004](0004-mit-license.md) | MIT license | Accepted |
| [0005](0005-backend-agnostic-api.md) | Backend-agnostic API | Accepted |
| [0006](0006-adopt-cairn-practices-subset.md) | Adopt a subset of cairn practices | Accepted |
| [0007](0007-climate-parameter-files.md) | Climate parameter files, `ClimateParameters` and the selector | Accepted |
| [0008](0008-assess-entry-point-and-result.md) | Public entry point `assess()` and the `Result` object | Proposed |
| [0009](0009-parameter-fingerprint-guard.md) | Climate results record their parameter set; mixing sets raises | Proposed |
| [0010](0010-carbon-cycle-feedback.md) | Carbon-cycle feedback for CH₄ and N₂O (AR6 on, exact) | Proposed |
| [0011](0011-fossil-ch4-oxidation-residual.md) | Fossil CH₄ oxidation keeps the perturbation lifetime; the AR6 gap is documented | Accepted |
| [0012](0012-minimum-horizon.md) | Minimum time horizon of 1e-6 yr | Accepted |
| [0013](0013-inventory-schema.md) | Inventory input schemas: `BuildingTotals` and `BuildingInventory` | Accepted |
| [0014](0014-module-timing.md) | Module timing: when each EN 15978 module's emissions happen | Accepted |
| [0015](0015-building-roll-up-and-breakdown.md) | Building roll-up and breakdown: `assess_building()` and `BuildingResult` | Accepted |
| [0016](0016-biogenic-carbon.md) | Biogenic carbon: declared uptake, regrowth options, storage report | Proposed |
