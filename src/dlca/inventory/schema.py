"""Input schemas for a building's emissions by EN 15978 module (record 0013).

Two schemas, never mixed in one building:

- `BuildingTotals`: whole-building amounts per module, in kg.
- `BuildingInventory`: assemblies of materials, each a quantity in a declared
  unit with amounts per declared unit.

Both use the gas keys `assess()` takes (`co2`, `ch4` non-fossil, `ch4_fossil`,
`n2o`). Module D, service life and replacement interval are not part of the
schema and are refused. Replacements (B4) and refurbishments (B5) are dated
events the user enters; the tool derives nothing.

Schema version 2 (#73) adds an optional `biogenic` field to `Material`,
`BuildingTotals` and `Event`: the biogenic carbon held in the product and how
it is taken up from the air. Version 1 files still load; a version 1 file may
not use `biogenic`.

This module only checks the input. Turning it into yearly emissions is the
timing engine's job (#58).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

SCHEMA_VERSION = 2
FIRST_BIOGENIC_VERSION = 2
TOTALS_TAG = "dlca.building_totals"
INVENTORY_TAG = "dlca.building_inventory"

OneOffModule = Literal["A1-A3", "A4", "A5", "C1", "C2", "C3", "C4"]
"""Modules with a single amount."""

BuildingPerYearModule = Literal["B1", "B2", "B3", "B6", "B7"]
"""Per-year modules in `BuildingTotals`."""

MaterialPerYearModule = Literal["B1", "B2", "B3"]
"""Per-year modules on a `Material`."""

OperationalModule = Literal["B6", "B7"]
"""Per-year modules on a `BuildingInventory` (operational energy and water)."""

Unit = Literal["m3", "m2", "m", "kg", "t", "item"]
"""Declared units. There is no conversion between them."""

Regrowth = Literal["none", "instant", "gaussian"]
"""How biogenic carbon is taken up from the air (#73, B2):

- ``"none"``: no uptake.
- ``"instant"``: all of it in the product's year.
- ``"gaussian"``: Cherubini et al. (2011) regrowth over `rotation` years.
"""


_Amount = Annotated[float, Field(allow_inf_nan=False)]
_Name = Annotated[str, Field(pattern=r"^\S(.*\S)?$")]
"""Non-empty, with no leading or trailing whitespace."""
_Year = Annotated[int, Field(ge=1)]
_Version = Annotated[int, Field(ge=1, le=SCHEMA_VERSION)]
_NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]


_OMIT_IF_NONE = ("biogenic", "rotation")


class _Strict(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        validate_by_name=False,
        validate_by_alias=True,
        serialize_by_alias=True,
        use_attribute_docstrings=True,
    )

    @model_serializer(mode="wrap")
    def _drop_unset_optional(self, handler):
        # An unset `biogenic` or `rotation` is left out, so a file without
        # biogenic carbon dumps exactly as under schema version 1.
        data = handler(self)
        if isinstance(data, dict):
            for key in _OMIT_IF_NONE:
                if key in data and data[key] is None:
                    del data[key]
        return data


class GasAmounts(_Strict):
    """Kilograms of each gas. The unit (kg, kg per year, per declared unit)
    is set by the field that holds it. Negative values are allowed (uptake)."""

    co2: _Amount = 0.0
    ch4: _Amount = 0.0
    """Non-fossil CH4, with no carbon credit (record 0010, C8)."""
    ch4_fossil: _Amount = 0.0
    n2o: _Amount = 0.0


class Biogenic(_Strict):
    """Biogenic carbon held in a product, and its uptake from the air (#73).

    The unit is set by the field that holds it: kg CO2 per declared unit on a
    `Material` or its events, kg CO2 on `BuildingTotals` or its events.

    Uptake goes into the timeline as negative `co2`, in its own part
    ``"biogenic-uptake"``. Release is not written by the tool: the user enters
    it in C1-C4 (or in a B4 event) as `co2` and non-fossil `ch4`, as for any
    other emission. `released_co2` says how much of the declared carbon those
    entries release as CO2; it is used only for the storage report and the
    over-release warning, and adds nothing to the emissions.
    """

    co2: _NonNegative
    """Biogenic carbon in the product, as kg CO2 (carbon x 44.01 / 12.011)."""
    regrowth: Regrowth
    rotation: Annotated[int, Field(ge=2)] | None = None
    """Rotation period [yr] for ``"gaussian"`` regrowth; required there and
    refused for the other options."""
    released_co2: _NonNegative = 0.0
    """Part of `co2` that the user's own C1-C4 (or event) entries release as
    CO2. Reporting only."""

    @model_validator(mode="after")
    def _rotation_only_for_gaussian(self) -> Biogenic:
        if self.regrowth == "gaussian" and self.rotation is None:
            raise ValueError("gaussian regrowth needs a rotation (whole years >= 2)")
        if self.regrowth != "gaussian" and self.rotation is not None:
            raise ValueError(f"rotation is only for gaussian regrowth, not {self.regrowth!r}")
        return self


class Event(_Strict):
    """A B4 (replacement) or B5 (refurbishment) event.

    `year` is a year of the study period, 1 to `study_period`. A B4 amount is
    the whole replacement: the new item's A1-A5 plus the old item's C1-C4.
    Events in the same year add together.
    """

    year: _Year
    amounts: GasAmounts
    biogenic: Biogenic | None = None
    """Biogenic carbon of the item the event puts in; its uptake starts in the
    event year (#73, B4)."""


def _check_event_years(events: list[Event], study_period: int, where: str) -> None:
    for event in events:
        if event.year > study_period:
            raise ValueError(
                f"{where}: event year {event.year} is after the study period ({study_period} years)"
            )


def _check_biogenic_version(version: int, items: list[Biogenic | None], where: str) -> None:
    if version < FIRST_BIOGENIC_VERSION and any(item is not None for item in items):
        raise ValueError(
            f"{where}: biogenic needs schema_version {FIRST_BIOGENIC_VERSION}, got {version}"
        )


def _event_biogenic(*event_lists: list[Event]) -> list[Biogenic | None]:
    return [event.biogenic for events in event_lists for event in events]


def _check_unique(names: list[str], where: str) -> None:
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ValueError(f"{where}: duplicate name {name!r}")
        seen.add(name)


class BuildingTotals(_Strict):
    """Whole-building amounts per module.

    - `modules`: kg, once.
    - `per_year`: kg per year, constant each year.
    - `b4`, `b5`: kg per event.
    """

    schema_: Literal["dlca.building_totals"] = Field(alias="schema")
    schema_version: _Version = SCHEMA_VERSION
    name: _Name
    study_period: _Year
    """Reference study period, whole years."""
    modules: dict[OneOffModule, GasAmounts] = Field(default_factory=dict)
    per_year: dict[BuildingPerYearModule, GasAmounts] = Field(default_factory=dict)
    b4: list[Event] = Field(default_factory=list)
    b5: list[Event] = Field(default_factory=list)
    biogenic: Biogenic | None = None
    """Biogenic carbon of the whole building, in kg CO2 (schema version 2)."""

    @model_validator(mode="after")
    def _events_in_study_period(self) -> BuildingTotals:
        _check_event_years(self.b4, self.study_period, "b4")
        _check_event_years(self.b5, self.study_period, "b5")
        _check_biogenic_version(
            self.schema_version,
            [self.biogenic, *_event_biogenic(self.b4, self.b5)],
            "building",
        )
        return self


class Material(_Strict):
    """A quantity of one product with amounts per declared unit.

    The emitted amount is `quantity` times the per-unit amount.

    - `modules`: kg per declared unit, once.
    - `per_year`: kg per declared unit per year, constant each year.
    - `b4`, `b5`: kg per declared unit per event.
    """

    name: _Name
    quantity: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    unit: Unit
    modules: dict[OneOffModule, GasAmounts] = Field(default_factory=dict)
    per_year: dict[MaterialPerYearModule, GasAmounts] = Field(default_factory=dict)
    b4: list[Event] = Field(default_factory=list)
    b5: list[Event] = Field(default_factory=list)
    biogenic: Biogenic | None = None
    """Biogenic carbon per declared unit, in kg CO2 (schema version 2)."""


class Assembly(_Strict):
    """A named group of materials (for example a floor or a wall)."""

    name: _Name
    materials: Annotated[list[Material], Field(min_length=1)]

    @model_validator(mode="after")
    def _unique_material_names(self) -> Assembly:
        _check_unique([m.name for m in self.materials], f"assembly {self.name!r}")
        return self


class BuildingInventory(_Strict):
    """A building as assemblies of materials.

    `per_year` holds the operational modules B6 and B7 for the whole
    building, in kg per year.
    """

    schema_: Literal["dlca.building_inventory"] = Field(alias="schema")
    schema_version: _Version = SCHEMA_VERSION
    name: _Name
    study_period: _Year
    """Reference study period, whole years."""
    assemblies: Annotated[list[Assembly], Field(min_length=1)]
    per_year: dict[OperationalModule, GasAmounts] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_tree(self) -> BuildingInventory:
        _check_unique([a.name for a in self.assemblies], "building")
        for assembly in self.assemblies:
            for material in assembly.materials:
                where = f"{assembly.name}/{material.name}"
                _check_event_years(material.b4, self.study_period, f"{where} b4")
                _check_event_years(material.b5, self.study_period, f"{where} b5")
                _check_biogenic_version(
                    self.schema_version,
                    [material.biogenic, *_event_biogenic(material.b4, material.b5)],
                    where,
                )
        return self


SCHEMA_FILES = {
    "building_totals.schema.json": BuildingTotals,
    "building_inventory.schema.json": BuildingInventory,
}
"""Committed JSON Schema file name (in `dlca/data/`) for each model."""


def json_schema(model: type[BaseModel]) -> dict:
    """The JSON Schema for `model`, as committed in `dlca/data/`."""
    return model.model_json_schema(by_alias=True)


def write_json_schemas(directory: Path | None = None) -> None:
    """Write the committed JSON Schema files. Run after changing a model:

    uv run python -c "from dlca.inventory.schema import write_json_schemas; write_json_schemas()"
    """
    directory = directory or Path(__file__).resolve().parents[1] / "data"
    for file_name, model in SCHEMA_FILES.items():
        text = json.dumps(json_schema(model), indent=2, ensure_ascii=False) + "\n"
        (directory / file_name).write_text(text, encoding="utf-8")
