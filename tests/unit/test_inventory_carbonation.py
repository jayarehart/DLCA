"""Concrete carbonation (#74, decisions K1-K8, Jay 2026-11-20; record 0017).

Every expected value here comes from outside the code, written down before it
ran:

- Lagerblad, B. (2005), CBI report 2:2005. Table 2 k values [mm / sqrt(yr)]
  for CEM I bare concrete: indoors 15 / 9 / 6 / 3.5, sheltered 10 / 6 / 4 /
  2.5, exposed 5 / 2.5 / 1.5 / 1 (strength <15, 15-25, 25-35, >35 MPa).
  Table 3 cover: indoor house x 0.7, outdoor house x 0.9. §5.1.5: uptake
  = 0.75 x C x CaO x M(CO2) / M(CaO). §5.3.2 worked examples (hollow core
  slab, cast-in-situ floor).
- Andersson, R. et al. (2013), Environ. Sci. Technol. 47, 11625, roof tiles:
  k_V(11.5) = (1 / 0.0017) x (0.8 x 0.9 x 0.2 + 1.5 x 0.8 x 0.15) / 1000
  x sqrt(11.5) = 0.646 (printed).
- Closed form, one face below full depth: U(t) = A k sqrt(t) / 1000 x DoC x
  C x CaO x 44.01 / 56.077.
- Sphere share after t years: 1 - ((r - d) / r)^3, d = k sqrt(t), capped at 1.

Faults these catch that no other test does: t in place of sqrt(t); a wrong
Table 2 cell or cover factor; the 0.75, the CaO share or the molar ratio left
out; mm read as m; uptake in the wrong years (year 0, or past RSP); no cap at
the volume; end-of-life uptake on the whole volume instead of the
uncarbonated remainder; a B4 event that does not restart the clock or leaves
the old item running; carbonation accepted under schema version 2.
"""

import math
import warnings

import numpy as np
import pytest
from pydantic import ValidationError

from dlca.climate import EMISSION_KEYS
from dlca.inventory import (
    BuildingInventory,
    BuildingResult,
    BuildingTotals,
    CarbonationWarning,
    Timeline,
    assess_building,
    timeline,
)
from dlca.inventory.carbonation import carbonated_volume, depth, in_use_volume, k_value
from dlca.inventory.schema import Carbonation

USE = "carbonation-uptake"
EOL = "carbonation-eol"
CO2_PER_CAO = 44.01 / 56.077  # molar masses, IUPAC


def carbonation(**fields):
    c = {
        "strength_class": "25-35",
        "cement": 300.0,
        "surfaces": [{"area": 2.5, "exposure": "indoors", "cover": "none"}],
        "end_of_life": {"radius": 10.0},
    }
    c.update(fields)
    return c


def inventory(study_period=50, schema_version=3, **material):
    m = {"name": "Slab", "quantity": 3.0, "unit": "m3", **material}
    return BuildingInventory.model_validate(
        {
            "schema": "dlca.building_inventory",
            "schema_version": schema_version,
            "name": "Hand case",
            "study_period": study_period,
            "assemblies": [{"name": "Floor", "materials": [m]}],
        }
    )


def part(t: Timeline, module):
    return t.parts[("Floor", "Slab", module)]["co2"]


# --- Lagerblad's tables and worked examples --------------------------------------


def test_k_values_match_lagerblad_section_5_2():
    """§5.2 lists, for C30 with CEM II/L (x 1.05): indoor 6 x 0.7 x 1.05,
    sheltered 4 x 0.9 x 1.05, exposed 1.5 x 0.9 x 1.05."""
    assert k_value("indoors", "25-35", "indoor_house", 1.05) == pytest.approx(6 * 0.7 * 1.05)
    assert k_value("sheltered", "25-35", "outdoor_house", 1.05) == pytest.approx(4 * 0.9 * 1.05)
    assert k_value("exposed", "25-35", "outdoor_house", 1.05) == pytest.approx(1.5 * 0.9 * 1.05)


