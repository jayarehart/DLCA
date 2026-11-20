"""Operational energy (B6) from energy use by fuel (#82, record 0019).

An energy line is an amount per year of one fuel in one energy unit (#80),
times a factor in kg of each gas per unit of energy, in each of years 1..RSP.

Packaged factors, combustion and generation only (no transmission and
distribution losses, no upstream emissions):

- Electricity: US EPA eGRID2023 Revision 2 (data year 2023, released
  2025-06-12), annual total output emission rates of CO2, CH4 and N2O in
  lb/MWh as published (sheets ``SRL23`` and ``ST23`` of
  ``egrid2023_data_rev2.xlsx``). Public domain.
- Natural gas and fuel oil No. 2: US EPA GHG Emission Factors Hub, January
  2025, Table 1 (40 CFR 98 Tables C-1 and C-2).

CH4 from the packaged factors is fossil (`ch4_fossil`).
"""

from __future__ import annotations

import csv
import math
from collections.abc import Callable, Iterable, Mapping
from functools import cache
from importlib.resources import files
from types import MappingProxyType

import numpy as np
from numpy.typing import NDArray

from dlca.climate import EMISSION_KEYS
from dlca.inventory.units import to_mj

KG_PER_LB = 0.45359237
"""International avoirdupois pound (exact)."""
MJ_PER_MWH = 3600.0

EGRID_SUBREGION_FILE = "egrid2023_rev2_subregion.csv"
EGRID_STATE_FILE = "egrid2023_rev2_state.csv"

FOSSIL_KEYS = ("co2", "ch4_fossil", "n2o")
"""Gases a trajectory scales (record 0018, E2)."""

_HUB_2025_PER_MMBTU = MappingProxyType(
    {
        # kg CO2, g CH4, g N2O per mmBtu (Hub 2025, Table 1)
        "natural_gas": (53.06, 1.0, 0.10),
        "fuel_oil_2": (73.96, 3.0, 0.60),
    }
)


def _per_mj(co2: float, ch4_fossil: float, n2o: float) -> Mapping[str, float]:
    return MappingProxyType({"co2": co2, "ch4": 0.0, "ch4_fossil": ch4_fossil, "n2o": n2o})


@cache
def _egrid_table(file_name: str) -> Mapping[str, Mapping[str, float]]:
    """Code -> kg of each gas per MJ, from a packaged eGRID file in lb/MWh."""
    table: dict[str, Mapping[str, float]] = {}
    with files("dlca.data").joinpath(file_name).open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row.get("subregion") or row["state"]
            scale = KG_PER_LB / MJ_PER_MWH
            table[code] = _per_mj(
                float(row["co2_lb_per_mwh"]) * scale,
                float(row["ch4_lb_per_mwh"]) * scale,
                float(row["n2o_lb_per_mwh"]) * scale,
            )
    return MappingProxyType(table)


def electricity_factor_per_mj(
    *, subregion: str | None = None, state: str | None = None
) -> Mapping[str, float]:
    """kg of each gas per MJ of electricity, eGRID2023 Rev 2.

    Give exactly one of `subregion` or `state`; each is looked up only in its
    own table.
    """
    if (subregion is None) == (state is None):
        raise ValueError("give exactly one of subregion or state")
    if subregion is not None:
        file_name, code, kind = EGRID_SUBREGION_FILE, subregion, "subregion"
    else:
        file_name, code, kind = EGRID_STATE_FILE, state, "state"
    table = _egrid_table(file_name)
    if code not in table:
        raise ValueError(f"unknown eGRID {kind} {code!r}")
    return table[code]


def fuel_factor_per_mj(fuel: str) -> Mapping[str, float]:
    """kg of each gas per MJ of `fuel` (``"natural_gas"`` or ``"fuel_oil_2"``), Hub 2025."""
    try:
        co2, ch4_g, n2o_g = _HUB_2025_PER_MMBTU[fuel]
    except KeyError:
        raise ValueError(f"no packaged factor for fuel {fuel!r}") from None
    mj = to_mj(1.0, "MMBtu")
    return _per_mj(co2 / mj, ch4_g / 1000 / mj, n2o_g / 1000 / mj)


