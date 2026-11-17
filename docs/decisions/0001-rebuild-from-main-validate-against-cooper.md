# 0001. Rebuild from `main`; validate against the Cooper et al. spreadsheet

- **Status:** Accepted
- **Date:** 2026-11-12
- **Decided by:** Jay Arehart

## Context

`src/dlca/engine.py` is a Python port of the *temporal climate impacts*
spreadsheet by Sam Cooper and colleagues (version 5, 01/10/2020, licensed
CC-BY), published as `mmc2.xlsx` supplementary material to Cooper et al.
(2020). The column names in the port match the spreadsheet. The code on `main`
also carried unused legacy code and had no validation reference. The spreadsheet
is an independent implementation, so it checks the port. It does not check the
underlying physics.

## Decision

We will rebuild the package from `main`. We will use the Cooper et al. (2020)
spreadsheet as the validation reference for the port: reference cases are
generated from it and compared with the engine (issue #15). We will validate the
physics separately against published IPCC values (milestone M1). Unused legacy
code leaves the package and stays in git history (tag `legacy-2023`).

## Alternatives considered

- **Check the code only against itself** (regression tests of its own output).
  Lost: a value the code produced is not an independent check
  (see `AGENTS.md`, science rule 1).
- **Validate the physics with the spreadsheet alone.** Lost: the spreadsheet
  uses one parameter set (IPCC AR5) and shares the port's method, so agreement
  proves the port matches it, not that the physics is right. Published IPCC
  values cover that.
- **Continue from another branch or start over.** Lost: `main` already holds the
  engine ported from the spreadsheet. (Rationale to confirm)

## Consequences

- Reference cases carry the CC-BY attribution and cite the paper wherever used.
- Where the engine disagrees with the spreadsheet, tests are marked
  `xfail(strict=True)`; expected values are never edited to match.
- AR6 reference values are not available from this spreadsheet and must come
  from published tables.

## References

- Cooper, S. J. G., Green, R., Hattam, L., Röder, M., Welfle, A., & McManus, M.
  (2020). *Biomass and Bioenergy*, 142, 105778.
  https://doi.org/10.1016/j.biombioe.2020.105778
- Issues #9, #15; `legacy/README.md`; tag `legacy-2023`.
