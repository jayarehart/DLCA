"""Climate parameter sets (IPCC AR5 and AR6) loaded from cited JSON files.

Each set lives in ``dlca/data/climate_parameters/<name>.json``. In the file every
value carries its unit, a source key, and where in that source it comes from;
every source carries a DOI. See decision record 0007 for the layout.

``ClimateParameters`` holds one set as plain, immutable values. Use
``get_parameters()`` to load one and ``dataclasses.replace()`` to make a variant
(for example a sensitivity run). A variant keeps its ``name`` but has a
different ``fingerprint()``, so results stay traceable.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from typing import Any

__all__ = [
    "DEFAULT_PARAMETER_SET",
    "ClimateParameters",
    "Source",
    "available_parameter_sets",
    "get_parameters",
]

DEFAULT_PARAMETER_SET = "AR6"

_SCHEMA_VERSION = 1
_INDIRECT_FORMS = ("multiplicative", "additive")
_GASES = ("co2", "ch4", "n2o")
_TUPLE_LENGTHS = {"co2_a": 4, "co2_tau": 3, "climate_q": 2, "climate_d": 2}


@dataclass(frozen=True)
class Source:
    """A cited source: a short key used in the JSON file, a citation and a DOI."""

    key: str
    citation: str
    doi: str


@dataclass(frozen=True)
class ClimateParameters:
    """One climate parameter set. Units are those of the JSON files.

    Attributes:
        name: Set name, for example ``"AR6"``.
        description: One-line description of the set.
        carbon_cycle_feedback: Whether non-CO2 metrics include a carbon-cycle
            feedback. False for both shipped sets (issue #33).
        co2_a: CO2 impulse-response fractions a0..a3 [1]; a0 is permanent.
        co2_tau: Time constants of the decaying pools a1..a3 [yr].
        co2_re: CO2 radiative efficiency [W m-2 ppb-1].
        co2_re_scale: Multiplier on ``co2_re`` [1] (AR5: Cooper factor; AR6: 1).
        ch4_lifetime, n2o_lifetime: Perturbation lifetimes [yr].
        ch4_re, n2o_re: Direct radiative efficiencies [W m-2 ppb-1].
        ch4_indirect_form, n2o_indirect_form: ``"multiplicative"`` (AR5) or
            ``"additive"`` (AR6); see ``effective_radiative_efficiency()``.
        ch4_o3, ch4_h2o: CH4 indirect terms. Fractions [1] if multiplicative,
            [W m-2 ppb-1] if additive.
        n2o_o3: N2O ozone term [W m-2 ppb-1] (0 in AR5).
        n2o_ch4_change: Change in CH4 per unit N2O [ppb CH4 per ppb N2O]; negative.
        climate_q: Two-box climate sensitivities [K (W m-2)-1].
        climate_d: Two-box response times [yr].
        molar_mass_co2, molar_mass_ch4, molar_mass_n2o, molar_mass_air: [g mol-1].
        atm_mass: Mass of the atmosphere [kg].
        ch4_fossil_co2_yield: CO2 formed per CH4 removed [mol mol-1], or None if
            the set has no confirmed value. Read it with ``fossil_ch4_co2_yield()``.
        sources: The sources cited by the set's JSON file.
    """

    name: str
    description: str
    carbon_cycle_feedback: bool
    co2_a: tuple[float, float, float, float]
    co2_tau: tuple[float, float, float]
    co2_re: float
    co2_re_scale: float
    ch4_lifetime: float
    ch4_re: float
    ch4_indirect_form: str
    ch4_o3: float
    ch4_h2o: float
    n2o_lifetime: float
    n2o_re: float
    n2o_indirect_form: str
    n2o_o3: float
    n2o_ch4_change: float
    climate_q: tuple[float, float]
    climate_d: tuple[float, float]
    molar_mass_co2: float
    molar_mass_ch4: float
    molar_mass_n2o: float
    molar_mass_air: float
    atm_mass: float
    ch4_fossil_co2_yield: float | None
    sources: tuple[Source, ...] = field(default=(), compare=True)

    def __post_init__(self) -> None:
        # Coerce sequences to tuples so the object stays hashable after
        # dataclasses.replace(..., co2_tau=[...]) or from_dict().
        for name, length in _TUPLE_LENGTHS.items():
            value = tuple(float(v) for v in getattr(self, name))
            if len(value) != length:
                raise ValueError(f"{name} needs {length} values, got {len(value)}")
            object.__setattr__(self, name, value)
        object.__setattr__(
            self,
            "sources",
            tuple(s if isinstance(s, Source) else Source(**s) for s in self.sources),
        )
        for form_name in ("ch4_indirect_form", "n2o_indirect_form"):
            if getattr(self, form_name) not in _INDIRECT_FORMS:
                raise ValueError(f"{form_name} must be one of {_INDIRECT_FORMS}")
        if not math.isclose(sum(self.co2_a), 1.0, rel_tol=0, abs_tol=1e-9):
            raise ValueError(f"co2_a must sum to 1, got {sum(self.co2_a)}")
        positive = ("ch4_lifetime", "n2o_lifetime", "atm_mass", "molar_mass_air")
        for name in positive:
            if not getattr(self, name) > 0:
                raise ValueError(f"{name} must be positive")
        if any(t <= 0 for t in self.co2_tau + self.climate_d):
            raise ValueError("co2_tau and climate_d must be positive")

    def effective_radiative_efficiency(self, gas: str) -> float:
        """Radiative efficiency including indirect effects [W m-2 ppb-1].

        - CO2: ``co2_re * co2_re_scale``.
        - CH4, multiplicative (AR5): ``ch4_re * (1 + ch4_o3 + ch4_h2o)``.
        - CH4, additive (AR6): ``ch4_re + ch4_o3 + ch4_h2o``.
        - N2O, multiplicative (AR5): ``n2o_re * (1 + n2o_ch4_change * RE_CH4,eff / n2o_re)``,
          the form in AR5 8.SM.11.3.3 and in ``DLCAInputData.adj_factor_N2O``.
        - N2O, additive (AR6): ``n2o_re + n2o_o3 + n2o_ch4_change * RE_CH4,eff``.
        """
        gas = gas.lower()
        if gas == "co2":
            return self.co2_re * self.co2_re_scale
        # The multiplicative forms keep DLCAInputData's order of operations, so AR5
        # reproduces its adj_factor_CH4 and adj_factor_N2O bit for bit.
        ch4_factor = 1 + self.ch4_h2o + self.ch4_o3
        if gas == "ch4":
            if self.ch4_indirect_form == "multiplicative":
                return self.ch4_re * ch4_factor
            return self.ch4_re + self.ch4_o3 + self.ch4_h2o
        if gas == "n2o":
            if self.ch4_indirect_form == "multiplicative":
                ch4_term = self.n2o_ch4_change * self.ch4_re * ch4_factor
            else:
                ch4_term = self.n2o_ch4_change * self.effective_radiative_efficiency("ch4")
            if self.n2o_indirect_form == "multiplicative":
                factor = 1 + ch4_term / self.n2o_re + self.n2o_o3 / self.n2o_re
                return self.n2o_re * factor
            return self.n2o_re + self.n2o_o3 + ch4_term
        raise ValueError(f"unknown gas {gas!r}; expected one of {list(_GASES)}")

    def fossil_ch4_co2_yield(self) -> float:
        """CO2 formed per fossil CH4 removed [mol mol-1].

        Raises ``ValueError`` if the set has no value (``None``), so a guessed
        value is never used silently. Both shipped sets have one (decision D4, #26).
        """
        if self.ch4_fossil_co2_yield is None:
            raise ValueError(
                f"Parameter set {self.name!r} has no fossil CH4 to CO2 yield. "
                "Use a set that has one, or supply a value with "
                "dataclasses.replace(params, ch4_fossil_co2_yield=...)."
            )
        return self.ch4_fossil_co2_yield

    def to_dict(self) -> dict[str, Any]:
        """Plain, JSON-serialisable dict of every field (lists for tuples)."""
        out: dict[str, Any] = {}
        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            if f.name == "sources":
                value = [dataclasses.asdict(s) for s in value]
            elif isinstance(value, tuple):
                value = list(value)
            out[f.name] = value
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClimateParameters:
        """Inverse of ``to_dict()``. Unknown or missing keys raise ``ValueError``."""
        names = {f.name for f in dataclasses.fields(cls)}
        unknown = set(data) - names
        missing = names - set(data) - {"sources"}
        if unknown or missing:
            raise ValueError(f"bad keys: unknown {sorted(unknown)}, missing {sorted(missing)}")
        return cls(**data)

    def fingerprint(self) -> str:
        """SHA-256 of the canonical JSON of ``to_dict()``; changes if any value changes."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _files() -> dict[str, Any]:
    folder = resources.files("dlca.data") / "climate_parameters"
    return {
        p.name[: -len(".json")].upper(): p for p in folder.iterdir() if p.name.endswith(".json")
    }


def available_parameter_sets() -> list[str]:
    """Names of the shipped parameter sets, sorted, for example ``["AR5", "AR6"]``."""
    return sorted(_files())


def _value(leaf: dict[str, Any]) -> Any:
    return leaf["value"]


def _from_document(doc: dict[str, Any]) -> ClimateParameters:
    if doc.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version {doc.get('schema_version')!r}")
    co2, ch4, n2o = doc["co2"], doc["ch4"], doc["n2o"]
    climate, atmosphere = doc["climate_response"], doc["atmosphere"]
    return ClimateParameters(
        name=doc["name"],
        description=doc["description"],
        carbon_cycle_feedback=doc["carbon_cycle_feedback"],
        co2_a=_value(co2["irf_a"]),
        co2_tau=_value(co2["irf_tau"]),
        co2_re=_value(co2["radiative_efficiency"]),
        co2_re_scale=_value(co2["radiative_efficiency_scale"]),
        ch4_lifetime=_value(ch4["lifetime"]),
        ch4_re=_value(ch4["radiative_efficiency"]),
        ch4_indirect_form=ch4["indirect"]["form"],
        ch4_o3=_value(ch4["indirect"]["o3"]),
        ch4_h2o=_value(ch4["indirect"]["h2o"]),
        n2o_lifetime=_value(n2o["lifetime"]),
        n2o_re=_value(n2o["radiative_efficiency"]),
        n2o_indirect_form=n2o["indirect"]["form"],
        n2o_o3=_value(n2o["indirect"]["o3"]),
        n2o_ch4_change=_value(n2o["indirect"]["ch4_change"]),
        climate_q=_value(climate["q"]),
        climate_d=_value(climate["d"]),
        molar_mass_co2=_value(co2["molar_mass"]),
        molar_mass_ch4=_value(ch4["molar_mass"]),
        molar_mass_n2o=_value(n2o["molar_mass"]),
        molar_mass_air=_value(atmosphere["molar_mass_air"]),
        atm_mass=_value(atmosphere["mass"]),
        ch4_fossil_co2_yield=_value(ch4["fossil_co2_yield"]),
        sources=tuple(Source(key=k, **v) for k, v in doc["sources"].items()),
    )


def load_document(name: str) -> dict[str, Any]:
    """The raw JSON document of a shipped set, with units, sources and checks."""
    files = _files()
    key = name.upper()
    if key not in files:
        raise ValueError(
            f"unknown parameter set {name!r}; valid names are {available_parameter_sets()}"
        )
    return json.loads(files[key].read_text(encoding="utf-8"))


@cache
def _cached(key: str) -> ClimateParameters:
    return _from_document(load_document(key))


def get_parameters(name: str = DEFAULT_PARAMETER_SET) -> ClimateParameters:
    """Load a shipped parameter set by name (case-insensitive). Default: ``"AR6"``.

    Raises ``ValueError`` listing the valid names if ``name`` is unknown.
    """
    if not isinstance(name, str):
        raise ValueError(f"parameter set name must be a string, got {name!r}")
    load_document(name)  # validates the name with a clear message
    return _cached(name.upper())
