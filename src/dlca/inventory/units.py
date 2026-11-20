"""Energy units (#80). Internal: not exported from `dlca` or `dlca.inventory`.

The package works in MJ for energy. Every factor is derived from two exact
definitions (NIST SP 811, 2008, Appendix B):

- 1 kWh = 3.6 MJ
- 1 Btu (International Table) = 1055.05585262 J

and 1 therm = 100 000 Btu (US therm, based on the IT Btu).
"""

from __future__ import annotations

from types import MappingProxyType

import numpy as np
from numpy.typing import ArrayLike, NDArray

_MJ_PER_KWH = 3.6
_MJ_PER_BTU = 1055.05585262e-6

MJ_PER_UNIT = MappingProxyType(
    {
        "MJ": 1.0,
        "GJ": 1.0e3,
        "kWh": _MJ_PER_KWH,
        "kBtu": 1.0e3 * _MJ_PER_BTU,
        "MMBtu": 1.0e6 * _MJ_PER_BTU,
        "therm": 1.0e5 * _MJ_PER_BTU,
    }
)
"""MJ in one of each energy unit."""


def _factor(unit: str) -> float:
    try:
        return MJ_PER_UNIT[unit]
    except (KeyError, TypeError):
        allowed = ", ".join(MJ_PER_UNIT)
        raise ValueError(f"unknown energy unit {unit!r}; allowed: {allowed}") from None


def to_mj(value: ArrayLike, unit: str) -> float | NDArray[np.float64]:
    """Convert `value` in `unit` to MJ. Floats give a float, arrays an array."""
    result = np.asarray(value, dtype=np.float64) * _factor(unit)
    return float(result) if result.ndim == 0 else result


def from_mj(value: ArrayLike, unit: str) -> float | NDArray[np.float64]:
    """Convert `value` in MJ to `unit`. Floats give a float, arrays an array."""
    result = np.asarray(value, dtype=np.float64) / _factor(unit)
    return float(result) if result.ndim == 0 else result
