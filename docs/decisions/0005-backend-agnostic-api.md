# 0005. Backend-agnostic API

- **Status:** Accepted
- **Date:** 2026-11-12
- **Decided by:** Jay Arehart

## Context

A web app is planned for DLCA, but its backend has not been chosen. The package's
public API will be used by it, and the API is a `science` surface because its
names, inputs, outputs and units shape every later use.

## Decision

The public API will be pure functions with JSON-serialisable inputs and outputs.
It will not depend on any web framework, database or server state. Results
include the parameter set used (see 0002).

## Alternatives considered

- **Build the API around a chosen web framework** (for example FastAPI or
  Flask). Lost: the backend isn't decided, so this would lock in a guess.
- **Stateful objects with methods that must be held in memory.** Lost: they do
  not serialise to JSON, so a web backend could not pass them between requests
  without extra code. (Rationale to confirm)

## Consequences

- Any backend, notebook or script can call the same functions.
- Inputs and outputs need plain types (numbers, strings, lists, dicts). Arrays
  and data frames must convert to and from JSON.
- The web backend decision is separate and still open.

## References

- Milestone M0 description; issue #14.
