"""Inventory input schemas `BuildingTotals` and `BuildingInventory` (#57, record 0013).

Faults these catch that no other test does: a gas key that does not match the
keys `assess()` takes; fossil CH4 folded into non-fossil CH4; a module D amount
accepted under any name (including as C4); service life or replacement
interval accepted; B4/B5 accepted as plain amounts instead of dated events; an
event year outside 1..study_period; a module accepted at the wrong level; a
totals file read as an inventory or the reverse, or a building mixing both;
loose types (a year as "60" or 60.5, NaN or infinite amounts); duplicate or
missing names; a field lost in the JSON round trip; a committed JSON Schema
file out of step with its model.
"""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dlca.climate import EMISSION_KEYS
from dlca.inventory import (
    BuildingInventory,
    BuildingTotals,
    Event,
    GasAmounts,
    Material,
)
from dlca.inventory.schema import SCHEMA_FILES, json_schema

DATA = Path(__file__).resolve().parents[2] / "src" / "dlca" / "data"

ONE_OFF = ["A1-A3", "A4", "A5", "C1", "C2", "C3", "C4"]
GAS = {"co2": 10.0, "ch4": 0.02, "ch4_fossil": 0.3, "n2o": -0.004}


def gas(scale=1.0):
    return {k: v * scale for k, v in GAS.items()}


def totals_dict():
    """A BuildingTotals with every module filled (illustrative numbers)."""
    return {
        "schema": "dlca.building_totals",
        "schema_version": 1,
        "name": "Totals demo",
        "study_period": 60,
        "modules": {m: gas(i + 1) for i, m in enumerate(ONE_OFF)},
        "per_year": {m: gas(0.1) for m in ["B1", "B2", "B3", "B6", "B7"]},
        "b4": [{"year": 25, "amounts": gas(2)}, {"year": 25, "amounts": gas(1)}],
        "b5": [{"year": 30, "amounts": gas(3)}],
    }


def material_dict(name="CLT"):
    return {
        "name": name,
        "quantity": 12.0,
        "unit": "m3",
        "modules": {m: gas(i + 1) for i, m in enumerate(ONE_OFF)},
        "per_year": {m: gas(0.01) for m in ["B1", "B2", "B3"]},
        "b4": [{"year": 40, "amounts": gas(5)}],
        "b5": [{"year": 1, "amounts": gas(0.5)}, {"year": 60, "amounts": gas(0.5)}],
    }


def inventory_dict():
    """A BuildingInventory with every module filled (illustrative numbers)."""
    return {
        "schema": "dlca.building_inventory",
        "schema_version": 1,
        "name": "Inventory demo",
        "study_period": 60,
        "assemblies": [
            {"name": "Floor", "materials": [material_dict("CLT"), material_dict("Screed")]},
            {"name": "Roof", "materials": [material_dict("CLT")]},
        ],
        "per_year": {"B6": gas(100), "B7": gas(1)},
    }


def first_material(d):
    return d["assemblies"][0]["materials"][0]


# --- gas keys ------------------------------------------------------------------------


def test_gas_keys_are_the_assess_keys():
    assert set(GasAmounts.model_fields) == set(EMISSION_KEYS)


def test_fossil_ch4_kept_apart_from_non_fossil():
    g = GasAmounts.model_validate_json('{"ch4": 1.5, "ch4_fossil": 7.0}')
    assert (g.ch4, g.ch4_fossil) == (1.5, 7.0)
    assert json.loads(g.model_dump_json()) == {
        "co2": 0.0,
        "ch4": 1.5,
        "ch4_fossil": 7.0,
        "n2o": 0.0,
    }


def test_missing_gas_is_zero_and_negative_allowed():
    g = GasAmounts.model_validate({"co2": -250.0})
    assert g == GasAmounts(co2=-250.0, ch4=0.0, ch4_fossil=0.0, n2o=0.0)


@pytest.mark.parametrize("bad", ['{"co2": NaN}', '{"co2": Infinity}', '{"n2o": -Infinity}'])
def test_non_finite_amount_refused(bad):
    with pytest.raises(ValidationError, match="finite"):
        GasAmounts.model_validate_json(bad)


