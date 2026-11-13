# 0002. Ship AR5 and AR6 parameter sets; AR6 is the default

- **Status:** Accepted
- **Date:** 2026-11-12
- **Decided by:** Jay Arehart

## Context

Climate results depend on parameters from IPCC assessment reports: CO₂ impulse
response, radiative efficiencies, gas lifetimes and the climate response model.
The reference spreadsheet (see 0001) uses the IPCC AR5 set. The current IPCC
assessment is AR6. Results that use different sets are not comparable unless the
set is known.

## Decision

We will ship both AR5 and AR6 parameter sets as cited data in
`src/dlca/data/`, each value traceable to its source. AR6 is the default. Every
result records the parameter set it used.

## Alternatives considered

- **AR5 only,** matching the spreadsheet. Lost: AR6 is the current assessment,
  and a new package would start out of date. (Rationale to confirm)
- **AR6 only.** Lost: the Cooper et al. reference cases use AR5, so the port
  could not be validated against them.
- **A single set chosen by the user, with no recorded default or provenance.**
  Lost: results would not say which parameters produced them, which hurts
  reproducibility. (Rationale to confirm)

## Consequences

- AR5 is used to reproduce the spreadsheet; AR6 reference values must come from
  published tables (milestone M1).
- Changing a parameter value is a `science` change and follows the deliberate
  lane.
- Result objects need a field for the parameter set; see 0005.

## References

- Issue #15 (what the spreadsheet contains); record 0001.
