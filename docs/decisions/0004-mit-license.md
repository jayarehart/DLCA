# 0004. MIT license

- **Status:** Accepted
- **Date:** 2026-11-12
- **Decided by:** Jay Arehart

## Context

`LICENSE.txt` was empty, so the code was legally "all rights reserved" and
nobody could reuse or cite it cleanly. This blocked making the repository
public. The project is research software that should be easy to reuse and cite.

## Decision

We will release the repository under the MIT license, copyright Jay Arehart and
contributors. The same license applies to prose and docs. Issue #8 offered
CC BY 4.0 for prose and figures with MIT for code only, with a default of MIT
for everything.

## Alternatives considered

- **Leave the license empty** (all rights reserved). Lost: it forbids reuse and
  clean citation, and blocks the public release.
- **MIT for code and CC BY 4.0 for prose and figures.** Lost: the issue's
  default was MIT for everything, and one license is simpler. (Rationale to
  confirm)
- **A copyleft license such as GPL or Apache 2.0.** Lost: MIT is the lightest
  and most permissive for reuse. (Rationale to confirm)

## Consequences

- Anyone may use, copy, modify and distribute the code with the notice kept.
- `CITATION.cff` carries the license and how to cite.
- Reference data taken from CC-BY sources keeps its own attribution
  (see 0001).

## References

- Issue #8.
