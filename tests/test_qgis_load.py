"""
Test that QGIS can actually open and load the project.
Requires: QGIS Python API (qgis.core).
Run with: python -m pytest tests/test_qgis_load.py -v
"""
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from qgis.core import QgsProject, QgsApplication
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False


@pytest.mark.skipif(not HAS_QGIS, reason="QGIS Python API not installed")
def test_qgis_project_loads():
    """QGIS can open and load the project."""
    qgs = QgsApplication([], False)
    qgs.initQgis()

    project = QgsProject.instance()
    qgz_path = ROOT / "output" / "site_100m" / "site_100m.qgz"
    if not qgz_path.exists():
        qgs.exitQgis()
        pytest.skip("Run clip_for_hecras.py first to generate site_100m.qgz")

    success = project.read(str(qgz_path))
    assert success, "QGIS failed to load project"

    crs = project.crs()
    assert crs.authid() == "EPSG:6340", f"Expected EPSG:6340, got {crs.authid()}"

    layers = project.mapLayers()
    assert len(layers) > 0, "No layers loaded"

    dem_layers = [l for l in layers.values() if "dem" in l.name().lower()]
    assert len(dem_layers) >= 1, "DEM layer not found"
    assert dem_layers[0].isValid(), "DEM layer invalid"

    qgs.exitQgis()
