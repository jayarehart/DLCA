"""The public API of record 0022 (P1): its names and their import paths (#96).

Faults these catch that no other test does: a public name added to, removed
from or renamed in a module's ``__all__`` without this list (and so record
0022) changing; a name in ``__all__`` that does not import; a name imported
into ``dlca`` or ``dlca.inventory`` but left out of ``__all__``; and a name
exported from two public modules that is not the same object in both.

If a test here fails because you changed the public API on purpose, update
record 0022 (or write a record that supersedes it) and the lists below in the
same PR, and state the release kind the change needs (record 0022, P2).
"""

import importlib
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
