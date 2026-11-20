"""Roll-up from material to building, with breakdowns (#59, record 0015).

`assess_building()` places a building's emissions in time with `timeline()`,
runs `dlca.assess()` on the whole building, and runs it again on each row of
four breakdowns:

- by module (EN 15978 order; B4 and B5 one row each);
- by gas, by input key: a row holds what that key causes, so `ch4_fossil`
  includes its oxidised CO2, and the CH4 and N2O rows include the CO2 that
  their carbon-cycle feedback releases (AR6);
- by material `(assembly, material)` and by assembly, for a
  `BuildingInventory` only. The building's own B6 and B7 form one more row,
  keyed `None`, so the rows add up to the total.

The engine is linear in the emissions, so in each breakdown the rows add up
to the total, up to rounding. Each row keeps six series: GWI and GTP, each
dynamic, sliding and static, over the whole timeline.

Sliding metrics give an emission in year k the horizon ``max(H - k, 0)``, so
an emission in year H or later counts zero in `gwi_sliding` and
`gtp_sliding`. The dynamic and static series still count it. Rows with any
such input emission are listed in `BuildingResult.sliding_incomplete`, and
`assess_building()` warns once (R6).

The flag looks at input emissions only. CO2 that forms in the atmosphere in
year H or later (from fossil CH4 oxidation, or released by the carbon-cycle
feedback of CH4 and N2O) also counts zero in the sliding series, even when
the CH4 or N2O was emitted before year H. That is part of the metric's
definition; such a row is not flagged.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from dataclasses import dataclass, fields
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dlca.climate import EMISSION_KEYS
from dlca.inventory.schema import INVENTORY_TAG, TOTALS_TAG, BuildingInventory, BuildingTotals
from dlca.inventory.timing import Timeline, _check_int, timeline
from dlca.parameters import ClimateParameters, get_parameters
from dlca.result import Result, assess

__all__ = [
    "BUILDING_RESULT_SCHEMA",
    "BUILDING_RESULT_SCHEMA_VERSION",
    "BuildingResult",
    "Metrics",
    "assess_building",
]

BUILDING_RESULT_SCHEMA = "dlca.building_result"
# Bump whenever the form of BuildingResult.to_dict() changes.
BUILDING_RESULT_SCHEMA_VERSION = 1

MODULE_ORDER = (
    "A1-A3", "A4", "A5",
    "B1", "B2", "B3", "B4", "B5", "B6", "B7",
    "C1", "C2", "C3", "C4",
)  # fmt: skip
"""EN 15978 order of the module rows."""

BREAKDOWNS = ("module", "gas", "material", "assembly")
"""Breakdown names, as used in `sliding_incomplete` and the JSON form."""

Emissions = dict[str, NDArray[np.float64]]


def _read_only(array: Any) -> NDArray[np.float64]:
    out = np.array(array, dtype=float)
    out.setflags(write=False)
    return out


@dataclass(frozen=True, eq=False)
class Metrics:
    """The climate metrics of one breakdown row, read-only [kg CO2e per year].

    Each field is the same series as in `Result` (`gwi.dynamic`,
    `gwi.sliding`, `gwi.static`, `gtp.dynamic`, ...), for that row's
    emissions alone, with the building's parameter set and horizon.
    """

    gwi_dynamic: NDArray[np.float64]
    gwi_sliding: NDArray[np.float64]
    gwi_static: NDArray[np.float64]
    gtp_dynamic: NDArray[np.float64]
    gtp_sliding: NDArray[np.float64]
    gtp_static: NDArray[np.float64]

    def __post_init__(self) -> None:
        shape = None
        for f in fields(self):
            array = _read_only(getattr(self, f.name))
            if array.ndim != 1 or (shape is not None and array.shape != shape):
                raise ValueError("every Metrics series must be 1-D and of the same length")
            if not np.all(np.isfinite(array)):
                raise ValueError(f"Metrics.{f.name} has non-finite values")
            shape = array.shape
            object.__setattr__(self, f.name, array)

    @property
    def years(self) -> int:
        """Length of every series."""
        return self.gwi_dynamic.shape[0]

    @classmethod
    def from_result(cls, result: Result) -> Metrics:
        """The six GWI and GTP series of `result`."""
        return cls(
            gwi_dynamic=result.gwi.dynamic,
            gwi_sliding=result.gwi.sliding,
            gwi_static=result.gwi.static,
            gtp_dynamic=result.gtp.dynamic,
            gtp_sliding=result.gtp.sliding,
            gtp_static=result.gtp.static,
        )

    def to_dict(self) -> dict[str, list[float]]:
        """Plain lists, one per field."""
        return {f.name: getattr(self, f.name).tolist() for f in fields(self)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Metrics:
        """Inverse of `to_dict()`."""
        names = {f.name for f in fields(cls)}
        if set(data) != names:
            raise ValueError(f"Metrics must have exactly the fields {sorted(names)}")
        return cls(**{name: data[name] for name in names})


@dataclass(frozen=True, eq=False)
class BuildingResult:
    """A building's climate result, whole and broken down (#59, record 0015).

    Attributes:
        building: The validated input, kept so the timeline can be rebuilt.
        total: `dlca.assess()` of the whole building (a schema-4 `Result`).
        by_module: Module name to its row, in EN 15978 order. Only modules the
            building gives appear.
        by_gas: Input key (`co2`, `ch4`, `ch4_fossil`, `n2o`) to its row; all
            four keys, always.
        by_material: `(assembly, material)` to its row, in input order, then
            `None` for the building's own B6 and B7 if it has any. Empty for
            `BuildingTotals`.
        by_assembly: Assembly name to its row, then `None` as above. Empty for
            `BuildingTotals`.
        horizon: H [yr], a whole number, used for the timeline and every metric.
        years: Length of every series (the timeline's).
        sliding_cutoff_year: H. Emissions in this year or later count zero in
            the sliding series.
        sliding_incomplete: Breakdown name to the keys of its rows that have a
            non-zero emission in year `sliding_cutoff_year` or later. A
            breakdown with no such row is left out.
    """

    building: BuildingTotals | BuildingInventory
    total: Result
    by_module: Mapping[str, Metrics]
    by_gas: Mapping[str, Metrics]
    by_material: Mapping[tuple[str, str] | None, Metrics]
    by_assembly: Mapping[str | None, Metrics]
    horizon: int
    years: int
    sliding_cutoff_year: int
    sliding_incomplete: Mapping[str, tuple[Any, ...]]

    def __post_init__(self) -> None:
        if not isinstance(self.building, (BuildingTotals, BuildingInventory)):
            raise TypeError("building must be a BuildingTotals or BuildingInventory")
        for name in ("horizon", "years", "sliding_cutoff_year"):
            object.__setattr__(self, name, _check_int(name, getattr(self, name)))
        if self.total.horizon != self.horizon:
            raise ValueError(
                f"horizon {self.horizon} differs from the total result's {self.total.horizon}"
            )
        if self.sliding_cutoff_year != self.horizon:
            raise ValueError("sliding_cutoff_year must equal horizon")
        if self.total.emissions["co2"].shape != (self.years,):
            raise ValueError(f"the total result is not {self.years} years long")
        for name in ("by_module", "by_gas", "by_material", "by_assembly"):
            rows = getattr(self, name)
            for key, row in rows.items():
                if row.years != self.years:
                    raise ValueError(f"{name}[{key!r}] is {row.years} years long, not {self.years}")
            object.__setattr__(self, name, MappingProxyType(dict(rows)))
        if tuple(self.by_gas) != EMISSION_KEYS:
            raise ValueError(f"by_gas must have exactly the keys {list(EMISSION_KEYS)}, in order")
        if isinstance(self.building, BuildingTotals) and (self.by_material or self.by_assembly):
            raise ValueError("a BuildingTotals has no material or assembly rows")
        unknown = set(self.sliding_incomplete) - set(BREAKDOWNS)
        if unknown:
            raise ValueError(f"unknown breakdowns in sliding_incomplete: {sorted(unknown)}")
        incomplete = {name: tuple(keys) for name, keys in self.sliding_incomplete.items()}
        for name, keys in incomplete.items():
            missing = [k for k in keys if k not in self._rows(name)]
            if missing:
                raise ValueError(
                    f"sliding_incomplete[{name!r}] names rows that do not exist: {missing}"
                )
        object.__setattr__(self, "sliding_incomplete", MappingProxyType(incomplete))
        # The total must be the building's own emissions, placed by timeline().
        t = timeline(self.building, horizon=self.horizon, years=self.years)
        for gas, series in t.emissions().items():
            if not np.array_equal(series, self.total.emissions[gas]):
                raise ValueError(f"the total result's {gas} emissions are not the building's")

    @property
    def total_metrics(self) -> Metrics:
        """The six GWI and GTP series of `total`, as a `Metrics`."""
        return Metrics.from_result(self.total)

    def _rows(self, name: str) -> Mapping[Any, Metrics]:
        return getattr(self, f"by_{name}")

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable dict (record 0005).

        Each breakdown is a list of rows in order, ``{"key": ..., <Metrics>}``.
        A material key is ``[assembly, material]`` and the building row's key
        is ``null``. ``BuildingResult.from_dict(json.loads(json.dumps(d)))``
        gives every array back bit for bit.
        """
        return {
            "schema": BUILDING_RESULT_SCHEMA,
            "schema_version": BUILDING_RESULT_SCHEMA_VERSION,
            "building": self.building.model_dump(mode="json", by_alias=True),
            "horizon": self.horizon,
            "years": self.years,
            "sliding_cutoff_year": self.sliding_cutoff_year,
            "sliding_incomplete": {
                name: [_key_to_json(k) for k in keys]
                for name, keys in self.sliding_incomplete.items()
            },
            "total": self.total.to_dict(),
            "breakdowns": {
                name: [
                    {"key": _key_to_json(key), **row.to_dict()}
                    for key, row in self._rows(name).items()
                ]
                for name in BREAKDOWNS
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BuildingResult:
        """Inverse of `to_dict()`.

        Raises:
            ValueError: for another schema or version, an unknown building
                schema, a missing field, a repeated row, or parts that do not
                fit together (horizon, length, the building's emissions, or a
                `sliding_incomplete` key that is not a row).
            TypeError: if `horizon`, `years` or `sliding_cutoff_year` is not an int.
        """
        try:
            return cls._from_dict(data)
        except (KeyError, AttributeError) as error:
            raise ValueError(f"malformed building result: {error!r}") from error

    @classmethod
    def _from_dict(cls, data: Mapping[str, Any]) -> BuildingResult:
        if data.get("schema") != BUILDING_RESULT_SCHEMA:
            raise ValueError(f"not a DLCA building result: schema {data.get('schema')!r}")
        if data.get("schema_version") != BUILDING_RESULT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported building result schema_version {data.get('schema_version')!r}"
            )
        raw = data["building"]
        model = {TOTALS_TAG: BuildingTotals, INVENTORY_TAG: BuildingInventory}.get(
            raw.get("schema")
        )
        if model is None:
            raise ValueError(f"unknown building schema {raw.get('schema')!r}")
        rows: dict[str, dict[Any, Metrics]] = {}
        for name in BREAKDOWNS:
            rows[name] = {}
            for entry in data["breakdowns"][name]:
                entry = dict(entry)
                key = _key_from_json(entry.pop("key"))
                if key in rows[name]:
                    raise ValueError(f"repeated {name} row {key!r}")
                rows[name][key] = Metrics.from_dict(entry)
        return cls(
            building=model.model_validate(raw),
            total=Result.from_dict(data["total"]),
            by_module=rows["module"],
            by_gas=rows["gas"],
            by_material=rows["material"],
            by_assembly=rows["assembly"],
            horizon=data["horizon"],
            years=data["years"],
            sliding_cutoff_year=data["sliding_cutoff_year"],
            sliding_incomplete={
                name: tuple(_key_from_json(k) for k in keys)
                for name, keys in data["sliding_incomplete"].items()
            },
        )


def _key_to_json(key: Any) -> Any:
    return list(key) if isinstance(key, tuple) else key


def _key_from_json(key: Any) -> Any:
    return tuple(key) if isinstance(key, list) else key


def _label(key: Any) -> str:
    if key is None:
        return "(building)"
    if isinstance(key, tuple):
        return "/".join(key)
    return str(key)


def _zeros(years: int) -> Emissions:
    return {gas: np.zeros(years) for gas in EMISSION_KEYS}


def _add(into: Emissions, series: Mapping[str, NDArray[np.float64]]) -> None:
    for gas in EMISSION_KEYS:
        into[gas] += series[gas]


def _groups(t: Timeline, inventory: bool) -> dict[str, dict[Any, Emissions]]:
    """Each breakdown's rows as emissions, from the timeline's parts."""
    total = t.emissions()
    by_module: dict[Any, Emissions] = {}
    by_material: dict[Any, Emissions] = {}
    by_assembly: dict[Any, Emissions] = {}
    for (assembly, material, module), series in t.parts.items():
        _add(by_module.setdefault(module, _zeros(t.years)), series)
        if inventory:
            key = None if assembly is None else (assembly, material)
            _add(by_material.setdefault(key, _zeros(t.years)), series)
            _add(by_assembly.setdefault(assembly, _zeros(t.years)), series)
    order = {m: i for i, m in enumerate(MODULE_ORDER)}
    groups = {
        "module": dict(sorted(by_module.items(), key=lambda kv: order[kv[0]])),
        "gas": {gas: {gas: total[gas]} for gas in EMISSION_KEYS},
        "material": by_material,
        "assembly": by_assembly,
    }
    # The building row (None) comes last in each breakdown.
    for name in ("material", "assembly"):
        if None in groups[name]:
            groups[name][None] = groups[name].pop(None)
    return groups


def assess_building(
    building: BuildingTotals | BuildingInventory,
    *,
    parameters: str | ClimateParameters = "AR6",
    horizon: int = 100,
    years: int | None = None,
) -> BuildingResult:
    """Climate metrics of a building, whole and broken down (#59, record 0015).

    Args:
        building: A validated `BuildingTotals` or `BuildingInventory`.
        parameters: A parameter set name or a `ClimateParameters`, as for
            `dlca.assess()`.
        horizon: H [yr], a whole number >= 1, for the timeline (record 0014)
            and every metric.
        years: Length of the series, as for `timeline()`. Default and minimum
            ``study_period + horizon + 2``.

    Returns:
        A `BuildingResult`. In each breakdown the rows add up to `total` up to
        rounding (the engine is linear).

    Warns:
        UserWarning: once, if any row has a non-zero emission in year H or
            later. Such emissions count zero in the sliding series; the rows
            are listed in `BuildingResult.sliding_incomplete`.

    Raises:
        TypeError: if `building` is neither schema, or `horizon` or `years` is
            not an int, or `parameters` is neither a name nor a set.
        ValueError: as for `timeline()` and `dlca.assess()`.
    """
    if not isinstance(building, (BuildingTotals, BuildingInventory)):
        raise TypeError(
            f"building must be a BuildingTotals or BuildingInventory, got {type(building).__name__}"
        )
    t = timeline(building, horizon=horizon, years=years)
    params = get_parameters(parameters) if isinstance(parameters, str) else parameters
    groups = _groups(t, isinstance(building, BuildingInventory))

    def run(emissions: Mapping[str, NDArray[np.float64]]) -> Result:
        return assess(emissions, parameters=params, horizon=t.horizon)

    rows = {
        name: {key: Metrics.from_result(run(e)) for key, e in group.items()}
        for name, group in groups.items()
    }
    incomplete = {}
    for name, group in groups.items():
        late = tuple(
            key
            for key, e in group.items()
            if any(np.any(series[t.horizon :]) for series in e.values())
        )
        if late:
            incomplete[name] = late
    if incomplete:
        listed = "; ".join(
            f"{name} " + ", ".join(_label(k) for k in keys) for name, keys in incomplete.items()
        )
        warnings.warn(
            f"emissions in year {t.horizon} or later get zero weight in the sliding GWI "
            f"and GTP (horizon H = {t.horizon}); dynamic and static still count them. "
            f"Rows affected: {listed}. (CO2 formed in the air in year {t.horizon} or later "
            f"from earlier CH4 or N2O also counts zero there and is not flagged.)",
            UserWarning,
            stacklevel=2,
        )
    return BuildingResult(
        building=building,
        total=run(t.emissions()),
        by_module=rows["module"],
        by_gas=rows["gas"],
        by_material=rows["material"],
        by_assembly=rows["assembly"],
        horizon=t.horizon,
        years=t.years,
        sliding_cutoff_year=t.horizon,
        sliding_incomplete=incomplete,
    )
