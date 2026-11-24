"""The public API of record 0022 (P1, P2): names, signatures, constants, fields (#96).

Faults these catch that no other test does: a public name added to, removed
from or renamed in a module's ``__all__`` without this list (and so record
0022) changing; a name in ``__all__`` that does not import; a name imported
into ``dlca`` or ``dlca.inventory`` but left out of ``__all__``; a name
exported from two public modules that is not the same object in both; a
changed argument, argument kind or default of a public function (for example
``horizon=100`` or ``parameters="AR6"``); a changed public constant (for
example ``DEFAULT_PARAMETER_SET``, or a schema version bumped without the
record's rules in mind); and a public dataclass field or input JSON key added,
removed or renamed (for example on ``Metrics`` or ``Result``).

If a test here fails because you changed the public API on purpose, update
record 0022 (or write a record that supersedes it) and the lists below in the
same PR, and state the release kind the change needs (record 0022, P2).
"""

import dataclasses
import importlib
import inspect
import types

import pytest

PUBLIC = {
    "dlca": {
        "assess",
        "Result",
        "assess_building",
        "BuildingResult",
        "ClimateParameters",
        "get_parameters",
        "available_parameter_sets",
        "DEFAULT_PARAMETER_SET",
    },
    "dlca.inventory": {
        # input schemas
        "BuildingTotals",
        "BuildingInventory",
        "Assembly",
        "Material",
        "GasAmounts",
        "Event",
        "Biogenic",
        "Carbonation",
        "Surface",
        "Stockpile",
        "EnergyUse",
        "Trajectory",
        "ConstantTrajectory",
        "LinearTrajectory",
        "SeriesTrajectory",
        # functions, results and warnings
        "assess_building",
        "BuildingResult",
        "Metrics",
        "biogenic_balance",
        "BiogenicBalance",
        "timeline",
        "Timeline",
        "to_study_years",
        "BiogenicCarbonWarning",
        "CarbonationWarning",
        # constants
        "SCHEMA_VERSION",
        "TOTALS_TAG",
        "INVENTORY_TAG",
        "BUILDING_RESULT_SCHEMA",
        "BUILDING_RESULT_SCHEMA_VERSION",
        "TIMELINE_SCHEMA",
        "TIMELINE_SCHEMA_VERSION",
        "UPTAKE_MODULE",
        "CARBONATION_UPTAKE_MODULE",
        "CARBONATION_EOL_MODULE",
    },
    "dlca.climate": {
        "burden",
        "forcing",
        "temperature",
        "gwi",
        "gtp",
        "static_gwp",
        "agwp",
        "agtp",
        "specific_forcing",
        "Burden",
        "Forcing",
        "Temperature",
        "GWI",
        "GTP",
        "StaticGWP",
        "GASES",
        "EMISSION_KEYS",
        "MIN_HORIZON",
        "CO2_PER_CH4_MASS_RATIO",
    },
    "dlca.parameters": {
        "ClimateParameters",
        "get_parameters",
        "available_parameter_sets",
        "DEFAULT_PARAMETER_SET",
        "Source",
    },
    "dlca.result": {
        "assess",
        "Result",
        "RESULT_SCHEMA",
        "RESULT_SCHEMA_VERSION",
    },
}

# Packages whose namespace should hold nothing public beyond __all__ and their
# own submodules (the other modules also hold their imports, such as numpy).
PACKAGES = ("dlca", "dlca.inventory")


@pytest.mark.parametrize("module_name", sorted(PUBLIC))
def test_all_is_the_record_list(module_name):
    module = importlib.import_module(module_name)
    exported = list(module.__all__)
    assert len(exported) == len(set(exported)), f"{module_name}.__all__ repeats a name"
    expected = PUBLIC[module_name]
    assert set(exported) == expected, (
        f"{module_name}.__all__ differs from record 0022: "
        f"added {sorted(set(exported) - expected)}, removed {sorted(expected - set(exported))}"
    )


@pytest.mark.parametrize("module_name", sorted(PUBLIC))
def test_every_public_name_imports(module_name):
    module = importlib.import_module(module_name)
    missing = [name for name in PUBLIC[module_name] if not hasattr(module, name)]
    assert not missing, f"{module_name} lacks {missing}"


@pytest.mark.parametrize("module_name", PACKAGES)
def test_package_namespace_has_nothing_public_outside_all(module_name):
    module = importlib.import_module(module_name)
    stray = {
        name
        for name, value in vars(module).items()
        if not name.startswith("_")
        and name not in module.__all__
        and not isinstance(value, types.ModuleType)
    }
    assert not stray, f"{module_name} has public names not in __all__: {sorted(stray)}"


def test_shared_names_are_one_object():
    seen = {}
    for module_name, names in PUBLIC.items():
        module = importlib.import_module(module_name)
        for name in names:
            seen.setdefault(name, []).append((module_name, getattr(module, name)))
    for name, places in seen.items():
        first_module, first = places[0]
        for module_name, value in places[1:]:
            assert value is first, f"{module_name}.{name} is not {first_module}.{name}"


