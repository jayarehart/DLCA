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

Forcing and GWI (issue #28, decisions D1-D5, 2026-11-18). The forcing in year t
is the specific forcing times the burden at the start of year t, just after that
year's pulse. Between whole years each pool decays as a continuous exponential,
so the forcing integrated over year j -> j+1 is exact:

    A * sum_p m_p[j] * g_p,  g_p = 1 (permanent pool), tau_p (1 - exp(-1/tau_p)).

For a pulse this equals the closed-form ``agwp()`` at whole years.

Temperature and GTP (issue #29, decisions T1-T7, 2026-11-19). Each box of the
two-box climate response steps exactly between whole years on the same
exponentially decaying forcing (see ``temperature()``), so for a pulse the
temperature change equals the closed-form ``agtp()`` at whole years.

Fossil CH4 and static metrics (issue #30, decisions S1-S7, 2026-11-19). Fossil
CH4 is its own emissions key, ``ch4_fossil``: it adds to the CH4 burden like
``ch4`` and is also oxidised to CO2 (``burden()``). Non-fossil ``ch4`` is not
oxidised. Static GWP and GTP multiply cumulative emissions by GWP_H or GTP_H;
for fossil CH4 the factor includes the oxidised CO2 by the closed form behind
AR5 Table 8.A.1 (Boucher et al. 2009), from ``agwp("ch4_fossil", ...)`` and
``agtp("ch4_fossil", ...)``.

Parameter-set guard (issue #37, decision record 0009, 2026-11-19). ``Burden``,
``Forcing`` and ``Temperature`` record ``parameter_fingerprint``, the
``fingerprint()`` of the set that made them. ``forcing()`` and ``temperature()``
raise ``ValueError`` when the burden's fingerprint differs from that of the set
they are given, so a burden made with one set cannot silently be used with
another. The check compares values, not names: a variant made with
``dataclasses.replace()`` keeps its name but is a different set.

Carbon-cycle feedback (issue #33, decisions C1-C8, decision record 0010,
2026-11-19). When ``params.carbon_cycle_feedback`` is True (AR6), the warming
from CH4 and N2O makes the land and ocean sinks release CO2 (Gasser et al.
2017). The carbon released up to time t is

    C(t) = gamma * sum_i w_i * integral_0^t T(s) exp(-(t - s)/tau_i) ds,

with T the CH4 + N2O temperature change and (gamma, w_i, tau_i) the set's
``ccf_*`` values. ``burden()`` adds that CO2 to the CO2 emissions (``ccf_co2``),
so forcing, temperature and the dynamic GWI and GTP include it with no further
change. ``agwp()`` and ``agtp()`` add the exact closed form of the same
convolutions. The CO2 IRF already includes CO2's own feedback, so CO2 (including
CO2 from fossil CH4 and the CCF CO2 itself) drives no CCF.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
from numpy.typing import ArrayLike, NDArray

from dlca.parameters import ClimateParameters

__all__ = [
    "CO2_PER_CH4_MASS_RATIO",
    "GASES",
    "GTP",
    "EMISSION_KEYS",
    "GWI",
    "MIN_HORIZON",
    "Burden",
    "StaticGWP",
    "Forcing",
    "Temperature",
    "agtp",
    "agwp",
    "burden",
    "forcing",
    "gtp",
    "gwi",
    "specific_forcing",
    "static_gwp",
    "temperature",
]

# The physical gases: one burden, forcing and temperature series each.
GASES = ("co2", "ch4", "n2o")

# The keys an emissions mapping may hold (decision S4 on #30). ``ch4`` is
# non-fossil (biogenic) CH4, which is not oxidised to CO2; ``ch4_fossil`` is
# fossil CH4, which is. Both add to the CH4 burden.
EMISSION_KEYS = ("co2", "ch4", "ch4_fossil", "n2o")

# Smallest horizon gwi(), gtp() and static_gwp() accept [yr] (decision H2 on
# #47, decision record 0011). Below about 1e-9 yr the closed forms lose
# precision (1 - exp(-H/tau) rounds to 0); at 1e-6 yr their relative error is
# at most about 3e-9. agwp() and agtp() still accept any H >= 0.
MIN_HORIZON = 1e-6

# kg CO2 per kg CH4 for a 1 mol/mol conversion, from nominal integer molar masses
# (12 + 2*16) / (12 + 4) = 44/16. Decision D1 on issue #27 (Jay, 2026-11-18): this
# reproduces the Cooper et al. 2020 spreadsheet. The parameter sets' own molar
# masses (44.01 / 16.05) would give 0.29% less oxidised CO2.
CO2_PER_CH4_MASS_RATIO = 44.0 / 16.0


def _arrays(data: Mapping, names: tuple[str, ...]) -> dict[str, NDArray[np.float64]]:
    """Float arrays from the lists of a ``to_dict()`` output (for ``from_dict()``)."""
    missing = [name for name in names if name not in data]
    if missing:
        raise ValueError(f"missing key(s) {missing}")
    return {name: np.asarray(data[name], dtype=float) for name in names}


def _fingerprint_from(data: Mapping) -> str:
    """The ``parameter_fingerprint`` of a ``to_dict()`` output (for ``from_dict()``)."""
    if "parameter_fingerprint" not in data:
        raise ValueError("missing key(s) ['parameter_fingerprint']")
    value = data["parameter_fingerprint"]
    if not isinstance(value, str):
        raise ValueError(f"parameter_fingerprint must be a string, got {type(value).__name__}")
    return value


def _require_fingerprint_str(obj: object) -> None:
    """``__post_init__`` check shared by ``Burden``, ``Forcing`` and ``Temperature``."""
    value = obj.parameter_fingerprint  # type: ignore[attr-defined]
    if not isinstance(value, str):
        raise TypeError(f"parameter_fingerprint must be a string, got {type(value).__name__}")


def _check_same_set(b: Burden, params: ClimateParameters, function: str) -> str:
    """``params.fingerprint()``, or ``ValueError`` if ``b`` was made with another set."""
    fingerprint = params.fingerprint()
    if b.parameter_fingerprint != fingerprint:
        raise ValueError(
            f"{function}() was given parameter set {params.name!r} ({fingerprint[:8]}), but "
            f"the burden was made with a different set ({b.parameter_fingerprint[:8]}). "
            f"Build the burden and the {function} with the same parameter set. A set "
            "changed with dataclasses.replace() (for example carbon_cycle_feedback) keeps "
            "its name but is a different set."
        )
    return fingerprint


@dataclass(frozen=True, eq=False)
class Burden:
    """Mass of each gas in the atmosphere, in kg, one value per year.

    Attributes:
        co2: Total CO2, the sum of ``co2_pools``. Shape (N,).
        co2_pools: CO2 per impulse-response pool. Shape (4, N). Pool 0 is the
            permanent fraction a0; pools 1-3 decay with ``co2_tau[0..2]``.
        ch4: CH4, fossil and non-fossil together (decision S5 on #30; ``burden()``
            is linear, so ``burden({"ch4_fossil": ...})`` gives the fossil part).
            Shape (N,).
        n2o: N2O. Shape (N,).
        ch4_to_co2: CO2 formed from fossil CH4 removed in each year, added to that
            year's CO2 emissions. Zeros without ``ch4_fossil`` emissions. Shape (N,).
        ccf_co2: CO2 released by the carbon sinks because of the CH4 and N2O
            warming (carbon-cycle feedback, #33) during year k-1 -> k, added to
            year k's CO2 emissions [kg CO2]. Zeros when
            ``params.carbon_cycle_feedback`` is False. Shape (N,).
        parameter_fingerprint: ``fingerprint()`` of the parameter set the burden
            was made with. Required: ``forcing()`` and ``temperature()`` refuse a
            burden whose fingerprint differs from their set's (#37). Kept as the
            last field.
    """

    co2: NDArray[np.float64]
    co2_pools: NDArray[np.float64]
    ch4: NDArray[np.float64]
    n2o: NDArray[np.float64]
    ch4_to_co2: NDArray[np.float64]
    ccf_co2: NDArray[np.float64]
    parameter_fingerprint: str

    def __post_init__(self) -> None:
        _require_fingerprint_str(self)

    def to_dict(self) -> dict[str, list | str]:
        """JSON-serialisable dict of plain lists and the fingerprint (decision record 0005)."""
        return {
            "co2": self.co2.tolist(),
            "co2_pools": self.co2_pools.tolist(),
            "ch4": self.ch4.tolist(),
            "n2o": self.n2o.tolist(),
            "ch4_to_co2": self.ch4_to_co2.tolist(),
            "ccf_co2": self.ccf_co2.tolist(),
            "parameter_fingerprint": self.parameter_fingerprint,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, list | str]) -> Burden:
        """Inverse of ``to_dict()``. A missing key raises ``ValueError``."""
        return cls(
            **_arrays(data, ("co2", "co2_pools", "ch4", "n2o", "ch4_to_co2", "ccf_co2")),
            parameter_fingerprint=_fingerprint_from(data),
        )


def _decay(emissions: NDArray[np.float64], tau: float) -> NDArray[np.float64]:
    """m[k] = E[k] + m[k-1] exp(-1/tau), as a convolution with exp(-t/tau)."""
    n = emissions.shape[0]
    kernel = np.exp(-np.arange(n, dtype=float) / tau)
    return np.convolve(emissions, kernel)[:n]


def _validate(emissions: Mapping[str, ArrayLike]) -> dict[str, NDArray[np.float64]]:
    unknown = set(emissions) - set(EMISSION_KEYS)
    if unknown:
        raise ValueError(
            f"unknown emissions key(s) {sorted(unknown)}; expected some of {list(EMISSION_KEYS)}"
        )
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
    return {key: arrays.get(key, np.zeros(n)) for key in EMISSION_KEYS}


def burden(emissions: Mapping[str, ArrayLike], params: ClimateParameters) -> Burden:
    """Mass of CO2, CH4 and N2O in the atmosphere from annual emissions.

    Args:
        emissions: ``{"co2": ..., "ch4": ..., "ch4_fossil": ..., "n2o": ...}``,
            emissions in kg of that gas (not kg C) per year, index 0 = year 0, all
            the same length. A missing key counts as zeros. Negative values
            (uptake) are allowed. ``ch4`` is non-fossil CH4; ``ch4_fossil`` is
            fossil CH4, which is also oxidised to CO2: the fossil CH4 removed
            during year k, ``m_fossil[k-1] * (1 - exp(-1/tau_CH4))``, times
            ``params.fossil_ch4_co2_yield()`` [mol/mol] times
            ``CO2_PER_CH4_MASS_RATIO``, is added to the CO2 emissions of year k
            before the CO2 pools are computed. Negative fossil CH4 (net removal)
            gives negative oxidised CO2.
        params: The climate parameter set. If ``params.carbon_cycle_feedback``
            is True, the CO2 the sinks release because of the CH4 and N2O
            warming is also added to the CO2 emissions (``ccf_co2``, see
            ``_ccf_co2()``; #33).

    Returns:
        A ``Burden`` with arrays in kg, and ``parameter_fingerprint`` set to
        ``params.fingerprint()``.

    Raises:
        ValueError: for an unknown key, arrays that are not 1-D, of unequal or zero
            length, or with non-finite values; or if ``ch4_fossil`` has a non-zero
            value and the set has no fossil CH4 yield.
    """
    e = _validate(emissions)
    n = e["co2"].shape[0]

    ch4_fossil = _decay(e["ch4_fossil"], params.ch4_lifetime)
    ch4 = _decay(e["ch4"], params.ch4_lifetime) + ch4_fossil
    n2o = _decay(e["n2o"], params.n2o_lifetime)

    ch4_to_co2 = np.zeros(n)
    if np.any(e["ch4_fossil"] != 0):
        kg_per_kg = params.fossil_ch4_co2_yield() * CO2_PER_CH4_MASS_RATIO
        removed = ch4_fossil[:-1] * (1.0 - np.exp(-1.0 / params.ch4_lifetime))
        ch4_to_co2[1:] = kg_per_kg * removed

    ccf_co2 = _ccf_co2(ch4, n2o, params) if params.carbon_cycle_feedback else np.zeros(n)

    co2_in = e["co2"] + ch4_to_co2 + ccf_co2
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
        ccf_co2=ccf_co2,
        parameter_fingerprint=params.fingerprint(),
    )


# --- Carbon-cycle feedback (issue #33) ---------------------------------------


def _ccf_co2(
    ch4: NDArray[np.float64], n2o: NDArray[np.float64], params: ClimateParameters
) -> NDArray[np.float64]:
    """CO2 released by the sinks in each year from the CH4 and N2O warming [kg CO2].

    The temperature T from the CH4 and N2O burdens is taken at whole years, by the
    same exact steps as ``temperature()``. The carbon released up to year k is
    ``C[k] = gamma sum_i w_i S_i[k]``, where ``S_i[k] = S_i[k-1] r_i + (T[k-1] r_i
    + T[k]) / 2`` and ``r_i = exp(-1/tau_i)`` (the trapezoid rule over each year,
    decision C4 on #33). The carbon released during year k-1 -> k,
    ``C[k] - C[k-1]``, times ``molar_mass_co2 / molar_mass_c``, is added to the
    CO2 emissions of year k, as for ``ch4_to_co2``. For a pulse this differs from
    the closed form of ``agwp()`` by up to about 0.1% (GWP20; 0.015% at GWP100).
    """
    n = ch4.shape[0]
    out = np.zeros(n)
    if n < 2:
        return out
    no_co2 = np.zeros((len(params.co2_a), n))
    series = _temperature_series(SimpleNamespace(co2_pools=no_co2, ch4=ch4, n2o=n2o), params)
    t = series["ch4"] + series["n2o"]
    released = np.zeros(n)  # carbon released by the sinks up to the start of year k [kg C]
    for w, tau in zip(params.ccf_weights, params.ccf_timescales, strict=True):
        r = np.exp(-1.0 / tau)
        increment = 0.5 * (t[:-1] * r + t[1:])
        released[1:] += w * np.convolve(increment, r ** np.arange(n - 1))[: n - 1]
    out[1:] = np.diff(params.ccf_gamma * released)
    return out * params.molar_mass_co2 / params.molar_mass_c


# A sum of terms c * t**k * exp(-r t), as a list of (c, r, k), k = 0 or 1.
_Terms = list[tuple[float, float, int]]

# Two rates closer than this (relative) are treated as equal in ``_convolve``.
_SAME_RATE = 1e-9


def _convolve(f: _Terms, g: _Terms) -> _Terms:
    """Exact convolution on [0, t] of two sums of exponentials (k = 0 terms only).

    ``integral_0^t exp(-r u) exp(-s (t - u)) du`` is ``(exp(-s t) - exp(-r t)) /
    (r - s)``, or ``t exp(-r t)`` for r = s. A k = 1 input means two rates
    coincided earlier; that case is refused with ``ValueError``.
    """
    out: _Terms = []
    for c, r, k in f:
        for b, s, m in g:
            if k or m:
                raise ValueError(
                    "the carbon-cycle feedback closed form is not defined for this "
                    "parameter set: two of its response times coincide"
                )
            if abs(r - s) <= _SAME_RATE * max(r, s):
                out.append((c * b, r, 1))
            else:
                ratio = c * b / (r - s)
                out += [(ratio, s, 0), (-ratio, r, 0)]
    return out


def _evaluate(f: _Terms, h: NDArray[np.float64]) -> NDArray[np.float64]:
    return sum((c * h**k * np.exp(-r * h) for c, r, k in f), np.zeros_like(h))


def _integral(f: _Terms, h: NDArray[np.float64]) -> NDArray[np.float64]:
    """``integral_0^H f(t) dt``."""
    out = np.zeros_like(h)
    for c, r, k in f:
        if r == 0.0:
            out = out + c * (h if k == 0 else h**2 / 2)
        elif k == 0:
            out = out + c * (1.0 - np.exp(-r * h)) / r
        else:
            out = out + c * (1.0 - np.exp(-r * h) * (1.0 + r * h)) / r**2
    return out


def _ccf_forcing_terms(gas: str, params: ClimateParameters) -> tuple[_Terms, _Terms]:
    """The extra CO2 forcing of a 1 kg pulse of CH4 or N2O from the CCF, and the
    climate response, as sums of exponentials.

    T = forcing of the gas convolved with the climate response; the carbon flux
    is ``gamma (T * r_F)`` with ``r_F = delta(t) sum_i w_i - sum_i (w_i / tau_i)
    exp(-t / tau_i)`` (Gasser et al. 2017, Section 3.3), in kg C yr-1 per kg; the
    forcing is that flux, in kg CO2, convolved with the CO2 forcing per kg.

    Returns:
        (rf_cc [W m-2 per kg], climate response [K (W m-2)-1 yr-1]).
    """
    climate = [(q / d, 1.0 / d, 0) for q, d in zip(params.climate_q, params.climate_d, strict=True)]
    rf_gas = [(specific_forcing(gas, params), 1.0 / _lifetime(gas, params), 0)]
    t = _convolve(rf_gas, climate)
    gamma = params.ccf_gamma * params.molar_mass_co2 / params.molar_mass_c
    flux = [(gamma * sum(params.ccf_weights) * c, r, k) for c, r, k in t]
    for w, tau in zip(params.ccf_weights, params.ccf_timescales, strict=True):
        flux += [(-gamma * w / tau * c, r, k) for c, r, k in _convolve(t, [(1.0, 1.0 / tau, 0)])]
    a_co2 = specific_forcing("co2", params)
    rf_co2 = [(a_co2 * params.co2_a[0], 0.0, 0)]
    rf_co2 += [
        (a_co2 * a, 1.0 / tau, 0) for a, tau in zip(params.co2_a[1:], params.co2_tau, strict=True)
    ]
    return _convolve(flux, rf_co2), climate


def _ccf_agwp(gas: str, h: NDArray[np.float64], params: ClimateParameters) -> NDArray[np.float64]:
    """AGWP added by the carbon-cycle feedback for CH4 or N2O [W m-2 yr kg-1]."""
    rf_cc, _ = _ccf_forcing_terms(gas, params)
    return _integral(rf_cc, h)


def _ccf_agtp(gas: str, h: NDArray[np.float64], params: ClimateParameters) -> NDArray[np.float64]:
    """AGTP added by the carbon-cycle feedback for CH4 or N2O [K kg-1]."""
    rf_cc, climate = _ccf_forcing_terms(gas, params)
    return _evaluate(_convolve(rf_cc, climate), h)


def _molar_mass(gas: str, params: ClimateParameters) -> float:
    return {
        "co2": params.molar_mass_co2,
        "ch4": params.molar_mass_ch4,
        "n2o": params.molar_mass_n2o,
    }[gas]


def _check_gas(gas: str, allowed: tuple[str, ...] = GASES) -> str:
    if not isinstance(gas, str) or gas.lower() not in allowed:
        raise ValueError(f"unknown gas {gas!r}; expected one of {list(allowed)}")
    return gas.lower()


def _check_horizon_array(horizon: ArrayLike) -> NDArray[np.float64]:
    h = np.asarray(horizon, dtype=float)
    if not np.all(np.isfinite(h)) or np.any(h < 0):
        raise ValueError("horizon must be finite and >= 0")
    return h


def _check_horizon(horizon: float) -> float:
    """The horizon of gwi(), gtp() and static_gwp(): finite and >= MIN_HORIZON."""
    horizon = float(horizon)
    if not np.isfinite(horizon) or horizon < MIN_HORIZON:
        raise ValueError(
            f"horizon must be finite and >= MIN_HORIZON = {MIN_HORIZON:g} yr, got {horizon}"
        )
    return horizon


def _after_ch4_decay(tau: float, c: float | None, h: NDArray[np.float64]) -> NDArray[np.float64]:
    """Integral of (1/tau) exp(-u/tau) exp(-(H-u)/c) du from 0 to H; c=None means c=inf.

    The fossil CH4 removed in [u, u+du] is (1/tau) exp(-u/tau) du per kg emitted at
    0, so this convolves the CH4 removal rate with a response exp(-t/c) to the CO2
    it forms. ``c / (c - tau) (exp(-H/c) - exp(-H/tau))``, or ``1 - exp(-H/tau)``
    for c = inf. Raises ``ValueError`` if c is within 1e-6 c of tau.
    """
    if c is None:
        return 1.0 - np.exp(-h / tau)
    if abs(c - tau) < 1e-6 * c:
        raise ValueError(
            f"CH4 lifetime {tau} yr equals a CO2 or climate response time {c} yr; "
            "the fossil CH4 closed form is not defined for this parameter set"
        )
    return c / (c - tau) * (np.exp(-h / c) - np.exp(-h / tau))


def _oxidised_co2_per_kg_ch4(params: ClimateParameters) -> float:
    """kg CO2 formed per kg fossil CH4 removed."""
    return params.fossil_ch4_co2_yield() * CO2_PER_CH4_MASS_RATIO


def _lifetime(gas: str, params: ClimateParameters) -> float:
    return params.ch4_lifetime if gas == "ch4" else params.n2o_lifetime


def specific_forcing(gas: str, params: ClimateParameters) -> float:
    """Radiative forcing per kg of a gas in the atmosphere [W m-2 kg-1].

    ``params.effective_radiative_efficiency(gas)`` [W m-2 ppb-1], which holds the
    indirect CH4 and N2O effects, times the ppb per kg of gas,
    ``molar_mass_air / molar_mass_<gas> * 1e9 / atm_mass``.
    """
    gas = _check_gas(gas)
    ppb_per_kg = params.molar_mass_air / _molar_mass(gas, params) * 1e9 / params.atm_mass
    return params.effective_radiative_efficiency(gas) * ppb_per_kg


@dataclass(frozen=True, eq=False)
class Forcing:
    """Radiative forcing of each gas, one value per year.

    Attributes:
        co2, ch4, n2o: Forcing at the start of year t, just after that year's
            pulse [W m-2]. Shape (N,).
        co2_integrated, ch4_integrated, n2o_integrated: Forcing integrated from
            year 0 to the start of year t [W yr m-2]; 0 at year 0. Shape (N,).
        parameter_fingerprint: ``fingerprint()`` of the parameter set that made
            it (#37). Kept as the last field.
    """

    co2: NDArray[np.float64]
    ch4: NDArray[np.float64]
    n2o: NDArray[np.float64]
    co2_integrated: NDArray[np.float64]
    ch4_integrated: NDArray[np.float64]
    n2o_integrated: NDArray[np.float64]
    parameter_fingerprint: str

    def __post_init__(self) -> None:
        _require_fingerprint_str(self)

    @property
    def total(self) -> NDArray[np.float64]:
        """Sum of the gases' forcing [W m-2]."""
        return self.co2 + self.ch4 + self.n2o

    @property
    def total_integrated(self) -> NDArray[np.float64]:
        """Sum of the gases' integrated forcing [W yr m-2]."""
        return self.co2_integrated + self.ch4_integrated + self.n2o_integrated

    def to_dict(self) -> dict[str, list | str]:
        """JSON-serialisable dict of plain lists and the fingerprint (decision record 0005)."""
        names = ("co2", "ch4", "n2o", "co2_integrated", "ch4_integrated", "n2o_integrated")
        out: dict[str, list | str] = {name: getattr(self, name).tolist() for name in names}
        out["parameter_fingerprint"] = self.parameter_fingerprint
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, list | str]) -> Forcing:
        """Inverse of ``to_dict()``. A missing key raises ``ValueError``."""
        names = ("co2", "ch4", "n2o", "co2_integrated", "ch4_integrated", "n2o_integrated")
        return cls(**_arrays(data, names), parameter_fingerprint=_fingerprint_from(data))


