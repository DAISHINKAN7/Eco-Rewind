"""Per site/track data cube in Zarr (MASTER_PROMPT §6.1).

Group layout
  data          (T, C, H, W) float32   channels = masks.CHANNELS; reflectance 0-1, indices, SAR in dB
  valid         (T, C, H, W) bool      per-channel validity (masks.py); invalid values are left as NaN
  n_clear       (T, H, W)    uint8     clear optical observations
  n_s1          (T, H, W)    uint8     Sentinel-1 acquisitions
  partial_*     same, for the event-quarter _PRE / _POST composites (P = 2)
  static/*      elevation_m, worldcover, coast_dist_m (H, W)
  attrs         site, track, keys, partial_keys, channels, crs, transform, data_hash, sources
T holds regular quarters only; the event quarter appears only as partials.
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import zarr
from zarr.codecs import BloscCodec

from . import io
from .indices import compute_indices
from .masks import CHANNELS, REFLECTANCE, optical_valid, sar_valid
from .periods import periods

COMPRESSOR = [BloscCodec(cname="zstd", clevel=3, shuffle="bitshuffle")]


def period_keys(start: str, end: str, landfall) -> tuple[list[str], list[str]]:
    ps = periods(start, end, landfall)
    return [p.key for p in ps if p.kind == "quarter"], [p.key for p in ps if p.kind != "quarter"]


def load_period(exports: Path, site: str, track: str, key: str, max_reflectance: float):
    """Return data (C, H, W), valid (C, H, W), n_clear, n_s1 for one period."""
    opt, meta = io.read_named(exports / io.file_name(site, track, key))
    s1, meta_s1 = io.read_named(exports / io.file_name(site, track, key, "S1"))
    if meta_s1["transform"] != meta["transform"] or meta_s1["shape"] != meta["shape"]:
        raise ValueError(f"{site} {track} {key}: optical and S1 grids differ")
    scale = io.OPTICAL_SCALE[track]
    refl = {b: opt[b] * scale for b in REFLECTANCE}
    n_clear = np.nan_to_num(opt["n_clear_obs"], nan=0)
    n_s1 = np.nan_to_num(s1["n_s1_obs"], nan=0)
    rv = optical_valid(refl, n_clear, None, max_reflectance)
    idx, iv = compute_indices(refl, rv)
    sar = {"VV": s1["VV"] * io.SAR_SCALE, "VH": s1["VH"] * io.SAR_SCALE, "VH_VV": s1["VH_VV_ratio"] * io.SAR_SCALE}
    sv = sar_valid(sar["VV"], sar["VH"], n_s1)
    vals = {**refl, **idx, **sar}
    oks = {**rv, **iv, **{k: sv for k in sar}}
    data = np.stack([np.where(oks[c], vals[c], np.nan).astype("float32") for c in CHANNELS])
    valid = np.stack([oks[c] for c in CHANNELS])
    return data, valid, n_clear.astype("uint8"), n_s1.astype("uint8"), meta


def _arr(g, name, shape, dtype, chunks):
    return g.create_array(name=name, shape=shape, dtype=dtype, chunks=chunks, compressors=COMPRESSOR,
                          fill_value=np.nan if np.dtype(dtype).kind == "f" else 0)


def build_cube(exports: Path, out: Path, site: str, track: str, start: str, end: str, landfall,
               max_reflectance: float = 1.0, chunk: int = 256, log=print) -> Path:
    exports, out = Path(exports), Path(out)
    keys, pkeys = period_keys(start, end, landfall)
    sources = sorted(exports / io.file_name(site, track, k, s) for k in keys + pkeys for s in ("", "S1"))
    sources.append(exports / io.file_name(site, track, None, "static"))
    missing = [p.name for p in sources if not p.exists()]
    if missing:
        raise FileNotFoundError(f"missing exports: {missing[:5]}")
    if out.exists():
        shutil.rmtree(out)
    _, meta = io.read_named(sources[0])
    H, W = meta["shape"]
    C = len(CHANNELS)
    g = zarr.open_group(str(out), mode="w")
    for prefix, ks in (("", keys), ("partial_", pkeys)):
        T = len(ks)
        d = _arr(g, prefix + "data", (T, C, H, W), "float32", (1, 1, chunk, chunk))
        v = _arr(g, prefix + "valid", (T, C, H, W), "bool", (1, 1, chunk, chunk))
        nc = _arr(g, prefix + "n_clear", (T, H, W), "uint8", (1, chunk, chunk))
        ns = _arr(g, prefix + "n_s1", (T, H, W), "uint8", (1, chunk, chunk))
        for t, k in enumerate(ks):
            data, valid, n_clear, n_s1, m = load_period(exports, site, track, k, max_reflectance)
            if m["transform"] != meta["transform"] or m["shape"] != meta["shape"]:
                raise ValueError(f"{k}: grid differs from {sources[0].name}")
            d[t], v[t], nc[t], ns[t] = data, valid, n_clear, n_s1
            log(f"  {site} {track} {k}: optical {valid[0].mean():.0%} SAR {valid[-1].mean():.0%}")
    st, _ = io.read_named(exports / io.file_name(site, track, None, "static"))
    sg = g.create_group("static")
    for name, arr, dt in (("elevation_m", st["elevation_m"], "float32"),
                          ("worldcover", np.nan_to_num(st["worldcover"], nan=0), "uint8")):
        a = _arr(sg, name, (H, W), dt, (chunk, chunk))
        a[:] = arr.astype(dt)
    g.attrs.update({
        "site": site, "track": track, "keys": keys, "partial_keys": pkeys, "channels": list(CHANNELS),
        "crs": meta["crs"], "transform": list(meta["transform"]), "shape": [H, W],
        "max_reflectance": max_reflectance, "data_hash": io.sha256_files(sources),
        "sources": [p.name for p in sources], "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    return out


class Cube:
    """Read access to a built cube (directory or .zip store)."""

    def __init__(self, path: str | Path):
        path = str(path)
        store = zarr.storage.ZipStore(path, mode="r") if path.endswith(".zip") else path
        self.g = zarr.open_group(store, mode="r")
        a = dict(self.g.attrs)
        self.site, self.track = a["site"], a["track"]
        self.keys, self.partial_keys = list(a["keys"]), list(a["partial_keys"])
        self.channels = list(a["channels"])
        self.transform, self.crs, self.shape = a["transform"], a["crs"], tuple(a["shape"])
        self.data_hash = a["data_hash"]
        self.data, self.valid = self.g["data"], self.g["valid"]
        self.n_clear, self.n_s1 = self.g["n_clear"], self.g["n_s1"]

    def static(self, name: str) -> np.ndarray:
        return self.g["static"][name][:]

    def channel(self, name: str) -> int:
        return self.channels.index(name)
