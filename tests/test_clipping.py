"""Clipping output validation tests."""
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import OUTPUT_DIR, QGIS_100M_DIR, DEM_PATH, BUFFER_200M, BUFFER_100M
from src.validation import validate_dem_output, validate_buffer, validate_shapefiles
import rasterio


@pytest.fixture(scope="module")
def dem_crs():
    """DEM CRS for buffer validation."""
    with rasterio.open(DEM_PATH) as src:
        yield src.crs


def test_200m_dem_output_exists():
    """200m clipped DEM file exists after running main script."""
    dem_path = OUTPUT_DIR / "dem_clipped_200m.tif"
    if not dem_path.exists():
        pytest.skip("Run clip_for_hecras.py first to generate output")
    result = validate_dem_output(dem_path, BUFFER_200M)
    assert result["valid"], "200m DEM output invalid"
    assert result["has_data"]


def test_200m_buffer_valid(dem_crs):
    """200m buffer has valid geometry and radius."""
    buffer_path = OUTPUT_DIR / "site_buffer_200m.shp"
    if not buffer_path.exists():
        pytest.skip("Run clip_for_hecras.py first")
    result = validate_buffer(buffer_path, BUFFER_200M, dem_crs)
    assert result["valid"]
    assert result["radius_diff"] < 5


def test_100m_dem_output_exists():
    """100m clipped DEM exists."""
    dem_path = QGIS_100M_DIR / "dem_clipped_100m.tif"
    if not dem_path.exists():
        pytest.skip("Run clip_for_hecras.py first")
    result = validate_dem_output(dem_path, BUFFER_100M)
    assert result["valid"]
    assert result["has_data"]


def test_100m_buffer_radius(dem_crs):
    """100m buffer has correct radius."""
    buffer_path = QGIS_100M_DIR / "site_buffer_100m.shp"
    if not buffer_path.exists():
        pytest.skip("Run clip_for_hecras.py first")
    result = validate_buffer(buffer_path, BUFFER_100M, dem_crs)
    assert result["valid"]
    assert result["radius_diff"] < 5


def test_200m_shapefiles_count():
    """200m output has expected shapefiles."""
    result = validate_shapefiles(OUTPUT_DIR, "200m")
    assert result["total"] > 0, "No clipped shapefiles found"


def test_100m_shapefiles_count():
    """100m output has expected shapefiles."""
    result = validate_shapefiles(QGIS_100M_DIR, "100m")
    assert result["total"] > 0