@pytest.mark.parametrize("bad", [{"co2": "1.0"}, {"co2": None}, {"co2": True}])
def test_non_number_amount_refused(bad):
    with pytest.raises(ValidationError):
        GasAmounts.model_validate(bad)


def test_unknown_gas_refused():
    with pytest.raises(ValidationError, match="Extra inputs"):
        GasAmounts.model_validate({"co2": 1.0, "co2_bio": -1.0})


# --- round trip ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "make"), [(BuildingTotals, totals_dict), (BuildingInventory, inventory_dict)]
)
def test_round_trip_every_module(model, make):
    b = model.model_validate(make())
    assert model.model_validate_json(b.model_dump_json()) == b
    assert json.loads(b.model_dump_json()) == make()


def test_python_construction_by_field_name():
    t = BuildingTotals(schema_="dlca.building_totals", name="x", study_period=1)
    assert json.loads(t.model_dump_json())["schema"] == "dlca.building_totals"


# --- schema tag and mixing (S1, S13) -------------------------------------------------


@pytest.mark.parametrize(
    ("model", "make"), [(BuildingTotals, totals_dict), (BuildingInventory, inventory_dict)]
)
def test_missing_schema_tag_refused(model, make):
    d = make()
    del d["schema"]
    with pytest.raises(ValidationError, match="schema"):
        model.model_validate(d)


def test_totals_file_refused_as_inventory():
    with pytest.raises(ValidationError):
        BuildingInventory.model_validate(totals_dict())


def test_inventory_file_refused_as_totals():
    with pytest.raises(ValidationError):
        BuildingTotals.model_validate(inventory_dict())


def test_wrong_tag_alone_refused():
    d = inventory_dict()
    d["schema"] = "dlca.building_totals"
    with pytest.raises(ValidationError, match="schema"):
        BuildingInventory.model_validate(d)


@pytest.mark.parametrize("version", [0, 2, "1"])
def test_unknown_schema_version_refused(version):
    d = totals_dict()
    d["schema_version"] = version
    with pytest.raises(ValidationError, match="schema_version"):
        BuildingTotals.model_validate(d)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("assemblies", inventory_dict()["assemblies"]),
        ("materials", [material_dict()]),
        ("quantity", 1.0),
        ("unit", "m3"),
    ],
)
def test_totals_with_inventory_fields_refused(field, value):
    d = totals_dict()
    d[field] = value
    with pytest.raises(ValidationError, match="Extra inputs"):
        BuildingTotals.model_validate(d)


@pytest.mark.parametrize("field", ["modules", "b4", "b5"])
def test_inventory_with_building_level_totals_refused(field):
    d = inventory_dict()
    d[field] = totals_dict()[field]
    with pytest.raises(ValidationError, match="Extra inputs"):
        BuildingInventory.model_validate(d)


# --- module D, service life (S8, S10) ------------------------------------------------


@pytest.mark.parametrize("key", ["D", "C4+D", "d"])
def test_module_d_key_refused_in_totals(key):
    d = totals_dict()
    d["modules"][key] = gas()
    with pytest.raises(ValidationError):
        BuildingTotals.model_validate(d)


def test_module_d_key_refused_on_material():
    d = inventory_dict()
    first_material(d)["modules"]["D"] = gas()
    with pytest.raises(ValidationError):
        BuildingInventory.model_validate(d)


@pytest.mark.parametrize("field", ["module_d", "D", "d"])
def test_module_d_field_refused(field):
    totals = totals_dict()
    totals[field] = gas()
    inventory = inventory_dict()
    first_material(inventory)[field] = gas()
    with pytest.raises(ValidationError, match="Extra inputs"):
        BuildingTotals.model_validate(totals)
    with pytest.raises(ValidationError, match="Extra inputs"):
        BuildingInventory.model_validate(inventory)


def test_module_d_not_read_as_c4():
    """A D amount must not be accepted under any module, C4 included."""
    d = totals_dict()
    d["modules"] = {"D": gas(-1)}
    with pytest.raises(ValidationError):
        BuildingTotals.model_validate(d)
    assert "D" not in BuildingTotals.model_fields["modules"].annotation.__args__[0].__args__


