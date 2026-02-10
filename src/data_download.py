"""Download public GIS datasets (NHD streams, FEMA flood zones, parcels) via REST APIs."""
from pathlib import Path
import json
import urllib.request
import urllib.parse

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import box


def _bbox_wgs84(lat: float, lon: float, buffer_m: int) -> tuple[float, float, float, float]:
    """Return (xmin, ymin, xmax, ymax) in WGS84 around site, roughly buffer_m."""
    # Approximate degrees for the buffer
    deg_lat = buffer_m / 111_000
    deg_lon = buffer_m / (111_000 * abs(max(0.1, __import__("math").cos(__import__("math").radians(lat)))))
    return (lon - deg_lon, lat - deg_lat, lon + deg_lon, lat + deg_lat)


def _query_arcgis_rest(url: str, bbox_wgs84: tuple, layer_id: int,
                       out_path: Path, label: str) -> Path | None:
    """Query an ArcGIS REST MapServer layer and save as shapefile."""
    xmin, ymin, xmax, ymax = bbox_wgs84
    params = {
        "where": "1=1",
        "geometry": f"{xmin},{ymin},{xmax},{ymax}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "outSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
    }
    query_url = f"{url}/{layer_id}/query?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(query_url, headers={"User-Agent": "HecRAS-GIS-Tool/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"    {label}: download failed ({e})")
        return None

    if "features" not in data or len(data["features"]) == 0:
        print(f"    {label}: no features found in area")
        return None

    try:
        gdf = gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:4326")
        if gdf.empty:
            print(f"    {label}: empty result")
            return None
        gdf.to_file(out_path)
        print(f"    {label}: {len(gdf)} features -> {out_path.name}")
        return out_path
    except Exception as e:
        print(f"    {label}: save failed ({e})")
        return None


def download_nhd_streams(lat: float, lon: float, buffer_m: int,
                         out_path: Path) -> Path | None:
    """Download NHD flowlines (streams/rivers) from USGS National Map."""
    bbox = _bbox_wgs84(lat, lon, buffer_m)
    # NHD MapServer: layer 6 = NHDFlowline
    return _query_arcgis_rest(
        "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer",
        bbox, 6, out_path, "NHD Streams",
    )


def download_fema_flood_zones(lat: float, lon: float, buffer_m: int,
                               out_path: Path) -> Path | None:
    """Download FEMA flood hazard zones from NFHL."""
    bbox = _bbox_wgs84(lat, lon, buffer_m)
    # NFHL MapServer: layer 28 = Flood Hazard Zones (S_Fld_Haz_Ar)
    return _query_arcgis_rest(
        "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer",
        bbox, 28, out_path, "FEMA Flood Zones",
    )


def download_parcels_la_county(lat: float, lon: float, buffer_m: int,
                                out_path: Path) -> Path | None:
    """Download parcel boundaries from LA County Assessor."""
    bbox = _bbox_wgs84(lat, lon, buffer_m)
    return _query_arcgis_rest(
        "https://public.gis.lacounty.gov/public/rest/services/LACounty_Cache/LACounty_Parcel/MapServer",
        bbox, 0, out_path, "LA County Parcels",
    )


def download_nhd_waterbodies(lat: float, lon: float, buffer_m: int,
                              out_path: Path) -> Path | None:
    """Download NHD waterbodies (lakes, ponds, reservoirs) from USGS."""
    bbox = _bbox_wgs84(lat, lon, buffer_m)
    # NHD MapServer: layer 3 = NHDWaterbody
    return _query_arcgis_rest(
        "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer",
        bbox, 3, out_path, "NHD Waterbodies",
    )


def download_nhd_catchments(lat: float, lon: float, buffer_m: int,
                             out_path: Path) -> Path | None:
    """Download NHDPlus catchment boundaries."""
    bbox = _bbox_wgs84(lat, lon, buffer_m)
    # NHD MapServer: layer 10 = Catchment
    return _query_arcgis_rest(
        "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer",
        bbox, 10, out_path, "NHD Catchments",
    )


def download_all(lat: float, lon: float, buffer_m: int,
                 out_dir: Path) -> dict[str, Path | None]:
    """Download all available datasets for the site area.

    Returns dict mapping dataset name to output path (or None if failed).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    results["nhd_streams"] = download_nhd_streams(
        lat, lon, buffer_m, out_dir / "nhd_streams.shp")
    results["nhd_waterbodies"] = download_nhd_waterbodies(
        lat, lon, buffer_m, out_dir / "nhd_waterbodies.shp")
    results["nhd_catchments"] = download_nhd_catchments(
        lat, lon, buffer_m, out_dir / "nhd_catchments.shp")
    results["fema_flood_zones"] = download_fema_flood_zones(
        lat, lon, buffer_m, out_dir / "fema_flood_zones.shp")
    results["parcels"] = download_parcels_la_county(
        lat, lon, buffer_m, out_dir / "parcels.shp")

    return results
