"""Validation: assets, outputs, QGIS project."""
from pathlib import Path
import zipfile

import geopandas as gpd
from pyproj import CRS
from shapely.geometry import Point
import rasterio


def validate_asset_dem(dem_path: Path) -> dict:
    """Validate DEM asset before processing: exists, readable, has CRS and data."""
    if not dem_path.exists():
        return {"valid": False, "error": f"DEM not found: {dem_path}"}
    try:
        with rasterio.open(dem_path) as src:
            data = src.read(1)
            crs = src.crs
            bounds = src.bounds
            shape = src.shape
        if crs is None:
            return {"valid": False, "error": "DEM has no CRS", "crs": None}
        has_data = data.max() > 0 and bool(data.any())
        return {
            "valid": True,
            "crs": crs,
            "bounds": bounds,
            "shape": shape,
            "has_data": has_data,
        }
    except Exception as e:
        return {"valid": False, "error": str(e), "crs": None}


def validate_asset_shapefiles(shape_dir: Path) -> dict:
    """Validate shapefile assets: directory exists, files have CRS."""
    if not shape_dir.exists():
        return {
            "valid": False,
            "count": 0,
            "with_crs": 0,
            "missing_crs": [],
        }
    shp_paths = sorted(shape_dir.glob("*.shp"))
    missing_crs = []
    with_crs = 0
    for p in shp_paths:
        try:
            gdf = gpd.read_file(p)
            if gdf.crs is not None:
                with_crs += 1
            else:
                missing_crs.append(p.name)
        except Exception:
            missing_crs.append(p.name)
    return {
        "valid": len(missing_crs) == 0 and with_crs == len(shp_paths),
        "count": len(shp_paths),
        "with_crs": with_crs,
        "missing_crs": missing_crs,
    }


def validate_dem_output(dem_path: Path, expected_buffer_m: int) -> dict:
    """Validate clipped DEM has data and correct properties."""
    with rasterio.open(dem_path) as src:
        data = src.read(1)
        bounds = src.bounds
        crs = src.crs
    width_m = bounds.right - bounds.left
    height_m = bounds.top - bounds.bottom
    return {
        "valid": data.max() > 0 and dem_path.stat().st_size > 0,
        "shape": (int(data.shape[0]), int(data.shape[1])),
        "bounds": bounds,
        "crs": crs,
        "has_data": bool(data.any()),
        "extent_m": (round(width_m, 2), round(height_m, 2)),
    }


def validate_buffer(buffer_path: Path, expected_radius_m: int, dem_crs) -> dict:
    """Validate buffer geometry and radius."""
    gdf = gpd.read_file(buffer_path)
    geom = gdf.geometry.iloc[0]
    bounds = geom.bounds
    actual_radius_crs = (bounds[2] - bounds[0]) / 2
    units = CRS.from_user_input(dem_crs).axis_info[0].unit_name.lower()
    if "foot" in units or "feet" in units:
        actual_radius_m = actual_radius_crs / 3.28084
    else:
        actual_radius_m = actual_radius_crs
    radius_diff = abs(actual_radius_m - expected_radius_m)
    return {
        "valid": geom.is_valid and radius_diff < 5,
        "expected_radius_m": expected_radius_m,
        "actual_radius_m": round(actual_radius_m, 2),
        "radius_diff": round(radius_diff, 2),
        "crs": gdf.crs,
    }


def validate_shapefiles(out_dir: Path, suffix: str) -> dict:
    """Count shapefiles with/without features."""
    shp_paths = sorted(out_dir.glob(f"*_clipped_{suffix}.shp"))
    with_data = 0
    empty = 0
    for p in shp_paths:
        gdf = gpd.read_file(p)
        if len(gdf) > 0:
            with_data += 1
        else:
            empty += 1
    return {"with_data": with_data, "empty": empty, "total": len(shp_paths)}


def validate_qgis_project(qgz_path: Path) -> dict:
    """Validate QGIS project has correct CRS."""
    with zipfile.ZipFile(qgz_path, "r") as zf:
        # Find the .qgs file inside (could be project.qgs or site_100m.qgs)
        qgs_names = [n for n in zf.namelist() if n.endswith(".qgs")]
        if not qgs_names:
            return {"valid": False, "has_crs": False, "readable": False}
        qgs_content = zf.read(qgs_names[0]).decode("utf-8")
        has_epsg6340 = "EPSG:6340" in qgs_content or "6340" in qgs_content
        has_utm11n = "UTM zone 11N" in qgs_content
    return {
        "valid": has_epsg6340 and has_utm11n,
        "has_crs": has_epsg6340,
        "readable": True,
    }