@pytest.mark.parametrize(
    ("exposure", "row"),
    [
        ("wet", (2, 1.0, 0.75, 0.5)),
        ("buried", (3, 1.5, 1.0, 0.75)),
        ("exposed", (5, 2.5, 1.5, 1)),
        ("sheltered", (10, 6, 4, 2.5)),
        ("indoors", (15, 9, 6, 3.5)),
    ],
)
def test_k_table_is_lagerblad_table_2(exposure, row):
    for strength, k in zip(("<15", "15-25", "25-35", ">35"), row, strict=True):
        assert k_value(exposure, strength, "none") == k


def test_lagerblad_cast_in_situ_floor():
    """§5.3.2: 13.2 m2 per m3, k = 6 x 0.7 x 1.1 (~4.6), 50 years, 298 kg
    Portland cement, 65 % CaO. Text: "around 32 mm", "0.43 m3", "128 kg CEM I",
    "around 83 kg CaO". He states the CaO before the 0.75 of §5.1.5; with it,
    0.75 x 83 kg is carbonated."""
    c = Carbonation.model_validate(
        carbonation(
            cement=298.0,
            binder_factor=1.1,
            surfaces=[{"area": 13.2, "exposure": "indoors", "cover": "indoor_house"}],
        )
    )
    k = k_value("indoors", "25-35", "indoor_house", 1.1)
    assert abs(float(depth(k, 50)) - 32) <= 1.0  # 32.7 with k = 4.62, 32.5 with 4.6
    volume = float(in_use_volume(c, 1.0, 50))
    assert abs(volume - 0.43) <= 0.005
    assert abs(volume * 298 - 128) <= 1.0
    assert abs(volume * 298 * 0.65 - 83) <= 1.0
    # CO2 from §5.1.5 by hand: 0.75 x 298 x 0.65 x 44.01 / 56.077 kg per m3
    # carbonated, times the volume above. Timeline: 1 m3, years 1..50.
    t = timeline(inventory(quantity=1.0, carbonation=c.model_dump()), horizon=5)
    expected = 0.75 * 298 * 0.65 * 44.01 / 56.077 * (13.2 * 6 * 0.7 * 1.1 * math.sqrt(50) / 1000)
    assert -part(t, USE).sum() == pytest.approx(expected, rel=1e-12)
    assert abs(-part(t, USE).sum() - 0.75 * 83 * CO2_PER_CAO) <= 1.0


def test_lagerblad_hollow_core_slab():
    """§5.3.2: 9.6 m2 per m3, k ~4.6, 50 years: "0.31 m3", "95 kg" of
    Portland cement (of 306 kg/m3) and, with 0.75 and 65 %, "46 kg" CaO."""
    c = Carbonation.model_validate(
        carbonation(
            cement=306.0,
            binder_factor=1.1,
            surfaces=[{"area": 9.6, "exposure": "indoors", "cover": "indoor_house"}],
        )
    )
    volume = float(in_use_volume(c, 1.0, 50))
    assert abs(volume - 0.31) <= 0.005
    assert abs(volume * 306 - 95) <= 1.5
    assert abs(0.75 * 0.65 * volume * 306 - 46) <= 1.0


def test_andersson_roof_tiles_k_v():
    """Andersson et al. (2013), eq. 2 example: tile 0.0017 m3, 0.2 m2 exposed
    (k 0.8, degree 0.90) and 0.15 m2 sheltered (k 1.5, degree 0.80): k_V(11.5)
    = 0.646. Their k come from their ref. 17, not Table 2, so the volume
    function takes them directly; the per-surface degree is applied here,
    since the schema has one degree per material."""
    exposed = float(carbonated_volume([0.2], [0.8], 11.5, 0.0017))
    sheltered = float(carbonated_volume([0.15], [1.5], 11.5, 0.0017))
    k_v = (0.9 * exposed + 0.8 * sheltered) / 0.0017
    assert round(k_v, 3) == 0.646


# --- Closed form and placement ---------------------------------------------------