def _integrate(increments: NDArray[np.float64]) -> NDArray[np.float64]:
    """Integrated value at the start of each year: 0, then a running sum."""
    out = np.zeros_like(increments)
    out[1:] = np.cumsum(increments[:-1])
    return out


def forcing(b: Burden, params: ClimateParameters) -> Forcing:
    """Radiative forcing and integrated forcing from a ``Burden``.

    Args:
        b: Atmospheric masses from ``burden()`` [kg].
        params: The climate parameter set ``b`` was made with.

    Returns:
        A ``Forcing`` with arrays of the burden's length and the set's
        ``parameter_fingerprint``. Inputs are not changed.

    Raises:
        ValueError: if ``b.parameter_fingerprint`` differs from
            ``params.fingerprint()`` (``b`` was made with another set, or a
            variant of this one; #37), or if ``b`` has the wrong number of CO2
            pools.
    """
    fingerprint = _check_same_set(b, params, "forcing")
    a_co2 = specific_forcing("co2", params)
    g = np.array([1.0] + [tau * (1.0 - np.exp(-1.0 / tau)) for tau in params.co2_tau])
    if b.co2_pools.shape[0] != g.shape[0]:
        raise ValueError(f"co2_pools must have {g.shape[0]} pools, got {b.co2_pools.shape[0]}")
    out = {
        "co2": a_co2 * b.co2,
        "co2_integrated": _integrate(a_co2 * (g @ b.co2_pools)),
    }
    for gas in ("ch4", "n2o"):
        a = specific_forcing(gas, params)
        tau = _lifetime(gas, params)
        mass = getattr(b, gas)
        out[gas] = a * mass
        out[f"{gas}_integrated"] = _integrate(a * tau * (1.0 - np.exp(-1.0 / tau)) * mass)
    return Forcing(**out, parameter_fingerprint=fingerprint)


