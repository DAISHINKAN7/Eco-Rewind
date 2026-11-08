"""Fixed UTM export grids per site and track.

The grid origin is snapped to multiples of 30 m, so the Track A 10 m grid and
the Track B 30 m grid nest exactly (one 30 m pixel = 3 x 3 10 m pixels), and
both line up with the native Sentinel-2 / HLS MGRS pixel lattice.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from pyproj import Transformer

SNAP_M = 30


@dataclass(frozen=True)
class Grid:
    crs: str
    res: int
    xmin: float
    ymax: float
    width: int
    height: int

    @property
    def xmax(self) -> float:
        return self.xmin + self.width * self.res

    @property
    def ymin(self) -> float:
        return self.ymax - self.height * self.res

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return self.xmin, self.ymin, self.xmax, self.ymax

    @property
    def crs_transform(self) -> list[float]:
        """Earth Engine / GDAL affine: [xScale, xShear, xOrigin, yShear, yScale, yOrigin]."""
        return [self.res, 0, self.xmin, 0, -self.res, self.ymax]


def utm_bounds(bounds_lonlat, crs: str, buffer_m: float = 0.0) -> tuple[float, float, float, float]:
    """Envelope of a lon/lat box in the target CRS (corners + edge points), plus a buffer."""
    w, s, e, n = bounds_lonlat
    t = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    lons = [w + (e - w) * i / 10 for i in range(11)]
    lats = [s + (n - s) * i / 10 for i in range(11)]
    pts = [(x, s) for x in lons] + [(x, n) for x in lons] + [(w, y) for y in lats] + [(e, y) for y in lats]
    xs, ys = zip(*(t.transform(*p) for p in pts))
    return min(xs) - buffer_m, min(ys) - buffer_m, max(xs) + buffer_m, max(ys) + buffer_m


def site_grid(bounds_lonlat, crs: str, res: int, buffer_m: float = 0.0) -> Grid:
    if SNAP_M % res:
        raise ValueError(f"resolution {res} must divide {SNAP_M}")
    x0, y0, x1, y1 = utm_bounds(bounds_lonlat, crs, buffer_m)
    xmin = math.floor(x0 / SNAP_M) * SNAP_M
    ymin = math.floor(y0 / SNAP_M) * SNAP_M
    xmax = math.ceil(x1 / SNAP_M) * SNAP_M
    ymax = math.ceil(y1 / SNAP_M) * SNAP_M
    return Grid(crs, res, xmin, ymax, int((xmax - xmin) // res), int((ymax - ymin) // res))
