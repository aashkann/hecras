#!/usr/bin/env python3
"""
Validate assets before processing.
Run this first to ensure DEM and shapefiles are valid.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.validation import validate_asset_dem, validate_asset_shapefiles
from src.config import DEM_PATH, SHAPE_DIR


def main() -> int:
    print("Validating assets...")

    dem_result = validate_asset_dem(DEM_PATH)
    print(f"DEM: {'VALID' if dem_result['valid'] else 'INVALID'}")
    if not dem_result["valid"]:
        print(f"  Error: {dem_result.get('error')}")
        return 1
    print(f"  CRS: {dem_result.get('crs')}")
    print(f"  Shape: {dem_result.get('shape')}")
    print(f"  Bounds: {dem_result.get('bounds')}")

    shp_result = validate_asset_shapefiles(SHAPE_DIR)
    print(f"Shapefiles: {'VALID' if shp_result['valid'] else 'INVALID'}")
    print(f"  Found: {shp_result['count']}")
    print(f"  With CRS: {shp_result['with_crs']}")

    if not shp_result["valid"]:
        if shp_result.get("missing_crs"):
            print(f"  Missing CRS: {', '.join(shp_result['missing_crs'])}")
        return 1

    print("All assets are valid!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