def test_closed_form_one_face_every_year():
    """One indoor face, 2.5 m2 per m3, C30 bare: k = 6. 3 m3. Depth at 50
    years is 42 mm, far below the cap. Cumulative uptake through year t is
    3 x 2.5 x 6 x sqrt(t) / 1000 x 0.75 x 300 x 0.65 x 44.01 / 56.077."""
    t = timeline(inventory(carbonation=carbonation()), horizon=5)
    co2 = part(t, USE)
    assert co2[0] == 0
    assert not np.any(co2[51:])
    cumulative = -np.cumsum(co2)
    for year in range(1, 51):
        expected = 3 * 2.5 * 6 * math.sqrt(year) / 1000 * 0.75 * 300 * 0.65 * 44.01 / 56.077
        assert cumulative[year] == pytest.approx(expected, rel=1e-12), year
    assert np.all(co2[1:51] < 0)
    for gas in ("ch4", "ch4_fossil", "n2o"):
        assert not np.any(t.parts[("Floor", "Slab", USE)][gas])


def test_inputs_scale_as_the_formula_says():
    """Degree, CaO share, binder factor and cover enter as factors."""
    base = -part(timeline(inventory(carbonation=carbonation()), horizon=5), USE).sum()
    changed = carbonation(
        degree_of_carbonation=0.9,
        cao_share=0.6,
        binder_factor=1.2,
        surfaces=[{"area": 2.5, "exposure": "indoors", "cover": "indoor_house"}],
    )
    other = -part(timeline(inventory(carbonation=changed), horizon=5), USE).sum()
    assert other == pytest.approx(base * (0.9 / 0.75) * (0.6 / 0.65) * 1.2 * 0.7, rel=1e-12)


def test_volume_cap_for_a_thin_element():
    """Unit m2, 0.1 m3 per m2, both faces indoors at <15 MPa (k = 15): the
    sum of area x depth reaches 0.1 m3 at sqrt(t) = 0.1 x 1000 / 30, about
    11.1 years, so year 12 (t from 11 to 12) has the last increment. From then
    on nothing more is taken up, and the total is the
    full-volume maximum 0.1 x 0.75 x 300 x 0.65 x 44.01 / 56.077 per m2."""
    c = carbonation(
        strength_class="<15",
        volume=0.1,
        surfaces=[
            {"area": 1.0, "exposure": "indoors", "cover": "none"},
            {"area": 1.0, "exposure": "indoors", "cover": "none"},
        ],
    )
    t = timeline(inventory(quantity=1.0, unit="m2", carbonation=c), horizon=5)
    co2 = part(t, USE)
    maximum = 0.1 * 0.75 * 300 * 0.65 * 44.01 / 56.077
    assert -co2.sum() == pytest.approx(maximum, rel=1e-12)
    assert np.all(co2[13:] == 0)
    assert co2[12] < 0
    assert not np.any(part(t, EOL))  # nothing left to crush


def test_end_of_life_stockpile_one_year():
    """RSP 50. In use: 2.5 m2 x 6 x sqrt(50) / 1000 = 0.10607 m3 per m3
    carbonated, so 0.89393 m3 is crushed in year 51 into 10 mm spheres,
    exposed C30 (k 1.5): d(1) = 1.5 mm, share 1 - 0.85^3 = 0.385875."""
    t = timeline(inventory(carbonation=carbonation()), horizon=5)
    co2 = part(t, EOL)
    remaining = 1 - 2.5 * 6 * math.sqrt(50) / 1000
    expected = 3 * remaining * 0.385875 * 0.75 * 300 * 0.65 * 44.01 / 56.077
    assert -co2[51] == pytest.approx(expected, rel=1e-12)
    assert np.flatnonzero(co2).tolist() == [51]


def test_end_of_life_stockpile_three_years_and_binder_factor():
    """n = 3, binder factor 1.1 (applies to the stockpile k too, no cover
    factor): d(j) = 1.5 x 1.1 x sqrt(j); yearly f(j + 1) - f(j) in years
    51, 52, 53."""
    c = carbonation(
        binder_factor=1.1,
        end_of_life={"radius": 10.0, "years": 3},
        surfaces=[{"area": 2.5, "exposure": "indoors", "cover": "indoor_house"}],
    )
    co2 = part(timeline(inventory(carbonation=c), horizon=5), EOL)
    remaining = 1 - 2.5 * 6 * 0.7 * 1.1 * math.sqrt(50) / 1000
    f = [1 - (1 - 1.65 * math.sqrt(j) / 10) ** 3 for j in range(4)]
    a = 0.75 * 300 * 0.65 * 44.01 / 56.077
    for j in range(3):
        assert -co2[51 + j] == pytest.approx(3 * a * remaining * (f[j + 1] - f[j]), rel=1e-12)
    assert np.flatnonzero(co2).tolist() == [51, 52, 53]


