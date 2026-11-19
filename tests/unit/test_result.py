"""dlca.Result and dlca.assess(): JSON round trip, provenance, inputs left alone (#31).

Faults these catch that no other test does: a field or array lost or rounded in
``to_dict()``/``from_dict()``; a result that does not record its parameter set
(name, fingerprint, CCF flag) or records it wrongly for a variant; a stored
result whose parameter values were edited; ``assess()`` writing to its inputs
or keeping a reference to them; a result whose arrays can be changed.
"""

import copy
import dataclasses
import json

import numpy as np
import pytest

import dlca
from dlca.climate import EMISSION_KEYS

N = 120


def all_keys():
    t = np.arange(N, dtype=float)
    return {
        "co2": 100.0 * np.exp(-t / 30.0) - 5.0,
        "ch4": np.r_[2.0, np.full(N - 1, 0.05)],
        "ch4_fossil": np.r_[np.zeros(60), np.ones(N - 60)],
        "n2o": np.full(N, 0.002),
    }


def assert_results_equal(a, b):
    """Bit-for-bit equality of every array and every scalar of two results."""
    assert a.to_dict() == b.to_dict()
    for key in EMISSION_KEYS:
        assert np.array_equal(a.emissions[key], b.emissions[key])
    for name in ("burden", "forcing", "temperature", "gwi", "gtp", "static_gwp"):
        x, y = getattr(a, name), getattr(b, name)
        for f in dataclasses.fields(x):
            u, v = getattr(x, f.name), getattr(y, f.name)
            if isinstance(u, np.ndarray):
                assert u.dtype == v.dtype == np.float64
                assert u.shape == v.shape
                assert np.array_equal(u, v), f"{name}.{f.name}"
            else:
                assert u == v, f"{name}.{f.name}"
    assert a.parameters == b.parameters


@pytest.mark.parametrize("parameters", ["AR5", "AR6"])
@pytest.mark.parametrize("horizon", [20, 100])
def test_json_round_trip_is_exact(parameters, horizon):
    r = dlca.assess(all_keys(), parameters=parameters, horizon=horizon)
    text = json.dumps(r.to_dict())
    back = dlca.Result.from_dict(json.loads(text))
    assert_results_equal(r, back)
    assert json.dumps(back.to_dict()) == text


def test_result_records_its_parameter_set():
    for name in ("AR5", "AR6"):
        p = dlca.get_parameters(name)
        r = dlca.assess(all_keys(), parameters=name)
        assert r.parameter_set == name
        assert r.parameter_fingerprint == p.fingerprint()
        ccf = {"AR5": False, "AR6": True}[name]  # decision C6 on #33
        assert r.carbon_cycle_feedback is ccf
        assert r.parameters == p
        d = r.to_dict()["parameters"]
        assert d["name"] == name
        assert d["fingerprint"] == p.fingerprint()
        assert d["carbon_cycle_feedback"] is ccf
        assert d["values"] == p.to_dict()


def test_variant_keeps_name_but_is_told_apart_by_fingerprint():
    ar5 = dlca.get_parameters("AR5")
    variant = dataclasses.replace(ar5, ch4_lifetime=12.0)
    r = dlca.assess(all_keys(), parameters=variant)
    assert r.parameter_set == "AR5"
    assert r.parameter_fingerprint == variant.fingerprint() != ar5.fingerprint()
    back = dlca.Result.from_dict(json.loads(json.dumps(r.to_dict())))
    assert back.parameters == variant
    assert not np.array_equal(r.burden.ch4, dlca.assess(all_keys(), parameters="AR5").burden.ch4)


def test_from_dict_rejects_edited_parameter_values():
    d = dlca.assess(all_keys(), parameters="AR5").to_dict()
    d["parameters"]["values"]["ch4_lifetime"] = 12.0
    with pytest.raises(ValueError, match="fingerprint"):
        dlca.Result.from_dict(d)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("schema", "something.else", "not a DLCA result"),
        ("schema_version", 1, "schema_version"),  # v1 predates the fingerprints (#37)
        ("schema_version", 2, "schema_version"),  # v2 predates ccf_co2 and the CCF values (#33)
        ("schema_version", 4, "schema_version"),
    ],
)
def test_from_dict_rejects_other_schemas(field, value, match):
    d = dlca.assess(all_keys(), parameters="AR5").to_dict()
    d[field] = value
    with pytest.raises(ValueError, match=match):
        dlca.Result.from_dict(d)


def test_from_dict_rejects_a_mislabelled_set():
    d = dlca.assess(all_keys(), parameters="AR5").to_dict()
    d["parameters"]["name"] = "AR6"
    with pytest.raises(ValueError, match="parameter_set"):
        dlca.Result.from_dict(d)