@pytest.mark.parametrize("field", ["service_life", "replacement_interval"])
def test_service_life_fields_refused(field):
    d = inventory_dict()
    first_material(d)[field] = 30
    with pytest.raises(ValidationError, match="Extra inputs"):
        BuildingInventory.model_validate(d)
    t = totals_dict()
    t[field] = 30
    with pytest.raises(ValidationError, match="Extra inputs"):
        BuildingTotals.model_validate(t)


# --- modules at the right level (S3) ------------------------------------------------


@pytest.mark.parametrize("key", ["B1", "B6", "B4", "B5", "B8", "A1", "A1-A5", "C"])
def test_one_off_modules_refuse_other_keys(key):
    d = totals_dict()
    d["modules"][key] = gas()
    with pytest.raises(ValidationError):
        BuildingTotals.model_validate(d)


@pytest.mark.parametrize("key", ["A4", "B4", "B5", "C1"])
def test_totals_per_year_refuses_non_per_year(key):
    d = totals_dict()
    d["per_year"][key] = gas()
    with pytest.raises(ValidationError):
        BuildingTotals.model_validate(d)


@pytest.mark.parametrize("key", ["B6", "B7", "B4", "A4"])
def test_material_per_year_only_b1_to_b3(key):
    d = inventory_dict()
    first_material(d)["per_year"][key] = gas()
    with pytest.raises(ValidationError):
        BuildingInventory.model_validate(d)


@pytest.mark.parametrize("key", ["B1", "B2", "B3", "A1-A3"])
def test_inventory_building_per_year_only_b6_b7(key):
    d = inventory_dict()
    d["per_year"][key] = gas()
    with pytest.raises(ValidationError):
        BuildingInventory.model_validate(d)


@pytest.mark.parametrize("key", ["B4", "B5"])
def test_b4_b5_as_plain_amount_refused(key):
    t = totals_dict()
    t["modules"][key] = gas()
    with pytest.raises(ValidationError):
        BuildingTotals.model_validate(t)
    m = inventory_dict()
    first_material(m)["modules"][key] = gas()
    with pytest.raises(ValidationError):
        BuildingInventory.model_validate(m)


@pytest.mark.parametrize("field", ["b4", "b5"])
def test_b4_b5_must_be_event_list(field):
    d = totals_dict()
    d[field] = gas()
    with pytest.raises(ValidationError):
        BuildingTotals.model_validate(d)


# --- events and years (S6, S11) ------------------------------------------------------


def test_events_in_same_year_both_kept():
    t = BuildingTotals.model_validate(totals_dict())
    assert [e.year for e in t.b4] == [25, 25]


@pytest.mark.parametrize("year", [1, 60])
def test_event_year_at_bounds_accepted(year):
    d = totals_dict()
    d["b5"] = [{"year": year, "amounts": gas()}]
    assert BuildingTotals.model_validate(d).b5[0].year == year


@pytest.mark.parametrize("field", ["b4", "b5"])
@pytest.mark.parametrize("year", [0, -1, 61, 1000])
def test_event_year_outside_study_period_refused_totals(field, year):
    d = totals_dict()
    d[field] = [{"year": year, "amounts": gas()}]
    with pytest.raises(ValidationError):
        BuildingTotals.model_validate(d)


@pytest.mark.parametrize("field", ["b4", "b5"])
@pytest.mark.parametrize("year", [0, 61])
def test_event_year_outside_study_period_refused_material(field, year):
    d = inventory_dict()
    d["assemblies"][1]["materials"][0][field] = [{"year": year, "amounts": gas()}]
    with pytest.raises(ValidationError, match="Roof/CLT|greater than or equal"):
        BuildingInventory.model_validate(d)


def test_shorter_study_period_moves_the_bound():
    d = totals_dict()
    d["study_period"] = 24  # b4 events are in year 25
    with pytest.raises(ValidationError, match="after the study period"):
        BuildingTotals.model_validate(d)


@pytest.mark.parametrize("year", ["30", 30.0, 30.5, None])
def test_event_year_must_be_whole_number(year):
    with pytest.raises(ValidationError):
        Event.model_validate_json(json.dumps({"year": year, "amounts": {}}))


