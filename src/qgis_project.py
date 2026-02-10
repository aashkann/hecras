"""QGIS project generation using PyQGIS (with XML fallback)."""
from pathlib import Path
import glob
import json
import subprocess
import sys
import textwrap


def _find_qgis_python() -> tuple[str, dict[str, str]] | None:
    """Return (python_binary, extra_env) for the QGIS Python, or None."""
    if sys.platform == "darwin":
        app = Path("/Applications/QGIS.app/Contents")
        binary = app / "MacOS" / "python3.12"
        if binary.exists():
            env = {
                "PYTHONHOME": str(app / "Frameworks"),
                "PYTHONPATH": ":".join([
                    str(app / "Resources/python3.11/site-packages"),
                    str(app / "Frameworks/lib/python3.12"),
                    str(app / "Frameworks/lib/python3.12/lib-dynload"),
                    str(app / "Resources/qgis/python"),
                ]),
                "DYLD_LIBRARY_PATH": ":".join([
                    str(app / "Frameworks"),
                    str(app / "Frameworks/lib"),
                    str(app / "MacOS/lib"),
                ]),
                "QT_QPA_PLATFORM": "offscreen",
                "PROJ_DATA": str(app / "Resources/qgis/proj"),
                "PROJ_LIB": str(app / "Resources/qgis/proj"),
                "GDAL_DATA": str(app / "Resources/qgis/gdal"),
            }
            return str(binary), env
    return None


_PYQGIS_SCRIPT = textwrap.dedent("""\
    import sys, os, glob, json

    args = json.loads(sys.argv[1])
    folder = args["folder"]
    dem_name = args["dem_name"]
    crs_authid = args["crs_authid"]

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from qgis.core import (
        QgsApplication,
        QgsProject,
        QgsCoordinateReferenceSystem,
        QgsRasterLayer,
        QgsVectorLayer,
    )

    QgsApplication.setPrefixPath(
        str(os.path.dirname(os.path.dirname(sys.executable)) + "/MacOS"), True
    )
    qgs = QgsApplication([], False)
    qgs.initQgis()

    project = QgsProject.instance()
    project.clear()
    project.setCrs(QgsCoordinateReferenceSystem(crs_authid))

    # Add DEM
    dem_path = os.path.join(folder, dem_name)
    dem = QgsRasterLayer(dem_path, os.path.splitext(dem_name)[0])
    if dem.isValid():
        project.addMapLayer(dem)

    # Add all non-empty shapefiles
    for shp in sorted(glob.glob(os.path.join(folder, "*.shp"))):
        name = os.path.splitext(os.path.basename(shp))[0]
        lyr = QgsVectorLayer(shp, name, "ogr")
        if lyr.isValid() and lyr.featureCount() > 0:
            project.addMapLayer(lyr)

    qgz = os.path.join(folder, "site_100m.qgz")
    ok = project.write(qgz)
    qgs.exitQgis()
    if ok:
        print(json.dumps({"ok": True, "path": qgz, "size": os.path.getsize(qgz)}))
    else:
        print(json.dumps({"ok": False}))
""")


def write_qgis_project(folder: Path, dem_name: str, shp_names: list[str]) -> None:
    """Write a QGIS 3 project (.qgz) into *folder* with all layers loaded.

    Uses the system QGIS Python (PyQGIS) for a fully valid project file.
    """
    found = _find_qgis_python()
    if found is None:
        print("  QGIS Python not found at /Applications/QGIS.app")
        print("  Skipping .qgz generation. Load layers manually in QGIS.")
        return

    qgis_python, extra_env = found
    args_json = json.dumps({
        "folder": str(folder.resolve()),
        "dem_name": dem_name,
        "crs_authid": "EPSG:6340",
    })

    import os as _os
    env = {**dict(_os.environ), **extra_env}

    result = subprocess.run(
        [qgis_python, "-c", _PYQGIS_SCRIPT, args_json],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )

    if result.returncode == 0:
        # Parse the last JSON line from stdout
        for line in reversed(result.stdout.strip().splitlines()):
            try:
                info = json.loads(line)
                if info.get("ok"):
                    print(f"QGIS project written: {info['path']} (open this file in QGIS)")
                    return
            except json.JSONDecodeError:
                continue

    # If we get here, PyQGIS failed
    stderr = result.stderr.strip() if result.stderr else ""
    if stderr:
        print(f"  PyQGIS warning: {stderr[:200]}")
    print(f"  PyQGIS project generation failed (exit {result.returncode})")
    print("  Load layers manually in QGIS: Layer > Add Layer > Add Raster/Vector Layer")
