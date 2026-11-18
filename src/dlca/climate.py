"""Climate engine core: pure NumPy functions of annual emissions.

Everything here works on plain arrays with year 0 at index 0 and one value per
year. No pandas. Parameters come from ``dlca.parameters.ClimateParameters``.

Discretisation (the same as the old ``DLCAEngine.calc_decay`` and the Cooper et
al. 2020 spreadsheet): an emission in year k enters the atmosphere in full at
year k, and the mass then decays as exp(-t/tau). For each gas (and each CO2
pool) the mass in year k is

    m[k] = E[k] + m[k-1] * exp(-1/tau),

so a 1 kg pulse at year 0 gives exactly exp(-t/tau) at whole years t. This is
computed as a convolution of the emissions with that kernel, with no Python loop
over years. Decision on issue #27 (2026-11-18).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from dlca.parameters import ClimateParameters

__all__ = ["CO2_PER_CH4_MASS_RATIO", "GASES", "Burden", "burden"]

GASES = ("co2", "ch4", "n2o")

# kg CO2 per kg CH4 for a 1 mol/mol conversion, from nominal integer molar masses
# (12 + 2*16) / (12 + 4) = 44/16. Decision D1 on issue #27 (Jay, 2026-11-18): this
# reproduces the Cooper et al. 2020 spreadsheet. The parameter sets' own molar
# masses (44.01 / 16.05) would give 0.29% less oxidised CO2.
CO2_PER_CH4_MASS_RATIO = 44.0 / 16.0


@dataclass(frozen=True, eq=False)
class Burden:
    """Mass of each gas in the atmosphere, in kg, one value per year.

    Attributes:
        co2: Total CO2, the sum of ``co2_pools``. Shape (N,).
        co2_pools: CO2 per impulse-response pool. Shape (4, N). Pool 0 is the
            permanent fraction a0; pools 1-3 decay with ``co2_tau[0..2]``.
        ch4: CH4. Shape (N,).
        n2o: N2O. Shape (N,).
        ch4_to_co2: CO2 formed from fossil CH4 removed in each year, added to that
            year's CO2 emissions. Zeros unless ``fossil_ch4=True``. Shape (N,).
    """

    co2: NDArray[np.float64]
    co2_pools: NDArray[np.float64]
    ch4: NDArray[np.float64]
    n2o: NDArray[np.float64]
    ch4_to_co2: NDArray[np.float64]

    def to_dict(self) -> dict[str, list]:
        """JSON-serialisable dict of plain lists (decision record 0005)."""
        return {
            "co2": self.co2.tolist(),
            "co2_pools": self.co2_pools.tolist(),
            "ch4": self.ch4.tolist(),
            "n2o": self.n2o.tolist(),
            "ch4_to_co2": self.ch4_to_co2.tolist(),
        }


def _decay(emissions: NDArray[np.float64], tau: float) -> NDArray[np.float64]:
    """m[k] = E[k] + m[k-1] exp(-1/tau), as a convolution with exp(-t/tau)."""
    n = emissions.shape[0]
    kernel = np.exp(-np.arange(n, dtype=float) / tau)
    return np.convolve(emissions, kernel)[:n]


def _validate(emissions: Mapping[str, ArrayLike]) -> dict[str, NDArray[np.float64]]:
    unknown = set(emissions) - set(GASES)
    if unknown:
        raise ValueError(f"unknown gas(es) {sorted(unknown)}; expected some of {list(GASES)}")
    if not emissions:
        raise ValueError("emissions is empty; give at least one gas")
    arrays = {}
    for gas, values in emissions.items():
        arr = np.asarray(values, dtype=float)
        if arr.ndim != 1:
            raise ValueError(f"{gas} emissions must be 1-D, got shape {arr.shape}")
        if not np.all(np.isfinite(arr)):
            raise ValueError(f"{gas} emissions contain non-finite values")
        arrays[gas] = arr
    lengths = {gas: arr.shape[0] for gas, arr in arrays.items()}
    if len(set(lengths.values())) != 1:
        raise ValueError(f"emissions arrays differ in length: {lengths}")
    n = next(iter(lengths.values()))
    if n == 0:
        raise ValueError("emissions arrays are empty")
    return {gas: arrays.get(gas, np.zeros(n)) for gas in GASES}


def burden(
    emissions: Mapping[str, ArrayLike],
    params: ClimateParameters,
    *,
    fossil_ch4: bool = False,
) -> Burden:
    """Mass of CO2, CH4 and N2O in the atmosphere from annual emissions.

    Args:
        emissions: ``{"co2": ..., "ch4": ..., "n2o": ...}``, emissions of each gas
            in kg of that gas (not kg C) per year, index 0 = year 0, all the same
            length. A missing gas counts as zeros. Negative values (uptake) are
            allowed.
        params: The climate parameter set.
        fossil_ch4: If true, CH4 removed from the atmosphere is oxidised to CO2.
            The CH4 removed during year k, ``ch4[k-1] * (1 - exp(-1/tau_CH4))``,
            times ``params.fossil_ch4_co2_yield()`` [mol/mol] times
            ``CO2_PER_CH4_MASS_RATIO``, is added to the CO2 emissions of year k
            before the CO2 pools are computed. The flag applies to all of the
            CH4 in ``emissions``; for a mix of fossil and biogenic CH4, call
            ``burden()`` once for each and add the results (it is linear).
            Negative CH4 (net removal) then gives negative oxidised CO2.

    Returns:
        A ``Burden`` with arrays in kg.

    Raises:
        ValueError: for an unknown gas, arrays that are not 1-D, of unequal or zero
            length, or with non-finite values; or if ``fossil_ch4`` is true and the
            set has no fossil CH4 yield.
    """
    e = _validate(emissions)
    n = e["co2"].shape[0]

    ch4 = _decay(e["ch4"], params.ch4_lifetime)
    n2o = _decay(e["n2o"], params.n2o_lifetime)

    ch4_to_co2 = np.zeros(n)
    if fossil_ch4:
        kg_per_kg = params.fossil_ch4_co2_yield() * CO2_PER_CH4_MASS_RATIO
        removed = ch4[:-1] * (1.0 - np.exp(-1.0 / params.ch4_lifetime))
        ch4_to_co2[1:] = kg_per_kg * removed

    co2_in = e["co2"] + ch4_to_co2
    a0, *a_decaying = params.co2_a
    pools = [a0 * np.cumsum(co2_in)]
    pools += [_decay(a * co2_in, tau) for a, tau in zip(a_decaying, params.co2_tau, strict=True)]
    co2_pools = np.stack(pools)

    return Burden(
        co2=co2_pools.sum(axis=0),
        co2_pools=co2_pools,
        ch4=ch4,
        n2o=n2o,
        ch4_to_co2=ch4_to_co2,
    )
