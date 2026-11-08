"""Static context channels and evaluation masks (MASTER_PROMPT §5.6, §6.5).

- elevation_m: Copernicus GLO-30 (GLO30_2024_1), bilinear to the grid.
- coast_dist_m: distance to the nearest WorldCover 'permanent water' (80) pixel, computed locally inside
  the buffered grid (EE distance kernels are limited to 512 px). Inland water counts too: a proxy.
- landcover one-hot from WorldCover 2021 (post-Irma: used only as context and to exclude non-wetland).
- wetland_main: herbaceous wetland (90) or mangroves (95). wetland_strict: wetland_main eroded by
  `erode_px` pixels, i.e. away from class edges and mixed pixels (robustness variant).
- aoi: pixel centres inside the original, un-buffered AOI (evaluation never leaves it).
"""
from __future__ import annotations

import numpy as np
from pyproj import Transformer
from scipy import ndimage

WORLDCOVER = {10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built", 60: "bare", 70: "snow",
              80: "water", 90: "herb_wetland", 95: "mangrove", 100: "moss"}
ONEHOT_CLASSES = (10, 30, 80, 90, 95)          # everything else -> "other"
WETLAND = (90, 95)


def pixel_centres(transform, shape):
    a, _, c, _, e, f = transform[:6]
    rows, cols = np.indices(shape)
    return c + (cols + 0.5) * a, f + (rows + 0.5) * e


def aoi_mask(transform, shape, crs: str, bounds_lonlat) -> np.ndarray:
    xs, ys = pixel_centres(transform, shape)
    lon, lat = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform(xs, ys)
    w, s, e, n = bounds_lonlat
    return (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)


def coast_distance(worldcover: np.ndarray, res: float) -> np.ndarray:
    water = worldcover == 80
    if not water.any():
        return np.full(worldcover.shape, np.inf, dtype="float32")
    return (ndimage.distance_transform_edt(~water) * res).astype("float32")


def static_layers(cube, bounds_lonlat, erode_px: int = 1) -> dict[str, np.ndarray]:
    wc = cube.static("worldcover")
    res = abs(cube.transform[0])
    out = {"elevation_m": cube.static("elevation_m"), "coast_dist_m": coast_distance(wc, res)}
    for k in ONEHOT_CLASSES:
        out[f"lc_{WORLDCOVER[k]}"] = (wc == k).astype("float32")
    out["lc_other"] = (~np.isin(wc, ONEHOT_CLASSES)).astype("float32")
    main = np.isin(wc, WETLAND)
    out["wetland_main"] = main
    out["wetland_strict"] = ndimage.binary_erosion(main, iterations=erode_px) if erode_px else main
    out["aoi"] = aoi_mask(cube.transform, cube.shape, cube.crs, bounds_lonlat)
    return out
