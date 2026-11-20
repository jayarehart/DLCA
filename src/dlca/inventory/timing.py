"""Timing engine: a building's modules as yearly emissions (#58, record 0014).

`timeline()` turns a `BuildingTotals` or a `BuildingInventory` into kg per year
of each gas, index 0 = year 0, the form `dlca.assess()` takes. With RSP the
building's `study_period`:

- A1-A3, A4, A5: once, in year 0.
- B1, B2, B3, B6, B7: the yearly amount in each of years 1..RSP.
- Energy lines (#82, record 0019): amount x factor(y) x m(y) in each of
  years 1..RSP, added into the same B6 part as `per_year["B6"]` (a building
  gives one or the other). See `dlca.inventory.operational`.
- C1-C4: once, in the end-of-life year RSP + 1.
- B4, B5: in the year each event gives (1..RSP, checked by the schema).
- Amounts in the same year add.
- Biogenic uptake (#73): negative `co2` from the product's year (0, or the
  B4/B5 event's year), in its own part, module ``"biogenic-uptake"``, net of
  the carbon released as non-fossil CH4. See `dlca.inventory.biogenic`.
- Concrete carbonation (#74, record 0017): negative `co2`. In use, the yearly
  increments of the cumulative sqrt(t) uptake in years s + 1 .. end, where s
  is the casting year (0, or a B4 event's year that carries `carbonation`)
  and end is RSP, or the year of the next such event (the replaced item
  carbonates through that year, then stops). Module ``"carbonation-uptake"``.
  The item in place at the end is crushed in RSP + 1 and its stockpile uptake goes in years
  RSP + 1 .. RSP + n, module ``"carbonation-eol"``. See
  `dlca.inventory.carbonation`.
- Emission-factor trajectory (#81, record 0018): if the building has a
  `b4_c_trajectory`, the fossil gases (`co2`, `ch4_fossil`, `n2o`) of each B4
  event are multiplied by m(event year), and those of C1-C4 by m(RSP + 1).
  Non-fossil `ch4` and every other module are left as entered. On a
  biogenic item (#86, record 0020) the `co2` of its B4 and C1-C4 amounts is
  left as entered too: a material that has a `biogenic` field, or any B4/B5
  event with one, or a `BuildingTotals` with one anywhere.

The series runs over years 0..RSP + 1 + H, so the end-of-life pulse gets a
full horizon H. Pass the same H to `assess()`.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dlca.climate import EMISSION_KEYS
from dlca.inventory.biogenic import (
    CUT_WARN,
    UPTAKE_MODULE,
    BiogenicCarbonWarning,
    uptake_factors,
    uptake_shares,
    warn_on_balance,
    years_for_full_uptake,
)
from dlca.inventory.carbonation import EOL_MODULE as CARBONATION_EOL_MODULE
from dlca.inventory.carbonation import UPTAKE_MODULE as CARBONATION_UPTAKE_MODULE
from dlca.inventory.carbonation import (
    CarbonationWarning,
    eol_increments,
    in_use_increments,
    volume_per_unit,
)
from dlca.inventory.operational import b6_series
from dlca.inventory.schema import (
    Biogenic,
    BuildingInventory,
    BuildingTotals,
    Carbonation,
    EnergyUse,
    Event,
    GasAmounts,
)

PartKey = tuple[str | None, str | None, str]
"""(assembly, material, module). Assembly and material are None for
`BuildingTotals` amounts and for an inventory's B6 and B7."""

Series = Mapping[str, NDArray[np.float64]]
"""Gas key to kg per year, index 0 = year 0."""

TIMELINE_SCHEMA = "dlca.timeline"
# Bump whenever the form of Timeline.to_dict() changes. Version 2 (#73) adds
# the module "biogenic-uptake"; version 3 (#74) adds "carbonation-uptake" and
# "carbonation-eol". Older data still loads.
TIMELINE_SCHEMA_VERSION = 3
_READABLE_TIMELINE_VERSIONS = (1, 2, 3)

