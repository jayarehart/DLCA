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

## Releasing

Releases go to GitHub only; nothing is published to PyPI. The version comes
from the git tag through [hatch-vcs](https://github.com/ofek/hatch-vcs), so
there is no version number to edit in `pyproject.toml`. Between tags, builds
get a development version such as `1.0.1.dev3+g1a2b3c4`. A build with no git
history at all (for example a "Download ZIP" archive) gets `0.0.0+unknown`.

To make a release (the maintainer does this):

1. On `main`, move the `[Unreleased]` entries in `CHANGELOG.md` under a new
   `## [X.Y.Z] - YYYY-MM-DD` heading, add its link at the bottom, and merge
   that through a PR.
2. Tag the merge commit and push the tag:

   ```bash
   git tag -a vX.Y.Z -m "DLCA X.Y.Z"
   git push origin vX.Y.Z
   ```

   Write the tag in normalized [PEP 440](https://peps.python.org/pep-0440/)
   form: `v1.0.0`, `v1.0.0rc1`, not `v1.0.0-rc.1`. The release workflow
   checks that the built version equals the tag without its `v`.
3. The [release workflow](.github/workflows/release.yml) then runs
   `uv build`, checks that the wheel holds every packaged data file
   (`scripts/check_wheel.py`), installs the wheel in a clean environment and
   checks the version it reports, and creates a GitHub release with the wheel
   and sdist attached. The release notes are that version's section of
   `CHANGELOG.md`; a final release with no section fails. A tag with `a`, `b`,
   `rc` or `dev` in it is marked as a pre-release and may have no section.

The wheel check also runs in CI on every PR (the `package` job). If you add a
packaged data file, add it to `REQUIRED_FILES` in `scripts/check_wheel.py`.
To run it locally:

```bash
uv build
python scripts/check_wheel.py dist/*.whl
```

### Installing a release

From the wheel attached to a GitHub release:

```bash
pip install https://github.com/jayarehart/DLCA/releases/download/v1.0.0/dlca-1.0.0-py3-none-any.whl
```

Or from the tag, which builds from source:

```bash
pip install "git+https://github.com/jayarehart/DLCA.git@v1.0.0"
```

While the repository is private, both need GitHub access: download the wheel
with `gh release download v1.0.0 --repo jayarehart/DLCA --pattern "*.whl"`
and install the file, or use an SSH URL (`git+ssh://git@github.com/...`).

## Reporting security problems

See [SECURITY.md](SECURITY.md). Don't open a public issue for a vulnerability.
