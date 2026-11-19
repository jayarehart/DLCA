# 0009. Climate results record their parameter set; mixing sets raises

- **Status:** Proposed
- **Date:** 2026-11-19
- **Decided by:**

## Context

`burden(emissions, params)` returns a `Burden`, and `forcing(b, params)` and
`temperature(b, params)` each take a parameter set again. Nothing tied the two
sets together, so a burden made with AR5 could be passed with AR6 and give a
silently wrong result. Measured on main for a 1 kg pulse at year 100: CH₄
integrated forcing +4.9% and temperature +5.7%, N₂O +3.9% and +7.9%. CO₂ moved
0.0%, because AR5 and AR6 share the CO₂ impulse response, so for a CO₂-only mix
the numbers cannot reveal the mistake. `ClimateParameters.fingerprint()` (record
0007) already identifies a set by its values. Issue #37 holds the proposal
(decisions G1–G9, revised R1–R6 after the #33 proposal). Jay approved both as
recommended on 2026-11-19.

## Decision

We will make every burden-derived output record its parameter set, and refuse
to mix sets:

- `Burden`, `Forcing` and `Temperature` gain a required field
  `parameter_fingerprint: str`, the full `params.fingerprint()`. It is the last
  field and has no default and no `None`. The name matches
  `Result.parameter_fingerprint`.
- Each `to_dict()` includes `"parameter_fingerprint"`, and `from_dict()`
  requires it (record 0005: results include the parameter set used).
- `forcing()` and `temperature()` raise `ValueError` when
  `b.parameter_fingerprint != params.fingerprint()`. The message names the given
  set, both 8-character fingerprint prefixes, and says that a set changed with
  `dataclasses.replace()` keeps its name but is a different set.
- The check compares fingerprints (values), not names. `fingerprint()` also
  covers `name`, `sources` and `carbon_cycle_feedback`, so a renamed copy is
  refused too; this can only refuse, never pass a mix.
- There is no override argument.
- `Result` refuses a `burden`, `forcing` or `temperature` whose fingerprint
  differs from its own. `RESULT_SCHEMA_VERSION` goes from 1 to 2.
- `GWI`, `GTP` and `StaticGWP` are unchanged: their functions take emissions
  and one set in a single call, so they cannot be mixed.
- Carbon-cycle feedback (#33) keeps every switch and value inside
  `ClimateParameters`, so the fingerprint covers it. If a later feature needs
  an option outside the set, this field becomes a hash of the fingerprint and
  that option.

## Alternatives considered

- **Compare `name`.** Lost: a variant (for example AR6 with CCF switched off)
  keeps its name but has other values.
- **An optional field, skipped when `None`.** Lost: a silent skip brings the
  gap back.
- **A `check=False` keyword.** Lost: an easy-to-copy silent skip, and no
  legitimate use for mixing sets is known. Anyone who means to can write
  `dataclasses.replace(b, parameter_fingerprint=p.fingerprint())`, which is
  visible in review.
- **Keep the fingerprint out of the components' `to_dict()` and fill it from
  `Result.parameters`.** Lost: a component's `to_dict()` would differ inside
  and outside a `Result`, and a standalone saved burden would lose its set.

## Consequences

- Calls that mix sets now raise instead of returning wrong numbers. `gwi()`,
  `gtp()` and `assess()` use one set throughout and are unaffected. No output
  value moves.
- Code that converts every `to_dict()` entry to a float array must skip the new
  string key.
- A v1 result file is refused by `Result.from_dict()`. v0.2.0 is unreleased.
- Each check computes `fingerprint()` (about 20 µs). If that matters, caching
  the fingerprint is its own issue.
- `temperature()` is the check plus a private `_temperature_series()` helper,
  which #33 can call inside `burden()` before a `Burden` exists.
- #33 numbers its record 0010, and bumps the result schema to 3 when it adds
  `Burden.ccf_co2`.

## References

- Issue #37 (proposal G1–G9 and revision R1–R6); PR #36 review, where the gap
  was found.
- Issue #33 (carbon-cycle feedback) proposal, decision C6.
- Records 0005, 0007 and 0008.
