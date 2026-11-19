"""Tests for the AR5/AR6 climate parameter sets and ClimateParameters (issue #26).

Independent check: closed-form AGWP100 and AGTP100 of CO2 (and AR5 CH4/N2O
AGWP100) computed here from each set's values, compared with the published IPCC
tables at their printed precision. Table and page numbers were checked against
the IPCC PDFs on #26 (comment of 2026-11-18). The expected values sit in the ``checks``
block of each JSON file, copied from the tables; the closed forms are written in
this file, not taken from the package.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import math
import re
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

import dlca
from dlca.parameters import ClimateParameters, load_document

REPO = Path(__file__).resolve().parents[2]
SETS = ["AR5", "AR6"]
DOI = re.compile(r"^10\.\d{4,9}/\S+$")


# --- closed forms (Myhre et al. 2013, 8.SM.11; Forster et al. 2021, 7.SM.5) ---


def specific_forcing(p: ClimateParameters, gas: str) -> float:
    """W m-2 kg-1 from W m-2 ppb-1 (CO2 RE is stored per ppb too)."""
    molar = {"co2": p.molar_mass_co2, "ch4": p.molar_mass_ch4, "n2o": p.molar_mass_n2o}[gas]
    return p.effective_radiative_efficiency(gas) * 1e9 * p.molar_mass_air / molar / p.atm_mass


def agwp_co2(p: ClimateParameters, h: float = 100.0) -> float:
    a0, *a = p.co2_a
    integral = a0 * h + sum(
        ai * t * (1 - math.exp(-h / t)) for ai, t in zip(a, p.co2_tau, strict=True)
    )
    return specific_forcing(p, "co2") * integral


def agtp_co2(p: ClimateParameters, h: float = 100.0) -> float:
    a0, *a = p.co2_a
    total = 0.0
    for q, d in zip(p.climate_q, p.climate_d, strict=True):
        total += a0 * q * (1 - math.exp(-h / d))
        for ai, t in zip(a, p.co2_tau, strict=True):
            total += ai * t * q * (math.exp(-h / t) - math.exp(-h / d)) / (t - d)
    return specific_forcing(p, "co2") * total


def agwp_decaying(p: ClimateParameters, gas: str, h: float = 100.0) -> float:
    life = {"ch4": p.ch4_lifetime, "n2o": p.n2o_lifetime}[gas]
    return specific_forcing(p, gas) * life * (1 - math.exp(-h / life))


def agtp_decaying(p: ClimateParameters, gas: str, h: float = 100.0) -> float:
    life = {"ch4": p.ch4_lifetime, "n2o": p.n2o_lifetime}[gas]
    total = sum(
        q * life * (math.exp(-h / life) - math.exp(-h / d)) / (life - d)
        for q, d in zip(p.climate_q, p.climate_d, strict=True)
    )
    return specific_forcing(p, gas) * total


def matches_printed(value: float, printed: float, *, truncated_ok: bool = False) -> bool:
    """True if ``value`` shown at ``printed``'s precision gives ``printed``."""
    p = Decimal(repr(printed))
    quantum = Decimal(1).scaleb(p.adjusted() - (len(p.as_tuple().digits) - 1))
    v = Decimal(repr(value))
    if v.quantize(quantum, rounding=ROUND_HALF_UP) == p:
        return True
    return truncated_ok and v.quantize(quantum, rounding=ROUND_DOWN) == p


def checks(name: str) -> dict[str, float]:
    return {k: v["value"] for k, v in load_document(name)["checks"].items()}


# --- provenance: every value has a unit and a source; every source has a DOI ---


def _leaves(node, path=""):
    if isinstance(node, dict):
        if "value" in node:
            yield path, node
            return
        for key, child in node.items():
            yield from _leaves(child, f"{path}.{key}" if path else key)


@pytest.mark.parametrize("name", SETS)
def test_every_value_has_unit_source_and_where(name):
    doc = load_document(name)
    sources = doc["sources"]
    leaves = list(_leaves({k: v for k, v in doc.items() if k != "sources"}))
    assert len(leaves) >= 20  # guards against the walker finding nothing
    for path, leaf in leaves:
        assert isinstance(leaf.get("unit"), str) and leaf["unit"], path
        assert leaf.get("source") in sources, path
        assert isinstance(leaf.get("where"), str) and leaf["where"], path


@pytest.mark.parametrize("name", SETS)
def test_every_numeric_value_is_inside_a_cited_leaf(name):
    """No bare numbers outside {value, unit, source} leaves (except schema_version)."""
    doc = load_document(name)
    doc.pop("schema_version")

    def bare_numbers(node, path=""):
        if isinstance(node, dict):
            if "value" in node:
                return
            for key, child in node.items():
                yield from bare_numbers(child, f"{path}.{key}")
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            yield path

    assert list(bare_numbers(doc)) == []


@pytest.mark.parametrize("name", SETS)
def test_every_source_has_a_doi(name):
    sources = load_document(name)["sources"]
    assert sources
    for key, source in sources.items():
        assert DOI.match(source.get("doi", "")), key
        assert source.get("citation"), key