def agwp(gas: str, horizon: ArrayLike, params: ClimateParameters) -> NDArray[np.float64] | float:
    """Absolute global warming potential of a 1 kg pulse [W m-2 yr kg-1], closed form.

    - CO2: ``A * (a0 H + sum_i a_i tau_i (1 - exp(-H / tau_i)))``.
    - CH4, N2O: ``A * tau (1 - exp(-H / tau))``. ``"ch4"`` is not oxidised.
    - ``"ch4_fossil"`` (decision S1/S2-A on #30): the CH4 term plus the oxidised
      CO2, ``Y * 44/16 * integral_0^H (1/tau) exp(-t/tau) AGWP_CO2(H - t) dt``,
      with ``Y = params.fossil_ch4_co2_yield()`` (Boucher et al. 2009, the method
      of AR5 Table 8.A.1). This is the continuous-time value. ``gwi().sliding``,
      which adds the oxidised CO2 in whole years, differs from it by 0.02% to
      0.05% for a fossil pulse (AR5 and AR6, H = 20 and 100; decision S2-A).

    ``A`` is ``specific_forcing(gas, params)``.

    If ``params.carbon_cycle_feedback`` is True, CH4 and N2O (and so
    ``"ch4_fossil"``) include the carbon-cycle feedback of Gasser et al. (2017)
    in exact closed form (decisions C2/C4 on #33). This is not the IPCC code's
    0.1-yr numerical value: AR6 CH4 GWP100 is 28.02 here against the printed
    27.9. CO2 has no CCF term: its IRF already includes the feedback.

    Args:
        gas: ``"co2"``, ``"ch4"``, ``"ch4_fossil"`` or ``"n2o"``.
        horizon: Time horizon(s) H [yr], >= 0. Any shape.
        params: The climate parameter set.

    Returns:
        An array of ``horizon``'s shape, or a float for a scalar ``horizon``.
    """
    gas = _check_gas(gas, EMISSION_KEYS)
    h = _check_horizon_array(horizon)
    if gas == "ch4_fossil":
        tau = params.ch4_lifetime
        a0, *a_decaying = params.co2_a
        ox = a0 * (h - tau * (1.0 - np.exp(-h / tau)))
        for ai, tau_i in zip(a_decaying, params.co2_tau, strict=True):
            ox = ox + ai * tau_i * (
                _after_ch4_decay(tau, None, h) - _after_ch4_decay(tau, tau_i, h)
            )
        co2 = specific_forcing("co2", params) * ox
        out = agwp("ch4", h, params) + _oxidised_co2_per_kg_ch4(params) * co2
        return float(out) if out.ndim == 0 else out
    out = _agwp_direct(gas, h, params)
    if gas != "co2" and params.carbon_cycle_feedback:
        out = out + _ccf_agwp(gas, h, params)
    return float(out) if out.ndim == 0 else out


