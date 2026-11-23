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
- Electricity by Cambium GEA region, year by year (#85, record 0021): NLR's
  eGRID-based historical intensities for the GEA regions (2014-2023), then a
  straight line to NLR Cambium 2024 ``aer_gen_*_c`` in 2030, then Cambium to
  2050, held after. Cambium's 2025 point is not used. Source: the Cambium
  2024 project on NLR's Scenario Viewer; see ``dlca/data/CAMBIUM_NOTICE.md``
  (not under the package's MIT licence).

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
CAMBIUM_FILE = "cambium2024_gea_aer_gen_c.csv"
CAMBIUM_HISTORICAL_FILE = "cambium2024_gea_historical.csv"
CAMBIUM_FIRST_YEAR = 2030
"""First Cambium year used; earlier Cambium points (2025) are dropped and the
series runs straight from the last historical year to this one (record 0021)."""
DEFAULT_CAMBIUM_SCENARIO = "MidCase"

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


def _read_rows(file_name: str) -> list[dict[str, str]]:
    with files("dlca.data").joinpath(file_name).open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@cache
def _cambium_kg_per_mwh(gea: str, scenario: str) -> Mapping[str, Mapping[int, float]]:
    """Gas -> {calendar year: kg per MWh} for one GEA region and scenario.

    Historical years from NLR's eGRID-based file, then Cambium `aer_gen_*_c`
    from `CAMBIUM_FIRST_YEAR` on (CH4 and N2O converted from g to kg).
    """
    out: dict[str, dict[int, float]] = {gas: {} for gas in FOSSIL_KEYS}
    for row in _read_rows(CAMBIUM_HISTORICAL_FILE):
        if row["gea"] == gea:
            year = int(row["year"])
            out["co2"][year] = float(row["co2_kg_per_mwh"])
            out["ch4_fossil"][year] = float(row["ch4_kg_per_mwh"])
            out["n2o"][year] = float(row["n2o_kg_per_mwh"])
    last_historical = max(out["co2"], default=None)
    for row in _read_rows(CAMBIUM_FILE):
        if row["gea"] == gea and row["scenario"] == scenario:
            year = int(row["year"])
            if year < CAMBIUM_FIRST_YEAR:
                continue
            out["co2"][year] = float(row["co2_kg_per_mwh"])
            out["ch4_fossil"][year] = float(row["ch4_g_per_mwh"]) / 1000
            out["n2o"][year] = float(row["n2o_g_per_mwh"]) / 1000
    if last_historical is None or max(out["co2"]) <= last_historical:
        raise ValueError(f"no packaged Cambium series for {gea!r}, scenario {scenario!r}")
    return MappingProxyType({gas: MappingProxyType(v) for gas, v in out.items()})


def cambium_factor_per_mj(
    gea: str, year_zero: int, n_years: int, scenario: str = DEFAULT_CAMBIUM_SCENARIO
) -> dict[str, NDArray[np.float64]]:
    """kg of each gas per MJ of electricity, study years 0..n_years - 1 (record 0021).

    Built with `to_study_years` from the joined calendar-year series of
    `gea` and `scenario`; `year_zero` is the calendar year of study year 0.
    """
    by_year = _cambium_kg_per_mwh(gea, scenario)
    out = {gas: np.zeros(n_years) for gas in EMISSION_KEYS}
    for gas in FOSSIL_KEYS:
        out[gas] = np.asarray(to_study_years(by_year[gas], year_zero, n_years)) / MJ_PER_MWH
    return out


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
    if getattr(line, "cambium_gea", None) is not None:
        per_mj = cambium_factor_per_mj(
            line.cambium_gea,
            line.year_zero,
            study_period + 1,
            line.cambium_scenario or DEFAULT_CAMBIUM_SCENARIO,
        )
        mj = to_mj(1.0, line.unit)
        return {gas: per_mj[gas][1:] * mj for gas in EMISSION_KEYS}
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
