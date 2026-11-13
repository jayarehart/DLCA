<!-- See AGENTS.md for the rules behind each section. Plain language; write for someone who didn't watch the work. -->

## Summary

<!-- Conclusion first: what changed and whether it works, in one or two sentences. Then details. Keep what you measured apart from what you assume. -->

## Linked issue

Closes #

## Lane

<!-- trivial / standard / deliberate (science) -->

## Checks run

<!-- Commands you ran and what you saw, e.g. `uv run pytest` (42 passed), `uv run ruff check .` (clean). -->

-

## Checks not run

<!-- What you didn't check, and why. "None" only if truly none. -->

-

## Numbers changed

<!-- Any output value that moved: which, by how much, and why. "None" if no output changed. -->

-

## Independent check and deliberate-mistake run (science only)

<!--
- Independent check: what was compared, and where the expected value came from outside the code.
- Deliberate-mistake run: the mistake made on purpose, and the failing output (paste it). Then confirm it was reverted.
- Positive control: required for any "no difference" result.
-->

## Review record

<!--
Science PRs: paste the fresh-session review (a session that didn't write the code). It answers
(1) should this happen as framed, (2) what's the best alternative, (3) what would show it wrong;
under 300 words, ending with what it didn't check.
Other PRs: note who reviewed, or "not yet reviewed".
-->