def _agwp_direct(
    gas: str, h: NDArray[np.float64], params: ClimateParameters
) -> NDArray[np.float64]:
    """AGWP of CO2, CH4 or N2O without the carbon-cycle feedback, as an array."""
    a = specific_forcing(gas, params)
    if gas == "co2":
        a0, *a_decaying = params.co2_a
        shape = a0 * h
        for ai, tau in zip(a_decaying, params.co2_tau, strict=True):
            shape = shape + ai * tau * (1.0 - np.exp(-h / tau))
    else:
        tau = _lifetime(gas, params)
        shape = tau * (1.0 - np.exp(-h / tau))
    return a * shape


@dataclass(frozen=True, eq=False)
class GWI:
    """Global warming impact in kg CO2-equivalent, one value per year.

    Attributes:
        dynamic: Forcing integrated from year 0 to year t, divided by
            ``agwp_co2`` [kg CO2e]. Shape (N,). (The old ``equiv_df.LCA_dyn``.)
        sliding: Forcing integrated up to the fixed year ``horizon`` from the
            emissions of years 0..t, divided by ``agwp_co2`` [kg CO2e]. An
            emission in year k gets horizon ``max(horizon - k, 0)``. For a
            whole-number horizon, ``sliding[t] == dynamic[horizon]`` for
            t >= horizon. CO2 formed from
            fossil CH4 counts as CO2 emitted in the year it forms (decision D2,
            #28). Shape (N,). (The Cooper spreadsheet's ``GWP_sliding_CO2e``.)
        static: ``static_gwp(...).total``: cumulative net emissions up to year t
            times GWP_H, summed over the keys [kg CO2e]. Fossil CH4 includes its
            oxidised CO2 (decision S3 on #30). Shape (N,). (``GWP_static_CO2e``.)
        horizon: Time horizon [yr].
        agwp_co2: ``agwp("co2", horizon, params)`` [W m-2 yr kg-1].
    """

    dynamic: NDArray[np.float64]
    sliding: NDArray[np.float64]
    static: NDArray[np.float64]
    horizon: float
    agwp_co2: float

    def to_dict(self) -> dict:
        """JSON-serialisable dict (decision record 0005)."""
        return {
            "dynamic": self.dynamic.tolist(),
            "sliding": self.sliding.tolist(),
            "static": self.static.tolist(),
            "horizon": self.horizon,
            "agwp_co2": self.agwp_co2,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> GWI:
        """Inverse of ``to_dict()``."""
        return cls(
            **_arrays(data, ("dynamic", "sliding", "static")),
            horizon=float(data["horizon"]),
            agwp_co2=float(data["agwp_co2"]),
        )


def gwi(
    emissions: Mapping[str, ArrayLike],
    params: ClimateParameters,
    *,
    horizon: float = 100,
) -> GWI:
    """Cumulative dynamic GWI and sliding and static GWP from annual emissions.

    Args:
        emissions: As for ``burden()``: kg per year of each key, index 0 = year 0.
        params: The climate parameter set.
        horizon: Time horizon H [yr] for the CO2 normalisation and the sliding
            and static GWP; >= ``MIN_HORIZON`` (1e-6 yr).

    Returns:
        A ``GWI``. All three series are normalised by AGWP_H(CO2) from the same
        ``params``.
    """
    horizon = _check_horizon(horizon)
    e = _validate(emissions)
    b = burden(e, params)
    f = forcing(b, params)
    ref = agwp("co2", horizon, params)

    n = b.co2.shape[0]
    remaining = np.clip(horizon - np.arange(n, dtype=float), 0.0, None)
    # CCF CO2 counts as CO2 emitted in the year it forms (C4 on #33), so the
    # CH4 and N2O terms here leave the feedback out.
    co2 = e["co2"] + b.ch4_to_co2 + b.ccf_co2
    contribution = co2 * _agwp_direct("co2", remaining, params)
    ch4 = e["ch4"] + e["ch4_fossil"]
    contribution = contribution + ch4 * _agwp_direct("ch4", remaining, params)
    contribution = contribution + e["n2o"] * _agwp_direct("n2o", remaining, params)

    return GWI(
        dynamic=f.total_integrated / ref,
        sliding=np.cumsum(contribution) / ref,
        static=static_gwp(e, params, horizon=horizon).total,
        horizon=horizon,
        agwp_co2=ref,
    )


@dataclass(frozen=True, eq=False)
class StaticGWP:
    """Static GWP by emissions key, in kg CO2-equivalent, one value per year.

    Each series is the cumulative net emissions of that key up to year t times
    its GWP_H, with no timing (decision S1 on #30). The totals over the whole
    period are the last values.

    Attributes:
        co2, ch4, ch4_fossil, n2o: [kg CO2e]. Shape (N,). ``ch4`` is non-fossil
            CH4; ``ch4_fossil`` includes the CO2 its oxidation forms.
        horizon: Time horizon [yr].
        gwp: GWP_H used for each key, ``agwp(key, H) / agwp("co2", H)`` [kg CO2e
            per kg]. Without fossil CH4 emissions, ``ch4_fossil`` is left out when
            the set cannot compute it (no fossil CH4 yield, or a CH4 lifetime equal
            to a CO2 or climate response time).
    """

    co2: NDArray[np.float64]
    ch4: NDArray[np.float64]
    ch4_fossil: NDArray[np.float64]
    n2o: NDArray[np.float64]
    horizon: float
    gwp: Mapping[str, float]

    @property
    def total(self) -> NDArray[np.float64]:
        """Sum over the keys [kg CO2e]."""
        return self.co2 + self.ch4 + self.ch4_fossil + self.n2o

    def to_dict(self) -> dict:
        """JSON-serialisable dict (decision record 0005)."""
        out: dict = {key: getattr(self, key).tolist() for key in EMISSION_KEYS}
        out["horizon"] = self.horizon
        out["gwp"] = dict(self.gwp)
        return out

    @classmethod
    def from_dict(cls, data: Mapping) -> StaticGWP:
        """Inverse of ``to_dict()``."""
        return cls(
            **_arrays(data, EMISSION_KEYS),
            horizon=float(data["horizon"]),
            gwp={key: float(value) for key, value in data["gwp"].items()},
        )


def _static_factors(
    e: Mapping[str, NDArray[np.float64]], params: ClimateParameters, horizon: float, metric
) -> dict[str, float]:
    """metric(key, H) / metric("co2", H) per key.

    The ch4_fossil factor is required (errors propagate) when there are fossil CH4
    emissions. Without them it is included only if the set can compute it (it has
    a yield, and the CH4 lifetime is not a CO2 or climate response time), so
    non-fossil input never fails because of the fossil closed form.
    """
    ref = metric("co2", horizon, params)
    factors = {key: metric(key, horizon, params) / ref for key in ("co2", "ch4", "n2o")}
    if np.any(e["ch4_fossil"] != 0):
        factors["ch4_fossil"] = metric("ch4_fossil", horizon, params) / ref
    else:
        try:
            factors["ch4_fossil"] = metric("ch4_fossil", horizon, params) / ref
        except ValueError:
            pass
    return {key: factors[key] for key in EMISSION_KEYS if key in factors}


def static_gwp(
    emissions: Mapping[str, ArrayLike],
    params: ClimateParameters,
    *,
    horizon: float = 100,
) -> StaticGWP:
    """Static GWP from annual emissions: cumulative emissions times GWP_H, by key.

    Args:
        emissions: As for ``burden()``: kg per year of each key, index 0 = year 0.
        params: The climate parameter set.
        horizon: Time horizon H [yr]; >= ``MIN_HORIZON`` (1e-6 yr).

    Returns:
        A ``StaticGWP``. GWP_H is ``agwp(key, H) / agwp("co2", H)`` from the same
        ``params``; for ``ch4_fossil`` it includes the oxidised CO2 (decision
        S2-A on #30).
    """
    horizon = _check_horizon(horizon)
    e = _validate(emissions)
    factors = _static_factors(e, params, horizon, agwp)
    series = {key: np.cumsum(e[key]) * factors.get(key, 0.0) for key in EMISSION_KEYS}
    return StaticGWP(**series, horizon=horizon, gwp=factors)


# --- Temperature and GTP (issue #29) -----------------------------------------


def _box_response(tau: float | None, d: float, q: float, t: ArrayLike) -> NDArray[np.float64]:
    """Box ``(q, d)`` temperature at time t from a unit forcing that starts at 0.

    The forcing is constant for the permanent CO2 pool (``tau is None``) and
    decays as exp(-s/tau) otherwise. The box's response to a forcing step is
    (q/d) exp(-t/d), so the result is

    - ``q (1 - exp(-t/d))`` for a constant forcing;
    - ``q tau / (tau - d) (exp(-t/tau) - exp(-t/d))`` for a decaying one.

    Raises ``ValueError`` if tau and d are within 1e-6 d of each other
    (decision T7 on #29), where the second form divides by almost zero.
    """
    t = np.asarray(t, dtype=float)
    if tau is None:
        return q * (1.0 - np.exp(-t / d))
    if abs(tau - d) < 1e-6 * d:
        raise ValueError(
            f"lifetime {tau} yr equals climate response time {d} yr; "
            "the two-box AGTP is not defined for this parameter set"
        )
    return q * tau / (tau - d) * (np.exp(-t / tau) - np.exp(-t / d))


def _components(gas: str, params: ClimateParameters) -> list[tuple[float, float | None]]:
    """(fraction, lifetime) of each decaying component of a 1 kg pulse; None = permanent."""
    if gas == "co2":
        return list(zip(params.co2_a, (None, *params.co2_tau), strict=True))
    return [(1.0, _lifetime(gas, params))]


@dataclass(frozen=True, eq=False)
class Temperature:
    """Global mean surface temperature change from each gas, one value per year.

    Attributes:
        co2, ch4, n2o: Temperature change at the start of year t [K]; 0 at
            year 0. Shape (N,).
        parameter_fingerprint: ``fingerprint()`` of the parameter set that made
            it (#37). Kept as the last field.
    """

    co2: NDArray[np.float64]
    ch4: NDArray[np.float64]
    n2o: NDArray[np.float64]
    parameter_fingerprint: str

    def __post_init__(self) -> None:
        _require_fingerprint_str(self)

    @property
    def total(self) -> NDArray[np.float64]:
        """Sum of the gases' temperature change [K]."""
        return self.co2 + self.ch4 + self.n2o

    def to_dict(self) -> dict[str, list | str]:
        """JSON-serialisable dict of plain lists and the fingerprint (decision record 0005)."""
        out: dict[str, list | str] = {name: getattr(self, name).tolist() for name in GASES}
        out["parameter_fingerprint"] = self.parameter_fingerprint
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, list | str]) -> Temperature:
        """Inverse of ``to_dict()``. A missing key raises ``ValueError``."""
        return cls(**_arrays(data, GASES), parameter_fingerprint=_fingerprint_from(data))