def validate_generated_files(
    output_dir: Path,
    qgis_100m_dir: Path,
    qgz_path: Path,
) -> dict:
    """
    Validate all generated files exist and are readable before opening in QGIS.
    Returns dict with valid, missing list, and details.
    """
    import re
    missing = []
    errors = []

    # Required 200m outputs
    dem_200 = output_dir / "dem_clipped_200m.tif"
    buf_200 = output_dir / "site_buffer_200m.shp"
    for p in (dem_200, buf_200):
        if not p.exists():
            missing.append(str(p))
        elif p.suffix == ".tif":
            try:
                with rasterio.open(p) as src:
                    if src.read(1).max() == 0:
                        errors.append(f"{p.name}: no data")
            except Exception as e:
                errors.append(f"{p.name}: {e}")
        elif p.suffix == ".shp":
            try:
                gpd.read_file(p)
            except Exception as e:
                errors.append(f"{p.name}: {e}")

    # Required 100m outputs (used by QGIS project)
    dem_100 = qgis_100m_dir / "dem_clipped_100m.tif"
    buf_100 = qgis_100m_dir / "site_buffer_100m.shp"
    for p in (dem_100, buf_100):
        if not p.exists():
            missing.append(str(p))
        elif p.suffix == ".tif":
            try:
                with rasterio.open(p) as src:
                    if src.read(1).max() == 0:
                        errors.append(f"{p.name}: no data")
            except Exception as e:
                errors.append(f"{p.name}: {e}")
        elif p.suffix == ".shp":
            try:
                gpd.read_file(p)
            except Exception as e:
                errors.append(f"{p.name}: {e}")

    # Layers referenced in QGIS project must exist
    if qgz_path.exists():
        try:
            with zipfile.ZipFile(qgz_path, "r") as zf:
                qgs_names = [n for n in zf.namelist() if n.endswith(".qgs")]
                if not qgs_names:
                    errors.append("QGIS project: no .qgs file found in archive")
                qgs_content = zf.read(qgs_names[0]).decode("utf-8") if qgs_names else ""
            # <datasource>filename</datasource>
            for m in re.finditer(r"<datasource>([^<]+)</datasource>", qgs_content):
                layer_path = qgis_100m_dir / m.group(1).strip()
                if not layer_path.exists():
                    missing.append(str(layer_path))
        except Exception as e:
            errors.append(f"QGIS project: {e}")

    return {
        "valid": len(missing) == 0 and len(errors) == 0,
        "missing": missing,
        "errors": errors,
    }


def validate_inputs(dem_path: Path, shape_dir: Path, lat: float, lon: float, dem_crs, dem_bounds) -> None:
    """Validate inputs and site within DEM; raise on failure."""
    if not dem_path.exists():
        raise FileNotFoundError(f"DEM not found: {dem_path}")
    if not shape_dir.exists():
        raise FileNotFoundError(f"Shapefile directory not found: {shape_dir}")
    if dem_crs is None:
        raise ValueError("DEM has no CRS. Define it before buffering/clipping.")
    site_wgs84 = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")
    site_proj = site_wgs84.to_crs(dem_crs)
    site_x = site_proj.x.iloc[0]
    site_y = site_proj.y.iloc[0]
    if not (dem_bounds.left <= site_x <= dem_bounds.right and dem_bounds.bottom <= site_y <= dem_bounds.top):
        raise ValueError(
            f"Site ({site_x:.0f}, {site_y:.0f}) is outside DEM bounds "
            f"({dem_bounds.left:.0f}-{dem_bounds.right:.0f}, {dem_bounds.bottom:.0f}-{dem_bounds.top:.0f})."
        )


def print_validation_summary(
    output_dir: Path,
    qgis_100m_dir: Path,
    lat: float,
    lon: float,
    dem_crs,
    results_200m: dict,
    results_100m: dict,
    results_qgis: dict,
) -> None:
    """Print validation summary report."""
    crs_desc = "NAD83(2011) / UTM zone 11N (EPSG:6340)" if dem_crs and "6340" in str(dem_crs) else str(dem_crs)
    print("\n" + "=" * 50)
    print("VALIDATION SUMMARY")
    print("=" * 50)
    print(f"Site: {lat}, {lon}")
    print(f"DEM CRS: {crs_desc}")
    print()
    print("200m Output:")
    r2 = results_200m
    dem_ok = r2["dem"].get("valid", False)
    buf_ok = r2["buffer"].get("valid", False)
    shp = r2["shapefiles"]
    print(f"  {'✓' if dem_ok else '✗'} DEM: {'Valid' if dem_ok else 'INVALID'}" + (f" ({r2['dem'].get('shape', (0, 0))[0]}x{r2['dem'].get('shape', (0, 0))[1]} pixels, ~{r2['dem'].get('extent_m', (0, 0))[0]:.0f}m extent)" if dem_ok else ""))
    print(f"  {'✓' if buf_ok else '✗'} Buffer: {'Valid' if buf_ok else 'INVALID'}" + (f" ({r2['buffer'].get('actual_radius_m', 0):.0f}m radius)" if buf_ok else ""))
    print(f"  {'✓' if shp['total'] else '✗'} Shapefiles: {shp['with_data']} with data, {shp['empty']} empty")
    print()
    print("100m Output:")
    r1 = results_100m
    dem_ok1 = r1["dem"].get("valid", False)
    buf_ok1 = r1["buffer"].get("valid", False)
    shp1 = r1["shapefiles"]
    print(f"  {'✓' if dem_ok1 else '✗'} DEM: {'Valid' if dem_ok1 else 'INVALID'}" + (f" ({r1['dem'].get('shape', (0, 0))[0]}x{r1['dem'].get('shape', (0, 0))[1]} pixels, ~{r1['dem'].get('extent_m', (0, 0))[0]:.0f}m extent)" if dem_ok1 else ""))
    print(f"  {'✓' if buf_ok1 else '✗'} Buffer: {'Valid' if buf_ok1 else 'INVALID'}" + (f" ({r1['buffer'].get('actual_radius_m', 0):.0f}m radius)" if buf_ok1 else ""))
    print(f"  {'✓' if shp1['total'] else '✗'} Shapefiles: {shp1['with_data']} with data, {shp1['empty']} empty")
    qgis_ok = results_qgis.get("valid", False)
    print(f"  {'✓' if qgis_ok else '✗'} QGIS Project: {'CRS set to EPSG:6340' if qgis_ok else 'INVALID or missing CRS'}")
    print()
    all_ok = (
        r2["dem"].get("valid") and r2["buffer"].get("valid")
        and r1["dem"].get("valid") and r1["buffer"].get("valid")
        and results_qgis.get("valid")
    )
    if all_ok:
        print("All outputs validated successfully.")
    else:
        print("WARNING: Some validations failed. Check output above.")
    print("\nUse output/ for HEC-RAS; open output/site_100m/site_100m.qgz in QGIS.")
