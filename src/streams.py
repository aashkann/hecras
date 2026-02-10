"""Stream delineation from DEM using D8 flow routing (numpy-vectorized)."""
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import LineString


# D8 neighbor offsets: 0=E, 1=SE, 2=S, 3=SW, 4=W, 5=NW, 6=N, 7=NE
_DR = np.array([0, 1, 1, 1, 0, -1, -1, -1], dtype=np.int32)
_DC = np.array([1, 1, 0, -1, -1, -1, 0, 1], dtype=np.int32)
_DIST = np.array([1.0, 1.414, 1.0, 1.414, 1.0, 1.414, 1.0, 1.414])


def _fill_sinks(dem: np.ndarray, nodata: float | None) -> np.ndarray:
    """Fill single-cell pits by raising them to the lowest neighbor."""
    filled = dem.astype(np.float64, copy=True)
    if nodata is not None:
        mask = filled == nodata
        filled[mask] = np.nan
    rows, cols = filled.shape

    for _ in range(50):  # iterate until stable
        padded = np.pad(filled, 1, mode="constant", constant_values=np.inf)
        min_nb = np.full_like(filled, np.inf)
        for i in range(8):
            nb = padded[1 + _DR[i]:rows + 1 + _DR[i], 1 + _DC[i]:cols + 1 + _DC[i]]
            min_nb = np.minimum(min_nb, nb)
        valid = ~np.isnan(filled)
        pits = valid & (filled < min_nb) & (min_nb < np.inf)
        if not np.any(pits):
            break
        filled[pits] = min_nb[pits]

    if nodata is not None:
        filled[mask] = nodata
    return filled


def _flow_direction_d8(dem: np.ndarray) -> np.ndarray:
    """Compute D8 flow direction (vectorized). Returns 0-7 or -1 for flat/nodata."""
    rows, cols = dem.shape
    fdir = np.full((rows, cols), -1, dtype=np.int8)
    max_slope = np.zeros((rows, cols), dtype=np.float64)
    padded = np.pad(dem, 1, mode="constant", constant_values=np.nan)

    for i in range(8):
        nb = padded[1 + _DR[i]:rows + 1 + _DR[i], 1 + _DC[i]:cols + 1 + _DC[i]]
        slope = (dem - nb) / _DIST[i]
        better = (~np.isnan(dem)) & (~np.isnan(nb)) & (slope > max_slope)
        fdir[better] = i
        max_slope[better] = slope[better]
    return fdir


def _flow_accumulation(fdir: np.ndarray) -> np.ndarray:
    """Compute flow accumulation using vectorized topological sort."""
    rows, cols = fdir.shape
    n = rows * cols
    flat_fdir = fdir.ravel()

    # Build flat target array: cell → downstream cell index (or -1)
    r_all, c_all = np.mgrid[0:rows, 0:cols]
    r_flat = r_all.ravel()
    c_flat = c_all.ravel()

    valid = flat_fdir >= 0
    nr = r_flat + _DR[np.clip(flat_fdir, 0, 7)]
    nc = c_flat + _DC[np.clip(flat_fdir, 0, 7)]
    in_bounds = valid & (nr >= 0) & (nr < rows) & (nc >= 0) & (nc < cols)

    target = np.full(n, -1, dtype=np.int64)
    target[in_bounds] = nr[in_bounds] * cols + nc[in_bounds]

    # Count in-degree for each cell
    in_degree = np.zeros(n, dtype=np.int32)
    valid_targets = target[target >= 0]
    np.add.at(in_degree, valid_targets, 1)

    # Topological sort with BFS
    acc = np.ones(n, dtype=np.float64)
    queue = np.where((in_degree == 0) & valid)[0]

    while len(queue) > 0:
        tgt = target[queue]
        valid_q = tgt >= 0
        if not np.any(valid_q):
            break
        valid_tgt = tgt[valid_q]
        valid_acc = acc[queue[valid_q]]
        np.add.at(acc, valid_tgt, valid_acc)
        np.add.at(in_degree, valid_tgt, -1)
        # Next batch: targets that now have in_degree 0
        candidates = np.unique(valid_tgt)
        queue = candidates[in_degree[candidates] == 0]

    return acc.reshape(rows, cols)


def _trace_streams(fdir: np.ndarray, acc: np.ndarray, threshold: int,
                   transform) -> list[LineString]:
    """Trace stream lines from headwater cells downstream."""
    rows, cols = fdir.shape
    stream_mask = acc >= threshold
    visited = np.zeros((rows, cols), dtype=bool)

    # Find stream heads: stream cells with no upstream stream neighbor flowing in
    is_head = stream_mask.copy()
    for i in range(8):
        opp = (i + 4) % 8  # opposite direction
        padded_fdir = np.pad(fdir, 1, mode="constant", constant_values=-1)
        padded_stream = np.pad(stream_mask, 1, mode="constant", constant_values=False)
        # Neighbor in direction 'opp' from each cell
        nb_fdir = padded_fdir[1 + _DR[opp]:rows + 1 + _DR[opp],
                              1 + _DC[opp]:cols + 1 + _DC[opp]]
        nb_stream = padded_stream[1 + _DR[opp]:rows + 1 + _DR[opp],
                                  1 + _DC[opp]:cols + 1 + _DC[opp]]
        # If that neighbor is a stream cell and flows toward us (direction i)
        flows_in = nb_stream & (nb_fdir == i)
        is_head[flows_in] = False

    # Trace from each head
    lines = []
    head_rows, head_cols = np.where(is_head)
    for start_r, start_c in zip(head_rows, head_cols):
        if visited[start_r, start_c]:
            continue
        coords = []
        cr, cc = int(start_r), int(start_c)
        while (0 <= cr < rows and 0 <= cc < cols
               and stream_mask[cr, cc] and not visited[cr, cc]):
            x, y = transform * (cc + 0.5, cr + 0.5)
            coords.append((x, y))
            visited[cr, cc] = True
            d = fdir[cr, cc]
            if d < 0:
                break
            cr, cc = cr + int(_DR[d]), cc + int(_DC[d])
        # Include junction point
        if (0 <= cr < rows and 0 <= cc < cols
                and stream_mask[cr, cc] and visited[cr, cc]):
            x, y = transform * (cc + 0.5, cr + 0.5)
            coords.append((x, y))
        if len(coords) >= 2:
            lines.append(LineString(coords))
    return lines


def delineate_streams(
    dem_path: Path,
    out_path: Path,
    threshold: int = 500,
) -> Path | None:
    """Extract stream network from DEM and save as shapefile.

    Parameters
    ----------
    dem_path : Path to clipped DEM GeoTIFF.
    out_path : Path for output streams shapefile.
    threshold : Minimum flow accumulation (in cells) to define a stream.

    Returns the output path, or None if no streams found.
    """
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float64)
        nodata = src.nodata
        transform = src.transform
        crs = src.crs

    print("    Filling sinks...")
    filled = _fill_sinks(dem, nodata)

    print("    Computing flow direction (D8)...")
    fdir = _flow_direction_d8(filled)

    print("    Computing flow accumulation...")
    acc = _flow_accumulation(fdir)

    print(f"    Extracting streams (threshold={threshold} cells)...")
    lines = _trace_streams(fdir, acc, threshold, transform)

    if not lines:
        print("    No streams found at this threshold.")
        return None

    gdf = gpd.GeoDataFrame(
        {"stream_id": range(len(lines))},
        geometry=lines,
        crs=crs,
    )
    gdf.to_file(out_path)
    print(f"    Streams written: {out_path} ({len(lines)} segments)")
    return out_path