def temperature(b: Burden, params: ClimateParameters) -> Temperature:
    """Temperature change from a ``Burden``, by the two-box impulse response.

    Each box i (sensitivity ``climate_q[i]`` [K (W m-2)-1], response time
    ``climate_d[i]`` [yr]) steps exactly between whole years. The forcing of each
    component p (CO2 pool or gas) decays from its value at the start of year j as
    in ``forcing()``, so

        T_i[j+1] = T_i[j] exp(-1/d_i) + sum_p F_p[j] h_pi,

    with ``h_pi = _box_response(tau_p, d_i, q_i, 1)``. This is computed as a
    convolution with exp(-t/d_i), with no Python loop. For a 1 kg pulse at year 0
    it equals ``agtp(gas, t)`` at whole years t. Decision T1 on #29 (2026-11-19):
    it takes a ``Burden``, not a ``Forcing``, because the exact step needs the
    forcing of each CO2 pool, not only the total.

    Args:
        b: Atmospheric masses from ``burden()`` [kg].
        params: The climate parameter set ``b`` was made with.

    Returns:
        A ``Temperature`` with arrays of the burden's length and the set's
        ``parameter_fingerprint``. Inputs are not changed.

    Raises:
        ValueError: if ``b.parameter_fingerprint`` differs from
            ``params.fingerprint()`` (``b`` was made with another set, or a
            variant of this one; #37), if ``b`` has the wrong number of CO2
            pools, or if a lifetime equals a climate response time (T7 on #29).
    """
    fingerprint = _check_same_set(b, params, "temperature")
    return Temperature(
        **_temperature_series(b, params),
        parameter_fingerprint=fingerprint,
    )