# --- independent check against published IPCC tables ---


@pytest.mark.parametrize("name", SETS)
def test_agwp100_co2_matches_published(name):
    expected = checks(name)["agwp100_co2"]
    assert matches_printed(agwp_co2(dlca.get_parameters(name)), expected)


@pytest.mark.parametrize("name", SETS)
def test_agtp100_co2_matches_published(name):
    expected = checks(name)["agtp100_co2"]
    assert matches_printed(agtp_co2(dlca.get_parameters(name)), expected)


@pytest.mark.parametrize("gas", ["ch4", "n2o"])
def test_ar5_agwp100_ch4_n2o_match_published(gas):
    expected = checks("AR5")[f"agwp100_{gas}"]
    assert matches_printed(agwp_decaying(dlca.get_parameters("AR5"), gas), expected)


@pytest.mark.parametrize("gas", ["ch4", "n2o"])
def test_ar5_agtp100_ch4_n2o_match_published(gas):
    expected = checks("AR5")[f"agtp100_{gas}"]
    assert matches_printed(agtp_decaying(dlca.get_parameters("AR5"), gas), expected)


def test_ar5_agwp20_co2_matches_published():
    assert matches_printed(
        agwp_co2(dlca.get_parameters("AR5"), h=20.0), checks("AR5")["agwp20_co2"]
    )


@pytest.mark.parametrize("metric", ["agwp100", "agtp100"])
@pytest.mark.parametrize("gas", ["ch4", "n2o"])
def test_ar6_ch4_n2o_match_ipcc_code_without_ccf(metric, gas):
    """Expected values from running the IPCC Chapter 7 functions (not a published table)."""
    compute = agwp_decaying if metric == "agwp100" else agtp_decaying
    expected = checks("AR6")[f"{metric}_{gas}"]
    assert matches_printed(compute(dlca.get_parameters("AR6"), gas), expected)


@pytest.mark.parametrize("gas", ["ch4", "n2o"])
def test_ar6_re_including_chemistry_matches_table_7_15(gas):
    """Checks the AR6 additive indirect terms (O3, H2O, N2O->CH4) against Table 7.15."""
    p = dlca.get_parameters("AR6")
    assert matches_printed(p.effective_radiative_efficiency(gas), checks("AR6")[f"re_eff_{gas}"])


@pytest.mark.parametrize("name", SETS)
@pytest.mark.parametrize("gas", ["ch4", "n2o"])
def test_lifetimes_match_published(name, gas):
    p = dlca.get_parameters(name)
    assert getattr(p, f"{gas}_lifetime") == checks(name)[f"{gas}_lifetime"]


