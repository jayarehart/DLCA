"""Unit tests for the building and energy models in ``dlca.models`` (kept until M4)."""

from dlca.models import (
    BldgDetails,
    BldgUseType,
    ClimateZone,
    ResHeatSystem,
    Scenario,
    USSubgrid,
)


def test_load_eui_and_ef():
    bldg = BldgDetails(
        use_type=BldgUseType.SMALLOFFICE,
        heating_system=ResHeatSystem.NONE,
        climate_zone=ClimateZone._2B,
        eGrid=USSubgrid.RMPA,
        area_m2=15000,
        lifespan=60,
        scenario=Scenario.S1,
    )

    assert bldg.ref_bldg.naturalgas_site_GJ is not None
    assert bldg.ref_bldg.electricity_site_GJ is not None
    assert bldg.ref_bldg.fueloilno2_kBtu is not None

    assert bldg.EF_electricity is not None
    assert bldg.EF_naturalgas is not None
    assert bldg.EF_fueloilno2 is not None
