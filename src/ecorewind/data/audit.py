"""Data audit for quarterly Sentinel-1/2 composites (plan section "Data inventory and audit").

Covers the six checks: completeness, geometry, bands, value ranges, coverage
and event timing. Everything here only reads rasters; nothing is written next
to the source files.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import rasterio

OPTICAL = ("Blue", "Green", "Red", "NIR")
INDICES = ("NDVI", "NDWI")
SAR = ("SAR_VV", "SAR_VH")
SUSPECT_FILLS = (-9999.0, -32768.0, -1.0, 0.0, 65535.0)

_NAME_RE = re.compile(
    r"^(?P<site>[A-Za-z]+)_(?:(?P<version>v\d+)_)?(?P<year>\d{4})_Q(?P<q>[1-4])_[A-Za-z]+"
    r"(?P<suffix>(?:_[A-Za-z]+)*)\.tif$"
)


@dataclass
class FileName:
    site: str
    version: str
    year: int
    quarter: int
    tags: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.year}Q{self.quarter}"

    @property
    def is_mask(self) -> bool:
        return "mask" in self.tags

    @property
    def is_interpolated(self) -> bool:
        return "INTERPOLATED" in self.tags


def parse_name(name: str) -> FileName | None:
    m = _NAME_RE.match(name)
    if not m:
        return None
    tags = [t for t in m["suffix"].split("_") if t]
    return FileName(m["site"].lower(), m["version"] or "v1", int(m["year"]), int(m["q"]), tags)


def quarter_range(start: str, end: str) -> list[str]:
    (y0, q0), (y1, q1) = (map(int, s.split("Q")) for s in (start, end))
    out, y, q = [], y0, q0
    while (y, q) <= (y1, q1):
        out.append(f"{y}Q{q}")
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def quarter_of(d: date) -> str:
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def event_phase(key: str, landfall: date) -> str:
    ev = quarter_of(landfall)
    if key == ev:
        return "event"
    return "pre" if _qkey(key) < _qkey(ev) else "post"


def _qkey(k: str) -> tuple[int, int]:
    y, q = k.split("Q")
    return int(y), int(q)


def pixel_size_m(ds) -> tuple[float, float]:
    """Pixel size in metres; approximates for geographic CRSs at the scene centre."""
    rx, ry = abs(ds.transform.a), abs(ds.transform.e)
    if ds.crs is not None and ds.crs.is_geographic:
        lat = (ds.bounds.top + ds.bounds.bottom) / 2
        return rx * 111_320 * math.cos(math.radians(lat)), ry * 110_574
    return rx, ry


def _band_stats(a: np.ndarray, nodata) -> dict:
    finite = np.isfinite(a)
    valid = finite & (a != nodata) if nodata is not None and not np.isnan(nodata) else finite
    v = a[valid]
    s = {
        "n": int(a.size),
        "nan_frac": float(1 - finite.mean()),
        "nodata_frac": float((a == nodata).mean()) if nodata is not None and not np.isnan(nodata) else 0.0,
        "zero_frac": float((a == 0).mean()),
        "valid_frac": float(valid.mean()),
        "fills": {str(f): float((a == f).mean()) for f in SUSPECT_FILLS if (a == f).mean() > 0.001},
    }
    if v.size:
        p = np.percentile(v, [0, 1, 50, 99, 100])
        s.update(min=float(p[0]), p1=float(p[1]), median=float(p[2]), p99=float(p[3]), max=float(p[4]))
    return s


def inspect_file(path: str | Path, stride: int = 1) -> dict:
    """Read one GeoTIFF and return geometry, band and value statistics.

    stride>1 decimates on read, which keeps Drive I/O and memory low.
    """
    path = Path(path)
    with rasterio.open(path) as ds:
        out_shape = (max(1, ds.height // stride), max(1, ds.width // stride))
        names = [d or f"band{i + 1}" for i, d in enumerate(ds.descriptions)]
        px = pixel_size_m(ds)
        rec = {
            "file": path.name,
            "size_mb": round(path.stat().st_size / 1e6, 1),
            "crs": ds.crs.to_string() if ds.crs else None,
            "geographic": bool(ds.crs and ds.crs.is_geographic),
            "width": ds.width,
            "height": ds.height,
            "transform": tuple(round(x, 10) for x in ds.transform[:6]),
            "bounds": tuple(round(x, 6) for x in ds.bounds),
            "pixel_m": (round(px[0], 2), round(px[1], 2)),
            "count": ds.count,
            "dtype": ds.dtypes[0],
            "nodata": ds.nodata,
            "bands": names,
            "stats": {},
        }
        arrays = {}
        for i, name in enumerate(names, start=1):
            a = ds.read(i, out_shape=out_shape).astype("float64")
            arrays[name] = a
            rec["stats"][name] = _band_stats(a, ds.nodata)

    rec["coverage"] = _coverage(arrays, rec["nodata"])
    rec["scale"] = _scales(rec["stats"])
    return rec


def _valid(a: np.ndarray, nodata) -> np.ndarray:
    m = np.isfinite(a)
    if nodata is not None and not np.isnan(nodata):
        m &= a != nodata
    return m


def _coverage(arrays: dict, nodata) -> dict:
    opt = [arrays[b] for b in OPTICAL if b in arrays]
    sar = [arrays[b] for b in SAR if b in arrays]
    cov = {}
    if opt:
        m = np.logical_and.reduce([_valid(a, nodata) for a in opt])
        m &= ~np.logical_and.reduce([a == 0 for a in opt])  # all-zero optical = fill
        cov["optical_valid"] = float(m.mean())
    for b in SAR:
        if b in arrays:
            a = arrays[b]
            cov[f"{b}_valid"] = float((_valid(a, nodata) & (a != 0)).mean())
    if "NDVI" in arrays:
        a = arrays["NDVI"]
        cov["ndvi_eq_minus1"] = float((a == -1).mean())
        cov["ndvi_out_of_range"] = float((_valid(a, nodata) & ((a < -1) | (a > 1))).mean())
    return cov


def _scales(stats: dict) -> dict:
    out = {}
    opt = [stats[b]["p99"] for b in OPTICAL if b in stats and "p99" in stats[b]]
    if opt:
        out["optical"] = "0-10000 (DN)" if max(opt) > 2 else "0-1 (reflectance)"
    for b in SAR:
        if b in stats and "median" in stats[b]:
            med = stats[b]["median"]
            out[b] = "zero-filled" if med == 0 else "dB" if med < 0 else "linear"
    return out


def grid_signature(rec: dict) -> tuple:
    return rec["crs"], rec["width"], rec["height"], rec["transform"]


def check_alignment(records: list[dict]) -> tuple[dict, tuple]:
    """Compare every file's grid to the most common grid of its source."""
    sigs = Counter(grid_signature(r) for r in records)
    ref, _ = sigs.most_common(1)[0]
    return {r["file"]: grid_signature(r) == ref for r in records}, ref


def completeness(names: list[FileName], calendar: list[str]) -> dict:
    data = [n for n in names if not n.is_mask]
    present = Counter(n.key for n in data)
    return {
        "present": sorted(present, key=_qkey),
        "missing": [k for k in calendar if k not in present],
        "duplicates": sorted(k for k, c in present.items() if c > 1),
        "outside_calendar": sorted(k for k in present if k not in calendar),
        "interpolated": sorted(n.key for n in data if n.is_interpolated),
        "masks": sorted(n.key for n in names if n.is_mask),
    }
