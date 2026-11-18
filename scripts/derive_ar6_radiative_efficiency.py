"""Derive the unrounded AR6 radiative efficiencies stored in ``ar6.json``.

Decision D1 on issue #26: store unrounded radiative efficiencies (REs), computed
once by this committed script, with the rounded published values kept next to
them for the check.

Method: as in the IPCC AR6 WG1 Chapter 7 code that produced Table 7.SM.7
(github.com/IPCC-WG1/Chapter-7, ``src/ar6/metrics/{co2,ch4,n2o}.py``, called from
``notebooks/335_chapter7_generate_metrics.ipynb``). That code calls FaIR 1.6.2's
``meinshausen(C, Cpi)`` with the 2019 concentrations as ``Cpi``, the formula's
pre-industrial reference. The RE is therefore the forcing of a 1 ppm (CO2) or
1 ppb (CH4, N2O) step *above 2019*, from the Meinshausen et al. (2020) formula
re-referenced to 2019. It then applies the AR6 tropospheric rapid adjustments.

This is not the same as the slope of the formula at 2019 with the 1750
reference: that slope is about 4% higher for CO2 and 4% lower for CH4, and it
does not reproduce the published AGWP100(CO2). ``slope_at_2019()`` is kept so the
difference stays visible.

Run:  uv run python scripts/derive_ar6_radiative_efficiency.py
The test ``tests/unit/test_parameters.py`` checks that ``ar6.json`` matches.
"""

from __future__ import annotations

import json
import math

# Meinshausen et al. (2020), GMD 13, 3571, Table 3, doi:10.5194/gmd-13-3571-2020,
# as coded in FaIR 1.6.2 fair/forcing/ghg.py (meinshausen()).
A1, B1, C1, D1 = -2.4785e-07, 0.00075906, -0.0021492, 5.2488
A2, B2, C2, D2 = -0.00034197, 0.00025455, -0.00024357, 0.12173
A3, B3, D3 = -8.9603e-05, -0.00012462, 0.045194
PREINDUSTRIAL = (277.15, 731.41, 273.87)  # CO2 ppm, CH4 ppb, N2O ppb

# AR6 2019 concentrations used for Table 7.SM.7 (notebook 335, cell "Define
# baseline GHG concentrations"). co2_analytical() fixes CH4 at 1866.3 ppb.
BASELINE_2019 = (409.9, 1866.3, 332.1)

# AR6 tropospheric rapid adjustments (fractions), from the same code.
RAPID_ADJUSTMENT = {"co2": 0.05, "ch4": -0.14, "n2o": 0.07}


def meinshausen(c, cpi=PREINDUSTRIAL):
    """SARF of CO2, CH4, N2O [W m-2] at ``c`` relative to ``cpi`` (FaIR 1.6.2, unscaled)."""
    co2, ch4, n2o = c
    co2_pi, ch4_pi, n2o_pi = cpi
    ca_max = co2_pi - B1 / (2 * A1)
    if co2_pi < co2 <= ca_max:
        alpha_p = D1 + A1 * (co2 - co2_pi) ** 2 + B1 * (co2 - co2_pi)
    elif co2 <= co2_pi:
        alpha_p = D1
    else:
        alpha_p = D1 - B1**2 / (4 * A1)
    f_co2 = (alpha_p + C1 * math.sqrt(n2o)) * math.log(co2 / co2_pi)
    f_ch4 = (A3 * math.sqrt(ch4) + B3 * math.sqrt(n2o) + D3) * (math.sqrt(ch4) - math.sqrt(ch4_pi))
    f_n2o = (A2 * math.sqrt(co2) + B2 * math.sqrt(n2o) + C2 * math.sqrt(ch4) + D2) * (
        math.sqrt(n2o) - math.sqrt(n2o_pi)
    )
    return f_co2, f_ch4, f_n2o


def derive(baseline=BASELINE_2019):
    """AR6 REs [W m-2 ppb-1], including rapid adjustments, by the IPCC Chapter 7 method."""
    co2, ch4, n2o = baseline
    base = (co2, ch4, n2o)
    # CO2: +1 ppm step, result per ppm -> divide by 1000 for per ppb.
    re_co2 = meinshausen((co2 + 1, ch4, n2o), base)[0] * (1 + RAPID_ADJUSTMENT["co2"]) / 1000
    re_ch4 = meinshausen((co2, ch4 + 1, n2o), base)[1] * (1 + RAPID_ADJUSTMENT["ch4"])
    re_n2o = meinshausen((co2, ch4, n2o + 1), base)[2] * (1 + RAPID_ADJUSTMENT["n2o"])
    return {"co2": re_co2, "ch4": re_ch4, "n2o": re_n2o}


def slope_at_2019(baseline=BASELINE_2019, step=1e-3):
    """Alternative not used: slope of the 1750-referenced formula at 2019 (incl. rapid adj.)."""
    co2, ch4, n2o = baseline
    f0 = meinshausen(baseline)
    return {
        "co2": (meinshausen((co2 + step, ch4, n2o))[0] - f0[0])
        / step
        * (1 + RAPID_ADJUSTMENT["co2"])
        / 1000,
        "ch4": (meinshausen((co2, ch4 + step, n2o))[1] - f0[1])
        / step
        * (1 + RAPID_ADJUSTMENT["ch4"]),
        "n2o": (meinshausen((co2, ch4, n2o + step))[2] - f0[2])
        / step
        * (1 + RAPID_ADJUSTMENT["n2o"]),
    }


if __name__ == "__main__":
    print(json.dumps({"ipcc_method": derive(), "slope_at_2019": slope_at_2019()}, indent=2))