# Signatures of the public functions: (argument, kind, repr of default or None).
# A changed default or argument is a major change (record 0022, P2). Checked
# against the records: assess (0008), assess_building (0015), timeline (0014),
# to_study_years (0019), get_parameters (0007).
P_OR_K = "POSITIONAL_OR_KEYWORD"
KW = "KEYWORD_ONLY"
SIGNATURES = {
    "agtp": (("gas", P_OR_K, None), ("horizon", P_OR_K, None), ("params", P_OR_K, None)),
    "agwp": (("gas", P_OR_K, None), ("horizon", P_OR_K, None), ("params", P_OR_K, None)),
    "assess": (("emissions", P_OR_K, None), ("parameters", KW, "'AR6'"), ("horizon", KW, "100")),
    "assess_building": (
        ("building", P_OR_K, None),
        ("parameters", KW, "'AR6'"),
        ("horizon", KW, "100"),
        ("years", KW, "None"),
    ),
    "available_parameter_sets": (),
    "biogenic_balance": (("building", P_OR_K, None),),
    "burden": (("emissions", P_OR_K, None), ("params", P_OR_K, None)),
    "forcing": (("b", P_OR_K, None), ("params", P_OR_K, None)),
    "get_parameters": (("name", P_OR_K, "'AR6'"),),
    "gtp": (("emissions", P_OR_K, None), ("params", P_OR_K, None), ("horizon", KW, "100")),
    "gwi": (("emissions", P_OR_K, None), ("params", P_OR_K, None), ("horizon", KW, "100")),
    "specific_forcing": (("gas", P_OR_K, None), ("params", P_OR_K, None)),
    "static_gwp": (("emissions", P_OR_K, None), ("params", P_OR_K, None), ("horizon", KW, "100")),
    "temperature": (("b", P_OR_K, None), ("params", P_OR_K, None)),
    "timeline": (("building", P_OR_K, None), ("horizon", KW, "100"), ("years", KW, "None")),
    "to_study_years": (
        ("values", P_OR_K, None),
        ("year_zero", P_OR_K, None),
        ("n_years", P_OR_K, None),
    ),
}

# Values of the public constants. DEFAULT_PARAMETER_SET (0007, D6), MIN_HORIZON
# (0012), CO2_PER_CH4_MASS_RATIO (44/16, decision D1 on #27) and EMISSION_KEYS
# (0008) come from the records. A schema version moves with each new JSON
# version (a minor change, P3); update it here in the same PR.
CONSTANTS = {
    "DEFAULT_PARAMETER_SET": "AR6",
    "MIN_HORIZON": 1e-6,
    "CO2_PER_CH4_MASS_RATIO": 44.0 / 16.0,
    "EMISSION_KEYS": ("co2", "ch4", "ch4_fossil", "n2o"),
    "GASES": ("co2", "ch4", "n2o"),
    "RESULT_SCHEMA": "dlca.result",
    "RESULT_SCHEMA_VERSION": 4,
    "BUILDING_RESULT_SCHEMA": "dlca.building_result",
    "BUILDING_RESULT_SCHEMA_VERSION": 6,
    "TIMELINE_SCHEMA": "dlca.timeline",
    "TIMELINE_SCHEMA_VERSION": 3,
    "TOTALS_TAG": "dlca.building_totals",
    "INVENTORY_TAG": "dlca.building_inventory",
    "SCHEMA_VERSION": 6,
    "UPTAKE_MODULE": "biogenic-uptake",
    "CARBONATION_UPTAKE_MODULE": "carbonation-uptake",
    "CARBONATION_EOL_MODULE": "carbonation-eol",
}

