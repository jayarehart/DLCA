# API reference

These pages document the public API of DLCA: exactly the names listed in
decision record [0022](../decisions/0022-public-api-and-stability-promise.md),
in five modules. Anything else importable from the package is internal and may
change without notice.

| Module | What it holds |
|---|---|
| [`dlca`](dlca.md) | The two entry points, `assess()` and `assess_building()`, and the parameter-set selector |
| [`dlca.inventory`](inventory.md) | Building input schemas, timing, the building roll-up and its results |
| [`dlca.climate`](climate.md) | The climate engine: burden, forcing, temperature, GWI, GTP, static GWP |
| [`dlca.parameters`](parameters.md) | The AR5 and AR6 climate parameter sets |
| [`dlca.result`](result.md) | `assess()` and its `Result` |

Units are in square brackets in the docstrings, for example [kg CO2e] or
[yr]. Series have one value per year, index 0 = year 0.

Record 0022 also says what may change in a minor or patch release and what
needs a major one.
