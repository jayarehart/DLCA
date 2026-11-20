"""Invariants of concrete carbonation (#74, K8).

- The carbonated volume is never more than the volume, for any surfaces, k
  and t.
- Cumulative in-use uptake never decreases (no negative yearly increment),
  and below the cap it is proportional to sqrt(t).
- The sphere share is in [0, 1] and never decreases.
- In-use plus stockpile uptake never exceeds the full-volume maximum
  DoC x C x CaO x 44.01 / 56.077 x volume.

Faults these catch that the hand cases do not: the legacy volume formula
without its clip, whose carbonated volume goes down once the depth passes half
the width; a cap that works for one surface but not for several; a sphere
share above 1 for depths past the radius; crushing the whole volume at end of
life instead of the uncarbonated remainder.
"""

import math

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from dlca.inventory.carbonation import (
    CO2_PER_CAO,
    carbonated_volume,
    cumulative_uptake,
    eol_increments,
    in_use_increments,
    sphere_share,
)
from dlca.inventory.schema import Carbonation

areas = st.lists(st.floats(0.01, 50.0), min_size=1, max_size=5)
ks = st.floats(0.1, 20.0)
volumes = st.floats(0.001, 2.0)
exposures = st.sampled_from(["indoors", "sheltered", "exposed", "wet", "buried"])
covers = st.sampled_from(["none", "indoor_house", "outdoor_house"])
strengths = st.sampled_from(["<15", "15-25", "25-35", ">35"])


@st.composite
def carbonations(draw):
    n = draw(st.integers(1, 4))
    return Carbonation.model_validate(
        {
            "strength_class": draw(strengths),
            "cement": draw(st.floats(50.0, 600.0)),
            "cao_share": draw(st.floats(0.3, 1.0)),
            "binder_factor": draw(st.floats(1.0, 1.5)),
            "degree_of_carbonation": draw(st.floats(0.1, 1.0)),
            "surfaces": [
                {
                    "area": draw(st.floats(0.01, 50.0)),
                    "exposure": draw(exposures),
                    "cover": draw(covers),
                }
                for _ in range(n)
            ],
            "end_of_life": {
                "radius": draw(st.floats(0.5, 200.0)),
                "years": draw(st.integers(1, 30)),
            },
        }
    )


@settings(max_examples=200, deadline=None)
@given(a=areas, k=ks, volume=volumes)
def test_carbonated_volume_never_exceeds_the_volume_and_never_decreases(a, k, volume):
    t = np.arange(0, 400)
    v = carbonated_volume(a, [k] * len(a), t, volume)
    assert np.all(v <= volume)
    assert np.all(np.diff(v) >= 0)


@settings(max_examples=200, deadline=None)
@given(c=carbonations(), volume=volumes, years=st.integers(1, 300))
def test_cumulative_uptake_never_decreases_and_is_bounded(c, volume, years):
    increments = in_use_increments(c, volume, years)
    assert increments.shape == (years,)
    assert np.all(increments >= 0)
    maximum = c.degree_of_carbonation * c.cement * c.cao_share * CO2_PER_CAO * volume
    total = increments.sum() + eol_increments(c, volume, years).sum()
    assert total <= maximum * (1 + 1e-12)


@settings(max_examples=200, deadline=None)
@given(c=carbonations(), t=st.floats(0.0, 400.0))
def test_below_the_cap_uptake_is_proportional_to_sqrt_t(c, t):
    huge = 1e9  # no cap
    one = float(cumulative_uptake(c, huge, 1.0))
    assert math.isclose(float(cumulative_uptake(c, huge, t)), one * math.sqrt(t), rel_tol=1e-12)


@settings(max_examples=200, deadline=None)
@given(radius=st.floats(0.01, 500.0), k=ks)
def test_sphere_share_is_a_share_and_never_decreases(radius, k):
    f = sphere_share(radius, k, np.arange(0, 200))
    assert f[0] == 0
    assert np.all((f >= 0) & (f <= 1))
    assert np.all(np.diff(f) >= 0)
