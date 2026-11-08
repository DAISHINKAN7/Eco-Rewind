"""Audit of the Phase 0 re-exports against the gate in MASTER_PROMPT.md §5.7.

Gate: UTM grids, square pixels, identical grid across all files of a site/track
(and Track B nesting onto Track A); every period present; SAR valid in most quarters
from 2015 on; no NDVI = -1 artefacts after local recomputation.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import rasterio

NAME_RE = re.compile(
    r"^(?P<site>[a-z]+)_(?P<track>[AB])(?:_(?P<sensor>S1|static))?(?:_(?P<key>\d{4}Q[1-4](?:_PRE|_POST)?))?\.tif$"
)
GENERIC = re.compile(r"^(band_?\d+|)$", re.I)


def parse(name: str) -> dict | None:
    m = NAME_RE.match(name)
    if not m:
        return None
    d = m.groupdict()
    d["sensor"] = d["sensor"] or "optical"
    return d


def band_names(ds, manifest_bands: list[str] | None) -> list[str]:
    desc = list(ds.descriptions)
    if all(d and not GENERIC.match(d) for d in desc):
        return desc
    if manifest_bands and len(manifest_bands) == ds.count:
        return list(manifest_bands)
    return [f"band{i + 1}" for i in range(ds.count)]


def ndvi(red: np.ndarray, nir: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """NDVI only where both bands are valid and the denominator is not ~0; NaN elsewhere."""
    red, nir = red.astype("float64"), nir.astype("float64")
    den = nir + red
    ok = valid & np.isfinite(den) & (np.abs(den) > 1e-6)
    out = np.full(red.shape, np.nan)
    out[ok] = (nir[ok] - red[ok]) / den[ok]
    return out


def inspect(path: Path, manifest_bands: list[str] | None = None, stride: int = 1) -> dict:
    meta = parse(path.name)
    with rasterio.open(path) as ds:
        names = band_names(ds, manifest_bands)
        shape = (max(1, ds.height // stride), max(1, ds.width // stride))
        arr = {n: ds.read(i + 1, out_shape=shape).astype("float64") for i, n in enumerate(names)}
        nod = ds.nodata
        rec = {
            "file": path.name, **meta, "crs": ds.crs.to_string() if ds.crs else None,
            "epsg": ds.crs.to_epsg() if ds.crs else None, "res": (abs(ds.transform.a), abs(ds.transform.e)),
            "transform": tuple(ds.transform[:6]), "width": ds.width, "height": ds.height,
            "bands": names, "dtype": ds.dtypes[0], "nodata": nod, "size_mb": round(path.stat().st_size / 1e6, 1),
        }

    def valid(a):
        m = np.isfinite(a)
        return m & (a != nod) if nod is not None else m

    if meta["sensor"] == "optical":
        refl = [n for n in ("Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2") if n in arr]
        v = np.logical_and.reduce([valid(arr[n]) & (arr[n] != 0) for n in refl]) if refl else None
        if "n_clear_obs" in arr:
            n = arr["n_clear_obs"]
            rec["n_clear_median"] = float(np.median(n))
            rec["n_clear_zero_frac"] = float((n == 0).mean())
            if v is not None:
                v &= n > 0
        if v is not None:
            rec["optical_valid"] = float(v.mean())
            p99 = max(float(np.percentile(arr[n][v], 99)) for n in refl) if v.any() else None
            rec["optical_scale"] = None if p99 is None else ("DN 0-10000" if p99 > 2 else "reflectance 0-1")
        if {"Red", "NIR"} <= arr.keys() and v is not None:
            nd = ndvi(arr["Red"], arr["NIR"], v & (arr["Red"] > 0) & (arr["NIR"] > 0))   # indices only where inputs > 0
            fin = np.isfinite(nd)
            rec["ndvi_median"] = float(np.nanmedian(nd)) if fin.any() else None
            rec["ndvi_eq_minus1"] = float((nd[fin] == -1).mean()) if fin.any() else 0.0
            rec["ndvi_out_of_range"] = float(((nd[fin] < -1) | (nd[fin] > 1)).mean()) if fin.any() else 0.0
    elif meta["sensor"] == "S1":
        if rec["dtype"] == "int16":   # stored as dB x 100
            for b in ("VV", "VH", "VH_VV_ratio"):
                if b in arr:
                    arr[b] = np.where(valid(arr[b]), arr[b] * 0.01, np.nan)
        n = arr.get("n_s1_obs")
        if n is not None:
            rec["n_s1_median"] = float(np.median(n))
            rec["sar_valid"] = float(((n > 0) & valid(arr["VV"]) & valid(arr["VH"])).mean())
        if "VV" in arr and valid(arr["VV"]).any():
            rec["vv_median_db"] = float(np.median(arr["VV"][valid(arr["VV"])]))
    return rec


def grid_key(r: dict) -> tuple:
    return r["crs"], r["width"], r["height"], tuple(round(x, 6) for x in r["transform"])


def gate_checks(recs: list[dict], expected: dict[tuple[str, str], list[str]],
                sar_from: str = "2015Q1", sar_majority: float = 0.8) -> list[tuple[str, bool, str]]:
    """Return (check, passed, detail) rows. expected maps (site, track) -> list of period keys."""
    out = []
    by_st: dict[tuple, list[dict]] = {}
    for r in recs:
        by_st.setdefault((r["site"], r["track"]), []).append(r)

    utm = [r["file"] for r in recs if not (r["epsg"] and 32601 <= r["epsg"] <= 32760)]
    out.append(("UTM CRS on every file", not utm, ", ".join(utm[:5])))
    sq = [r["file"] for r in recs if abs(r["res"][0] - r["res"][1]) > 1e-6]
    out.append(("Square pixels", not sq, ", ".join(sq[:5])))

    for (site, track), rs in sorted(by_st.items()):
        keys = {grid_key(r) for r in rs}
        out.append((f"{site}/{track}: one grid across all files", len(keys) == 1,
                    f"{len(keys)} distinct grids" if len(keys) > 1 else f"{rs[0]['width']}x{rs[0]['height']} @ {rs[0]['res'][0]:g} m"))
        exp = expected.get((site, track), [])
        for sensor in ("optical", "S1"):
            have = {r["key"] for r in rs if r["sensor"] == sensor}
            miss = [k for k in exp if k not in have]
            out.append((f"{site}/{track}/{sensor}: all {len(exp)} periods present", not miss, ", ".join(miss)))
        s1 = [r for r in rs if r["sensor"] == "S1" and r["key"] and r["key"][:6] >= sar_from]
        if s1:
            good = [r for r in s1 if r.get("sar_valid", 0) >= 0.5]
            frac = len(good) / len(s1)
            out.append((f"{site}/{track}: SAR valid in ≥{sar_majority:.0%} of periods from {sar_from}",
                        frac >= sar_majority, f"{len(good)}/{len(s1)} periods"))
        opt = [r for r in rs if r["sensor"] == "optical"]
        bad = [r["file"] for r in opt if r.get("ndvi_eq_minus1", 0) > 0.001 or r.get("ndvi_out_of_range", 0) > 0]
        out.append((f"{site}/{track}: no NDVI = −1 / out-of-range artefacts", not bad, ", ".join(bad[:5])))

    for site in {s for s, _ in by_st}:
        a, b = by_st.get((site, "A")), by_st.get((site, "B"))
        if a and b:
            ta, tb = a[0]["transform"], b[0]["transform"]
            nest = (abs(ta[2] - tb[2]) < 1e-6 and abs(ta[5] - tb[5]) < 1e-6 and abs(tb[0] - 3 * ta[0]) < 1e-6
                    and a[0]["width"] == 3 * b[0]["width"] and a[0]["height"] == 3 * b[0]["height"])
            out.append((f"{site}: Track B grid nests in Track A (3×3)", nest, f"A {ta}, B {tb}"))
    return out