def to_study_years(values: Mapping[int, float], year_zero: int, n_years: int) -> list[float]:
    """Calendar-year values as a list indexed by study year 0..n_years - 1.

    A straight line between given years; the first value is held before the
    first given year and the last value after the last (record 0019). Works
    on plain numbers: call it once per gas for a factor series, or once for a
    trajectory series.

    Args:
        values: Calendar year (int) to a finite value >= 0. At least one.
        year_zero: The calendar year of study year 0 (construction).
        n_years: Length of the result, >= 1.

    Raises:
        TypeError: if a year, `year_zero` or `n_years` is not an int.
        ValueError: for no values, a value that is not finite or is negative,
            or `n_years` < 1.
    """
    for name, number in (("year_zero", year_zero), ("n_years", n_years)):
        if isinstance(number, bool) or not isinstance(number, (int, np.integer)):
            raise TypeError(f"{name} must be an int, got {number!r}")
    if n_years < 1:
        raise ValueError(f"n_years must be >= 1, got {n_years}")
    if not values:
        raise ValueError("values must have at least one year")
    for year, value in values.items():
        if isinstance(year, bool) or not isinstance(year, (int, np.integer)):
            raise TypeError(f"calendar years must be ints, got {year!r}")
        if isinstance(value, bool) or not math.isfinite(value) or value < 0:
            raise ValueError(f"value for {year} must be finite and >= 0, got {value!r}")
    known = sorted(values)
    calendar = np.arange(n_years) + int(year_zero)
    # np.interp holds the end values outside the given range.
    result = np.interp(calendar, known, [float(values[y]) for y in known])
    return [float(v) for v in result]


Multiplier = Callable[[int], NDArray[np.float64]]
"""Given a length n, the multiplier m(y) for y = 0..n - 1."""


def b6_series(
    lines: Iterable[object],
    study_period: int,
    years: int,
    multiplier: Callable[[object], Multiplier | None],
) -> dict[str, NDArray[np.float64]]:
    """kg of each gas per year from energy lines, years 1..RSP (record 0019).

    `lines` are validated `EnergyUse` objects. `multiplier(line)` gives the
    line's trajectory multiplier, or None for constant.
    """
    out = {gas: np.zeros(years) for gas in EMISSION_KEYS}
    use = slice(1, study_period + 1)
    for line in lines:
        per_year = _factor_by_year(line, study_period)  # gas -> kg per unit, years 1..RSP
        m = multiplier(line)
        scale = np.ones(study_period) if m is None else np.asarray(m(study_period + 1))[1:]
        for gas in EMISSION_KEYS:
            kg = line.amount * per_year[gas]
            if gas in FOSSIL_KEYS:
                kg = kg * scale
            out[gas][use] += kg
    return out


def _factor_by_year(line, study_period: int) -> dict[str, NDArray[np.float64]]:
    """kg of each gas per unit of the line's energy, for years 1..RSP."""
    factor = line.factor
    if factor is None:
        if line.fuel == "electricity":
            per_mj = electricity_factor_per_mj(
                subregion=line.egrid_subregion, state=line.egrid_state
            )
        else:
            per_mj = fuel_factor_per_mj(line.fuel)
        mj = to_mj(1.0, line.unit)
        return {gas: np.full(study_period, per_mj[gas] * mj) for gas in EMISSION_KEYS}
    if isinstance(factor, (list, tuple)):
        # Entry i is study year i; a short series holds its last value.
        index = np.minimum(np.arange(1, study_period + 1), len(factor) - 1)
        return {
            gas: np.array([getattr(factor[i], gas) for i in index], dtype=float)
            for gas in EMISSION_KEYS
        }
    return {gas: np.full(study_period, float(getattr(factor, gas))) for gas in EMISSION_KEYS}
