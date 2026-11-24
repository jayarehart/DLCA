# Quick start

## An emission series

Emissions go in as kilograms of each gas per year, with index 0 as year 0.
This assesses 1000 kg of CO2 emitted in year 0 and 5 kg of (non-fossil)
methane emitted in year 1, over a 100-year horizon, with the AR6 parameters:

```python
from dlca import assess

result = assess(
    {"co2": [1000, 0, 0], "ch4": [0, 5, 0]},
    parameters="AR6",
    horizon=100,
)

print(result.gwi.dynamic)  # global warming impact by year [kg CO2e]
print(result.gtp.dynamic)  # global temperature change potential by year [kg CO2e]
print(result.static_gwp.total)  # the same emissions with no timing [kg CO2e]
```

The emission keys are `co2`, `ch4` (non-fossil methane), `ch4_fossil` and
`n2o`; a missing key counts as zeros. [`assess()`](api/result.md#dlca.result.assess)
returns a frozen [`Result`](api/result.md#dlca.result.Result) that holds every
series, a copy of the inputs and the parameter set used.
`result.to_dict()` gives a JSON-ready form.

## A building

[`assess_building()`](api/inventory.md#dlca.inventory.assess_building) takes a
building in one of the two [input schemas](inputs.md): `BuildingTotals`
(emissions by EN 15978 module) or `BuildingInventory` (assemblies of
materials). Validate the input with pydantic first. This example uses
made-up, illustrative numbers:

```python
from dlca import assess_building
from dlca.inventory import BuildingTotals

building = BuildingTotals.model_validate(
    {
        "schema": "dlca.building_totals",
        "schema_version": 1,
        "name": "Illustrative building",
        "study_period": 50,
        "modules": {
            "A1-A3": {"co2": 250000, "ch4_fossil": 300, "n2o": 8},
            "C4": {"co2": 2000, "ch4": 50},
        },
        "per_year": {"B2": {"co2": 500}},
        "b4": [{"year": 20, "amounts": {"co2": 8000}}],
    }
)

result = assess_building(building, parameters="AR6", horizon=100)

print(result.total.gwi.dynamic)  # the whole building [kg CO2e]
print(list(result.by_module))  # the modules in EN 15978 order
print(result.by_module["A1-A3"].gwi_dynamic)  # one module's share [kg CO2e]
```

The result is a [`BuildingResult`](api/inventory.md#dlca.inventory.BuildingResult):
the whole building in `total`, and breakdowns by module, gas, assembly and
material whose rows add up to the total.

More example inputs are in
[`tests/data/inventories/`](https://github.com/jayarehart/DLCA/tree/main/tests/data/inventories).
Every number in them is illustrative.
