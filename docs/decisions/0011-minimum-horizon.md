# 0011. Minimum time horizon of 1e-6 yr

- **Status:** Proposed
- **Date:** 2026-11-19
- **Decided by:**

## Context

`gwi()`, `gtp()`, `static_gwp()` and `assess()` accepted any finite horizon
H > 0. Below about 1e-9 yr the closed forms of AGWP and AGTP lose precision,
because `1 - exp(-H/tau)` and `exp(-H/tau) - exp(-H/d)` round to 0 when H/tau is
below machine epsilon. At H = 2.22e-16 (found by a randomised property-test run,
#47), AR5 `gtp()` raised `ZeroDivisionError`, and the other functions returned
values up to 300% off without any error. At 1e-6 yr the measured relative
error of the AGWP and AGTP closed forms is at most about 3e-9.

## Decision

We will refuse horizons below `dlca.climate.MIN_HORIZON = 1e-6` yr (about 32
seconds) with a `ValueError` that names the minimum. The check is in
`_check_horizon`, so it covers `gwi()`, `gtp()`, `static_gwp()` and `assess()`
alike. `agwp()` and `agtp()` still accept any H >= 0: they do not divide, and
the sliding metrics use them for the remaining horizons H - k, where an
inaccurate tiny value adds a negligible absolute error.

## Alternatives considered

- **A minimum of 1 yr**, the model's time step. Stricter than needed:
  fractional horizons are documented as allowed, and nothing numerical goes
  wrong between 1e-6 and 1 yr.
- **Handle tiny horizons** by rewriting every closed form with `expm1`. It
  would still need a guard for subnormal H (AGTP of CO2 underflows to 0 near
  1e-300), it touches the AGWP, AGTP, fossil CH4 and CCF code, and it moves the
  last digits of results everywhere. It can be done later as its own issue if
  sub-microyear horizons are ever wanted.

## Consequences

A horizon below 1e-6 yr is now an error, not a crash or a silent wrong value.
No horizon in use (20, 100, 500) is affected and no output value moves. The
property tests draw `MIN_HORIZON` itself in about one example in ten, so the
invariants are checked at the boundary. At the minimum, GWP_H and GTP_H of
every key agree with their H -> 0 limit `A_x / A_CO2` to 4e-8.

## References

- Issue #47 (proposal H1–H5, approved by Jay on 2026-11-19).
- `tests/unit/test_climate_horizon.py`, `tests/analytic/test_small_horizon.py`.