def _temperature_series(b: Burden, params: ClimateParameters) -> dict[str, NDArray[np.float64]]:
    """The ``co2``, ``ch4`` and ``n2o`` series of ``temperature()``, with no set check.

    For callers that hold arrays made with ``params`` but no finished ``Burden``
    of that set, for example a step inside ``burden()`` (R5 on #37). Only
    ``co2_pools``, ``ch4`` and ``n2o`` of ``b`` are read.
    """
    n_pools = len(params.co2_a)
    if b.co2_pools.shape[0] != n_pools:
        raise ValueError(f"co2_pools must have {n_pools} pools, got {b.co2_pools.shape[0]}")
    masses = {"co2": b.co2_pools, "ch4": b.ch4[np.newaxis], "n2o": b.n2o[np.newaxis]}
    out = {}
    for gas in GASES:
        f = specific_forcing(gas, params) * masses[gas]  # (P, N) forcing per component
        lifetimes = [tau for _, tau in _components(gas, params)]
        n = f.shape[1]
        t = np.zeros(n)
        for q, d in zip(params.climate_q, params.climate_d, strict=True):
            h = np.array([_box_response(tau, d, q, 1.0) for tau in lifetimes])
            step = h @ f  # rise of box i over year j -> j+1 from the forcing at year j
            kernel = np.exp(-np.arange(n, dtype=float) / d)
            t[1:] += np.convolve(step, kernel)[: n - 1]
        out[gas] = t
    return out


