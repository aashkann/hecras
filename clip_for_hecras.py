"""
Clip DEM and shapefiles to a buffer around a site for HEC-RAS and QGIS.
Reads site coordinates from cooridante.txt.
- output/           : 200 m buffer (HEC-RAS).
- output/site_100m/ : 100 m buffer, QGIS-ready (open project.qgz in QGIS).
"""
from pathlib import Path
import json
import zipfile

import geopandas as gpd
from shapely.geometry import Point
from pyproj import CRS
import rasterio
from rasterio.mask import mask

# ---------------------------
# USER INPUTS
# ---------------------------
BUFFER_200_M = 200  # meters (main output for HEC-RAS)
BUFFER_100_M = 100  # meters (output/site_100m for QGIS)

# Paths relative to script directory
SCRIPT_DIR = Path(__file__).resolve().parent
COORD_FILE = SCRIPT_DIR / "cooridante.txt"
DEM_PATH = SCRIPT_DIR / "USGS_OPR_CA_LosAngeles_B23_11SLT033900377900.tif"
SHAPE_DIR = SCRIPT_DIR / "GOVTUNIT_California_State_Shape" / "Shape"
OUT_DIR = SCRIPT_DIR / "output"
QGIS_100M_DIR = OUT_DIR / "site_100m"  # 100 m radius, open in QGIS


def read_coordinates(path: Path) -> tuple[float, float]:
    """Read lat, lon from first line of coordinate file (format: lat, lon)."""
    text = path.read_text().strip()
    first_line = text.splitlines()[0].strip()
    parts = [p.strip() for p in first_line.split(",")]
    if len(parts) != 2:
        raise ValueError(f"Expected 'lat, lon' in {path}, got: {first_line}")
    lat = float(parts[0])
    lon = float(parts[1])
    return lat, lon


def buffer_distance_meters(dem_crs, buffer_m: int) -> float:
    """Return buffer distance in CRS units (meters or feet)."""
    units = CRS.from_user_input(dem_crs).axis_info[0].unit_name.lower()
    if "foot" in units or "feet" in units:
        return buffer_m * 3.28084
    return float(buffer_m)


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

    buffer_geojson = json.loads(buffer_gdf.to_json())
    buffer_geom_for_mask = buffer_geojson["features"][0]["geometry"]

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
        clipped.to_file(out_shp, engine="fiona")
        written.append(out_shp)
        print(f"Clipped shapefile written: {out_shp}")

    return written


def write_qgis_project(folder: Path, dem_name: str, shp_names: list[str]) -> None:
    """Write a minimal QGIS 3 project (.qgz) into folder so it opens with layers loaded."""
    layers_xml = []
    for name in [dem_name] + shp_names:
        if name.endswith(".tif"):
            layers_xml.append(
                f'    <maplayer type="raster" name="{Path(name).stem}">\n'
                f'      <datasource>{name}</datasource>\n'
                "    </maplayer>"
            )
        else:
            layers_xml.append(
                f'    <maplayer type="vector" name="{Path(name).stem}">\n'
                f'      <datasource>{name}</datasource>\n'
                "    </maplayer>"
            )

    layer_tree = "".join(
        f'    <layer-tree-layer name="{Path(n).stem}" source="{n}" />\n'
        for n in [dem_name] + shp_names
    )
    project_qgs = f"""<?xml version="1.0" encoding="UTF-8"?>
<qgis version="3.44.7-Solothurn">
  <projectCrs>
    <spatialrefsys nativeFormat="Wkt">
      <wkt>PROJCS["NAD83 / California zone 5 (ftUS)",GEOGCS["NAD83",DATUM["North_American_Datum_1983",SPHEROID["GRS 1980",6378137,298.257222101]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],PROJECTION["Lambert_Conformal_Conic_2SP"],PARAMETER["latitude_of_origin",33.33333333333334],PARAMETER["central_meridian",-118],PARAMETER["standard_parallel_1",35.46666666666667],PARAMETER["standard_parallel_2",34.03333333333334],PARAMETER["false_easting",6561666.666666666],PARAMETER["false_northing",1640416.666666667],UNIT["US survey foot",0.3048006096012192],AXIS["Easting",EAST],AXIS["Northing",NORTH]]</wkt>
    </spatialrefsys>
  </projectCrs>
  <layer-tree-group name="Site 100m">
{layer_tree}
  </layer-tree-group>
{"".join(layers_xml)}
</qgis>
"""
    qgz_path = folder / "site_100m.qgz"
    with zipfile.ZipFile(qgz_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.qgs", project_qgs.encode("utf-8"))
    print(f"QGIS project written: {qgz_path} (open this file in QGIS)")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    lat, lon = read_coordinates(COORD_FILE)
    print(f"Site coordinates (WGS84): {lat}, {lon}")

    if not DEM_PATH.exists():
        raise FileNotFoundError(f"DEM not found: {DEM_PATH}")
    with rasterio.open(DEM_PATH) as src:
        dem_crs = src.crs
    if dem_crs is None:
        raise ValueError("DEM has no CRS. Define it before buffering/clipping.")

    # 200 m output (HEC-RAS)
    print("\n--- 200 m buffer (output/) ---")
    run_clip(lat, lon, dem_crs, BUFFER_200_M, OUT_DIR, "200m")

    # 100 m output (QGIS folder)
    print("\n--- 100 m buffer (output/site_100m/) ---")
    run_clip(lat, lon, dem_crs, BUFFER_100_M, QGIS_100M_DIR, "100m")

    # QGIS project for 100m folder (DEM + buffer + clipped shapefiles)
    dem_100 = QGIS_100M_DIR / "dem_clipped_100m.tif"
    shp_100 = sorted(QGIS_100M_DIR.glob("*_clipped_100m.shp"))
    if dem_100.exists():
        write_qgis_project(
            QGIS_100M_DIR,
            "dem_clipped_100m.tif",
            ["site_buffer_100m.shp"] + [p.name for p in shp_100],
        )

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

    print("\nDone. Use output/ for HEC-RAS; open output/site_100m/site_100m.qgz in QGIS.")


if __name__ == "__main__":
    main()
