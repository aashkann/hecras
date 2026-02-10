HEC-RAS 2D Terrain Package
========================================

Buffer: 200 m radius
CRS: NAD83(2011) / UTM zone 11N (EPSG:6340)
Vertical datum: NAVD88

Files:
  terrain.tif      - Clipped DEM (import as terrain in RAS Mapper)
  projection.prj   - ESRI projection file for RAS Mapper
  site_buffer.shp  - Study area boundary (reference layer)
  streams.shp      - Delineated stream network (if available)

Import into HEC-RAS:
  1. Open RAS Mapper
  2. Project > Set Projection > browse to projection.prj
  3. Project > New Terrain > select terrain.tif
  4. (Optional) Add streams.shp and site_buffer.shp as reference layers
  5. Create 2D Flow Area covering the study area
  6. Set boundary conditions for flood return periods
     (1, 2, 5, 10, 25, 100, 200-year events)
