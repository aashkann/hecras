"""Package clipped terrain and streams for HEC-RAS RAS Mapper import."""
from pathlib import Path
import shutil

import rasterio
from pyproj import CRS


def _write_prj(crs, out_path: Path) -> None:
    """Write an ESRI-style .prj file from a CRS object."""
    proj_crs = CRS(crs)
    # Extract horizontal component if compound CRS
    if proj_crs.is_compound:
        for sub in proj_crs.sub_crs_list:
            if sub.is_projected or sub.is_geographic:
                proj_crs = sub
                break
    wkt = proj_crs.to_wkt("WKT1_ESRI")
    out_path.write_text(wkt, encoding="utf-8")


def export_for_hecras(
    dem_path: Path,
    buffer_shp: Path,
    streams_shp: Path | None,
    out_dir: Path,
    buffer_m: int,
) -> None:
    """Copy terrain, projection, streams, and buffer into a HEC-RAS-ready folder.

    Parameters
    ----------
    dem_path : Clipped DEM GeoTIFF.
    buffer_shp : Buffer boundary shapefile.
    streams_shp : Delineated streams shapefile (or None).
    out_dir : Output directory for HEC-RAS package.
    buffer_m : Buffer distance used (for documentation).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Terrain GeoTIFF
    terrain_dst = out_dir / "terrain.tif"
    shutil.copy2(dem_path, terrain_dst)
    print(f"    terrain.tif copied")

    # 2) Standalone .prj for RAS Mapper "Set Projection"
    with rasterio.open(dem_path) as src:
        crs = src.crs
    prj_path = out_dir / "projection.prj"
    _write_prj(crs, prj_path)
    print(f"    projection.prj written (ESRI WKT)")

    # 3) Buffer boundary (reference layer)
    stem = buffer_shp.stem
    for ext in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
        src_file = buffer_shp.with_suffix(ext)
        if src_file.exists():
            shutil.copy2(src_file, out_dir / f"site_buffer{ext}")
    print(f"    site_buffer.shp copied")

    # 4) Streams (if available)
    if streams_shp and streams_shp.exists():
        for ext in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
            src_file = streams_shp.with_suffix(ext)
            if src_file.exists():
                shutil.copy2(src_file, out_dir / f"streams{ext}")
        print(f"    streams.shp copied")

    # 5) README with import instructions
    readme = out_dir / "README_HECRAS.txt"
    readme.write_text(
        f"HEC-RAS 2D Terrain Package\n"
        f"{'=' * 40}\n\n"
        f"Buffer: {buffer_m} m radius\n"
        f"CRS: NAD83(2011) / UTM zone 11N (EPSG:6340)\n"
        f"Vertical datum: NAVD88\n\n"
        f"Files:\n"
        f"  terrain.tif      - Clipped DEM (import as terrain in RAS Mapper)\n"
        f"  projection.prj   - ESRI projection file for RAS Mapper\n"
        f"  site_buffer.shp  - Study area boundary (reference layer)\n"
        f"  streams.shp      - Delineated stream network (if available)\n\n"
        f"Import into HEC-RAS:\n"
        f"  1. Open RAS Mapper\n"
        f"  2. Project > Set Projection > browse to projection.prj\n"
        f"  3. Project > New Terrain > select terrain.tif\n"
        f"  4. (Optional) Add streams.shp and site_buffer.shp as reference layers\n"
        f"  5. Create 2D Flow Area covering the study area\n"
        f"  6. Set boundary conditions for flood return periods\n"
        f"     (1, 2, 5, 10, 25, 100, 200-year events)\n",
        encoding="utf-8",
    )
    print(f"    README_HECRAS.txt written")
