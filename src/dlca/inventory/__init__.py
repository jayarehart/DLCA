"""Building inventory input (record 0013), its timing (record 0014), roll-up (record 0015)
biogenic carbon (#73), concrete carbonation (#74), emission-factor trajectories (#81) and
operational energy (#82)."""

from dlca.inventory.aggregate import (
    BUILDING_RESULT_SCHEMA,
    BUILDING_RESULT_SCHEMA_VERSION,
    BuildingResult,
    Metrics,
    assess_building,
)
from dlca.inventory.biogenic import (
    UPTAKE_MODULE,
    BiogenicBalance,
    BiogenicCarbonWarning,
    biogenic_balance,
)
from dlca.inventory.carbonation import EOL_MODULE as CARBONATION_EOL_MODULE
from dlca.inventory.carbonation import UPTAKE_MODULE as CARBONATION_UPTAKE_MODULE
from dlca.inventory.carbonation import CarbonationWarning
from dlca.inventory.operational import to_study_years
from dlca.inventory.schema import (
    INVENTORY_TAG,
    SCHEMA_VERSION,
    TOTALS_TAG,
    Assembly,
    Biogenic,
    BuildingInventory,
    BuildingTotals,
    Carbonation,
    ConstantTrajectory,
    EnergyUse,
    Event,
    GasAmounts,
    LinearTrajectory,
    Material,
    SeriesTrajectory,
    Stockpile,
    Surface,
    Trajectory,
)
from dlca.inventory.timing import TIMELINE_SCHEMA, TIMELINE_SCHEMA_VERSION, Timeline, timeline

__all__ = [
    "BUILDING_RESULT_SCHEMA",
    "BUILDING_RESULT_SCHEMA_VERSION",
    "CARBONATION_EOL_MODULE",
    "CARBONATION_UPTAKE_MODULE",
    "INVENTORY_TAG",
    "SCHEMA_VERSION",
    "TIMELINE_SCHEMA",
    "TIMELINE_SCHEMA_VERSION",
    "TOTALS_TAG",
    "UPTAKE_MODULE",
    "Assembly",
    "Biogenic",
    "BiogenicBalance",
    "BiogenicCarbonWarning",
    "BuildingResult",
    "BuildingInventory",
    "BuildingTotals",
    "Carbonation",
    "CarbonationWarning",
    "ConstantTrajectory",
    "EnergyUse",
    "Event",
    "GasAmounts",
    "LinearTrajectory",
    "Material",
    "Metrics",
    "SeriesTrajectory",
    "Stockpile",
    "Surface",
    "Timeline",
    "Trajectory",
    "assess_building",
    "biogenic_balance",
    "timeline",
    "to_study_years",
]
