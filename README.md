# HEC-RAS GIS Automation

Clip DEM terrain and shapefiles to a 200-meter buffer around a site for clean, shareable inputs to HEC-RAS.

## What This Does

- Reads your site coordinates from `cooridante.txt` (lat, lon in WGS84)
- Builds a 200 m buffer in the DEM’s coordinate system (handles meters vs feet)
- Clips the DEM (GeoTIFF) to that buffer
- Clips all California government unit shapefiles in `GOVTUNIT_California_State_Shape/Shape/` to the same buffer
- Writes everything to `output/` for import into HEC-RAS

## Requirements

- Python 3.9+
- DEM and shapefiles with defined CRS (coordinate reference system)

## Installation

Create a virtual environment and install dependencies (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

This installs: `geopandas`, `shapely`, `pyproj`, `rasterio`, `fiona`.

## Usage

1. **Site coordinates**  
   Edit `cooridante.txt` so the first line is your site in WGS84:
   ```
   lat, lon
   ```
   Example: `34.142534, -118.743983`

2. **Run the script** (from the project root, with the venv activated if you use it):

   ```bash
   python clip_for_hecras.py
   ```

3. **Outputs** are written to `output/`:
   - `site_buffer_200m.shp` – 200 m buffer polygon (for QA/maps)
   - `dem_clipped_200m.tif` – clipped terrain for HEC-RAS
   - `*_clipped_200m.shp` – one clipped shapefile per input layer

## Importing into HEC-RAS

1. Open your HEC-RAS project.
2. **Terrain (DEM)**  
   - RAS Mapper → **Terrains** → **Add New Terrain**  
   - Select `output/dem_clipped_200m.tif`
3. **Shapefile layers**  
   - RAS Mapper → **Add Existing Layer** (or equivalent)  
   - Add any of `output/*_clipped_200m.shp` as needed (e.g. county, incorporated place, reserve).

## Customization

- **Buffer distance**: In `clip_for_hecras.py`, change `BUFFER_M = 200` (meters).
- **Site**: Edit `cooridante.txt` or the paths/coordinates in the script.
- **Which shapefiles**: Script processes every `.shp` in `GOVTUNIT_California_State_Shape/Shape/`. To limit layers, adjust the `shp_paths` logic in the script (e.g. filter by name).

## Troubleshooting

### “DEM has no CRS”
The GeoTIFF has no projection metadata. Define the CRS in a GIS (e.g. QGIS: Layer → Set CRS) or re-export the DEM with CRS from your data source.

### “Shapefile has no CRS”
Same idea: set the CRS on the shapefile in QGIS (or similar) so the script can reproject and clip correctly.

### Buffer seems wrong (too big/small or wrong shape)
Buffering is done in the DEM’s CRS. If the DEM is in **feet** (e.g. US State Plane), the script converts 200 m to feet automatically. If your DEM is in an unusual or undefined unit, check its CRS (e.g. `gdalinfo your_dem.tif` or open in QGIS).

### Site outside DEM extent
If the site is outside the DEM bounds, the clipped DEM or clip results may be empty or useless. Confirm the site (lat/lon) lies within the DEM coverage.

### Empty clipped shapefiles
Some layers may have no features inside the 200 m buffer (e.g. no county boundary there). The script still writes the empty shapefile and prints a note. You can ignore those layers in HEC-RAS.

## Project Layout

```
hecras/
├── clip_for_hecras.py    # Main script
├── requirements.txt      # Python dependencies
├── cooridante.txt        # Site lat, lon (one line)
├── output/               # Clipped DEM and shapefiles
├── USGS_OPR_CA_LosAngeles_*.tif   # Input DEM
└── GOVTUNIT_California_State_Shape/
    └── Shape/            # Input shapefiles
```