def test_sphere_fully_carbonated_is_capped():
    """1 mm spheres, k 1.5: d(1) = 1.5 mm > r, so the whole remainder
    carbonates in year RSP + 1 and nothing after."""
    c = carbonation(end_of_life={"radius": 1.0, "years": 4})
    co2 = part(timeline(inventory(carbonation=c), horizon=5), EOL)
    remaining = 1 - 2.5 * 6 * math.sqrt(50) / 1000
    assert -co2[51] == pytest.approx(3 * remaining * 0.75 * 300 * 0.65 * CO2_PER_CAO, rel=1e-12)
    assert np.flatnonzero(co2).tolist() == [51]


def test_stockpile_past_the_series_end_is_cut_and_warned():
    c = carbonation(end_of_life={"radius": 50.0, "years": 20})
    with pytest.warns(CarbonationWarning, match="after the series end"):
        t = timeline(inventory(study_period=10, carbonation=c), horizon=3)  # years 0..14
    assert np.flatnonzero(part(t, EOL)).tolist() == [11, 12, 13, 14]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        timeline(inventory(study_period=10, carbonation=c), horizon=3, years=31)


# --- Replacements (K5) -----------------------------------------------------------


def test_b4_with_carbonation_restarts_the_clock():
    """Own item cast in year 0 (k 6), B4 in year 20 with a new item (cement
    350). Old: increments in years 1..20, so U_old(20); year 20 holds only its
    last increment, U_old(20) - U_old(19) (Jay, PR #77). New: years 21..50, so
    U_new(30). Crushed at the end: the new item at age 30."""
    new = carbonation(cement=350.0)
    t = timeline(
        inventory(
            carbonation=carbonation(),
            b4=[{"year": 20, "amounts": {"co2": 400.0}, "carbonation": new}],
        ),
        horizon=5,
    )
    co2 = part(t, USE)
    per_m3 = 2.5 * 6 / 1000 * 0.75 * 0.65 * CO2_PER_CAO  # per kg cement per sqrt(yr)
    assert -co2[1:21].sum() == pytest.approx(3 * per_m3 * 300 * math.sqrt(20), rel=1e-12)
    old_last = 3 * per_m3 * 300 * (math.sqrt(20) - math.sqrt(19))
    assert -co2[20] == pytest.approx(old_last, rel=1e-12)
    assert -co2[21:51].sum() == pytest.approx(3 * per_m3 * 350 * math.sqrt(30), rel=1e-12)
    assert -co2[21] == pytest.approx(3 * per_m3 * 350, rel=1e-12)  # age 1 again
    remaining = 1 - 2.5 * 6 * math.sqrt(30) / 1000
    eol = 3 * remaining * 0.385875 * 0.75 * 350 * 0.65 * CO2_PER_CAO
    assert -part(t, EOL)[51] == pytest.approx(eol, rel=1e-12)


def test_b4_carbonation_without_own_starts_at_the_event():
    t = timeline(
        inventory(b4=[{"year": 30, "amounts": {"co2": 1.0}, "carbonation": carbonation()}]),
        horizon=5,
    )
    co2 = part(t, USE)
    assert np.flatnonzero(co2).tolist() == list(range(31, 51))


def test_b4_without_carbonation_warns_and_keeps_the_clock():
    with pytest.warns(CarbonationWarning, match="year 20 has no carbonation"):
        t = timeline(
            inventory(carbonation=carbonation(), b4=[{"year": 20, "amounts": {"co2": 1.0}}]),
            horizon=5,
        )
    base = timeline(inventory(carbonation=carbonation()), horizon=5)
    np.testing.assert_array_equal(part(t, USE), part(base, USE))


# --- No input, no change ---------------------------------------------------------


