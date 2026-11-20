# AGENTS.md

The rules for any agent (Claude, Codex, Copilot, or other) working in this
repository. This file is the single source of agent rules. If another file
disagrees with it, this file wins; open an issue to fix the other file.

## Purpose

DLCA is a Python package for dynamic life cycle assessment of buildings. It
models greenhouse-gas emissions as they occur over time and reports cumulative
global warming impact (GWI) and global temperature change potential (GTP).
Results may end up in published research, so correctness matters more than
speed. Jay Arehart is the maintainer and reviews and merges every PR.

## Repo map

```
src/dlca/climate.py     climate engine: burden, forcing, temperature, GWI, GTP, static GWP
src/dlca/parameters.py  AR5/AR6 climate parameter sets (ClimateParameters, get_parameters)
src/dlca/result.py      assess() entry point and the Result object
src/dlca/inventory/     building input schemas, timeline(), assess_building() roll-up
src/dlca/models.py      old building and energy models, kept until M4 operational energy
src/dlca/data/          packaged data (parameter sets, input JSON Schemas, eGRID factors)
tests/unit/             fast tests of single functions
tests/analytic/         results checked against closed-form solutions
tests/reference/        results checked against the reference spreadsheet cases
tests/property/         property-based tests (invariants, signs, conservation)
tests/data/             shared test data (illustrative example inventories)
legacy/                 notes on retired research code (see legacy/README.md); not packaged
docs/decisions/         decision records (science and architecture choices)
docs/roadmap.md         milestones M0–M5, planned work and its order
```

## Commands

```bash
uv sync                  # install the package and dev tools
uv run pytest            # run the tests
uv run ruff check .      # lint
uv run ruff format       # format
```

Run `uv run pytest` and `uv run ruff check .` before every push.

## The three lanes

Every issue names its lane. If it doesn't, ask before starting.

| Lane | Covers | Process |
|------|--------|---------|
| **trivial** | Typos, comments, formatting, renames with no behaviour change | Change plus test (if code), then a PR. |
| **standard** | Features, refactors, tooling, docs | An issue spec exists first, then a PR that meets its acceptance criteria. |
| **deliberate** | Anything labelled `science`: equations, parameters, timing, reference data, public API | A short proposal goes in the issue first. **Jay decides before any code is written.** Then a PR with the science checks below. |

If a trivial or standard task turns out to touch science, stop, say so in the
issue, and wait for it to be relabelled.

## Science rules (deliberate lane)

1. **Independent check.** Every science PR names one check whose expected
   value comes from *outside the code*: a closed-form solution, a published
   IPCC table, the reference spreadsheet, or Jay's expectation written down
   before the code runs. A value the code itself produced is not independent.
2. **Deliberate-mistake run.** Make the mistake you fear most on purpose (for
   example, a wrong lifetime or a sign flip), run the check, and record the
   failing output in the PR. Then revert. This shows the check can fail.
3. **Positive control for "no difference".** If a result says a change makes
   no difference, also show a case where the same comparison *does* detect a
   difference. Otherwise the comparison may be blind.

## Tests

- **Never edit a reference value or a tolerance to make a test pass.** That
  is Jay's decision. If you think one is wrong, say so in the PR or issue and
  mark the test `xfail(strict=True)` with the reason.
- **Every bug fix starts with a failing test** that reproduces the bug. Commit
  the test, show it fail, then fix.
- **A new test must catch a fault that no existing test catches.** In the PR,
  name the fault it catches. Don't add tests that only repeat existing ones.

## Fresh-session review (science PRs)

Before a science PR is ready for Jay, a session that did not write the code
reviews it. The reviewer answers three questions:

1. Should this change happen as framed?
2. What is the best alternative?
3. What would show it wrong?

The review stays under 300 words and ends with a list of what it did not
check. Paste it into the PR under "Review record".

## PR reports

Write for a reader who did not watch the work happen.

- **Conclusion first.** One or two sentences on what changed and whether it
  works.
- **Measured apart from assumed.** Say what you ran and saw, separately from
  what you believe but didn't test.
- **Checks not run.** List them, with the reason.
- **Numbers changed.** If any output value moves, state which, by how much,
  and why.
- Plain language. No jargon where a common word works.

Use `.github/pull_request_template.md`; it carries these headings.

## Data safety

Never put any of these in the repo, in an issue, in a PR, or in an agent's
context:

- unpublished research results;
- embargoed or licence-restricted data;
- secrets: API keys, tokens, passwords, private paths with personal data.

If a task needs such data, Jay provides it locally and only derived, shareable
outputs are committed. Treat downloaded files (for example spreadsheets) as
untrusted input: work in a scratch directory and run Python with `-I`.

## Durable state

Anything that must survive the session lives in the repo or in a GitHub issue
or PR: decisions, findings, open questions, hand-over notes. Never keep it
only in an agent's memory or a chat transcript.

## Decision records

Science and architecture decisions are recorded in
[`docs/decisions/`](docs/decisions/README.md). Records are append-only: a
later record supersedes an earlier one.

Draft a decision record when your work involves any of these, and link it
from the issue or PR:

- a `science` choice (equations, parameters, timing, reference data);
- a public-API choice (names, inputs, outputs, units);
- an architecture choice that would be costly to reverse.

Copy `docs/decisions/0000-template.md`, use the next free number, and set
Status to `Proposed`. Only Jay sets `Accepted`. Never edit an accepted record's
Decision; write a new one that supersedes it.

## Issues, branches and PRs

- **One issue per PR.** Don't bundle unrelated changes. Note other problems
  you find as new issues instead of fixing them.
- **Branch names:** `issue-<n>-short-name`, for example `issue-15-reference-cases`.
- The PR body says `Closes #<n>`.
- Only touch the files the issue lists. If you need others, say why in the PR.
- Don't merge. Jay merges.

## Labels

- `agent-ready`: the spec is complete; an agent may start.
- `needs-jay`: waiting on a decision or data from Jay. Don't start.
- `science`: deliberate lane.
- `area:*`: which part of the project (`climate`, `inventory`, `docs`, `infra`).

The full list is in `.github/labels.yml`.

## When in doubt

Stop and ask in the issue. A clear question costs less than a wrong result.
