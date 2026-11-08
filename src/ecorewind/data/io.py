"""Read Phase 0 exports by band name (never by position; v1 had files with band1..band7)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import rasterio

OPTICAL_SCALE = {"A": 1e-4, "B": 1.0}   # Track A stores DN (reflectance x 1e4), Track B reflectance
SAR_SCALE = 0.01                          # int16 dB x 100


def file_name(site: str, track: str, key: str | None, sensor: str = "") -> str:
    parts = [site, track] + ([sensor] if sensor else []) + ([key] if key else [])
    return "_".join(parts) + ".tif"


def read_named(path: str | Path) -> tuple[dict[str, np.ndarray], dict]:
    """All bands as float32 with nodata -> NaN, keyed by the band description stored in the file."""
    with rasterio.open(path) as ds:
        names = list(ds.descriptions)
        if not all(names) or len(set(names)) != len(names):
            raise ValueError(f"{path}: missing or duplicate band names {names}")
        a = ds.read().astype("float32")
        if ds.nodata is not None:
            a[a == ds.nodata] = np.nan
        meta = {"crs": ds.crs.to_string(), "transform": tuple(ds.transform[:6]), "shape": (ds.height, ds.width)}
    return dict(zip(names, a)), meta


def sha256_files(paths: list[Path], chunk: int = 1 << 23) -> str:
    """Hash of file names and contents, in the order given (callers sort)."""
    h = hashlib.sha256()
    for p in paths:
        h.update(p.name.encode())
        with open(p, "rb") as f:
            while b := f.read(chunk):
                h.update(b)
    return h.hexdigest()
