"""Asset validation tests."""
import pytest
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.validation import validate_asset_dem, validate_asset_shapefiles
from src.config import DEM_PATH, SHAPE_DIR


def test_dem_exists():
    """DEM file exists and is readable."""
    assert DEM_PATH.exists(), f"DEM not found: {DEM_PATH}"


def test_dem_has_crs():
    """DEM has a valid CRS."""
    result = validate_asset_dem(DEM_PATH)
    assert result["valid"], result.get("error", "DEM validation failed")
    assert result.get("crs") is not None


def test_dem_has_data():
    """DEM contains elevation data."""
    result = validate_asset_dem(DEM_PATH)
    assert result["valid"]
    assert result.get("has_data", False), "DEM has no data"


def test_shapefiles_dir_exists():
    """Shapefile directory exists."""
    assert SHAPE_DIR.exists(), f"Shape directory not found: {SHAPE_DIR}"


def test_shapefiles_have_crs():
    """All shapefiles have CRS defined."""
    result = validate_asset_shapefiles(SHAPE_DIR)
    assert result["valid"], f"Shapefiles missing CRS: {result.get('missing_crs', [])}"
    assert result["with_crs"] == result["count"]
