#!/usr/bin/env python3
"""
HEC-RAS GIS Workflow
====================
Clip DEM and shapefiles, delineate streams, package for HEC-RAS, generate QGIS project.

Usage:
    python main.py                       # defaults: 200 m HEC-RAS buffer, 100 m QGIS buffer
    python main.py --buffer 500          # 500 m HEC-RAS study area
    python main.py --buffer 1000 --stream-threshold 2000
"""
import argparse
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import (
    COORD_FILE,
    DEM_PATH,
    SHAPE_DIR,
    OUTPUT_DIR,
    BUFFER_200M,
    BUFFER_100M,
)
from src.utils import read_coordinates
from src.validation import (
    validate_asset_dem,
    validate_asset_shapefiles,
    validate_inputs,
    validate_dem_output,
    validate_buffer,
    validate_shapefiles,
    validate_qgis_project,
    validate_generated_files,
    print_validation_summary,
)
from src.clipping import run_clip
from src.qgis_project import write_qgis_project
from src.streams import delineate_streams
from src.hecras_export import export_for_hecras
import rasterio


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="HEC-RAS GIS Workflow: clip terrain, delineate streams, export for RAS Mapper",
    )
    p.add_argument(
        "--buffer", type=int, default=BUFFER_200M,
        help=f"HEC-RAS study area buffer radius in meters (default: {BUFFER_200M})",
    )
    p.add_argument(
        "--buffer-qgis", type=int, default=BUFFER_100M,
        help=f"QGIS visualization buffer radius in meters (default: {BUFFER_100M})",
    )
    p.add_argument(
        "--stream-threshold", type=int, default=500,
        help="Min flow accumulation (cells) for stream extraction (default: 500). "
             "Higher = fewer/larger streams.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    buffer_hecras = args.buffer
    buffer_qgis = args.buffer_qgis
    stream_threshold = args.stream_threshold

    suffix_hecras = f"{buffer_hecras}m"
    suffix_qgis = f"{buffer_qgis}m"
    qgis_dir = OUTPUT_DIR / f"site_{suffix_qgis}"
    hecras_dir = OUTPUT_DIR / "hecras"

    print("=" * 60)
    print("HEC-RAS GIS Workflow")
    print("=" * 60)
    print(f"  HEC-RAS buffer: {buffer_hecras} m")
    print(f"  QGIS buffer:    {buffer_qgis} m")
    print(f"  Stream threshold: {stream_threshold} cells")

    # ── 1) Validate assets ──────────────────────────────────────
    print(f"\n[1/5] Validating assets...")
    dem_result = validate_asset_dem(DEM_PATH)
    if not dem_result["valid"]:
        print(f"ERROR: DEM invalid - {dem_result.get('error')}")
        return 1
    print("  DEM: OK")

    shp_result = validate_asset_shapefiles(SHAPE_DIR)
    if not shp_result["valid"]:
        print(f"ERROR: Shapefiles invalid - missing CRS: {shp_result.get('missing_crs')}")
        return 1
    print(f"  Shapefiles: OK ({shp_result['count']} layers)")

    lat, lon = read_coordinates(COORD_FILE)
    print(f"  Site (WGS84): {lat}, {lon}")

    with rasterio.open(DEM_PATH) as src:
        dem_crs = src.crs
        dem_bounds = src.bounds
    validate_inputs(DEM_PATH, SHAPE_DIR, lat, lon, dem_crs, dem_bounds)

    # ── 2) Clip DEM and shapefiles ─────────────────────────────
    print(f"\n[2/5] Clipping ({suffix_hecras} HEC-RAS, {suffix_qgis} QGIS)...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    run_clip(lat, lon, dem_crs, buffer_hecras, OUTPUT_DIR, suffix_hecras)
    run_clip(lat, lon, dem_crs, buffer_qgis, qgis_dir, suffix_qgis)

    # ── 3) Stream delineation ──────────────────────────────────
    print(f"\n[3/5] Delineating streams...")
    dem_hecras_path = OUTPUT_DIR / f"dem_clipped_{suffix_hecras}.tif"
    streams_hecras = None
    if dem_hecras_path.exists():
        streams_out = OUTPUT_DIR / f"streams_{suffix_hecras}.shp"
        streams_hecras = delineate_streams(
            dem_hecras_path, streams_out, threshold=stream_threshold,
        )

    # Also run on QGIS buffer for visualization
    dem_qgis_path = qgis_dir / f"dem_clipped_{suffix_qgis}.tif"
    streams_qgis = None
    if dem_qgis_path.exists():
        streams_qgis_out = qgis_dir / f"streams_{suffix_qgis}.shp"
        streams_qgis = delineate_streams(
            dem_qgis_path, streams_qgis_out, threshold=stream_threshold,
        )

    # ── 4) HEC-RAS export package ─────────────────────────────
    print(f"\n[4/5] Preparing HEC-RAS export...")
    buffer_shp = OUTPUT_DIR / f"site_buffer_{suffix_hecras}.shp"
    if dem_hecras_path.exists() and buffer_shp.exists():
        export_for_hecras(
            dem_hecras_path, buffer_shp, streams_hecras,
            hecras_dir, buffer_hecras,
        )
    print(f"  HEC-RAS files in: {hecras_dir}")

    # ── 5) QGIS project ───────────────────────────────────────
    print(f"\n[5/5] Generating QGIS project...")
    dem_qgis = qgis_dir / f"dem_clipped_{suffix_qgis}.tif"
    shp_qgis = sorted(qgis_dir.glob(f"*_clipped_{suffix_qgis}.shp"))
    shp_list = [f"site_buffer_{suffix_qgis}.shp"] + [p.name for p in shp_qgis]
    if streams_qgis and streams_qgis.exists():
        shp_list.append(streams_qgis.name)
    if dem_qgis.exists():
        write_qgis_project(qgis_dir, dem_qgis.name, shp_list)

    # ── Validation summary ─────────────────────────────────────
    dem_hec_path = OUTPUT_DIR / f"dem_clipped_{suffix_hecras}.tif"
    buffer_hec_path = OUTPUT_DIR / f"site_buffer_{suffix_hecras}.shp"
    buffer_q_path = qgis_dir / f"site_buffer_{suffix_qgis}.shp"
    qgz_path = qgis_dir / "site_100m.qgz"

    results_hecras = {
        "dem": validate_dem_output(dem_hec_path, buffer_hecras) if dem_hec_path.exists() else {"valid": False},
        "buffer": validate_buffer(buffer_hec_path, buffer_hecras, dem_crs) if buffer_hec_path.exists() else {"valid": False},
        "shapefiles": validate_shapefiles(OUTPUT_DIR, suffix_hecras),
    }
    results_qgis_v = {
        "dem": validate_dem_output(dem_qgis, buffer_qgis) if dem_qgis.exists() else {"valid": False},
        "buffer": validate_buffer(buffer_q_path, buffer_qgis, dem_crs) if buffer_q_path.exists() else {"valid": False},
        "shapefiles": validate_shapefiles(qgis_dir, suffix_qgis),
    }
    results_qgis_proj = validate_qgis_project(qgz_path) if qgz_path.exists() else {"valid": False}

    print_validation_summary(
        OUTPUT_DIR, qgis_dir, lat, lon, dem_crs,
        results_hecras, results_qgis_v, results_qgis_proj,
    )

    # ── Final summary ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print("OUTPUT SUMMARY")
    print("=" * 60)
    print(f"  HEC-RAS terrain:  output/hecras/terrain.tif")
    print(f"  HEC-RAS project:  output/hecras/projection.prj")
    if streams_hecras:
        print(f"  Streams:          output/hecras/streams.shp")
    print(f"  QGIS project:     {qgis_dir}/site_100m.qgz")
    print(f"\n  Import output/hecras/ into RAS Mapper for 2D flood modeling.")
    print("=" * 60)

    # Try to open QGIS
    if qgz_path.exists():
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(qgz_path.resolve())], check=False)
            elif sys.platform == "win32":
                subprocess.run(["start", "", str(qgz_path.resolve())], shell=True, check=False)
            else:
                subprocess.run(["xdg-open", str(qgz_path.resolve())], check=False)
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
