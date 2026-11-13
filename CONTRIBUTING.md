# Contributing to DLCA

Thanks for helping. This guide is for people. If you are an AI agent, or you
direct one, read [AGENTS.md](AGENTS.md): it holds the full rules, and they
apply to human contributors too.

## Development setup

You need Python 3.10 or newer and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/jayarehart/DLCA.git
cd DLCA
uv sync
```

Then, before you push:

```bash
uv run pytest
uv run ruff check .
uv run ruff format
```

## How work flows

1. **Start from an issue.** Use the "Task" or "Bug" form. Blank issues are
   turned off so that every issue carries the fields reviewers need.
2. **Pick the lane.** Every issue has one:
   - **trivial**: typos, formatting, renames with no behaviour change. Just
     make the change (with a test, if it's code) and open a PR.
   - **standard**: features, refactors, tooling, docs. The issue spec comes
     first, then a PR that meets its acceptance criteria.
   - **deliberate**: anything labelled `science` (equations, parameters,
     timing, reference data, public API). Post a short proposal in the issue
     and wait for the maintainer's decision before writing code.
3. **Branch** as `issue-<n>-short-name`, one issue per branch.
4. **Open a PR** using the template, with `Closes #<n>` in the body. The
   maintainer reviews and merges.

## PR checklist

- [ ] The PR closes exactly one issue.
- [ ] The summary starts with the conclusion, in plain language.
- [ ] `uv run pytest` and `uv run ruff check .` pass.
- [ ] Checks you didn't run are listed, with the reason.
- [ ] Any changed output numbers are listed, with size and reason.
- [ ] No reference value or test tolerance was changed to make a test pass.
- [ ] A bug fix includes a test that failed before the fix.
- [ ] Each new test catches a fault that no existing test catches.
- [ ] No unpublished results, embargoed data or secrets are included.
- [ ] **Science PRs only:** an independent check, a deliberate-mistake run,
      and a fresh-session review are recorded (see [AGENTS.md](AGENTS.md)).

## Reporting security problems

See [SECURITY.md](SECURITY.md). Don't open a public issue for a vulnerability.
