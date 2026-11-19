"""Print AR6 metrics from the IPCC Chapter 7 code, without and with carbon-cycle feedback.

The ``agwp100_ch4``, ``agtp100_ch4``, ``agwp100_n2o`` and ``agtp100_n2o`` values in
the ``checks`` block of ``src/dlca/data/climate_parameters/ar6.json`` came from the
first part of this script (H = 100, no CCF). The ``*_ccf`` checks came from the
second part (issue #33, decision C2): ``carbon_cycle_adjustment()`` is a
rectangle-rule convolution whose error is first order in the time step, so it is
run at dt = 0.02 and 0.01 yr and Richardson-extrapolated to dt -> 0
(``2 f(0.01) - f(0.02)``). The dt = 0.1 values are the published ones
(Table 7.SM.7). The CCF part takes a few minutes, from the O(n^2) Python loops.

It isn't run by the tests or CI, because it needs FaIR 1.6.2 and the IPCC
repository.

Setup (outside this repo; FaIR 1.6.2 needs old numpy and scipy):

    uv venv -p 3.10 ~/.venvs/fair162
    uv pip install --python ~/.venvs/fair162/bin/python "fair==1.6.2" "numpy<2" "scipy<1.12"
    git clone https://github.com/IPCC-WG1/Chapter-7 ~/src/ipcc-ch7
    git -C ~/src/ipcc-ch7 checkout 2f948c8

Run:

    ~/.venvs/fair162/bin/python -I scripts/check_ar6_against_ipcc_code.py ~/src/ipcc-ch7/src

Inputs are those of notebooks/335_chapter7_generate_metrics.ipynb.
"""

import sys

sys.path.insert(0, sys.argv[1])

import numpy as np  # noqa: E402
from ar6.metrics.ch4 import ch4_analytical  # noqa: E402
from ar6.metrics.co2 import co2_analytical  # noqa: E402
from ar6.metrics.n2o import n2o_analytical  # noqa: E402

D = np.array([3.424102092311, 285.003477841911])
Q = np.array([0.443767728883447, 0.313998206372015])
H = np.array([100.0])
BASE = {"co2": 409.9, "n2o": 332.1}

_, agwp, agtp, _ = co2_analytical(
    H,
    d=D,
    q=Q,
    a=np.array([0.2173, 0.2240, 0.2824, 0.2763]),
    alpha_co2=np.array([0, 394.4, 36.54, 4.304]),
    co2_ra=0.05,
    **BASE,
)
print("co2", agwp[0], agtp[0])
_, agwp, agtp, _ = ch4_analytical(
    H, d=D, q=Q, ch4=1866.3, ch4_ra=-0.14, alpha_ch4=11.8, ch4_o3=1.4e-4, ch4_h2o=4e-5, **BASE
)
print("ch4", agwp[0], agtp[0])
_, agwp, agtp, _ = n2o_analytical(H, d=D, q=Q, ch4=1866.3, **BASE)
print("n2o", agwp[0], agtp[0])


# --- With carbon-cycle feedback (issue #33) ---------------------------------
from ar6.metrics.gasser import carbon_cycle_adjustment  # noqa: E402

CO2_IRF = {
    "a": np.array([0.2173, 0.2240, 0.2824, 0.2763]),
    "alpha_co2": np.array([0, 394.4, 36.54, 4.304]),
}
results = {}
for dt in (0.1, 0.02, 0.01):
    steps = int(round(1 / dt))
    h = np.linspace(0, 100, 100 * steps + 1)
    _, agwp_co2, agtp_co2, _ = co2_analytical(h, d=D, q=Q, co2_ra=0.05, **CO2_IRF, **BASE)
    gases = {
        "ch4": ch4_analytical(
            h,
            d=D,
            q=Q,
            ch4=1866.3,
            ch4_ra=-0.14,
            alpha_ch4=11.8,
            ch4_o3=1.4e-4,
            ch4_h2o=4e-5,
            **BASE,
        ),
        "n2o": n2o_analytical(h, d=D, q=Q, ch4=1866.3, **BASE),
    }
    for gas, (_, agwp, agtp, _) in gases.items():
        _, agwp_cc, agtp_cc = carbon_cycle_adjustment(h, agtp, co2_ra=0.05, d=D, q=Q, **BASE)
        for horizon in (20, 100):
            i = horizon * steps
            results[dt, gas, horizon] = (agwp[i] + agwp_cc[i], agtp[i] + agtp_cc[i])
            gwp = (agwp[i] + agwp_cc[i]) / agwp_co2[i]
            total_agwp, total_agtp = results[dt, gas, horizon]
            print(
                f"dt={dt} {gas} H={horizon}: AGWP {total_agwp!r} AGTP {total_agtp!r} GWP {gwp:.4f}"
            )
for gas in ("ch4", "n2o"):
    for horizon in (20, 100):
        fine, coarse = results[0.01, gas, horizon], results[0.02, gas, horizon]
        agwp_x, agtp_x = (2 * f - c for f, c in zip(fine, coarse, strict=True))
        print(f"dt->0 {gas} H={horizon}: AGWP {agwp_x!r} AGTP {agtp_x!r}")
