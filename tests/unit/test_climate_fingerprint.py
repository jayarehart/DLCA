"""Every climate output records its parameter set; mixing sets raises (#37, #46).

The expected behaviour was written on #37 (decisions G1-G9 and R1-R6) and #46
(decisions F1-F6) before the code (Jay, 2026-11-19). No expected value here
comes from the code.

Faults these catch that no other test does:

- ``forcing()`` or ``temperature()`` accepting a burden made with another set
  (the mismatch tests; AR5 and AR6 in both directions);
- a check that compares ``name`` instead of the values (the one-value variant
  and CCF-flag variant tests: both keep the name);
- a check that compares object identity instead of the values (the copy test);
- a fingerprint lost by ``to_dict()``/``from_dict()`` or not passed on to
  ``Forcing`` and ``Temperature`` (the round-trip and carry tests);
- a ``Result`` assembled from a component of another set (the Result tests),
  including ``gwi``, ``gtp`` or ``static_gwp``, alone or all three (#46).
"""

import dataclasses
import json

import numpy as np
import pytest

import dlca
from dlca.climate import (
    GTP,
    GWI,
    Burden,
    Forcing,
    StaticGWP,
    Temperature,
    burden,
    forcing,
    gtp,
    gwi,
    static_gwp,
    temperature,
)
from dlca.parameters import ClimateParameters, get_parameters

AR5 = get_parameters("AR5")
AR6 = get_parameters("AR6")
CONSUMERS = [forcing, temperature]
EMISSIONS = {
    "co2": np.r_[1.0, np.zeros(30)],
    "ch4": np.r_[1.0, np.zeros(30)],
    "ch4_fossil": np.r_[0.5, np.zeros(30)],
    "n2o": np.r_[1.0, np.zeros(30)],
}
OUTPUTS = [Burden, Forcing, Temperature, GWI, GTP, StaticGWP]
COMPONENTS = ["burden", "forcing", "temperature", "gwi", "gtp", "static_gwp"]


def make(cls, params):
    """The ``cls`` output of ``EMISSIONS`` under ``params``, from its public function."""
    if cls is GWI:
        return gwi(EMISSIONS, params)
    if cls is GTP:
        return gtp(EMISSIONS, params)
    if cls is StaticGWP:
        return static_gwp(EMISSIONS, params)
    b = burden(EMISSIONS, params)
    return {Burden: b, Forcing: forcing(b, params), Temperature: temperature(b, params)}[cls]


def variants():
    """Sets that keep a shipped set's name but differ in one value."""
    return {
        "AR5 ch4_lifetime + 0.1": (
            AR5,
            dataclasses.replace(AR5, ch4_lifetime=AR5.ch4_lifetime + 0.1),
        ),
        "AR6 CCF flag flipped": (
            AR6,
            dataclasses.replace(AR6, carbon_cycle_feedback=not AR6.carbon_cycle_feedback),
        ),
    }


@pytest.mark.parametrize("fn", CONSUMERS, ids=lambda f: f.__name__)
@pytest.mark.parametrize(
    ("made_with", "given"), [(AR5, AR6), (AR6, AR5)], ids=["AR5-AR6", "AR6-AR5"]
)
def test_burden_of_another_set_raises(fn, made_with, given):
    b = burden(EMISSIONS, made_with)
    with pytest.raises(ValueError, match="different set") as info:
        fn(b, given)
    message = str(info.value)
    assert f"{fn.__name__}()" in message
    assert repr(given.name) in message
    assert given.fingerprint()[:8] in message
    assert made_with.fingerprint()[:8] in message
    assert "dataclasses.replace()" in message  # R6: a variant keeps its name


@pytest.mark.parametrize("fn", CONSUMERS, ids=lambda f: f.__name__)
@pytest.mark.parametrize("name", list(variants()))
def test_variant_with_the_same_name_raises(fn, name):
    base, variant = variants()[name]
    assert variant.name == base.name
    with pytest.raises(ValueError, match="different set"):
        fn(burden(EMISSIONS, base), variant)
    with pytest.raises(ValueError, match="different set"):
        fn(burden(EMISSIONS, variant), base)


