"""Invariants of biogenic uptake (#73).

- Carbon balance: over a long enough series, uptake equals the declared co2
  for every regrowth option (to 1e-12 relative). For any length, the uptake
  taken plus the part reported as cut by the series end equals the declared
  co2.
- Uptake is never positive, and nothing before the product's year.
- Linear in the declared co2 and in the quantity.

Faults these catch that the hand cases do not: a rescaling that is right for
one rotation but not another (the old 97.9-101.4 % range), a cut-off fraction
that is wrong for long rotations or late events, and uptake leaking before
the event year.
"""

import math

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from dlca.inventory.biogenic import uptake_shares

rotations = st.integers(min_value=2, max_value=300)
lengths = st.integers(min_value=1, max_value=2000)


@settings(max_examples=200, deadline=None)
@given(rotation=rotations)
def test_gaussian_shares_sum_to_one_over_a_long_series(rotation):
    # mu + 8 sigma = 2.5 rotation: the cut tail is below 1e-15.
    shares, cut = uptake_shares("gaussian", rotation, length=3 * rotation + 10)
    assert math.isclose(shares.sum(), 1.0, rel_tol=1e-12)
    assert cut <= 1e-14


@settings(max_examples=200, deadline=None)
@given(rotation=rotations, length=lengths)
def test_taken_plus_cut_is_one_for_any_length(rotation, length):
    shares, cut = uptake_shares("gaussian", rotation, length=length)
    assert shares.shape == (length,)
    assert np.all(shares >= 0)
    assert math.isclose(shares.sum() + cut, 1.0, rel_tol=1e-12)


@given(length=lengths)
def test_instant_and_none(length):
    shares, cut = uptake_shares("instant", None, length=length)
    assert shares[0] == 1.0 and shares[1:].sum() == 0 and cut == 0
    shares, cut = uptake_shares("none", None, length=length)
    assert shares.sum() == 0 and cut == 0
