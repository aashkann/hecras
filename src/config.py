"""Configuration and paths."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

COORD_FILE = PROJECT_ROOT / "cooridante.txt"
ASSETS_DIR = PROJECT_ROOT / "assets"
# Resolve DEM: use specific file if present, else first .tif in assets
_DEM_GLOB = list(ASSETS_DIR.glob("*.tif")) if ASSETS_DIR.exists() else []
DEM_PATH = ASSETS_DIR / "USGS_OPR_CA_LosAngeles_B23_11SLT033900377900.tif"
if not DEM_PATH.exists() and _DEM_GLOB:
    DEM_PATH = _DEM_GLOB[0]

SHAPE_DIR = ASSETS_DIR / "GOVTUNIT_California_State_Shape" / "Shape"
OUTPUT_DIR = PROJECT_ROOT / "output"
QGIS_100M_DIR = OUTPUT_DIR / "site_100m"

BUFFER_200M = 200
BUFFER_100M = 100
