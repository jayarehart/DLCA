"""Biogenic carbon: uptake shares and the storage balance (#73).

Decisions B1-B7 and their follow-ups (Jay, 2026-11-20, on #73):

- Uptake is the declared `Biogenic.co2`, as negative `co2`, starting in the
  product's year (year 0, or a B4/B5 event's year). It is placed by
  `timeline()` in its own part, module ``"biogenic-uptake"``.
- ``"instant"``: all of it in the product's year.
- ``"gaussian"``: Cherubini et al. (2011), mu = rotation / 2, sigma = mu / 2.
  The pdf is integrated over each year [k, k + 1), k >= 0, from the product's
  year, and rescaled over [0, inf). Anything after the series end is cut off
  and reported (`BiogenicCarbonWarning`) when it is more than `CUT_WARN` of
  the item's uptake.
- ``"none"``: no uptake.
- The engine never oxidises non-fossil `ch4` to CO2, so its `ch4` already
  nets the carbon's uptake against its return (AR6's non-fossil convention).
  So the carbon released as `ch4` is taken off the uptake (B5, Option 1 on
  #73): per material, net uptake = declared - ch4 x 44.01 / 16.043, with the
  CH4 carbon (C1-C4 and B4/B5 events) spread over that material's uptake items
  in proportion to their `co2`. Never below zero.
- `biogenic_balance()` checks the declared carbon against what the user's
  entries release.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from dlca.inventory.schema import Biogenic, BuildingInventory, BuildingTotals, Event, GasAmounts

UPTAKE_MODULE = "biogenic-uptake"
"""Module name of the uptake part in a `Timeline` and the breakdown (B7)."""

CO2_PER_CH4_CARBON = 44.01 / 16.043
"""kg CO2 that the carbon in 1 kg CH4 took from the air (B5; AR6 Table 7.15's
basis). Used to net CH4 carbon out of the uptake, for the storage report and
for the warning. Fossil CH4 oxidation keeps 44/16 (decision D1 on #27)."""

CUT_WARN = 1e-9
"""Relative part of an item's Gaussian uptake that may fall after the series
end before `timeline()` warns."""

BALANCE_RTOL = 1e-12
"""Relative slack before releases count as more than the declared carbon."""

_END_OF_LIFE = ("C1", "C2", "C3", "C4")


class BiogenicCarbonWarning(UserWarning):
    """Biogenic carbon that does not add up: CH4 carbon with no declared
    uptake, more released than declared, or uptake cut by the series end."""


def _survival(z: float) -> float:
    """P(Z > z) for a standard normal Z, accurate in both tails."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def uptake_shares(
    regrowth: str, rotation: int | None, length: int
) -> tuple[NDArray[np.float64], float]:
    """Share of the declared carbon taken up in each year from the product's year.

    Args:
        regrowth: ``"none"``, ``"instant"`` or ``"gaussian"``.
        rotation: Rotation period [yr] for ``"gaussian"``; ignored otherwise.
        length: Number of years from the product's year to the series end.

    Returns:
        ``(shares, cut)``: `shares` has `length` entries, each >= 0; `cut` is
        the share that falls after the series end. ``shares.sum() + cut`` is 1
        for ``"instant"`` and ``"gaussian"`` and 0 for ``"none"``.
    """
    if length < 1:
        raise ValueError(f"length must be >= 1, got {length}")
    shares = np.zeros(length)
    if regrowth == "none":
        return shares, 0.0
    if regrowth == "instant":
        shares[0] = 1.0
        return shares, 0.0
    if regrowth != "gaussian":
        raise ValueError(f"unknown regrowth {regrowth!r}")
    if rotation is None or rotation < 2:
        raise ValueError(f"gaussian regrowth needs a rotation >= 2, got {rotation!r}")
    mu = rotation / 2.0
    sigma = mu / 2.0
    # S(z) at the edges z_k = (k - mu) / sigma, k = 0..length. The total over
    # [0, inf) is S(z_0) = S(-2); share_k = (S(z_k) - S(z_k+1)) / S(z_0).
    edges = np.array([_survival((k - mu) / sigma) for k in range(length + 1)])
    total = edges[0]
    shares = (edges[:-1] - edges[1:]) / total
    cut = edges[-1] / total
    return shares, float(cut)


def years_for_full_uptake(rotation: int, start: int) -> int:
    """Smallest series length for which a Gaussian uptake starting in year
    `start` has at most `CUT_WARN` cut off."""
    mu = rotation / 2.0
    sigma = mu / 2.0
    total = _survival(-2.0)
    k = math.ceil(mu)
    while _survival((k - mu) / sigma) / total > CUT_WARN:
        k += 1
    return start + k


@dataclass(frozen=True)
class BiogenicBalance:
    """Biogenic carbon of one material (or of a `BuildingTotals`), in kg CO2.

    Attributes:
        declared: Declared carbon, the material's own plus its events', times
            its quantity.
        uptake: Uptake the timeline holds: the declared carbon of items whose
            regrowth is not ``"none"``, less `released_ch4_as_co2`, never
            below zero (before any cut at the series end).
        released_co2: Sum of `Biogenic.released_co2`, times quantity.
        released_ch4_as_co2: Non-fossil CH4 in C1-C4 and in B4/B5 events,
            times quantity, times 44.01 / 16.043.
        stored: declared - released_co2 - released_ch4_as_co2: carbon still
            held when the timeline ends. Negative means more is released than
            declared.
    """

    declared: float
    uptake: float
    released_co2: float
    released_ch4_as_co2: float

    @property
    def stored(self) -> float:
        return self.declared - self.released_co2 - self.released_ch4_as_co2


_Item = tuple[tuple[str, str] | None, float, Biogenic | None, dict[str, GasAmounts], list[Event]]


def _items(building: BuildingTotals | BuildingInventory) -> Iterator[_Item]:
    if isinstance(building, BuildingTotals):
        yield None, 1.0, building.biogenic, building.modules, [*building.b4, *building.b5]
        return
    for assembly in building.assemblies:
        for m in assembly.materials:
            yield (assembly.name, m.name), m.quantity, m.biogenic, m.modules, [*m.b4, *m.b5]


def biogenic_balance(
    building: BuildingTotals | BuildingInventory,
) -> dict[tuple[str, str] | None, BiogenicBalance]:
    """Declared, released and stored biogenic carbon, per material (#73, B6).

    Keys are ``(assembly, material)`` for a `BuildingInventory` and ``None``
    for a `BuildingTotals`. Only items with a `biogenic` field (their own or
    an event's) appear: non-fossil CH4 with no declared biogenic carbon follows
    AR6's convention and needs no balance.
    """
    out: dict[tuple[str, str] | None, BiogenicBalance] = {}
    for key, scale, own, modules, events in _items(building):
        items = [b for b in (own, *(e.biogenic for e in events)) if b is not None]
        if not items:
            continue
        declared = sum(b.co2 for b in items)
        taken = sum(b.co2 for b in items if b.regrowth != "none")
        released = sum(b.released_co2 for b in items)
        ch4 = sum(modules[m].ch4 for m in _END_OF_LIFE if m in modules)
        ch4 += sum(e.amounts.ch4 for e in events)
        ch4_carbon = ch4 * CO2_PER_CH4_CARBON
        out[key] = BiogenicBalance(
            declared=scale * declared,
            uptake=scale * max(taken - ch4_carbon, 0.0),
            released_co2=scale * released,
            released_ch4_as_co2=scale * ch4_carbon,
        )
    return out


def uptake_factors(
    building: BuildingTotals | BuildingInventory,
) -> dict[tuple[str, str] | None, float]:
    """Factor (0..1) on each uptake item's `co2`, per material: the net uptake
    over the declared carbon of its items whose regrowth is not ``"none"``.
    Materials with no such item are left out."""
    balance = biogenic_balance(building)
    factors: dict[tuple[str, str] | None, float] = {}
    for key, scale, own, _, events in _items(building):
        items = [b for b in (own, *(e.biogenic for e in events)) if b is not None]
        taken = scale * sum(b.co2 for b in items if b.regrowth != "none")
        if taken > 0.0:
            factors[key] = balance[key].uptake / taken
    return factors


def warn_on_balance(building: BuildingTotals | BuildingInventory) -> None:
    """Warn for each item whose releases exceed its declared carbon (B5)."""
    for key, bal in biogenic_balance(building).items():
        where = "building" if key is None else "/".join(key)
        released = bal.released_co2 + bal.released_ch4_as_co2
        if released <= bal.declared * (1 + BALANCE_RTOL):
            continue
        message = (
            f"{where}: releases {released:.6g} kg CO2 of biogenic carbon "
            f"(released_co2 {bal.released_co2:.6g} + CH4 carbon "
            f"{bal.released_ch4_as_co2:.6g}), more than the {bal.declared:.6g} declared."
        )
        warnings.warn(message, BiogenicCarbonWarning, stacklevel=3)
