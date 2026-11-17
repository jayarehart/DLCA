# 0006. Adopt a subset of cairn practices

- **Status:** Accepted
- **Date:** 2026-11-12
- **Decided by:** Jay Arehart

## Context

Agents will do most of the implementation, and results may end up in published
research. The project needs checks that catch a wrong science result, and the
reasons for choices need to be kept. MSUHydrogeology/cairn is a framework for
this kind of work.

## Decision

We will adopt four cairn practices, in a lighter form, and write them into
`AGENTS.md`:

1. an independent scientific check on every science PR;
2. three lanes (trivial, standard, deliberate);
3. fresh-session review of science PRs;
4. decision records (this folder).

We will not install cairn itself.

## Alternatives considered

- **Install and follow cairn in full.** Lost: more process than a small
  package needs; the lighter subset covers what matters. (Rationale to confirm)
- **No formal process,** relying on reviewing each PR. Lost: it does not
  guarantee that a science result has an independent check or that reasons
  survive past the chat.

## Consequences

- Rules live in `AGENTS.md`, which is the single source for agents.
- Science PRs carry extra work: a named check, a deliberate-mistake run and a
  review record.
- We maintain these rules ourselves and may drift from cairn.

## References

- https://github.com/MSUHydrogeology/cairn
- Issues #13, #14.
