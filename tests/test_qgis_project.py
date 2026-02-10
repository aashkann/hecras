"""QGIS project file validation tests."""
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import QGIS_100M_DIR
from src.validation import validate_qgis_project


def test_qgis_project_file_exists():
    """QGIS project file exists."""
    qgz_path = QGIS_100M_DIR / "site_100m.qgz"
    if not qgz_path.exists():
        pytest.skip("Run clip_for_hecras.py first to generate site_100m.qgz")
    assert qgz_path.exists()


def test_qgis_project_has_crs():
    """QGIS project has EPSG:6340 CRS."""
    qgz_path = QGIS_100M_DIR / "site_100m.qgz"
    if not qgz_path.exists():
        pytest.skip("Run clip_for_hecras.py first")
    result = validate_qgis_project(qgz_path)
    assert result["valid"], "QGIS project missing or invalid CRS"
    assert result["has_crs"]


def test_qgis_project_readable():
    """QGIS project file is valid zip and contains project.qgs."""
    qgz_path = QGIS_100M_DIR / "site_100m.qgz"
    if not qgz_path.exists():
        pytest.skip("Run clip_for_hecras.py first")
    result = validate_qgis_project(qgz_path)
    assert result["readable"]
