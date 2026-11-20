"""Energy unit table (#80).

Expected values are literals from the NIST SP 811 (2008) Appendix B
definitions, not computed by the module: 1 kWh = 3.6 MJ exactly,
1 Btu_IT = 1.05505585262 kJ exactly, 1 therm = 100 000 Btu_IT.
"""

import numpy as np
import pytest

from dlca.inventory.units import MJ_PER_UNIT, from_mj, to_mj

# MJ in one of each unit, typed from the definitions above.
EXPECTED_MJ = {
    "MJ": 1.0,
    "GJ": 1000.0,
    "kWh": 3.6,
    "kBtu": 1.05505585262,
    "MMBtu": 1055.05585262,
    "therm": 105.505585262,
}


def test_table_covers_exactly_the_expected_units():
    assert set(MJ_PER_UNIT) == set(EXPECTED_MJ)


@pytest.mark.parametrize("unit", EXPECTED_MJ)
def test_one_unit_in_mj_matches_nist_definition(unit):
    assert to_mj(1.0, unit) == pytest.approx(EXPECTED_MJ[unit], rel=1e-12)


@pytest.mark.parametrize("unit", EXPECTED_MJ)
def test_round_trip_returns_input(unit):
    values = np.array([0.0, 1.0, 12345.678, -3.5])
    np.testing.assert_allclose(from_mj(to_mj(values, unit), unit), values, rtol=1e-14)


def test_array_in_array_out_float_in_float_out():
    out = to_mj([1.0, 2.0], "kWh")
    assert isinstance(out, np.ndarray)
    np.testing.assert_allclose(out, [3.6, 7.2], rtol=1e-14)
    assert isinstance(to_mj(1, "kWh"), float)
    assert isinstance(from_mj(3.6, "kWh"), float)


def test_known_conversion_between_units():
    # 1 MMBtu = 1055.05585262 MJ = 293.07107017... kWh (1055.05585262 / 3.6).
    assert from_mj(to_mj(1.0, "MMBtu"), "kWh") == pytest.approx(293.071070172222, rel=1e-12)


@pytest.mark.parametrize("unit", ["kwh", "MWh", "Btu", "", None])
def test_unknown_unit_raises_and_lists_allowed(unit):
    with pytest.raises(ValueError, match="allowed: MJ, GJ, kWh, kBtu, MMBtu, therm"):
        to_mj(1.0, unit)
    with pytest.raises(ValueError, match="unknown energy unit"):
        from_mj(1.0, unit)