def agtp(gas: str, horizon: ArrayLike, params: ClimateParameters) -> NDArray[np.float64] | float:
    """Absolute global temperature change potential of a 1 kg pulse [K kg-1], closed form.

    ``A * sum_p a_p sum_i h(tau_p, d_i, q_i, H)``, where ``A`` is
    ``specific_forcing(gas, params)`` and h is the box response of
    ``_box_response``. For CO2 the components are the permanent pool a0 and the
    three decaying pools a1..a3 with ``co2_tau`` (the third pool uses a3, not a1:
    the AGTP p1 -> p3 fix, issue #29). For CH4 and N2O there is one component
    with the gas's lifetime; ``"ch4"`` is not oxidised. If
    ``params.carbon_cycle_feedback`` is True, CH4 and N2O (and so
    ``"ch4_fossil"``) include the carbon-cycle feedback in exact closed form, as
    in ``agwp()`` (#33).

    ``"ch4_fossil"`` (decision S1/S2-A on #30) adds the oxidised CO2,
    ``Y * 44/16 * integral_0^H (1/tau) exp(-t/tau) AGTP_CO2(H - t) dt``, in closed
    form, as in ``agwp()``.

    Args:
        gas: ``"co2"``, ``"ch4"``, ``"ch4_fossil"`` or ``"n2o"``.
        horizon: Time horizon(s) H [yr], >= 0. Any shape.
        params: The climate parameter set.

    Returns:
        An array of ``horizon``'s shape, or a float for a scalar ``horizon``.
    """
    gas = _check_gas(gas, EMISSION_KEYS)
    h = _check_horizon_array(horizon)
    if gas == "ch4_fossil":
        tau = params.ch4_lifetime
        ox = np.zeros_like(h)
        for a_p, tau_p in _components("co2", params):
            for q, d in zip(params.climate_q, params.climate_d, strict=True):
                if tau_p is None:  # box response q (1 - exp(-t/d))
                    ox = ox + a_p * q * (
                        _after_ch4_decay(tau, None, h) - _after_ch4_decay(tau, d, h)
                    )
                else:  # q tau_p / (tau_p - d) (exp(-t/tau_p) - exp(-t/d))
                    _box_response(tau_p, d, q, 0.0)  # refuses tau_p == d (T7)
                    ox = ox + a_p * q * tau_p / (tau_p - d) * (
                        _after_ch4_decay(tau, tau_p, h) - _after_ch4_decay(tau, d, h)
                    )
        co2 = specific_forcing("co2", params) * ox
        out = agtp("ch4", h, params) + _oxidised_co2_per_kg_ch4(params) * co2
        return float(out) if out.ndim == 0 else out
    out = _agtp_direct(gas, h, params)
    if gas != "co2" and params.carbon_cycle_feedback:
        out = out + _ccf_agtp(gas, h, params)
    return float(out) if out.ndim == 0 else out


