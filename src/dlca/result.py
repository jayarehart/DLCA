"""The public entry point ``assess()`` and its ``Result`` (issue #31, decision record 0008).

``assess()`` runs the pure functions of ``dlca.climate`` once, with one parameter
set, and returns a frozen ``Result``. The result holds every series, a copy of
the inputs and the parameter set that made it, and it round-trips through JSON
exactly (decision record 0005). It never changes its inputs.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import metadata
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from dlca.climate import (
    EMISSION_KEYS,
    GTP,
    GWI,
    Burden,
    Forcing,
    StaticGWP,
    Temperature,
    _check_horizon,
    _validate,
    burden,
    forcing,
    gtp,
    gwi,
    static_gwp,
    temperature,
)
from dlca.parameters import ClimateParameters, get_parameters

__all__ = ["RESULT_SCHEMA", "RESULT_SCHEMA_VERSION", "Result", "assess"]

RESULT_SCHEMA = "dlca.result"
# Bump whenever the form of Result.to_dict() changes.
# 2: burden, forcing and temperature carry parameter_fingerprint (#37, G6).
# 3: burden carries ccf_co2 and the parameter values carry the CCF fields (#33, C7).
# 4: gwi, gtp and static_gwp carry parameter_fingerprint (#46, F3).
RESULT_SCHEMA_VERSION = 4


def _package_version() -> str:
    try:
        return metadata.version("dlca")
    except metadata.PackageNotFoundError:  # running from a source tree that is not installed
        return "unknown"


def _read_only(array: NDArray[np.float64]) -> NDArray[np.float64]:
    array.setflags(write=False)
    return array


def _freeze(component: Any) -> Any:
    """Make a component's array fields read-only and its mappings immutable (in place)."""
    for f in dataclasses.fields(component):
        value = getattr(component, f.name)
        if isinstance(value, np.ndarray):
            _read_only(value)
        elif isinstance(value, Mapping) and not isinstance(value, MappingProxyType):
            object.__setattr__(component, f.name, MappingProxyType(dict(value)))
    return component


_COMPONENTS = ("burden", "forcing", "temperature", "gwi", "gtp", "static_gwp")