# Fields of the public classes: dataclass fields, or the JSON keys (aliases) of
# the pydantic input models. Order is not promised (P1), so these are sets.
# Removing or renaming one is major; adding one is minor (P2, N3). Checked
# against the records: Result (0008), BuildingResult and Metrics (0015, R3/R4),
# GasAmounts (0013).
FIELDS = {
    "Assembly": {"materials", "name"},
    "Biogenic": {"co2", "regrowth", "released_co2", "rotation"},
    "BiogenicBalance": {"declared", "regrowing", "released_ch4_as_co2", "released_co2", "uptake"},
    "BuildingInventory": {
        "assemblies",
        "b4_c_trajectory",
        "energy",
        "name",
        "per_year",
        "schema",
        "schema_version",
        "study_period",
    },
    "BuildingResult": {
        "building",
        "by_assembly",
        "by_gas",
        "by_material",
        "by_module",
        "horizon",
        "sliding_cutoff_year",
        "sliding_incomplete",
        "total",
        "years",
    },
    "BuildingTotals": {
        "b4",
        "b4_c_trajectory",
        "b5",
        "biogenic",
        "energy",
        "modules",
        "name",
        "per_year",
        "schema",
        "schema_version",
        "study_period",
    },
    "Burden": {"ccf_co2", "ch4", "ch4_to_co2", "co2", "co2_pools", "n2o", "parameter_fingerprint"},
    "Carbonation": {
        "binder_factor",
        "cao_share",
        "cement",
        "degree_of_carbonation",
        "end_of_life",
        "strength_class",
        "surfaces",
        "volume",
    },
    "ClimateParameters": {
        "atm_mass",
        "carbon_cycle_feedback",
        "ccf_gamma",
        "ccf_timescales",
        "ccf_weights",
        "ch4_fossil_co2_yield",
        "ch4_h2o",
        "ch4_indirect_form",
        "ch4_lifetime",
        "ch4_o3",
        "ch4_re",
        "climate_d",
        "climate_q",
        "co2_a",
        "co2_re",
        "co2_re_scale",
        "co2_tau",
        "description",
        "molar_mass_air",
        "molar_mass_c",
        "molar_mass_ch4",
        "molar_mass_co2",
        "molar_mass_n2o",
        "n2o_ch4_change",
        "n2o_indirect_form",
        "n2o_lifetime",
        "n2o_o3",
        "n2o_re",
        "name",
        "sources",
    },
    "ConstantTrajectory": {"kind"},
    "EnergyUse": {
        "amount",
        "cambium_gea",
        "cambium_scenario",
        "egrid_state",
        "egrid_subregion",
        "factor",
        "fuel",
        "trajectory",
        "unit",
        "year_zero",
    },
    "Event": {"amounts", "biogenic", "carbonation", "year"},
    "Forcing": {
        "ch4",
        "ch4_integrated",
        "co2",
        "co2_integrated",
        "n2o",
        "n2o_integrated",
        "parameter_fingerprint",
    },
    "GTP": {"agtp_co2", "dynamic", "horizon", "parameter_fingerprint", "sliding", "static"},
    "GWI": {"agwp_co2", "dynamic", "horizon", "parameter_fingerprint", "sliding", "static"},
    "GasAmounts": {"ch4", "ch4_fossil", "co2", "n2o"},
    "LinearTrajectory": {"kind", "target", "target_year"},
    "Material": {
        "b4",
        "b5",
        "biogenic",
        "carbonation",
        "modules",
        "name",
        "per_year",
        "quantity",
        "unit",
    },
    "Metrics": {
        "gtp_dynamic",
        "gtp_sliding",
        "gtp_static",
        "gwi_dynamic",
        "gwi_sliding",
        "gwi_static",
    },
    "Result": {
        "burden",
        "carbon_cycle_feedback",
        "dlca_version",
        "emissions",
        "forcing",
        "gtp",
        "gwi",
        "horizon",
        "parameter_fingerprint",
        "parameter_set",
        "parameters",
        "static_gwp",
        "temperature",
    },
    "SeriesTrajectory": {"kind", "values"},
    "Source": {"citation", "doi", "key"},
    "StaticGWP": {"ch4", "ch4_fossil", "co2", "gwp", "horizon", "n2o", "parameter_fingerprint"},
    "Stockpile": {"radius", "years"},
    "Surface": {"area", "cover", "exposure"},
    "Temperature": {"ch4", "co2", "n2o", "parameter_fingerprint"},
    "Timeline": {"horizon", "parts", "study_period", "years"},
}


def _public_object(name):
    for module_name, names in PUBLIC.items():
        if name in names:
            return getattr(importlib.import_module(module_name), name)
    raise AssertionError(f"{name} is not in PUBLIC")


def test_every_function_and_class_is_pinned():
    objects = {name: _public_object(name) for names in PUBLIC.values() for name in names}
    functions = {n for n, v in objects.items() if inspect.isfunction(v)}
    classes = {
        n
        for n, v in objects.items()
        if inspect.isclass(v) and (dataclasses.is_dataclass(v) or hasattr(v, "model_fields"))
    }
    assert functions == set(SIGNATURES)
    assert classes == set(FIELDS)


@pytest.mark.parametrize("name", sorted(SIGNATURES))
def test_signature(name):
    parameters = inspect.signature(_public_object(name)).parameters.values()
    found = tuple(
        (p.name, p.kind.name, None if p.default is p.empty else repr(p.default)) for p in parameters
    )
    assert found == SIGNATURES[name]


@pytest.mark.parametrize("name", sorted(CONSTANTS))
def test_constant(name):
    assert _public_object(name) == CONSTANTS[name]


@pytest.mark.parametrize("name", sorted(FIELDS))
def test_fields(name):
    cls = _public_object(name)
    if dataclasses.is_dataclass(cls):
        found = {f.name for f in dataclasses.fields(cls)}
    else:
        found = {field.alias or key for key, field in cls.model_fields.items()}
    assert found == FIELDS[name]
