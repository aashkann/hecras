"""Utility functions: coordinates, CRS."""
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point
from pyproj import CRS


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
