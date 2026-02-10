#!/usr/bin/env python3
"""
Clip DEM and shapefiles to a buffer around a site for HEC-RAS and QGIS.
- output/           : 200 m buffer (HEC-RAS).
- output/site_100m/ : 100 m buffer, QGIS-ready.
Run validate_assets.py first to check inputs.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import (
    COORD_FILE,
    DEM_PATH,
    SHAPE_DIR,
    OUTPUT_DIR,
    QGIS_100M_DIR,
    BUFFER_200M,
    BUFFER_100M,
)
from src.utils import read_coordinates
from src.validation import (
    validate_inputs,
    validate_dem_output,
    validate_buffer,
    validate_shapefiles,
    validate_qgis_project,
    print_validation_summary,
)
from src.clipping import run_clip
from src.qgis_project import write_qgis_project
import rasterio


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    lat, lon = read_coordinates(COORD_FILE)
    print(f"Site coordinates (WGS84): {lat}, {lon}")

    with rasterio.open(DEM_PATH) as src:
        dem_crs = src.crs
        dem_bounds = src.bounds
    validate_inputs(DEM_PATH, SHAPE_DIR, lat, lon, dem_crs, dem_bounds)

    print("\n--- 200 m buffer (output/) ---")
    run_clip(lat, lon, dem_crs, BUFFER_200M, OUTPUT_DIR, "200m")

    dem_200_path = OUTPUT_DIR / "dem_clipped_200m.tif"
    buffer_200_path = OUTPUT_DIR / "site_buffer_200m.shp"
    results_200m = {
        "dem": validate_dem_output(dem_200_path, BUFFER_200M) if dem_200_path.exists() else {"valid": False},
        "buffer": validate_buffer(buffer_200_path, BUFFER_200M, dem_crs) if buffer_200_path.exists() else {"valid": False},
        "shapefiles": validate_shapefiles(OUTPUT_DIR, "200m"),
    }

    print("\n--- 100 m buffer (output/site_100m/) ---")
    run_clip(lat, lon, dem_crs, BUFFER_100M, QGIS_100M_DIR, "100m")

    dem_100 = QGIS_100M_DIR / "dem_clipped_100m.tif"
    buffer_100_path = QGIS_100M_DIR / "site_buffer_100m.shp"
    shp_100 = sorted(QGIS_100M_DIR.glob("*_clipped_100m.shp"))

    results_100m = {
        "dem": validate_dem_output(dem_100, BUFFER_100M) if dem_100.exists() else {"valid": False},
        "buffer": validate_buffer(buffer_100_path, BUFFER_100M, dem_crs) if buffer_100_path.exists() else {"valid": False},
        "shapefiles": validate_shapefiles(QGIS_100M_DIR, "100m"),
    }

    if dem_100.exists():
        write_qgis_project(
            QGIS_100M_DIR,
            "dem_clipped_100m.tif",
            ["site_buffer_100m.shp"] + [p.name for p in shp_100],
        )
    qgz_path = QGIS_100M_DIR / "site_100m.qgz"
    results_qgis = validate_qgis_project(qgz_path) if qgz_path.exists() else {"valid": False}

    readme = QGIS_100M_DIR / "OPEN_IN_QGIS.txt"
    readme.write_text(
        "Site 100 m radius – open in QGIS\n"
        "================================\n\n"
        "Double-click:  site_100m.qgz   (opens QGIS with all layers loaded)\n\n"
        "Or in QGIS: Layer → Add Layer → Add Raster Layer (dem_clipped_100m.tif)\n"
        "            Layer → Add Layer → Add Vector Layer (any .shp in this folder)\n",
        encoding="utf-8",
    )
    print(f"Instructions written: {readme}")

    print_validation_summary(
        OUTPUT_DIR,
        QGIS_100M_DIR,
        lat,
        lon,
        dem_crs,
        results_200m,
        results_100m,
        results_qgis,
    )


if __name__ == "__main__":
    main()
