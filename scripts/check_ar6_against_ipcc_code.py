"""Print AR6 metrics (H = 100, no carbon-cycle feedback) from the IPCC Chapter 7 code.

The ``agwp100_ch4``, ``agtp100_ch4``, ``agwp100_n2o`` and ``agtp100_n2o`` values in
the ``checks`` block of ``src/dlca/data/climate_parameters/ar6.json`` came from this
script. It isn't run by the tests or CI, because it needs FaIR 1.6.2 and the IPCC
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
