# Inputs

A building goes into [`assess_building()`](api/inventory.md#dlca.inventory.assess_building)
in one of two schemas (decision record
[0013](decisions/0013-inventory-schema.md)):

| Schema | `schema` tag | What it holds |
|---|---|---|
| [`BuildingTotals`](api/inventory.md#dlca.inventory.BuildingTotals) | `dlca.building_totals` | Emissions of the whole building by EN 15978 module |
| [`BuildingInventory`](api/inventory.md#dlca.inventory.BuildingInventory) | `dlca.building_inventory` | Assemblies of materials, each with emissions per declared unit |

Both are pydantic models. The JSON Schema files below are made from them
and ship inside the package, in
`dlca/data/`. Use them to check an input file in another tool or language.
The field descriptions are the same text as the
[API reference](api/inventory.md#input-schemas).

## `BuildingTotals`

Download:
[`building_totals.schema.json`](https://raw.githubusercontent.com/jayarehart/DLCA/main/src/dlca/data/building_totals.schema.json)

??? note "building_totals.schema.json"

    ```json
    --8<-- "src/dlca/data/building_totals.schema.json"
    ```

## `BuildingInventory`

Download:
[`building_inventory.schema.json`](https://raw.githubusercontent.com/jayarehart/DLCA/main/src/dlca/data/building_inventory.schema.json)

??? note "building_inventory.schema.json"

    ```json
    --8<-- "src/dlca/data/building_inventory.schema.json"
    ```

## Example inputs

Illustrative example files for both schemas are in
[`tests/data/inventories/`](https://github.com/jayarehart/DLCA/tree/main/tests/data/inventories).
Every number in them is made up.