_YEAR_ZERO = ("A1-A3", "A4", "A5")
_END_OF_LIFE = ("C1", "C2", "C3", "C4")
_MODULES = (
    UPTAKE_MODULE, *_YEAR_ZERO, "B1", CARBONATION_UPTAKE_MODULE, "B2", "B3", "B4", "B5",
    "B6", "B7", *_END_OF_LIFE, CARBONATION_EOL_MODULE,
)  # fmt: skip


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

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable dict (record 0005, R7 on #59).

        JSON keys cannot be tuples, so `parts` is a list in the timeline's
        order, each entry ``{assembly, material, module, co2, ch4,
        ch4_fossil, n2o}``; no assembly or material is ``null``.
        ``Timeline.from_dict(json.loads(json.dumps(t.to_dict())))`` gives
        every array back bit for bit.
        """
        return {
            "schema": TIMELINE_SCHEMA,
            "schema_version": TIMELINE_SCHEMA_VERSION,
            "study_period": self.study_period,
            "horizon": self.horizon,
            "years": self.years,
            "parts": [
                {
                    "assembly": assembly,
                    "material": material,
                    "module": module,
                    **{gas: series[gas].tolist() for gas in EMISSION_KEYS},
                }
                for (assembly, material, module), series in self.parts.items()
            ],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Timeline:
        """Inverse of `to_dict()`.

        Raises:
            ValueError: for another schema or version, a horizon < 1, `years`
                below ``study_period + horizon + 2``, a part with missing or
                extra fields or an unknown module, a repeated part, or a
                series whose length is not `years`.
            TypeError: if `study_period`, `horizon` or `years` is not an int.
        """
        if data.get("schema") != TIMELINE_SCHEMA:
            raise ValueError(f"not a DLCA timeline: schema {data.get('schema')!r}")
        if data.get("schema_version") not in _READABLE_TIMELINE_VERSIONS:
            raise ValueError(f"unsupported timeline schema_version {data.get('schema_version')!r}")
        study_period = _check_int("study_period", data["study_period"])
        horizon = _check_int("horizon", data["horizon"])
        years = _check_int("years", data["years"])
        if study_period < 1 or horizon < 1:
            raise ValueError("study_period and horizon must be >= 1")
        if years < study_period + horizon + 2:
            raise ValueError(f"years must be >= study_period + horizon + 2, got {years}")
        fields = {"assembly", "material", "module", *EMISSION_KEYS}
        parts: dict[PartKey, Series] = {}
        for entry in data["parts"]:
            if set(entry) != fields:
                raise ValueError(f"a timeline part must have exactly the fields {sorted(fields)}")
            key = (entry["assembly"], entry["material"], entry["module"])
            if entry["module"] not in _MODULES:
                raise ValueError(f"unknown module {entry['module']!r}")
            if key in parts:
                raise ValueError(f"repeated timeline part {key!r}")
            series = {gas: np.asarray(entry[gas], dtype=float) for gas in EMISSION_KEYS}
            for gas, array in series.items():
                if array.shape != (years,):
                    raise ValueError(
                        f"part {key!r} {gas} has shape {array.shape}, expected ({years},)"
                    )
            parts[key] = _freeze(series)
        return cls(
            study_period=study_period,
            horizon=horizon,
            years=years,
            parts=MappingProxyType(parts),
        )


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
    horizon = _check_int("horizon", horizon)
    if horizon < 1:
        raise ValueError(f"horizon must be >= 1 year, got {horizon}")
    rsp = building.study_period
    minimum = rsp + horizon + 2
    if years is None:
        years = minimum
    years = _check_int("years", years)
    if years < minimum:
        raise ValueError(
            f"years must be >= study_period + horizon + 2 = {minimum} so the end-of-life "
            f"year {rsp + 1} gets the full horizon, got {years}"
        )

    warn_on_balance(building)
    factors = uptake_factors(building)
    trajectory = building.b4_c_trajectory
    m = None if trajectory is None else trajectory.multipliers(rsp + 2)
    builder = _Builder(rsp, years, m)
    if isinstance(building, BuildingTotals):
        builder.add(
            None,
            None,
            1.0,
            building.modules,
            building.per_year,
            building.b4,
            building.b5,
            biogenic=_is_biogenic(building.biogenic, building.b4, building.b5),
        )
        builder.add_biogenic(
            None, None, factors.get(None, 0.0), building.biogenic, building.b4, building.b5
        )
    else:
        for assembly in building.assemblies:
            for m in assembly.materials:
                builder.add(
                    assembly.name,
                    m.name,
                    m.quantity,
                    m.modules,
                    m.per_year,
                    m.b4,
                    m.b5,
                    biogenic=_is_biogenic(m.biogenic, m.b4, m.b5),
                )
                f = factors.get((assembly.name, m.name), 0.0)
                builder.add_biogenic(assembly.name, m.name, m.quantity * f, m.biogenic, m.b4, m.b5)
                builder.add_carbonation(
                    assembly.name, m.name, m.quantity, m.unit, m.carbonation, m.b4
                )
        builder.add(None, None, 1.0, {}, building.per_year, [], [])
    builder.add_energy(building.energy)

    parts = MappingProxyType({key: _freeze(series) for key, series in builder.parts.items()})
    return Timeline(study_period=rsp, horizon=horizon, years=years, parts=parts)


class _Builder:
    def __init__(
        self, study_period: int, years: int, multipliers: NDArray[np.float64] | None = None
    ) -> None:
        self.rsp = study_period
        self.years = years
        self.m = multipliers  # m(y) for years 0..RSP + 1; None = as entered
        self.parts: dict[PartKey, dict[str, NDArray[np.float64]]] = {}

    def _series(self, key: PartKey) -> dict[str, NDArray[np.float64]]:
        if key not in self.parts:
            self.parts[key] = {gas: np.zeros(self.years) for gas in EMISSION_KEYS}
        return self.parts[key]

    def _place(self, key: PartKey, where: int | slice, amounts: GasAmounts, scale: float) -> None:
        series = self._series(key)
        for gas in EMISSION_KEYS:
            series[gas][where] += scale * getattr(amounts, gas)

    def _place_scaled(
        self, key: PartKey, year: int, amounts: GasAmounts, scale: float, biogenic: bool
    ) -> None:
        """Place a B4 or C1-C4 amount, its fossil gases times m(year) (record 0018).

        Non-fossil CH4 is never scaled. On a biogenic item `co2` is not
        scaled either, because it holds the release of stored carbon (record 0020).
        """
        if self.m is None:
            self._place(key, year, amounts, scale)
            return
        kept = ("ch4", "co2") if biogenic else ("ch4",)
        series = self._series(key)
        for gas in EMISSION_KEYS:
            factor = 1.0 if gas in kept else self.m[year]
            series[gas][year] += scale * getattr(amounts, gas) * factor

    def add(
        self,
        assembly: str | None,
        material: str | None,
        scale: float,
        modules: Mapping[str, GasAmounts],
        per_year: Mapping[str, GasAmounts],
        b4: Iterable[Event],
        b5: Iterable[Event],
        *,
        biogenic: bool = False,
    ) -> None:
        for module, amounts in modules.items():
            if module in _YEAR_ZERO:
                year = 0
            elif module in _END_OF_LIFE:
                self._place_scaled(
                    (assembly, material, module), self.rsp + 1, amounts, scale, biogenic
                )
                continue
            else:  # the schema allows no other one-off module
                raise ValueError(f"no timing rule for module {module!r}")
            self._place((assembly, material, module), year, amounts, scale)
        for module, amounts in per_year.items():
            self._place((assembly, material, module), slice(1, self.rsp + 1), amounts, scale)
        for module, events in (("B4", b4), ("B5", b5)):
            for event in events:
                if not 1 <= event.year <= self.rsp:  # the schema checks this too
                    raise ValueError(f"{module} event year {event.year} is outside 1..{self.rsp}")
                key = (assembly, material, module)
                if module == "B4":
                    self._place_scaled(key, event.year, event.amounts, scale, biogenic)
                else:
                    self._place(key, event.year, event.amounts, scale)

    def add_energy(self, energy: Iterable[EnergyUse]) -> None:
        energy = list(energy)
        if not energy:
            return
        series = self._series((None, None, "B6"))
        added = b6_series(energy, self.rsp, self.years, _multiplier)
        for gas in EMISSION_KEYS:
            series[gas] += added[gas]

    def add_biogenic(
        self,
        assembly: str | None,
        material: str | None,
        scale: float,  # quantity x the CH4-carbon factor from `uptake_factors`
        own: Biogenic | None,
        b4: Iterable[Event],
        b5: Iterable[Event],
    ) -> None:
        items = [(0, own), *((e.year, e.biogenic) for e in (*b4, *b5))]
        where = "building" if assembly is None else f"{assembly}/{material}"
        for start, item in items:
            if item is None or item.regrowth == "none":
                continue
            shares, cut = uptake_shares(item.regrowth, item.rotation, self.years - start)
            series = self._series((assembly, material, UPTAKE_MODULE))
            series["co2"][start:] -= scale * item.co2 * shares
            if cut > CUT_WARN and scale * item.co2 != 0.0:
                needed = years_for_full_uptake(item.rotation, start)
                warnings.warn(
                    f"{where}: {cut:.3g} of the biogenic uptake starting in year {start} "
                    f"({scale * item.co2 * cut:.6g} kg CO2) falls after the series end and "
                    f"is left out; pass years >= {needed} to keep it.",
                    BiogenicCarbonWarning,
                    stacklevel=3,
                )

    def add_carbonation(
        self,
        assembly: str,
        material: str,
        scale: float,  # quantity
        unit: str,
        own: Carbonation | None,
        b4: Iterable[Event],
    ) -> None:
        b4 = list(b4)
        items = [(0, own)] if own is not None else []
        items += sorted(
            ((e.year, e.carbonation) for e in b4 if e.carbonation is not None),
            key=lambda item: item[0],
        )
        if not items:
            return
        where = f"{assembly}/{material}"
        first = items[0][0]
        for event in b4:
            if event.carbonation is None and event.year > first:
                warnings.warn(
                    f"{where}: the B4 event in year {event.year} has no carbonation, so the "
                    "carbonation clock is not restarted; give the event a carbonation field "
                    "if it replaces the concrete.",
                    CarbonationWarning,
                    stacklevel=3,
                )
        for i, (start, item) in enumerate(items):
            volume = volume_per_unit(item, unit)
            end = items[i + 1][0] if i + 1 < len(items) else self.rsp
            if end > start:
                series = self._series((assembly, material, CARBONATION_UPTAKE_MODULE))
                series["co2"][start + 1 : end + 1] -= scale * in_use_increments(
                    item, volume, end - start
                )
        start, item = items[-1]
        volume = volume_per_unit(item, unit)
        increments = scale * eol_increments(item, volume, self.rsp - start)
        first_year = self.rsp + 1
        fits = min(len(increments), self.years - first_year)
        series = self._series((assembly, material, CARBONATION_EOL_MODULE))
        series["co2"][first_year : first_year + fits] -= increments[:fits]
        cut = float(increments[fits:].sum())
        if cut > 0.0:
            warnings.warn(
                f"{where}: {cut:.6g} kg CO2 of stockpile carbonation falls after the series "
                f"end and is left out; pass years >= {first_year + len(increments)} to keep it.",
                CarbonationWarning,
                stacklevel=3,
            )


def _is_biogenic(own: Biogenic | None, b4: Iterable[Event], b5: Iterable[Event]) -> bool:
    """Whether an item's B4 and C1-C4 `co2` is kept out of the trajectory: it,
    or any of its B4/B5 events, has a `biogenic` field (record 0020)."""
    return own is not None or any(e.biogenic is not None for e in (*b4, *b5))


def _multiplier(line: EnergyUse):
    """The line's trajectory multiplier, or None for constant."""
    return None if line.trajectory is None else line.trajectory.multipliers


def _check_int(name: str, value: object) -> int:
    """An int or NumPy integer (not a bool or a float), returned as int."""
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be a whole number of years (int), got {value!r}")
    return int(value)


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
