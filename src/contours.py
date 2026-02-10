"""Generate elevation contour lines from a DEM GeoTIFF."""
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import LineString


def generate_contours(
    dem_path: Path,
    out_path: Path,
    interval: float = 1.0,
) -> Path | None:
    """Generate contour lines from a DEM and save as shapefile.

    Parameters
    ----------
    dem_path : Path to clipped DEM GeoTIFF.
    out_path : Path for output contours shapefile.
    interval : Contour interval in DEM vertical units (meters). Default 1 m.

    Returns the output path, or None if generation fails.
    """
    from matplotlib import pyplot as plt

    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float64)
        nodata = src.nodata
        transform = src.transform
        crs = src.crs

    if nodata is not None:
        dem[dem == nodata] = np.nan

    valid = dem[~np.isnan(dem)]
    if len(valid) == 0:
        print("    No valid elevation data for contours.")
        return None

    zmin, zmax = np.nanmin(dem), np.nanmax(dem)
    levels = np.arange(np.floor(zmin / interval) * interval, zmax + interval, interval)

    rows, cols = dem.shape
    # Build coordinate grids in map CRS
    col_coords = np.arange(cols) * transform.a + transform.c + transform.a / 2
    row_coords = np.arange(rows) * transform.e + transform.f + transform.e / 2

    fig, ax = plt.subplots()
    cs = ax.contour(col_coords, row_coords, dem, levels=levels)
    plt.close(fig)

    lines = []
    elevations = []
    for level_idx, level_val in enumerate(cs.levels):
        for path in cs.allsegs[level_idx]:
            if len(path) >= 2:
                lines.append(LineString(path))
                elevations.append(float(level_val))

    if not lines:
        print("    No contour lines generated.")
        return None

    gdf = gpd.GeoDataFrame(
        {"elevation": elevations},
        geometry=lines,
        crs=crs,
    )
    gdf.to_file(out_path)
    print(f"    Contours written: {out_path} ({len(lines)} lines, {interval}m interval)")
    return out_path
