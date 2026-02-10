"""Clipping: DEM and shapefiles to buffer."""
from pathlib import Path
import warnings

import geopandas as gpd
from shapely.geometry import Point, mapping
import rasterio
from rasterio.mask import mask

from .config import DEM_PATH, SHAPE_DIR
from .utils import buffer_distance_meters


def run_clip(
    lat: float,
    lon: float,
    dem_crs,
    buffer_m: int,
    out_dir: Path,
    suffix: str,
) -> list[Path]:
    """Clip DEM and shapefiles to buffer; write to out_dir. Returns paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    site_wgs84 = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")
    site_proj = site_wgs84.to_crs(dem_crs)
    buffer_dist = buffer_distance_meters(dem_crs, buffer_m)
    buffer_geom = site_proj.buffer(buffer_dist).iloc[0]
    buffer_gdf = gpd.GeoDataFrame(geometry=[buffer_geom], crs=dem_crs)

    buffer_path = out_dir / f"site_buffer_{suffix}.shp"
    buffer_gdf.to_file(buffer_path)
    written.append(buffer_path)
    print(f"Buffer written: {buffer_path}")

    buffer_geom_for_mask = mapping(buffer_geom)

    with rasterio.open(DEM_PATH) as src:
        clipped_img, clipped_transform = mask(
            src, [buffer_geom_for_mask], crop=True
        )
        clipped_meta = src.meta.copy()
        clipped_meta.update({
            "height": clipped_img.shape[1],
            "width": clipped_img.shape[2],
            "transform": clipped_transform,
        })

    clipped_dem_path = out_dir / f"dem_clipped_{suffix}.tif"
    with rasterio.open(clipped_dem_path, "w", **clipped_meta) as dst:
        dst.write(clipped_img)
    written.append(clipped_dem_path)
    print(f"Clipped DEM written: {clipped_dem_path}")

    shp_paths = sorted(SHAPE_DIR.glob("*.shp"))
    for shp in shp_paths:
        gdf = gpd.read_file(shp)
        if gdf.crs is None:
            continue
        gdf = gdf.to_crs(dem_crs)
        clipped = gpd.clip(gdf, buffer_gdf)
        if clipped.empty:
            print(f"  {shp.stem}: no features in buffer (empty clip)")
        for col in clipped.select_dtypes(include=["datetime64"]).columns:
            clipped = clipped.assign(**{col: clipped[col].astype(str)})
        out_shp = out_dir / f"{shp.stem}_clipped_{suffix}.shp"
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="You are attempting to write an empty DataFrame",
                category=UserWarning,
                module="geopandas",
            )
            clipped.to_file(out_shp, engine="fiona")
        written.append(out_shp)
        print(f"Clipped shapefile written: {out_shp}")

    return written