def test_no_carbonation_changes_nothing_and_positive_control():
    """Without `carbonation` there are no carbonation parts, and every part is
    identical between a schema version 2 and a version 3 file. The same
    comparison sees the uptake once it is added. Both runs use this code, so
    this cannot show that nothing changed from before #74. That was checked
    once against main by hashing the example files' timeline and result JSON
    (recorded in the PR)."""
    fields = {"modules": {"A1-A3": {"co2": 300.0}, "C3": {"co2": 5.0}}}
    base = timeline(inventory(schema_version=2, **fields), horizon=20)
    v3 = timeline(inventory(**fields), horizon=20)
    with_c = timeline(inventory(carbonation=carbonation(), **fields), horizon=20)
    assert list(v3.parts) == list(base.parts)
    for key in base.parts:
        for gas in EMISSION_KEYS:
            np.testing.assert_array_equal(v3.parts[key][gas], base.parts[key][gas], strict=True)
    assert not np.array_equal(with_c.emissions()["co2"], base.emissions()["co2"])
    assert {m for (_, _, m) in with_c.parts} - {m for (_, _, m) in base.parts} == {USE, EOL}


# --- Schema ----------------------------------------------------------------------


@pytest.mark.parametrize("version", [1, 2])
def test_carbonation_refused_before_schema_version_3(version):
    with pytest.raises(ValidationError, match="schema_version 3"):
        inventory(schema_version=version, carbonation=carbonation())
    with pytest.raises(ValidationError, match="schema_version 3"):
        inventory(
            schema_version=version,
            b4=[{"year": 5, "amounts": {}, "carbonation": carbonation()}],
        )
    assert inventory(schema_version=version).schema_version == version


@pytest.mark.parametrize(
    ("material", "match"),
    [
        ({"carbonation": carbonation(volume=1.0)}, "may not be given"),
        ({"unit": "m2", "carbonation": carbonation()}, "needs a volume"),
        ({"b5": [{"year": 5, "amounts": {}, "carbonation": carbonation()}]}, "B4 events only"),
        (
            {
                "b4": [
                    {"year": 5, "amounts": {}, "carbonation": carbonation()},
                    {"year": 5, "amounts": {}, "carbonation": carbonation()},
                ]
            },
            "more than one",
        ),
        ({"carbonation": carbonation(surfaces=[])}, "surfaces"),
        ({"carbonation": carbonation(end_of_life={})}, "radius"),
        ({"carbonation": carbonation(end_of_life={"radius": 0.0})}, "radius"),
        ({"carbonation": carbonation(strength_class="C30")}, "strength_class"),
        ({"carbonation": carbonation(binder_factor=0.9)}, "binder_factor"),
        ({"carbonation": carbonation(degree_of_carbonation=1.1)}, "degree_of_carbonation"),
        (
            {"carbonation": carbonation(surfaces=[{"area": 1.0, "exposure": "indoors"}])},
            "cover",
        ),
    ],
)
def test_bad_carbonation_input_refused(material, match):
    with pytest.raises(ValidationError, match=match):
        inventory(**material)


def test_carbonation_refused_on_building_totals_events():
    with pytest.raises(ValidationError, match="BuildingTotals"):
        BuildingTotals.model_validate(
            {
                "schema": "dlca.building_totals",
                "name": "T",
                "study_period": 10,
                "b4": [{"year": 5, "amounts": {}, "carbonation": carbonation()}],
            }
        )


def test_dump_round_trip_and_unset_fields_left_out():
    b = inventory(carbonation=carbonation())
    dumped = b.model_dump()
    material = dumped["assemblies"][0]["materials"][0]
    assert "volume" not in material["carbonation"]
    assert material["carbonation"]["degree_of_carbonation"] == 0.75
    assert BuildingInventory.model_validate(dumped) == b
    assert "carbonation" not in inventory().model_dump()["assemblies"][0]["materials"][0]


def test_result_json_round_trip_with_carbonation_rows():
    fields = {"modules": {"C4": {"co2": 1.0}}, "per_year": {"B1": {"co2": 0.1}}}
    r = assess_building(inventory(carbonation=carbonation(), **fields), horizon=100)
    d = r.to_dict()
    assert d["schema_version"] == 5
    assert list(r.by_module) == ["B1", USE, "C4", EOL]
    back = BuildingResult.from_dict(d)
    assert list(back.by_module) == list(r.by_module)
    t = timeline(inventory(carbonation=carbonation()), horizon=20)
    again = Timeline.from_dict(t.to_dict())
    np.testing.assert_array_equal(
        again.parts[("Floor", "Slab", EOL)]["co2"], part(t, EOL), strict=True
    )
