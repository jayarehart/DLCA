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

Schema version 3 (#74) adds an optional `carbonation` field to `Material` and
to its B4 events: concrete carbonation by Lagerblad (2005). Version 1 and 2
files still load and may not use it.

Schema version 4 (#81, record 0018) adds an optional `b4_c_trajectory` to
`BuildingTotals` and `BuildingInventory`: a multiplier m(y) on study years for
the fossil gases of B4 events and of C1-C4. Absent means constant. Version 1-3
files still load and may not use it. On an item with a `biogenic` field (a
material, or a whole `BuildingTotals`, or any of its B4/B5 events) the `co2`
of those amounts is not scaled (#86, record 0020).
Schema version 5 (#82, record 0019) adds an optional building-level `energy`
field: operational energy (B6) as energy use by fuel. A building gives
`energy` or `per_year["B6"]`, never both. Version 1-4 files still load and may
not use it.

Schema version 6 (#85, record 0021) adds a Cambium factor source to an
electricity energy line: `cambium_gea`, `cambium_scenario` and `year_zero`.
Version 1-5 files still load and may not use it.

This module only checks the input. Turning it into yearly emissions is the
timing engine's job (#58).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

SCHEMA_VERSION = 6
FIRST_BIOGENIC_VERSION = 2
FIRST_CARBONATION_VERSION = 3
FIRST_TRAJECTORY_VERSION = 4
FIRST_ENERGY_VERSION = 5
FIRST_CAMBIUM_VERSION = 6
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


Exposure = Literal["indoors", "sheltered", "exposed", "wet", "buried"]
"""Environment of a concrete surface: the rows of Lagerblad (2005) Table 2
(#74, K2). ``"wet"`` is his "wet/submerged"; ``"buried"`` is concrete in the
ground, not in direct contact with the air."""

Cover = Literal["none", "indoor_house", "outdoor_house"]
"""Surface cover of a concrete surface, Lagerblad (2005) Table 3: ``"none"``
(x 1.0, bare concrete or painted infrastructure), ``"indoor_house"`` (x 0.7)
and ``"outdoor_house"`` (x 0.9)."""

StrengthClass = Literal["<15", "15-25", "25-35", ">35"]
"""Cylinder strength band [MPa] for Lagerblad (2005) Table 2. The bands are
those of his appendix A2.3; Table 2 labels its second column 15-20 MPa (#74,
K2)."""

Fuel = Literal["electricity", "natural_gas", "fuel_oil_2"]
"""Fuels of an energy line (#82, record 0019)."""

EnergyUnit = Literal["kWh", "MJ", "GJ", "MMBtu", "kBtu", "therm"]
"""Energy units (#80). Kept equal to `dlca.inventory.units.MJ_PER_UNIT` by a test."""

EgridSubregion = Literal[
    "AKGD", "AKMS", "AZNM", "CAMX", "ERCT", "FRCC", "HIMS", "HIOA", "MROE",
    "MROW", "NEWE", "NWPP", "NYCW", "NYLI", "NYUP", "PRMS", "RFCE", "RFCM",
    "RFCW", "RMPA", "SPNO", "SPSO", "SRMV", "SRMW", "SRSO", "SRTV", "SRVC",
]  # fmt: skip
"""eGRID2023 subregions. Kept equal to the packaged file by a test."""

EgridState = Literal[
    "AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI",
    "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME", "MI", "MN",
    "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV", "NY", "OH",
    "OK", "OR", "PA", "PR", "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VT",
    "WA", "WI", "WV", "WY",
]  # fmt: skip
"""eGRID2023 states (with DC and PR). Kept equal to the packaged file by a test."""

CambiumGea = Literal[
    "CAISO", "ERCOT", "FRCC", "ISONE", "MISO_Central", "MISO_North", "MISO_South",
    "NYISO", "NorthernGrid_East", "NorthernGrid_South", "NorthernGrid_West",
    "PJM_East", "PJM_West", "SERTP", "SPP_North", "SPP_South",
    "WestConnect_North", "WestConnect_South",
]  # fmt: skip
"""NLR Cambium 2024 generation and emission assessment (GEA) regions (#85,
record 0021). They are not eGRID subregions. Kept equal to the packaged
files by a test."""

CambiumScenario = Literal[
    "MidCase", "HighDemandGrowth", "HighNGPrice", "LowNGPrice", "HighRECost",
    "LowRECost", "HighRECost_LowNGPrice", "LowRECost_HighNGPrice",
]  # fmt: skip
"""Cambium 2024 scenarios, named as in NLR's files. Kept equal to the packaged
file by a test."""


_Amount = Annotated[float, Field(allow_inf_nan=False)]
_Name = Annotated[str, Field(pattern=r"^\S(.*\S)?$")]
"""Non-empty, with no leading or trailing whitespace."""
_Year = Annotated[int, Field(ge=1)]
_Version = Annotated[int, Field(ge=1, le=SCHEMA_VERSION)]
_NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
_Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
_Share = Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)]


_OMIT_IF_NONE = (
    "biogenic", "rotation", "carbonation", "volume", "b4_c_trajectory", "egrid_subregion",
    "egrid_state", "factor", "trajectory", "cambium_gea", "cambium_scenario", "year_zero",
)  # fmt: skip
_OMIT_IF_EMPTY = ("energy",)


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
        # Unset optional fields (`_OMIT_IF_NONE`) and an empty `energy` list are
        # left out, so a file without them dumps exactly as under schema version 1.
        data = handler(self)
        if isinstance(data, dict):
            for key in _OMIT_IF_NONE:
                if key in data and data[key] is None:
                    del data[key]
            for key in _OMIT_IF_EMPTY:
                if key in data and data[key] == []:
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


class Surface(_Strict):
    """One kind of exposed concrete surface (#74, K2; Andersson et al. 2013, eq. 2)."""

    area: _Positive
    """m2 per declared unit."""
    exposure: Exposure
    cover: Cover


class Stockpile(_Strict):
    """End of life: crushed and stockpiled in the open (#74, K4).

    In the end-of-life year the concrete still uncarbonated is crushed into
    spheres of `radius`. They carbonate as ``"exposed"`` concrete of the same
    strength class and binder, with no cover factor, for `years` years.
    """

    radius: _Positive
    """Radius of the crushed pieces [mm]. Required, no default."""
    years: Annotated[int, Field(ge=1)] = 1
    """Years in the stockpile, from the end-of-life year on."""


class Carbonation(_Strict):
    """Concrete carbonation by Lagerblad (2005), CBI report 2:2005 (#74).

    Depth d = k sqrt(t) [mm], t in years from casting, with k from Table 2
    (strength class x exposure) times the cover factor (Table 3) times
    `binder_factor`. Uptake per m3 carbonated = `degree_of_carbonation` x
    `cement` x `cao_share` x 44.01 / 56.077 kg CO2. The carbonated volume is
    the sum over `surfaces` of area x d, capped at the volume per declared
    unit. See `dlca.inventory.carbonation`.
    """

    strength_class: StrengthClass
    cement: _Positive
    """Portland cement (clinker) content [kg per m3 of concrete]. For a
    blended cement, the Portland part only (Lagerblad §5.3.2)."""
    surfaces: Annotated[list[Surface], Field(min_length=1)]
    end_of_life: Stockpile
    cao_share: _Share = 0.65
    """Mass share of CaO in the Portland cement (Lagerblad's example value)."""
    binder_factor: Annotated[float, Field(ge=1, allow_inf_nan=False)] = 1.0
    """Factor on k for the binder; Lagerblad Table 4 is guidance (it and his
    appendix A2.4 disagree, so neither is encoded)."""
    degree_of_carbonation: _Share = 0.75
    """Share of the CaO that carbonates in the carbonated layer (Lagerblad
    §5.1.5; Andersson et al. 2013 use 0.8-0.9)."""
    volume: _Positive | None = None
    """m3 of concrete per declared unit. Required unless the material's unit
    is ``"m3"`` (then it is 1 and may not be given)."""


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
    carbonation: Carbonation | None = None
    """Carbonation of the concrete a B4 event puts in, per declared unit of its
    material: the clock restarts in the event year and the replaced item's
    uptake stops after the event year (#74, K5; schema version 3). Not allowed on B5 events or on
    `BuildingTotals`."""


def _check_count(n: int) -> int:
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError(f"n must be a whole number >= 1, got {n!r}")
    return n


class ConstantTrajectory(_Strict):
    """m(y) = 1 in every year: amounts as entered (#81, record 0018)."""

    kind: Literal["constant"]

    def multipliers(self, n: int) -> NDArray[np.float64]:
        """m(y) for study years 0..n - 1."""
        return np.ones(_check_count(n))


class LinearTrajectory(_Strict):
    """A straight line from m(0) = 1 to `target` in `target_year`, then held
    at `target` (#81, record 0018). A delayed start needs a `SeriesTrajectory`."""

    kind: Literal["linear"]
    target: _NonNegative
    """m in `target_year` and every year after it."""
    target_year: _Year
    """Study year (year 0 = construction) in which m reaches `target`."""

    def multipliers(self, n: int) -> NDArray[np.float64]:
        """m(y) for study years 0..n - 1."""
        y = np.arange(_check_count(n), dtype=float)
        return 1.0 + (self.target - 1.0) * np.minimum(y, self.target_year) / self.target_year


class SeriesTrajectory(_Strict):
    """m(y) given per study year: `values[y]` (#81, record 0018).

    Years past the last value use the last value; values past the series end
    are ignored.
    """

    kind: Literal["series"]
    values: Annotated[list[_NonNegative], Field(min_length=1)]
    """m(0), m(1), ...: each finite and >= 0, the first exactly 1."""

    @model_validator(mode="after")
    def _starts_at_one(self) -> SeriesTrajectory:
        if self.values[0] != 1.0:
            raise ValueError(f"a series trajectory must start at 1, got {self.values[0]!r}")
        return self

    def multipliers(self, n: int) -> NDArray[np.float64]:
        """m(y) for study years 0..n - 1."""
        n = _check_count(n)
        values = np.asarray(self.values[:n], dtype=float)
        return np.concatenate([values, np.full(n - values.size, values[-1])])


Trajectory = Annotated[
    ConstantTrajectory | LinearTrajectory | SeriesTrajectory, Field(discriminator="kind")
]
"""A multiplier m(y) on study years, chosen by ``kind`` (#81, record 0018).
Each kind has ``multipliers(n)``, m(y) for years 0..n - 1, with m(0) = 1."""


def _check_trajectory(version: int, trajectory: Trajectory | None) -> None:
    if trajectory is not None and version < FIRST_TRAJECTORY_VERSION:
        raise ValueError(
            f"b4_c_trajectory needs schema_version {FIRST_TRAJECTORY_VERSION}, got {version}"
        )


class EnergyUse(_Strict):
    """One fuel's energy use per year, for B6 (#82, record 0019).

    B6 in year y (1..RSP) is `amount` x factor(y) x m(y), where m is the
    `trajectory` multiplier (constant when absent), applied to the fossil
    gases only.

    Factor source:

    - ``"electricity"``: exactly one of `egrid_subregion`, `egrid_state`
      (packaged eGRID2023 Rev 2), `factor` or `cambium_gea` (packaged NLR
      Cambium 2024 series, with `year_zero` and optional `cambium_scenario`;
      schema version 6, record 0021).
    - ``"natural_gas"``, ``"fuel_oil_2"``: `factor`, or none for the packaged
      EPA Hub 2025 factor.

    Packaged factors cover combustion and generation only: no transmission
    and distribution losses and no upstream emissions.
    """

    fuel: Fuel
    amount: _NonNegative
    """Energy used per year, in `unit`."""
    unit: EnergyUnit
    egrid_subregion: EgridSubregion | None = None
    egrid_state: EgridState | None = None
    factor: GasAmounts | Annotated[list[GasAmounts], Field(min_length=1)] | None = None
    """kg of each gas per one `unit` of energy. One `GasAmounts` (constant) or
    a list indexed by study year (entry i is year i; B6 uses 1..RSP; a short
    list holds its last value)."""
    trajectory: Trajectory | None = None
    """Multiplier m(y) on the fossil gases of this line (record 0018 kinds).
    Absent means constant. Not with a series `factor` or `cambium_gea`."""
    cambium_gea: CambiumGea | None = None
    """Cambium GEA region for a packaged, year-by-year electricity factor:
    NLR's eGRID-based GEA history, then Cambium 2024 `aer_gen_*_c` from 2030
    (record 0021). Needs `year_zero`."""
    cambium_scenario: CambiumScenario | None = None
    """Cambium scenario; absent means ``"MidCase"``. Only with `cambium_gea`."""
    year_zero: int | None = None
    """Calendar year of study year 0 (construction). Only with `cambium_gea`,
    and required there."""

    @model_validator(mode="after")
    def _one_factor_source(self) -> EnergyUse:
        series = isinstance(self.factor, list) or self.cambium_gea is not None
        if series and self.trajectory is not None and self.trajectory.kind != "constant":
            raise ValueError(
                "a series or Cambium factor may not have a non-constant trajectory "
                "(it would be scaled twice)"
            )
        if self.cambium_gea is None:
            for name in ("cambium_scenario", "year_zero"):
                if getattr(self, name) is not None:
                    raise ValueError(f"{name} is only for a line with cambium_gea")
        elif self.year_zero is None:
            raise ValueError("cambium_gea needs year_zero (the calendar year of study year 0)")
        sources = [
            name
            for name in ("egrid_subregion", "egrid_state", "factor", "cambium_gea")
            if getattr(self, name) is not None
        ]
        if self.fuel == "electricity":
            if len(sources) != 1:
                raise ValueError(
                    "electricity needs exactly one of egrid_subregion, egrid_state, factor or "
                    f"cambium_gea, got {sources or 'none'}"
                )
        elif self.egrid_subregion is not None or self.egrid_state is not None:
            raise ValueError(f"{self.fuel}: eGRID codes are for electricity only")
        elif self.cambium_gea is not None:
            raise ValueError(f"{self.fuel}: Cambium regions are for electricity only")
        return self


def _check_energy(version: int, energy: list[EnergyUse], per_year: Mapping, where: str) -> None:
    if not energy:
        return
    if version < FIRST_ENERGY_VERSION:
        raise ValueError(
            f"{where}: energy needs schema_version {FIRST_ENERGY_VERSION}, got {version}"
        )
    if "B6" in per_year:
        raise ValueError(f'{where}: give B6 as energy or as per_year["B6"], not both')
    if version < FIRST_CAMBIUM_VERSION and any(line.cambium_gea is not None for line in energy):
        raise ValueError(
            f"{where}: cambium_gea needs schema_version {FIRST_CAMBIUM_VERSION}, got {version}"
        )


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


def _check_carbonation_version(version: int, items: list[Carbonation | None], where: str) -> None:
    if version < FIRST_CARBONATION_VERSION and any(item is not None for item in items):
        raise ValueError(
            f"{where}: carbonation needs schema_version {FIRST_CARBONATION_VERSION}, got {version}"
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
    b4_c_trajectory: Trajectory | None = None
    """Multiplier on the fossil gases of B4 events and C1-C4 (schema version 4,
    record 0018). Absent means constant. If the building or any of its events
    has a `biogenic` field, their `co2` is not scaled (record 0020)."""
    energy: list[EnergyUse] = Field(default_factory=list)
    """Operational energy (B6) by fuel (schema version 5). Not with `per_year["B6"]`."""

    @model_validator(mode="after")
    def _events_in_study_period(self) -> BuildingTotals:
        _check_energy(self.schema_version, self.energy, self.per_year, "building")
        _check_event_years(self.b4, self.study_period, "b4")
        _check_event_years(self.b5, self.study_period, "b5")
        _check_biogenic_version(
            self.schema_version,
            [self.biogenic, *_event_biogenic(self.b4, self.b5)],
            "building",
        )
        if any(event.carbonation is not None for event in (*self.b4, *self.b5)):
            raise ValueError(
                "building: carbonation is for materials of a BuildingInventory, "
                "not BuildingTotals events"
            )
        _check_trajectory(self.schema_version, self.b4_c_trajectory)
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
    carbonation: Carbonation | None = None
    """Concrete carbonation per declared unit (schema version 3, #74)."""

    @model_validator(mode="after")
    def _check_carbonation(self) -> Material:
        if any(event.carbonation is not None for event in self.b5):
            raise ValueError(f"{self.name}: carbonation is for B4 events only, not B5")
        years = [event.year for event in self.b4 if event.carbonation is not None]
        if len(years) != len(set(years)):
            raise ValueError(f"{self.name}: more than one B4 event with carbonation in one year")
        for item in (self.carbonation, *(event.carbonation for event in self.b4)):
            if item is None:
                continue
            if self.unit == "m3" and item.volume is not None:
                raise ValueError(
                    f"{self.name}: carbonation volume is 1 m3 for unit 'm3' and may not be given"
                )
            if self.unit != "m3" and item.volume is None:
                raise ValueError(f"{self.name}: carbonation needs a volume (m3 per {self.unit!r})")
        return self


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
    b4_c_trajectory: Trajectory | None = None
    """Multiplier on the fossil gases of every material's B4 events and C1-C4
    (schema version 4, record 0018). Absent means constant. A material that has
    a `biogenic` field, or any B4/B5 event with one, keeps the `co2` of those
    amounts as entered (record 0020)."""
    energy: list[EnergyUse] = Field(default_factory=list)
    """Operational energy (B6) by fuel (schema version 5). Not with `per_year["B6"]`."""

    @model_validator(mode="after")
    def _check_tree(self) -> BuildingInventory:
        _check_energy(self.schema_version, self.energy, self.per_year, "building")
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
                _check_carbonation_version(
                    self.schema_version,
                    [material.carbonation, *(e.carbonation for e in material.b4)],
                    where,
                )
        _check_trajectory(self.schema_version, self.b4_c_trajectory)
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
