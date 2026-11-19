# 0008. Public entry point `assess()` and the `Result` object

- **Status:** Proposed
- **Date:** 2026-11-19
- **Decided by:**

## Context

Record 0005 says the public API is pure functions with JSON-serialisable inputs
and outputs, and that results include the parameter set used. Record 0002 says
every result records its set. Record 0007 says a `Result` records the set's name,
`fingerprint()` and "no CCF". Issues #27–#30 rebuilt the climate engine as pure
functions in `dlca.climate`. The old `DLCAEngine` was stateful: it mutated
`DLCAInputData` and returned pandas frames in `DLCAResults`. Issue #31 holds the
proposal (decisions A1–A9). Jay approved it as recommended on 2026-11-19.

## Decision

We will expose one entry point:

```python
dlca.assess(emissions, *, parameters="AR6", horizon=100) -> dlca.Result
```

- `emissions` maps `co2`, `ch4`, `ch4_fossil` and `n2o` to kg per year, index 0 =
  year 0, as lists or arrays. A missing key counts as zeros. Fossil CH4 is its
  own key (decision S4 on #30), so there is no `fossil_ch4` flag.
- `parameters` is a set name for `get_parameters()` or a `ClimateParameters`
  (for example a variant made with `dataclasses.replace()`).
- `horizon` is H in years, > 0, used for every normalised and sliding metric.

`assess()` calls `burden`, `forcing`, `temperature`, `gwi`, `gtp` and
`static_gwp` once each with the same set and H. It copies its inputs and never
changes them.

`Result` is a frozen dataclass of the component results (`burden`, `forcing`,
`temperature`, `gwi`, `gtp`, `static_gwp`), the copied `emissions`, `horizon`,
the **full** `ClimateParameters` used, `parameter_set` (its name),
`parameter_fingerprint` and `carbon_cycle_feedback`, plus `dlca_version`. Every
array is read-only.

`Result.to_dict()` gives plain lists, floats, strings and bools under
`schema: "dlca.result"`, `schema_version: 1`. The parameter set sits under
`parameters: {name, fingerprint, carbon_cycle_feedback, values}`.
`Result.from_dict()` is its exact inverse: every array comes back bit for bit.
It raises for another schema or version. It also raises if the stored name,
fingerprint or CCF flag does not match the stored values.

The old `DLCAEngine`, `DLCAInputData`, `DLCAResults` and the pasted
`AGWP_supp_data.csv` / `AGTP_supp_data.csv` tables and their loaders are removed.

## Alternatives considered

- **Keep `DLCAEngine` as a thin wrapper over the new functions.** Lost: it keeps
  a stateful, order-dependent API that record 0005 rejects, and two ways to get
  the same numbers.
- **Return a pandas `DataFrame` per result.** Lost: it is not JSON-native
  (record 0005), it loses the per-pool CO2 split, and it adds a runtime
  dependency to the core.
- **Store only the set's name and fingerprint (not its values).** Lost: a
  variant keeps its set's name, so a saved result could not say which values
  made it. The full set is 26 fields, which is small. (Judgement call.)
- **A `fossil_ch4` flag on `assess()`.** Lost: it would undo decision S4 on #30,
  which made fossil CH4 an emissions key.

## Consequences

- One call gives every series. A web backend can store `to_dict()` as it is.
- Any change to the JSON form must bump `RESULT_SCHEMA_VERSION`.
- `assess()` computes every component, which costs some extra work. Callers who
  need one series can still call the `dlca.climate` functions.
- Issue #37 (a fingerprint on `Burden`/`Forcing`, and a guard in `forcing()`)
  stays separate. `assess()` cannot mix sets. If #37 lands, the fingerprint will
  also appear inside the nested component dicts, and `from_dict()` could check
  that the two agree.
- The Cooper reference cases now name their set (`parameter_set` in
  `settings.csv`). The run reads it with no default.
- CCF (#33) will change what `carbon_cycle_feedback` can be. The field is
  already in the result.

## References

- Issue #31 (proposal A1–A9 and Jay's approval); issues #26–#30, #33, #37.
- Records 0002, 0005, 0007.
