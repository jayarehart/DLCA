# Internal review before v1.0

Jay Arehart and colleagues review DLCA before the v1.0.0 release and the JOSS
submission. This page is the review packet, and at the end it holds the review
summary. The process is in [record 0023](../../decisions/0023-internal-review-before-v1.md)
and the steps are milestone M5r in the [roadmap](../../roadmap.md).

## At a glance

| | |
|---|---|
| Version under review | `v1.0.0rc1` (not yet tagged) |
| Review window | _start date_ to _end date_ |
| Wrap-up meeting | _date_ |
| Where findings go | A GitHub issue from the **Review finding** form, one finding per issue |

Review the tagged release candidate, not `main`, so everyone looks at the same
code. If fixes move any output numbers, a `v1.0.0rc2` follows and only the
changed areas are re-checked.

## Before you start

- **The repository is public.** Findings are public issues. Don't paste
  unpublished results, embargoed or licence-restricted data, or secrets. If a
  finding depends on such data, describe it with a small made-up input, or
  raise it with Jay directly.
- **Install the release candidate** from its GitHub release page (wheel
  attached), or from the tag:

  ```bash
  pip install "git+https://github.com/jayarehart/DLCA@v1.0.0rc1"
  ```

- **Read first:** the methodology page, the quick start, the inputs page and
  the [decision records](../../decisions/README.md). Each science rule has a
  record that says what was decided and why.

## Areas

Each reviewer takes one or two areas. One area can have more than one
reviewer.

| Area | Check against | Starting points | Reviewer(s) |
|---|---|---|---|
| Climate engine and parameters | IPCC AR5 and AR6 tables, closed-form results | `dlca.climate`, `dlca.parameters`; records 0002, 0007, 0009–0012 | _name_ |
| Inventory, timing and EN 15978 modules | EN 15978; records 0013–0015 | `dlca.inventory`; inputs page | _name_ |
| Biogenic carbon, carbonation, B6 and trajectories | The sources cited in records 0016–0021 | Records 0016–0021 | _name_ |
| Usability and public API | Running the tutorials, then a shareable building of your own | Quick start, tutorials, record 0022 | _name_ |
| Docs, methodology and paper | Whether each claim matches the code | Methodology page, `paper.md` | _name_ |

### Questions worth asking

- Does any result have the wrong sign, unit or year?
- Is anything counted twice, or not at all (for example biogenic carbon, record
  0010 C8)?
- Do the docs or the paper claim something the code doesn't do?
- Would you trust the defaults for a published study?
- Is there a public name, input or output you would want changed before the
  v1.0 stability promise (record 0022) makes it hard to change?

## Known gaps: no need to report these

These are already tracked. Comment on the issue if you think one should block
v1.0.

- Parameter uncertainty ranges and Monte Carlo sampling (#26).
- AR6's CO₂ sink for biogenic CH₄ (0.7 ± 0.7 kg per kg), which neither
  parameter set models (#26).
- Other concrete carbonation models, such as Jungclaus et al. (2025) (#76).
- Entry point for inventories that are not buildings (#107, after v1.0).
- Strict xfails, where DLCA disagrees with the Cooper et al. (2020)
  spreadsheet on purpose (record 0001). They are listed in `tests/reference/`.

## Severity

- **blocker**: a result is wrong, or the docs or paper claim something the
  code doesn't do. Fixed before v1.0.0.
- **should-fix**: a real problem that doesn't make a result wrong. Fixed
  before v1.0.0 if cheap, otherwise moved to M6.
- **later**: can wait past v1.0.

Jay sets the final severity at triage, with a `review:*` label.

## After the review window

1. At the wrap-up meeting, each reviewer presents their blockers and proposed
   fixes. Jay decides each finding's severity and milestone, and records the
   decision in the issue.
2. Each fix is one PR that closes its finding. Science fixes follow the
   deliberate lane in `AGENTS.md`: a proposal first, and Jay decides before
   code is written.
3. The reviewer who raised a finding confirms the fix in the issue before it
   is closed.

## Review summary

_Filled in when the review closes._

- **Reviewers and areas:** _who reviewed what_
- **Version reviewed:** _tags, including any rc2_
- **Findings:** _n_ blocker, _n_ should-fix, _n_ later; _n_ closed as not a
  problem
- **What changed:** _the main fixes, with their PRs, and any output numbers
  that moved_
- **Not reviewed:** _areas or files no one checked, and why_
