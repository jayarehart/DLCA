# 0024. The internal review is Jay and possibly one other reviewer

- **Status:** Proposed
- **Date:** 2026-11-24
- **Decided by:**

## Context

Record 0023 set up the internal review before v1.0 assuming several
colleagues, each taking one or two areas, and a wrap-up meeting where they
present findings. The review will actually be Jay Arehart, plus possibly
Fatemah Khajah. With one or two reviewers, splitting areas between people and
holding a presentation meeting don't fit, and Jay made every science decision
in the records, so where he reviews alone the review is not independent of
those decisions.

## Decision

This record supersedes record 0023, decisions 2, 3 and the "reviewer who
raised it" part of 4. The rest of 0023 stands: the release-candidate tag, the
evidence-from-outside-the-code requirement, re-checking after a new rc, and
the gate on v1.0.0 and the JOSS submission.

We will:

1. Have Jay review every area in the review packet
   (`docs/reviews/v1.0-internal/README.md`).
2. If Fatemah Khajah takes part, have her take the three science areas first
   (climate engine and parameters; inventory and timing; biogenic carbon,
   carbonation, B6 and trajectories), since a second reader is most useful
   where Jay made the decisions. Her areas are agreed before the review
   window opens.
3. Allow, for an area only Jay reviews, a first pass by an agent session that
   did not write the code. Its findings use the same form, are marked as
   agent findings, and Jay decides each one.
4. Replace the wrap-up meeting with a triage session: Jay, with Fatemah if
   she reviewed. If Jay reviews alone, triage can happen issue by issue.
5. Have the person who raised a finding confirm its fix. For Jay's findings
   and agent findings, Jay confirms the fix against the finding's evidence,
   not only against the tests.
6. Mark in the review summary every area that only Jay reviewed, and any
   agent first pass.

## Alternatives considered

- **Recruit several colleagues, one or two areas each** (record 0023 as
  written). Lost: Jay chose a small review. More reviewers would give more
  independence but take longer to arrange.
- **Jay alone, with no agent first pass.** Lost: it leaves the areas Jay
  reviews alone checked only against his own choices. A fresh agent pass is
  cheap and sometimes catches what the author misses. (Its value here is a
  guess; it has not been tried on a whole area.)

## Consequences

- The review is faster to arrange but less independent than 0023 assumed.
  The evidence-from-outside-the-code field, the agent first pass and
  Fatemah's science areas reduce this but don't remove it. The review summary
  makes the gap visible.
- If Fatemah can't take part, every area is Jay-only, and the summary and the
  JOSS paper should say so.

## References

- #123 (this change), #120 and PR #121 (the review setup).
- Record 0023 (internal review gate before v1.0), superseded in part.
- Record 0006 (cairn practices: independent check, fresh-session review).