@pytest.mark.xfail(
    strict=True,
    reason="B4 may not fall in the end-of-life year (#57 S11), but that year "
    "(RSP or RSP+1) is #58's decision; add the check with #58.",
)
def test_b4_in_end_of_life_year_refused():
    d = totals_dict()
    d["b4"] = [{"year": d["study_period"], "amounts": gas()}]
    with pytest.raises(ValidationError):
        BuildingTotals.model_validate(d)


# --- study period, names, quantities, units (S6, S9) ---------------------------------


@pytest.mark.parametrize("value", [0, -60, 60.0, 60.5, "60", None])
def test_study_period_must_be_whole_number_at_least_one(value):
    d = totals_dict()
    d["study_period"] = value
    with pytest.raises(ValidationError):
        BuildingTotals.model_validate_json(json.dumps(d))


@pytest.mark.parametrize("value", [0.0, -12.0, float("nan"), float("inf"), "12"])
def test_quantity_must_be_positive_finite_number(value):
    d = material_dict()
    d["quantity"] = value
    with pytest.raises(ValidationError):
        Material.model_validate(d)


@pytest.mark.parametrize("unit", ["m^3", "M3", "kg/m3", "ft3", ""])
def test_unknown_unit_refused(unit):
    d = material_dict()
    d["unit"] = unit
    with pytest.raises(ValidationError):
        Material.model_validate(d)


def test_duplicate_material_names_in_assembly_refused():
    d = inventory_dict()
    d["assemblies"][0]["materials"][1]["name"] = "CLT"
    with pytest.raises(ValidationError, match="duplicate name 'CLT'"):
        BuildingInventory.model_validate(d)


def test_same_material_name_in_two_assemblies_allowed():
    assert BuildingInventory.model_validate(inventory_dict())  # CLT in Floor and Roof


def test_duplicate_assembly_names_refused():
    d = inventory_dict()
    d["assemblies"][1]["name"] = "Floor"
    with pytest.raises(ValidationError, match="duplicate name 'Floor'"):
        BuildingInventory.model_validate(d)


def test_empty_building_and_assembly_refused():
    d = inventory_dict()
    d["assemblies"] = []
    with pytest.raises(ValidationError):
        BuildingInventory.model_validate(d)
    d = inventory_dict()
    d["assemblies"][0]["materials"] = []
    with pytest.raises(ValidationError):
        BuildingInventory.model_validate(d)


@pytest.mark.parametrize("where", ["building", "assembly", "material"])
def test_empty_name_refused(where):
    d = inventory_dict()
    target = {"building": d, "assembly": d["assemblies"][0], "material": first_material(d)}
    target[where]["name"] = ""
    with pytest.raises(ValidationError):
        BuildingInventory.model_validate(d)


def test_validation_leaves_input_alone():
    d = inventory_dict()
    before = copy.deepcopy(d)
    BuildingInventory.model_validate(d)
    assert d == before


# --- committed JSON Schema files -----------------------------------------------------

REGENERATE = (
    'uv run python -c "from dlca.inventory.schema import write_json_schemas; write_json_schemas()"'
)


@pytest.mark.parametrize("file_name", sorted(SCHEMA_FILES))
def test_committed_json_schema_matches_model(file_name):
    committed = json.loads((DATA / file_name).read_text(encoding="utf-8"))
    assert committed == json_schema(SCHEMA_FILES[file_name]), f"regenerate: {REGENERATE}"


def test_json_schemas_carry_their_tag():
    for file_name, model in SCHEMA_FILES.items():
        schema = json.loads((DATA / file_name).read_text(encoding="utf-8"))
        assert (
            schema["properties"]["schema"]["const"]
            == model.model_fields["schema_"].annotation.__args__[0]
        )
        assert "schema" in schema["required"]


def test_write_json_schemas_reproduces_committed_files(tmp_path):
    from dlca.inventory.schema import write_json_schemas

    write_json_schemas(tmp_path)
    for file_name in SCHEMA_FILES:
        assert (tmp_path / file_name).read_bytes() == (DATA / file_name).read_bytes()