@pytest.mark.parametrize("fn", CONSUMERS, ids=lambda f: f.__name__)
@pytest.mark.parametrize("params", [AR5, AR6], ids=["AR5", "AR6"])
def test_same_set_or_a_copy_with_the_same_values_passes(fn, params):
    b = burden(EMISSIONS, params)
    copy = ClimateParameters.from_dict(params.to_dict())
    assert copy is not params
    fn(b, params)
    fn(b, copy)
    fn(burden(EMISSIONS, copy), params)


@pytest.mark.parametrize("cls", OUTPUTS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("params", [AR5, AR6], ids=["AR5", "AR6"])
def test_every_output_carries_the_fingerprint(cls, params):
    assert make(cls, params).parameter_fingerprint == params.fingerprint()


@pytest.mark.parametrize("cls", OUTPUTS, ids=lambda c: c.__name__)
def test_fingerprint_is_the_last_field(cls):
    assert dataclasses.fields(cls)[-1].name == "parameter_fingerprint"


@pytest.mark.parametrize("cls", OUTPUTS, ids=lambda c: c.__name__)
def test_to_dict_records_the_fingerprint_and_from_dict_restores_it(cls):
    obj = make(cls, AR5)
    d = json.loads(json.dumps(obj.to_dict()))
    assert d["parameter_fingerprint"] == AR5.fingerprint()
    back = cls.from_dict(d)
    assert back.parameter_fingerprint == AR5.fingerprint()
    del d["parameter_fingerprint"]
    with pytest.raises(ValueError, match="parameter_fingerprint"):
        cls.from_dict(d)


@pytest.mark.parametrize("fn", CONSUMERS, ids=lambda f: f.__name__)
def test_round_tripped_burden_keeps_its_check(fn):
    b = Burden.from_dict(json.loads(json.dumps(burden(EMISSIONS, AR5).to_dict())))
    fn(b, AR5)
    with pytest.raises(ValueError, match="different set"):
        fn(b, AR6)


def test_burden_built_by_hand_needs_a_fingerprint():
    b = burden(EMISSIONS, AR6)
    arrays = {f.name: getattr(b, f.name) for f in dataclasses.fields(b)}
    del arrays["parameter_fingerprint"]
    with pytest.raises(TypeError):
        Burden(**arrays)


@pytest.mark.parametrize("component", COMPONENTS)
def test_result_rejects_a_component_of_another_set(component):
    r = dlca.assess(EMISSIONS, parameters="AR5")
    other = dlca.assess(EMISSIONS, parameters="AR6")
    with pytest.raises(ValueError, match=f"{component} was made with a different"):
        dataclasses.replace(r, **{component: getattr(other, component)})


def test_result_rejects_the_three_metrics_of_another_set_together():
    """The PR #45 review's example (#46): only the three metrics swapped."""
    r_ar6 = dlca.assess(EMISSIONS, parameters="AR6")
    r_ar5 = dlca.assess(EMISSIONS, parameters="AR5")
    with pytest.raises(ValueError, match="was made with a different"):
        dataclasses.replace(r_ar6, gwi=r_ar5.gwi, gtp=r_ar5.gtp, static_gwp=r_ar5.static_gwp)


@pytest.mark.parametrize("component", COMPONENTS)
def test_result_from_dict_rejects_an_edited_component_fingerprint(component):
    d = json.loads(json.dumps(dlca.assess(EMISSIONS, parameters="AR5").to_dict()))
    d[component]["parameter_fingerprint"] = AR6.fingerprint()
    with pytest.raises(ValueError, match=f"{component} was made with a different"):
        dlca.Result.from_dict(d)


@pytest.mark.parametrize("cls", OUTPUTS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("bad", [None, 123, b"bytes"], ids=["None", "int", "bytes"])
def test_a_fingerprint_that_is_not_a_string_is_refused(cls, bad):
    """Found by the fresh-session review: from_dict turned None into 'None', and a
    non-string fingerprint made the mismatch message raise TypeError, not ValueError."""
    obj = make(cls, AR5)
    d = obj.to_dict()
    d["parameter_fingerprint"] = bad
    with pytest.raises(ValueError, match="parameter_fingerprint must be a string"):
        cls.from_dict(d)
    with pytest.raises(TypeError, match="parameter_fingerprint must be a string"):
        dataclasses.replace(obj, parameter_fingerprint=bad)
