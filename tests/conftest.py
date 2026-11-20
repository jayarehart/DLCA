"""Shared pytest fixtures."""

from pathlib import Path

import pytest

from dlca.inventory import BuildingInventory, BuildingTotals

INVENTORY_DIR = Path(__file__).resolve().parent / "data" / "inventories"
"""Illustrative example inventories (#60); see the README there."""

EXAMPLE_INVENTORY_NAMES = ("timber", "steel", "concrete")


def load_example_inventory(name: str) -> BuildingInventory:
    """Load `tests/data/inventories/<name>.json` with the model (validated)."""
    text = (INVENTORY_DIR / f"{name}.json").read_text(encoding="utf-8")
    return BuildingInventory.model_validate_json(text)


def load_example_totals() -> BuildingTotals:
    """Load `tests/data/inventories/totals.json` with the model (validated)."""
    text = (INVENTORY_DIR / "totals.json").read_text(encoding="utf-8")
    return BuildingTotals.model_validate_json(text)


@pytest.fixture(scope="session")
def example_inventory_dir() -> Path:
    """The folder holding the example JSON files."""
    return INVENTORY_DIR


@pytest.fixture(scope="session")
def example_inventories() -> dict[str, BuildingInventory]:
    """The three illustrative inventories, by name: timber, steel, concrete."""
    return {name: load_example_inventory(name) for name in EXAMPLE_INVENTORY_NAMES}


@pytest.fixture(scope="session")
def example_totals() -> BuildingTotals:
    """The illustrative whole-building `BuildingTotals` example."""
    return load_example_totals()