def test_assess_leaves_its_inputs_unchanged():
    arrays = all_keys()
    lists = {key: value.tolist() for key, value in all_keys().items()}
    before_arrays, before_lists = copy.deepcopy(arrays), copy.deepcopy(lists)
    params = dlca.get_parameters("AR5")
    params_before = params.to_dict()

    r = dlca.assess(arrays, parameters=params)
    dlca.assess(lists, parameters="AR6")

    for key in EMISSION_KEYS:
        assert np.array_equal(arrays[key], before_arrays[key])
        assert lists[key] == before_lists[key]
    assert params.to_dict() == params_before
    # The result holds copies: changing the caller's arrays later does not change it.
    held = r.emissions["co2"].copy()
    arrays["co2"][:] = 0.0
    assert np.array_equal(r.emissions["co2"], held)


def test_result_arrays_are_read_only():
    r = dlca.assess(all_keys(), parameters="AR5")
    back = dlca.Result.from_dict(r.to_dict())
    for result in (r, back):
        with pytest.raises(ValueError):
            result.emissions["co2"][0] = 1.0
        for name in ("burden", "forcing", "temperature", "gwi", "gtp", "static_gwp"):
            comp = getattr(result, name)
            for f in dataclasses.fields(comp):
                value = getattr(comp, f.name)
                if isinstance(value, np.ndarray):
                    assert not value.flags.writeable, f"{name}.{f.name}"


def test_result_matches_the_functions_it_composes():
    """assess() is the climate functions run once with one set and one horizon."""
    from dlca.climate import burden, forcing, gtp, gwi, static_gwp, temperature

    e, p = all_keys(), dlca.get_parameters("AR5")
    r = dlca.assess(e, parameters=p, horizon=20)
    b = burden(e, p)
    assert b.to_dict() == r.burden.to_dict()
    assert forcing(b, p).to_dict() == r.forcing.to_dict()
    assert temperature(b, p).to_dict() == r.temperature.to_dict()
    assert gwi(e, p, horizon=20).to_dict() == r.gwi.to_dict()
    assert gtp(e, p, horizon=20).to_dict() == r.gtp.to_dict()
    assert static_gwp(e, p, horizon=20).to_dict() == r.static_gwp.to_dict()
    np.testing.assert_array_equal(r.static_gwp.total, r.gwi.static)


def test_missing_keys_are_zeros():
    r = dlca.assess({"co2": [1.0, 0.0, 0.0]}, parameters="AR5")
    for key in ("ch4", "ch4_fossil", "n2o"):
        assert np.array_equal(r.emissions[key], np.zeros(3))


@pytest.mark.parametrize(
    ("kwargs", "error", "match"),
    [
        ({"parameters": "AR4"}, ValueError, "AR4"),
        ({"parameters": 5}, TypeError, "set name or a ClimateParameters"),
        ({"horizon": 0}, ValueError, "horizon"),
    ],
)
def test_assess_rejects_bad_arguments(kwargs, error, match):
    with pytest.raises(error, match=match):
        dlca.assess({"co2": [1.0, 0.0]}, **kwargs)


def test_assess_rejects_the_old_fossil_flag():
    """No fossil_ch4 flag (decision A1): fossil CH4 is the ch4_fossil key (S4 on #30)."""
    with pytest.raises(TypeError):
        dlca.assess({"ch4": [1.0, 0.0]}, fossil_ch4=True)


def test_result_mappings_cannot_be_changed():
    r = dlca.assess(all_keys(), parameters="AR5")
    with pytest.raises(TypeError):
        r.emissions["co2"] = np.zeros(N)
    with pytest.raises(TypeError):
        r.static_gwp.gwp["ch4"] = 1.0


def test_result_built_directly_is_frozen_too():
    """Result's own __post_init__ freezes; assess() and from_dict() are not the only guard."""
    r = dlca.assess(all_keys(), parameters="AR5")
    raw = {key: value.copy() for key, value in all_keys().items()}
    direct = dataclasses.replace(r, emissions=raw)
    assert not direct.emissions["co2"].flags.writeable
    assert raw["co2"].flags.writeable  # the caller's array is copied, not frozen


@pytest.mark.parametrize(
    ("edit", "match"),
    [
        (lambda d: d["gwi"].update(horizon=7.0), "gwi.horizon"),
        (lambda d: d["gtp"].update(horizon=7.0), "gtp.horizon"),
        (lambda d: d["static_gwp"].update(horizon=7.0), "static_gwp.horizon"),
        (lambda d: d["emissions"].update(co2=[1.0, 2.0]), "shape|values"),
        (lambda d: d["forcing"].update(ch4=d["forcing"]["ch4"][:-1]), "forcing.ch4"),
        (lambda d: d["burden"].update(co2_pools=d["burden"]["co2_pools"][:3]), "co2_pools"),
    ],
)
def test_from_dict_rejects_an_inconsistent_result(edit, match):
    """Found by the fresh-session review: from_dict accepted mixed horizons and lengths."""
    d = json.loads(json.dumps(dlca.assess(all_keys(), parameters="AR5").to_dict()))
    edit(d)
    with pytest.raises(ValueError, match=match):
        dlca.Result.from_dict(d)