def _agtp_direct(
    gas: str, h: NDArray[np.float64], params: ClimateParameters
) -> NDArray[np.float64]:
    """AGTP of CO2, CH4 or N2O without the carbon-cycle feedback, as an array."""
    shape = np.zeros_like(h)
    for a_p, tau in _components(gas, params):
        for q, d in zip(params.climate_q, params.climate_d, strict=True):
            shape = shape + a_p * _box_response(tau, d, q, h)
    return specific_forcing(gas, params) * shape


@dataclass(frozen=True, eq=False)
class GTP:
    """Global temperature change potential in kg CO2-equivalent, one value per year.

    Attributes:
        dynamic: Temperature change at year t divided by ``agtp_co2`` [kg CO2e].
            Shape (N,). (The Cooper spreadsheet's ``temp_over_AGTP_CO2``.)
        sliding: Temperature change at the fixed year ``horizon`` from the
            emissions of years 0..t, divided by ``agtp_co2`` [kg CO2e]. An
            emission in year k gets horizon ``max(horizon - k, 0)``. For a
            whole-number horizon, ``sliding[t] == dynamic[horizon]`` for
            t >= horizon. CO2 formed from fossil CH4 counts as CO2 emitted in the
            year it forms (decision T2, #29). Shape (N,). (``GTP_sliding_CO2e``.)
        static: Cumulative net emissions of each key up to year t times its
            GTP_H, summed over the keys [kg CO2e]. Fossil CH4 includes its
            oxidised CO2, by the closed form of ``agtp("ch4_fossil", ...)``
            (decision S3 on #30, which replaces T3 on #29). Shape (N,).
            (``GTP_static_CO2e``.)
        horizon: Time horizon [yr].
        agtp_co2: ``agtp("co2", horizon, params)`` [K kg-1].
    """

    dynamic: NDArray[np.float64]
    sliding: NDArray[np.float64]
    static: NDArray[np.float64]
    horizon: float
    agtp_co2: float

    def to_dict(self) -> dict:
        """JSON-serialisable dict (decision record 0005)."""
        return {
            "dynamic": self.dynamic.tolist(),
            "sliding": self.sliding.tolist(),
            "static": self.static.tolist(),
            "horizon": self.horizon,
            "agtp_co2": self.agtp_co2,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> GTP:
        """Inverse of ``to_dict()``."""
        return cls(
            **_arrays(data, ("dynamic", "sliding", "static")),
            horizon=float(data["horizon"]),
            agtp_co2=float(data["agtp_co2"]),
        )


def gtp(
    emissions: Mapping[str, ArrayLike],
    params: ClimateParameters,
    *,
    horizon: float = 100,
) -> GTP:
    """Dynamic, sliding and static GTP from annual emissions.

    Args:
        emissions: As for ``burden()``: kg per year of each key, index 0 = year 0.
        params: The climate parameter set.
        horizon: Time horizon H [yr] for the CO2 normalisation, the sliding GTP
            and the static GTP; >= ``MIN_HORIZON`` (1e-6 yr).

    Returns:
        A ``GTP``. All three series are normalised by AGTP_H(CO2) from the same
        ``params``.
    """
    horizon = _check_horizon(horizon)
    e = _validate(emissions)
    b = burden(e, params)
    ref = agtp("co2", horizon, params)

    n = b.co2.shape[0]
    remaining = np.clip(horizon - np.arange(n, dtype=float), 0.0, None)
    # CCF CO2 counts as CO2 emitted in the year it forms (C4 on #33).
    co2 = e["co2"] + b.ch4_to_co2 + b.ccf_co2
    contribution = co2 * _agtp_direct("co2", remaining, params)
    ch4 = e["ch4"] + e["ch4_fossil"]
    contribution = contribution + ch4 * _agtp_direct("ch4", remaining, params)
    contribution = contribution + e["n2o"] * _agtp_direct("n2o", remaining, params)
    factors = _static_factors(e, params, horizon, agtp)
    static = sum(np.cumsum(e[key]) * factors.get(key, 0.0) for key in EMISSION_KEYS)

    return GTP(
        dynamic=temperature(b, params).total / ref,
        sliding=np.cumsum(contribution) / ref,
        static=static,
        horizon=horizon,
        agtp_co2=ref,
    )