@dataclass(frozen=True, eq=False)
class Result:
    """Everything ``assess()`` computed, with the inputs and the parameter set used.

    All arrays have one value per year, index 0 = year 0, and are read-only.

    Attributes:
        emissions: Copy of the checked inputs, all of ``EMISSION_KEYS``, a missing
            key as zeros [kg of that gas per year].
        burden: Mass of each gas in the atmosphere [kg].
        forcing: Radiative forcing [W m-2] and integrated forcing [W yr m-2].
        temperature: Temperature change from each gas [K].
        gwi: Dynamic, sliding and static GWI [kg CO2e], time horizon ``horizon``.
        gtp: Dynamic, sliding and static GTP [kg CO2e], time horizon ``horizon``.
        static_gwp: Static GWP by emissions key [kg CO2e]; ``total`` equals
            ``gwi.static``.
        horizon: Time horizon H [yr].
        parameters: The full parameter set used (decision A2 on #31).
        parameter_set: ``parameters.name``. A variant keeps its set's name, so
            this alone does not identify the values; the fingerprint does.
        parameter_fingerprint: ``parameters.fingerprint()``.
        carbon_cycle_feedback: ``parameters.carbon_cycle_feedback``: True for
            the shipped AR6 set, False for AR5 (decision C6 on #33, record 0010).
        dlca_version: Version of the package that made the result.
    """

    emissions: Mapping[str, NDArray[np.float64]]
    burden: Burden
    forcing: Forcing
    temperature: Temperature
    gwi: GWI
    gtp: GTP
    static_gwp: StaticGWP
    horizon: float
    parameters: ClimateParameters
    parameter_set: str
    parameter_fingerprint: str
    carbon_cycle_feedback: bool
    dlca_version: str

    def __post_init__(self) -> None:
        if self.parameter_fingerprint != self.parameters.fingerprint():
            raise ValueError(
                "parameter_fingerprint does not match the stored parameter set "
                f"({self.parameter_fingerprint[:8]} vs {self.parameters.fingerprint()[:8]})"
            )
        if self.parameter_set != self.parameters.name:
            raise ValueError(
                f"parameter_set {self.parameter_set!r} does not match the stored "
                f"parameter set's name {self.parameters.name!r}"
            )
        if self.carbon_cycle_feedback != self.parameters.carbon_cycle_feedback:
            raise ValueError("carbon_cycle_feedback does not match the stored parameter set")
        for name in _COMPONENTS:
            own = getattr(self, name).parameter_fingerprint
            if own != self.parameter_fingerprint:
                raise ValueError(
                    f"{name} was made with a different parameter set ({own[:8]}) than "
                    f"the result's ({self.parameter_fingerprint[:8]}) (#37, #46)"
                )
        self._check_consistent()
        # Read-only arrays and immutable mappings however the result was built.
        emissions = {
            key: _read_only(np.array(self.emissions[key], dtype=float)) for key in EMISSION_KEYS
        }
        object.__setattr__(self, "emissions", MappingProxyType(emissions))
        for name in _COMPONENTS:
            _freeze(getattr(self, name))

    def _check_consistent(self) -> None:
        """Every series has one value per year, and every metric uses ``horizon``."""
        if set(self.emissions) != set(EMISSION_KEYS):
            raise ValueError(f"emissions must have exactly the keys {list(EMISSION_KEYS)}")
        n = np.shape(self.emissions["co2"])
        if len(n) != 1:
            raise ValueError("emissions must be 1-D")
        n = n[0]
        pools = len(self.parameters.co2_a)
        for name in _COMPONENTS:
            component = getattr(self, name)
            for f in dataclasses.fields(component):
                value = getattr(component, f.name)
                if not isinstance(value, np.ndarray):
                    continue
                want = (pools, n) if f.name == "co2_pools" else (n,)
                if value.shape != want:
                    raise ValueError(f"{name}.{f.name} has shape {value.shape}, expected {want}")
        for key in EMISSION_KEYS:
            if np.shape(self.emissions[key]) != (n,):
                raise ValueError(f"emissions[{key!r}] must have {n} values")
        for name in ("gwi", "gtp", "static_gwp"):
            if getattr(self, name).horizon != self.horizon:
                raise ValueError(
                    f"{name}.horizon {getattr(self, name).horizon} differs from horizon "
                    f"{self.horizon}"
                )

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable dict of plain lists, floats, strings and bools (record 0005).

        ``Result.from_dict(json.loads(json.dumps(r.to_dict())))`` rebuilds ``r``
        with every array bit-for-bit equal.
        """
        return {
            "schema": RESULT_SCHEMA,
            "schema_version": RESULT_SCHEMA_VERSION,
            "dlca_version": self.dlca_version,
            "parameters": {
                "name": self.parameter_set,
                "fingerprint": self.parameter_fingerprint,
                "carbon_cycle_feedback": self.carbon_cycle_feedback,
                "values": self.parameters.to_dict(),
            },
            "horizon": self.horizon,
            "emissions": {key: self.emissions[key].tolist() for key in EMISSION_KEYS},
            "burden": self.burden.to_dict(),
            "forcing": self.forcing.to_dict(),
            "temperature": self.temperature.to_dict(),
            "gwi": self.gwi.to_dict(),
            "gtp": self.gtp.to_dict(),
            "static_gwp": self.static_gwp.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Result:
        """Inverse of ``to_dict()``.

        Raises:
            ValueError: for another schema or schema version, if the stored
                name, fingerprint or CCF flag does not match the stored values,
                or if a component's ``parameter_fingerprint`` differs from the
                result's (#37, #46).
        """
        if data.get("schema") != RESULT_SCHEMA:
            raise ValueError(f"not a DLCA result: schema {data.get('schema')!r}")
        if data.get("schema_version") != RESULT_SCHEMA_VERSION:
            raise ValueError(f"unsupported result schema_version {data.get('schema_version')!r}")
        p = data["parameters"]
        params = ClimateParameters.from_dict(p["values"])
        emissions = {
            key: _read_only(np.asarray(data["emissions"][key], dtype=float))
            for key in EMISSION_KEYS
        }
        return cls(
            emissions=emissions,
            burden=_freeze(Burden.from_dict(data["burden"])),
            forcing=_freeze(Forcing.from_dict(data["forcing"])),
            temperature=_freeze(Temperature.from_dict(data["temperature"])),
            gwi=_freeze(GWI.from_dict(data["gwi"])),
            gtp=_freeze(GTP.from_dict(data["gtp"])),
            static_gwp=_freeze(StaticGWP.from_dict(data["static_gwp"])),
            horizon=float(data["horizon"]),
            parameters=params,
            parameter_set=p["name"],
            parameter_fingerprint=p["fingerprint"],
            carbon_cycle_feedback=p["carbon_cycle_feedback"],
            dlca_version=data["dlca_version"],
        )


def assess(
    emissions: Mapping[str, ArrayLike],
    *,
    parameters: str | ClimateParameters = "AR6",
    horizon: float = 100,
) -> Result:
    """Dynamic LCA climate metrics of annual emissions, with one parameter set.

    Args:
        emissions: ``{"co2": ..., "ch4": ..., "ch4_fossil": ..., "n2o": ...}``, kg
            of that gas per year, index 0 = year 0, all the same length (lists or
            arrays). A missing key counts as zeros. ``ch4`` is non-fossil CH4;
            fossil CH4 goes under ``ch4_fossil`` and is also oxidised to CO2
            (decision S4 on #30). Negative values (uptake) are allowed.
        parameters: A parameter set name for ``get_parameters()`` (``"AR5"`` or
            ``"AR6"``, case-insensitive) or a ``ClimateParameters``, for example a
            variant made with ``dataclasses.replace()``.
        horizon: Time horizon H [yr] for the CO2 normalisation and the sliding
            and static metrics; >= ``MIN_HORIZON`` (1e-6 yr).

    Returns:
        A ``Result``. Every component comes from the same parameter set and H.
        The inputs are copied and never changed.

    Raises:
        ValueError: for unknown emissions keys, empty, non-1-D, non-finite or
            unequal-length emissions, a bad horizon, or an unknown set name.
        TypeError: if ``parameters`` is neither a name nor a ``ClimateParameters``.
    """
    if isinstance(parameters, str):
        params = get_parameters(parameters)
    elif isinstance(parameters, ClimateParameters):
        params = parameters
    else:
        raise TypeError(
            f"parameters must be a set name or a ClimateParameters, got {type(parameters).__name__}"
        )
    horizon = _check_horizon(horizon)
    e = {key: _read_only(np.array(arr, dtype=float)) for key, arr in _validate(emissions).items()}

    b = burden(e, params)
    return Result(
        emissions=e,
        burden=_freeze(b),
        forcing=_freeze(forcing(b, params)),
        temperature=_freeze(temperature(b, params)),
        gwi=_freeze(gwi(e, params, horizon=horizon)),
        gtp=_freeze(gtp(e, params, horizon=horizon)),
        static_gwp=_freeze(static_gwp(e, params, horizon=horizon)),
        horizon=horizon,
        parameters=params,
        parameter_set=params.name,
        parameter_fingerprint=params.fingerprint(),
        carbon_cycle_feedback=params.carbon_cycle_feedback,
        dlca_version=_package_version(),
    )
