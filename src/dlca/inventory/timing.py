"""Timing engine: a building's modules as yearly emissions (#58, record 0014).

`timeline()` turns a `BuildingTotals` or a `BuildingInventory` into kg per year
of each gas, index 0 = year 0, the form `dlca.assess()` takes. With RSP the
building's `study_period`:

- A1-A3, A4, A5: once, in year 0.
- B1, B2, B3, B6, B7: the yearly amount in each of years 1..RSP.
- C1-C4: once, in the end-of-life year RSP + 1.
- B4, B5: in the year each event gives (1..RSP, checked by the schema).
- Amounts in the same year add.

The series runs over years 0..RSP + 1 + H, so the end-of-life pulse gets a
full horizon H. Pass the same H to `assess()`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from numpy.typing import NDArray

from dlca.climate import EMISSION_KEYS
from dlca.inventory.schema import BuildingInventory, BuildingTotals, Event, GasAmounts

PartKey = tuple[str | None, str | None, str]
"""(assembly, material, module). Assembly and material are None for
`BuildingTotals` amounts and for an inventory's B6 and B7."""

Series = Mapping[str, NDArray[np.float64]]
"""Gas key to kg per year, index 0 = year 0."""

_YEAR_ZERO = ("A1-A3", "A4", "A5")
_END_OF_LIFE = ("C1", "C2", "C3", "C4")


@dataclass(frozen=True, eq=False)
class Timeline:
    """Yearly emissions of a building, one series per part and module.

    Attributes:
        study_period: RSP [yr], from the building.
        horizon: H [yr] the length was set for.
        years: Length of every series (years 0..years - 1).
        parts: (assembly, material, module) to a read-only series of each gas
            [kg/yr]. Only modules the building gives appear. B4 and B5 are one
            part each per material (or per building), all events added.
    """

    study_period: int
    horizon: int
    years: int
    parts: Mapping[PartKey, Series]

    @property
    def end_of_life_year(self) -> int:
        """The year C1-C4 fall in: RSP + 1."""
        return self.study_period + 1

    def emissions(self) -> dict[str, NDArray[np.float64]]:
        """Sum of all parts, every gas key present: the input for `dlca.assess()`.

        New, writable arrays each call.
        """
        return _sum(self.parts.values(), self.years)

    def by_module(self) -> dict[str, dict[str, NDArray[np.float64]]]:
        """Module name to the sum of its parts."""
        groups: dict[str, list[Series]] = {}
        for (_, _, module), series in self.parts.items():
            groups.setdefault(module, []).append(series)
        return {module: _sum(group, self.years) for module, group in groups.items()}

    def by_material(self) -> dict[tuple[str, str], dict[str, NDArray[np.float64]]]:
        """(assembly, material) to the sum of its modules. Parts with no
        material (totals input, B6, B7) are left out."""
        groups: dict[tuple[str, str], list[Series]] = {}
        for (assembly, material, _), series in self.parts.items():
            if assembly is not None and material is not None:
                groups.setdefault((assembly, material), []).append(series)
        return {key: _sum(group, self.years) for key, group in groups.items()}


def timeline(
    building: BuildingTotals | BuildingInventory,
    *,
    horizon: int = 100,
    years: int | None = None,
) -> Timeline:
    """Place a building's emissions in time (record 0014).

    Args:
        building: A validated `BuildingTotals` or `BuildingInventory`.
        horizon: H [yr], a whole number >= 1: the series runs H years past the
            end-of-life year. Pass the same H to `dlca.assess()`.
        years: Total length of the series. Default and minimum
            ``study_period + horizon + 2`` (years 0..RSP + 1 + H). Longer
            series are padded with zeros.

    Returns:
        A `Timeline`. `Timeline.emissions()` goes straight into `dlca.assess()`.

    Raises:
        TypeError: if `building` is neither schema, or `horizon` or `years` is
            not an int.
        ValueError: if `horizon` < 1 or `years` is shorter than the default.
    """
    if not isinstance(building, (BuildingTotals, BuildingInventory)):
        raise TypeError(
            f"building must be a BuildingTotals or BuildingInventory, got {type(building).__name__}"
        )
    _check_int("horizon", horizon)
    if horizon < 1:
        raise ValueError(f"horizon must be >= 1 year, got {horizon}")
    rsp = building.study_period
    minimum = rsp + horizon + 2
    if years is None:
        years = minimum
    _check_int("years", years)
    if years < minimum:
        raise ValueError(
            f"years must be >= study_period + horizon + 2 = {minimum} so the end-of-life "
            f"year {rsp + 1} gets the full horizon, got {years}"
        )

    builder = _Builder(rsp, years)
    if isinstance(building, BuildingTotals):
        builder.add(None, None, 1.0, building.modules, building.per_year, building.b4, building.b5)
    else:
        for assembly in building.assemblies:
            for m in assembly.materials:
                builder.add(assembly.name, m.name, m.quantity, m.modules, m.per_year, m.b4, m.b5)
        builder.add(None, None, 1.0, {}, building.per_year, [], [])

    parts = MappingProxyType({key: _freeze(series) for key, series in builder.parts.items()})
    return Timeline(study_period=rsp, horizon=horizon, years=years, parts=parts)


class _Builder:
    def __init__(self, study_period: int, years: int) -> None:
        self.rsp = study_period
        self.years = years
        self.parts: dict[PartKey, dict[str, NDArray[np.float64]]] = {}

    def _series(self, key: PartKey) -> dict[str, NDArray[np.float64]]:
        if key not in self.parts:
            self.parts[key] = {gas: np.zeros(self.years) for gas in EMISSION_KEYS}
        return self.parts[key]

    def _place(self, key: PartKey, where: int | slice, amounts: GasAmounts, scale: float) -> None:
        series = self._series(key)
        for gas in EMISSION_KEYS:
            series[gas][where] += scale * getattr(amounts, gas)

    def add(
        self,
        assembly: str | None,
        material: str | None,
        scale: float,
        modules: Mapping[str, GasAmounts],
        per_year: Mapping[str, GasAmounts],
        b4: Iterable[Event],
        b5: Iterable[Event],
    ) -> None:
        for module, amounts in modules.items():
            if module in _YEAR_ZERO:
                year = 0
            elif module in _END_OF_LIFE:
                year = self.rsp + 1
            else:  # the schema allows no other one-off module
                raise ValueError(f"no timing rule for module {module!r}")
            self._place((assembly, material, module), year, amounts, scale)
        for module, amounts in per_year.items():
            self._place((assembly, material, module), slice(1, self.rsp + 1), amounts, scale)
        for module, events in (("B4", b4), ("B5", b5)):
            for event in events:
                if not 1 <= event.year <= self.rsp:  # the schema checks this too
                    raise ValueError(f"{module} event year {event.year} is outside 1..{self.rsp}")
                self._place((assembly, material, module), event.year, event.amounts, scale)


def _check_int(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a whole number of years (int), got {value!r}")


def _freeze(series: dict[str, NDArray[np.float64]]) -> Series:
    for array in series.values():
        array.setflags(write=False)
    return MappingProxyType(series)


def _sum(group: Iterable[Series], years: int) -> dict[str, NDArray[np.float64]]:
    out = {gas: np.zeros(years) for gas in EMISSION_KEYS}
    for series in group:
        for gas in EMISSION_KEYS:
            out[gas] += series[gas]
    return out
