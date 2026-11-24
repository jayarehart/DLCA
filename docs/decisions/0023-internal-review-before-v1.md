# 0023. Internal review gate before v1.0

- **Status:** Accepted
- **Date:** 2026-11-24
- **Decided by:** Jay Arehart, accepted 2026-11-24 (#120, PR #121)

## Context

Before v1.0, every science PR was reviewed by Jay and by a fresh agent session
(record 0006). No one outside that loop has reviewed the package as a whole.
v1.0 starts the stability promise of record 0022, and the JOSS paper and the
Zenodo DOI will make the package citable. A wrong result or a misleading
claim found after that is much harder to fix.

## Decision

We will hold an internal review, milestone M5r, between the methodology page
and tutorials (#98, #99) and the v1.0.0 tag and JOSS submission (#104, #102):

1. Jay tags a release candidate (`v1.0.0rc1`), and everyone reviews that tag.
2. Jay and colleagues each take one or two areas from the review packet
   (`docs/reviews/v1.0-internal/README.md`) and file one issue per finding
   with the **Review finding** form. Each finding gives evidence from outside
   the code, as for the independent check in record 0006.
3. At a wrap-up meeting, reviewers present their findings and proposed fixes.
   Jay sorts each one as blocker, should-fix or later.
4. Every blocker is fixed through its normal lane, and the reviewer who raised
   it confirms the fix. If output numbers move, a new rc is tagged and the
   changed areas are re-checked.
5. v1.0.0 and the JOSS submission wait until every blocker is closed and the
   review summary, including what was not reviewed, is written in the packet.

## Alternatives considered

- **No separate review; rely on the per-PR reviews.** Lost: per-PR reviews
  check one change at a time and miss problems that only show across the
  package, such as double counting between modules or docs that contradict
  the code.
- **Let the JOSS review be the external review.** Lost: JOSS reviewers check
  software quality, not the science in detail, and fixes found then would
  come after the DOI and the v1.0 promise.
- **Review `main` as it moves, without a release candidate.** Lost: reviewers
  would look at different code, and a finding could not be tied to a version.

## Consequences

- v1.0.0 and the JOSS submission are delayed by the review window (planned at
  two to three weeks) plus the time to fix blockers.
- The repository is already public, so findings are public issues. Reviewers
  must not post unpublished or restricted data; the form says so.
- Each rc tag creates a GitHub pre-release. If the Zenodo integration archives
  pre-releases, each rc also gets a DOI version unless Jay turns that off.
  Not yet checked.
- The summary's "not reviewed" list becomes known limits of v1.0, and can go
  into the paper.

## References

- #120 (setting up the review), roadmap milestone M5r.
- Record 0006 (cairn practices: independent check, fresh-session review).
- Record 0022 (v1.0 public API and its stability promise).
