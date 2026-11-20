"""Concrete carbonation: CO2 uptake in use and after demolition (#74).

Method: Lagerblad, B. (2005), *Carbon dioxide uptake during concrete life
cycle: state of the art*, CBI report 2:2005. Decisions K1-K8 (Jay,
2026-11-20, on #74; record 0017):

- Depth d = k sqrt(t) [mm], t in years from casting. k is Table 2 (strength
  class x exposure, CEM I, bare concrete) times the cover factor (Table 3)
  times `binder_factor`.
- Uptake per m3 of carbonated concrete
  a = degree_of_carbonation x cement x cao_share x 44.01 / 56.077 [kg CO2/m3]
  (§5.1.5, with the fixed 0.75 made an input).
- Carbonated volume per declared unit = sum over surfaces of area x d / 1000,
  capped at the volume per declared unit (Andersson et al. 2013, eq. 2).
- In use: the yearly increments U(t) - U(t - 1) (Andersson et al. 2013,
  eq. 1), cast in year 0 (or a B4 event's year s), placed in years
  s + 1 .. end, where end is RSP or the year of the replacing B4 event.
  Module ``"carbonation-uptake"``.
- End of life: in RSP + 1 the uncarbonated remainder is crushed into spheres
  of radius r. Their carbonated share is 1 - ((r - d) / r)^3, capped at 1,
  with k for ``"exposed"``, the same strength class and binder, no cover
  factor, t counted from crushing. Years RSP + 1 .. RSP + n, module
  ``"carbonation-eol"``.

All uptake is returned here as positive kg CO2; `timeline()` writes it as
negative `co2`.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from dlca.inventory.schema import Carbonation, Cover, Exposure, StrengthClass

UPTAKE_MODULE = "carbonation-uptake"
"""Module name of the in-use carbonation part (K3)."""

EOL_MODULE = "carbonation-eol"
"""Module name of the crushed-stockpile carbonation part (K3, K4)."""

M_CO2 = 44.01
M_CAO = 56.077
CO2_PER_CAO = M_CO2 / M_CAO
"""kg CO2 bound per kg CaO carbonated (CaO + CO2 -> CaCO3)."""

K_TABLE: dict[Exposure, dict[StrengthClass, float]] = {
    "wet": {"<15": 2.0, "15-25": 1.0, "25-35": 0.75, ">35": 0.5},
    "buried": {"<15": 3.0, "15-25": 1.5, "25-35": 1.0, ">35": 0.75},
    "exposed": {"<15": 5.0, "15-25": 2.5, "25-35": 1.5, ">35": 1.0},
    "sheltered": {"<15": 10.0, "15-25": 6.0, "25-35": 4.0, ">35": 2.5},
    "indoors": {"<15": 15.0, "15-25": 9.0, "25-35": 6.0, ">35": 3.5},
}
"""Lagerblad (2005) Table 2: k [mm / sqrt(yr)] for CEM I, bare concrete.
Column bands per appendix A2.3 (Table 2 prints the second as 15-20 MPa)."""

COVER_FACTOR: dict[Cover, float] = {"none": 1.0, "indoor_house": 0.7, "outdoor_house": 0.9}
"""Lagerblad (2005) Table 3."""

EOL_EXPOSURE: Exposure = "exposed"
"""Exposure of the crushed stockpile (K4)."""


def k_value(
    exposure: Exposure, strength_class: StrengthClass, cover: Cover, binder_factor: float = 1.0
) -> float:
    """k [mm / sqrt(yr)]: Table 2 x cover factor x binder factor."""
    return K_TABLE[exposure][strength_class] * COVER_FACTOR[cover] * binder_factor


def depth(k: float, t: ArrayLike) -> NDArray[np.float64]:
    """Carbonation depth k sqrt(t) [mm], t [yr] >= 0."""
    t = np.asarray(t, dtype=float)
    if np.any(t < 0):
        raise ValueError("t must be >= 0")
    return k * np.sqrt(t)


def carbonated_volume(
    areas: Sequence[float], ks: Sequence[float], t: ArrayLike, volume: float
) -> NDArray[np.float64]:
    """Carbonated volume [m3] after t years: sum(area x k sqrt(t)) / 1000,
    capped at `volume`.

    Args:
        areas: m2 of each surface.
        ks: k [mm / sqrt(yr)] of each surface.
        t: Years since casting (scalar or array), >= 0.
        volume: The concrete volume the surfaces bound [m3].
    """
    if len(areas) != len(ks):
        raise ValueError("areas and ks must have the same length")
    t = np.asarray(t, dtype=float)
    rate = sum(a * k for a, k in zip(areas, ks, strict=True))  # m2 mm / sqrt(yr)
    return np.minimum(rate * depth(1.0, t) / 1000.0, volume)


def uptake_per_m3(c: Carbonation) -> float:
    """kg CO2 per m3 of carbonated concrete (Lagerblad §5.1.5)."""
    return c.degree_of_carbonation * c.cement * c.cao_share * CO2_PER_CAO


def volume_per_unit(c: Carbonation, unit: str) -> float:
    """m3 of concrete per declared unit: 1 for ``"m3"``, else `c.volume`."""
    if unit == "m3":
        return 1.0
    if c.volume is None:
        raise ValueError(f"carbonation needs a volume for unit {unit!r}")
    return c.volume


def _surface_ks(c: Carbonation) -> tuple[list[float], list[float]]:
    areas = [s.area for s in c.surfaces]
    ks = [k_value(s.exposure, c.strength_class, s.cover, c.binder_factor) for s in c.surfaces]
    return areas, ks


def in_use_volume(c: Carbonation, volume: float, t: ArrayLike) -> NDArray[np.float64]:
    """Carbonated volume [m3 per declared unit] t years after casting."""
    areas, ks = _surface_ks(c)
    return carbonated_volume(areas, ks, t, volume)


def cumulative_uptake(c: Carbonation, volume: float, t: ArrayLike) -> NDArray[np.float64]:
    """U(t): kg CO2 per declared unit taken up in use by t years after casting."""
    return uptake_per_m3(c) * in_use_volume(c, volume, t)


def in_use_increments(c: Carbonation, volume: float, years: int) -> NDArray[np.float64]:
    """U(t) - U(t - 1) for t = 1..years [kg CO2 per declared unit], each >= 0."""
    if years < 0:
        raise ValueError(f"years must be >= 0, got {years}")
    cumulative = cumulative_uptake(c, volume, np.arange(years + 1))
    return np.diff(cumulative)


def sphere_share(radius: float, k: float, t: ArrayLike) -> NDArray[np.float64]:
    """Carbonated share of a sphere of `radius` [mm] after t years:
    1 - ((r - d) / r)^3 with d = k sqrt(t), and 1 once d >= r."""
    if radius <= 0:
        raise ValueError(f"radius must be > 0, got {radius}")
    remaining = np.clip(1.0 - depth(k, t) / radius, 0.0, 1.0)
    return 1.0 - remaining**3


def eol_increments(c: Carbonation, volume: float, age: int) -> NDArray[np.float64]:
    """Stockpile uptake in each of its `c.end_of_life.years` years [kg CO2
    per declared unit], for concrete crushed at `age` years after casting.

    Year j (j = 0..n - 1, year 0 = the crushing year) gets
    a x V_u x (f(j + 1) - f(j)), with V_u the uncarbonated volume at `age`
    and f the sphere share.
    """
    if age < 0:
        raise ValueError(f"age must be >= 0, got {age}")
    remaining = volume - float(in_use_volume(c, volume, age))
    k = k_value(EOL_EXPOSURE, c.strength_class, "none", c.binder_factor)
    share = sphere_share(c.end_of_life.radius, k, np.arange(c.end_of_life.years + 1))
    return uptake_per_m3(c) * remaining * np.diff(share)


class CarbonationWarning(UserWarning):
    """Carbonation input the timeline cannot fully place: stockpile years past
    the series end, or a B4 event that replaces carbonating concrete without
    its own `carbonation` field."""