def test_ar6_unrounded_re_match_derivation_script_and_published():
    spec = importlib.util.spec_from_file_location(
        "derive_ar6_re", REPO / "scripts" / "derive_ar6_radiative_efficiency.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    derived = module.derive()
    doc = load_document("AR6")
    for gas in ("co2", "ch4", "n2o"):
        leaf = doc[gas]["radiative_efficiency"]
        assert leaf["value"] == derived[gas], gas
        # Table 7.SM.7 prints CH4 as 0.000388 for 0.00038864 (truncated, not rounded).
        truncated_ok = gas == "ch4"
        assert matches_printed(leaf["value"], leaf["published"], truncated_ok=truncated_ok), gas


# The checks above must be able to fail. Each mutation is a plausible mistake.
MISTAKES = [
    ("AR5", "agwp100_co2", {"co2_tau": (36.54, 394.4, 4.304)}),  # swapped CO2 pool lifetimes
    ("AR6", "agwp100_co2", {"co2_tau": (36.54, 394.4, 4.304)}),
    ("AR5", "agwp100_co2", {"co2_re_scale": 1.0}),  # Cooper factor dropped
    ("AR6", "agtp100_co2", {"climate_q": (0.443767728883447, 0.319591049742508)}),  # D2 other q2
    ("AR6", "agwp100_co2", {"co2_re": 1.33e-05}),  # rounded RE (D1 option a)
    ("AR5", "agwp100_ch4", {"ch4_o3": 0.0}),  # ozone term lost
    ("AR5", "agwp100_n2o", {"n2o_ch4_change": 0.36}),  # sign flip
    ("AR5", "agtp100_ch4", {"climate_d": (409.5, 8.4)}),  # climate response times swapped
    ("AR6", "re_eff_ch4", {"ch4_o3": 0.0}),  # AR6 ozone term lost
    ("AR6", "re_eff_ch4", {"ch4_h2o": 0.0}),  # AR6 water-vapour term lost
    ("AR6", "re_eff_n2o", {"n2o_ch4_change": 1.7}),  # AR6 sign flip
    ("AR6", "re_eff_n2o", {"n2o_o3": 0.0}),  # AR6 N2O ozone term lost
    ("AR6", "agwp100_ch4", {"ch4_h2o": 0.0}),  # small term lost: caught at 6 digits
    ("AR6", "agwp100_ch4", {"ch4_lifetime": 12.4}),  # AR5 CH4 lifetime in AR6
    ("AR6", "agwp100_n2o", {"n2o_ch4_change": 1.7}),  # sign flip
    ("AR6", "agtp100_n2o", {"climate_q": (0.443767728883447, 0.319591049742508)}),  # D2 other q2
]


@pytest.mark.parametrize(("name", "check", "change"), MISTAKES)
def test_checks_detect_deliberate_mistakes(name, check, change):
    p = dataclasses.replace(dlca.get_parameters(name), **change)
    compute = {
        "agwp100_co2": agwp_co2,
        "agtp100_co2": agtp_co2,
        "agwp100_ch4": lambda q: agwp_decaying(q, "ch4"),
        "agwp100_n2o": lambda q: agwp_decaying(q, "n2o"),
        "agtp100_ch4": lambda q: agtp_decaying(q, "ch4"),
        "agtp100_n2o": lambda q: agtp_decaying(q, "n2o"),
        "re_eff_ch4": lambda q: q.effective_radiative_efficiency("ch4"),
        "re_eff_n2o": lambda q: q.effective_radiative_efficiency("n2o"),
    }[check]
    assert not matches_printed(compute(p), checks(name)[check])


# --- ClimateParameters: frozen, hashable, round-trips ---


@pytest.mark.parametrize("name", SETS)
def test_frozen(name):
    p = dlca.get_parameters(name)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.ch4_lifetime = 1.0  # type: ignore[misc]


@pytest.mark.parametrize("name", SETS)
def test_hashable_and_usable_as_key(name):
    p = dlca.get_parameters(name)
    assert {p: 1}[ClimateParameters.from_dict(p.to_dict())] == 1


@pytest.mark.parametrize("name", SETS)
def test_json_round_trip(name):
    p = dlca.get_parameters(name)
    again = ClimateParameters.from_dict(json.loads(json.dumps(p.to_dict())))
    assert again == p
    assert hash(again) == hash(p)
    assert again.fingerprint() == p.fingerprint()


def test_replace_with_list_stays_hashable_and_changes_fingerprint():
    p = dlca.get_parameters("AR6")
    variant = dataclasses.replace(p, co2_tau=[394.4, 36.54, 4.0])
    assert isinstance(variant.co2_tau, tuple)
    hash(variant)
    assert variant.name == p.name
    assert variant.fingerprint() != p.fingerprint()


def test_from_dict_rejects_unknown_and_missing_keys():
    d = dlca.get_parameters("AR6").to_dict()
    with pytest.raises(ValueError, match="unknown"):
        ClimateParameters.from_dict({**d, "extra": 1})
    d.pop("ch4_lifetime")
    with pytest.raises(ValueError, match="ch4_lifetime"):
        ClimateParameters.from_dict(d)


def test_bad_values_rejected():
    p = dlca.get_parameters("AR6")
    with pytest.raises(ValueError, match="sum to 1"):
        dataclasses.replace(p, co2_a=(0.3, 0.224, 0.2824, 0.2763))
    with pytest.raises(ValueError, match="co2_tau needs 3"):
        dataclasses.replace(p, co2_tau=(394.4, 36.54))
    with pytest.raises(ValueError, match="indirect_form"):
        dataclasses.replace(p, ch4_indirect_form="mixed")


# --- selector ---


def test_available_parameter_sets():
    assert dlca.available_parameter_sets() == ["AR5", "AR6"]


def test_default_is_ar6():
    # Decision D6 on #26: AR6 is the default now that D1-D4 are settled.
    assert dlca.DEFAULT_PARAMETER_SET == "AR6"
    assert dlca.get_parameters().name == "AR6"


def test_name_is_case_insensitive():
    assert dlca.get_parameters("ar5") == dlca.get_parameters("AR5")


def test_unknown_name_lists_valid_names():
    with pytest.raises(ValueError, match=r"AR5.*AR6"):
        dlca.get_parameters("AR4")


def test_sets_differ():
    assert dlca.get_parameters("AR5").fingerprint() != dlca.get_parameters("AR6").fingerprint()


# --- fossil CH4 yield (decision D4) ---


def test_ar6_fossil_ch4_yield_is_the_ar6_central_value():
    # Decision D4 as revised on #26: AR6 Ch7 Section 7.6.1.3 central value 75% (molar).
    assert dlca.get_parameters("AR6").fossil_ch4_co2_yield() == 0.75


def test_missing_fossil_ch4_yield_raises_instead_of_guessing():
    p = dataclasses.replace(dlca.get_parameters("AR6"), ch4_fossil_co2_yield=None)
    with pytest.raises(ValueError, match="fossil CH4"):
        p.fossil_ch4_co2_yield()


def test_ccf_on_for_ar6_off_for_ar5():
    # Decision C6 on #33 (supersedes D3 on #26): AR6 ships with CCF, AR5 without.
    assert dlca.get_parameters("AR6").carbon_cycle_feedback is True
    assert dlca.get_parameters("AR5").carbon_cycle_feedback is False
