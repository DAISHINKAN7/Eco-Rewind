"""Thorough checks of the Phase 0 re-exports (beyond the gate in audit_exports.py).

Self-contained (numpy, pandas, rasterio, matplotlib) so it can run from a single file on Drive:

    python deep_checks.py --dir /content/drive/MyDrive/EcoRewind2_exports \
                          --out /content/drive/MyDrive/EcoRewind2/reports/deep_checks

Checks
  1  Inventory      every expected file exists once; no "(1)" duplicates or unknown files
  2  Grid           CRS / shape / transform identical per site+track; Track B nests 3x3 in Track A
  3  Bands & types  band count, dtype, nodata per file kind; static bands sane
  4  Values         reflectance scale, negative-reflectance share, NDVI/NDWI/NDMI range, SAR dB range
  5  Coverage       optical valid share and clear-observation counts; SAR valid share and n_s1_obs
  6  Date windows   doy_mean inside each file's compositing window (PRE/POST split respected)
  7  Time series    per-quarter NDVI / VV medians vs same-season median (robust z-score)
  8  Cross-track    Track A aggregated to 30 m vs Track B, same quarter: NDVI correlation and bias
  9  SAR A vs B     30 m SAR vs 10 m SAR aggregated in linear power
 10  Static         elevation range, WorldCover classes, wetland share inside the AOI
Outputs: deep_checks.md (PASS / WARN / FAIL per check), per-file CSV, figures/*.png.
Per-file statistics are cached in <out>/cache, so a dropped Colab session resumes.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

# ----------------------------------------------------------------------------- study design
SITES = {
    "everglades": {"landfall": date(2017, 9, 10), "crs": "EPSG:32617", "aoi": (-80.8988, 25.2100, -80.7009, 25.3901)},
    "mississippi": {"landfall": date(2021, 8, 29), "crs": "EPSG:32615", "aoi": (-90.8025, 29.3600, -90.5972, 29.5400)},
}
TRACKS = {"A": {"res": 10, "start": "2015Q3", "end": "2023Q4"}, "B": {"res": 30, "start": "2013Q2", "end": "2023Q4"}}
POST_OFFSET = 3
NODATA = -32768
OPT_BANDS = {"A": ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2", "n_clear_obs", "doy_mean"],
             "B": ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2", "n_clear_obs", "doy_mean", "water_frac"]}
S1_BANDS = ["VV", "VH", "VH_VV_ratio", "n_s1_obs"]
STATIC_BANDS = ["elevation_m", "worldcover"]
WORLDCOVER = {10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built", 60: "bare", 70: "snow",
              80: "water", 90: "herb. wetland", 95: "mangrove", 100: "moss"}
NAME_RE = re.compile(r"^(?P<site>[a-z]+)_(?P<track>[AB])(?:_(?P<sensor>S1|static))?(?:_(?P<key>\d{4}Q[1-4](?:_PRE|_POST)?))?\.tif$")


def qkeys(start, end):
    y, q = map(int, start.split("Q"))
    y1, q1 = map(int, end.split("Q"))
    out = []
    while (y, q) <= (y1, q1):
        out.append(f"{y}Q{q}")
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def qwindow(k):
    y, q = map(int, k.split("Q"))
    return date(y, 3 * q - 2, 1), (date(y + 1, 1, 1) if q == 4 else date(y, 3 * q + 1, 1))


def periods(site, track):
    lf = SITES[site]["landfall"]
    ev = f"{lf.year}Q{(lf.month - 1) // 3 + 1}"
    out = {}
    for k in qkeys(TRACKS[track]["start"], TRACKS[track]["end"]):
        s, e = qwindow(k)
        if k == ev:
            out[f"{k}_PRE"] = (s, lf)
            out[f"{k}_POST"] = (lf + timedelta(days=POST_OFFSET), e)
        else:
            out[k] = (s, e)
    return out


def expected_files():
    exp = {}
    for s in SITES:
        for t in TRACKS:
            for k, w in periods(s, t).items():
                exp[f"{s}_{t}_{k}.tif"] = ("optical", s, t, k, w)
                exp[f"{s}_{t}_S1_{k}.tif"] = ("S1", s, t, k, w)
            exp[f"{s}_{t}_static.tif"] = ("static", s, t, None, None)
    return exp


# ----------------------------------------------------------------------------- per-file stats
def read(ds, stride):
    shape = (max(1, ds.height // stride), max(1, ds.width // stride))
    a = ds.read(out_shape=(ds.count, *shape)).astype("float64")
    if ds.nodata is not None:
        a[a == ds.nodata] = np.nan
    return a


def pct(v, q):
    return float(np.percentile(v, q)) if v.size else None


def index(a, b, valid):
    den = a + b
    ok = valid & (np.abs(den) > 1e-6)
    out = np.full(a.shape, np.nan)
    out[ok] = (a[ok] - b[ok]) / den[ok]
    return out


def optical_stats(a, track, window, scale):
    B = {n: a[i] for i, n in enumerate(OPT_BANDS[track])}
    refl = [B[n] * scale for n in OPT_BANDS[track][:6]]
    finite = np.logical_and.reduce([np.isfinite(r) for r in refl])
    n = B["n_clear_obs"]
    valid = finite & (n > 0)
    pos = valid & np.logical_and.reduce([r > 0 for r in refl])
    r = dict(zip(OPT_BANDS[track][:6], refl))
    ndvi, ndwi, ndmi = index(r["NIR"], r["Red"], pos), index(r["Green"], r["NIR"], pos), index(r["NIR"], r["SWIR1"], pos)
    s = {"valid": float(valid.mean()), "neg_refl": float((valid & ~pos).sum() / max(valid.sum(), 1)),
         "n_clear_median": float(np.median(n[np.isfinite(n)])) if np.isfinite(n).any() else 0.0,
         "n_clear_zero": float((n == 0).mean()), "n_clear_max": float(np.nanmax(n)) if np.isfinite(n).any() else 0.0}
    for k, v in r.items():
        vv = v[valid]
        s[f"{k}_med"], s[f"{k}_p99"] = pct(vv, 50), pct(vv, 99)
    for k, v in (("ndvi", ndvi), ("ndwi", ndwi), ("ndmi", ndmi)):
        f = v[np.isfinite(v)]
        s[f"{k}_med"], s[f"{k}_p1"], s[f"{k}_p99"] = pct(f, 50), pct(f, 1), pct(f, 99)
        s[f"{k}_eq_pm1"] = float((np.abs(f) == 1).mean()) if f.size else 0.0
    d = B["doy_mean"][valid]
    if d.size and window:
        lo, hi = window[0].timetuple().tm_yday, (window[1] - timedelta(days=1)).timetuple().tm_yday
        s["doy_min"], s["doy_max"] = float(d.min()), float(d.max())
        s["doy_outside"] = float(((d < lo - 0.5) | (d > hi + 0.5)).mean())
        s["doy_lo"], s["doy_hi"] = lo, hi
    if track == "B":
        w = B["water_frac"][valid]
        s["water_frac_mean"] = float(w.mean()) if w.size else None
    return s, ndvi


def s1_stats(a, dtype):
    B = {n: a[i] for i, n in enumerate(S1_BANDS)}
    k = 0.01 if dtype == "int16" else 1.0
    vv, vh, n = B["VV"] * k, B["VH"] * k, B["n_s1_obs"]
    valid = np.isfinite(vv) & np.isfinite(vh) & (n > 0)
    s = {"valid": float(valid.mean()), "n_s1_median": float(np.nanmedian(n)), "n_s1_max": float(np.nanmax(n))}
    for nm, v in (("vv", vv), ("vh", vh), ("ratio", B["VH_VV_ratio"] * k)):
        f = v[valid]
        s[f"{nm}_med"], s[f"{nm}_p1"], s[f"{nm}_p99"] = pct(f, 50), pct(f, 1), pct(f, 99)
    s["vv_gt5db"] = float((vv[valid] > 5).mean()) if valid.any() else 0.0
    s["vh_gt_vv"] = float((vh[valid] > vv[valid]).mean()) if valid.any() else 0.0
    return s


def static_stats(a, site, ds):
    elev, wc = a[0], a[1]
    s = {"elev_min": float(np.nanmin(elev)), "elev_med": float(np.nanmedian(elev)), "elev_max": float(np.nanmax(elev)),
         "elev_nan": float(np.isnan(elev).mean())}
    # restrict class shares to the un-buffered AOI
    from rasterio.warp import transform_bounds
    w, so, e, n = transform_bounds("EPSG:4326", ds.crs, *SITES[site]["aoi"])
    rows, cols = np.indices(wc.shape)
    sy, sx = ds.height / wc.shape[0], ds.width / wc.shape[1]
    xs = ds.transform.c + (cols + 0.5) * sx * ds.transform.a
    ys = ds.transform.f + (rows + 0.5) * sy * ds.transform.e
    inside = (xs >= w) & (xs <= e) & (ys >= so) & (ys <= n)
    vals, cnt = np.unique(wc[inside & np.isfinite(wc)], return_counts=True)
    tot = cnt.sum()
    s["classes"] = {WORLDCOVER.get(int(v), str(int(v))): round(c / tot, 4) for v, c in zip(vals, cnt)}
    s["unknown_classes"] = [int(v) for v in vals if int(v) not in WORLDCOVER]
    s["wetland_share"] = round(sum(c for v, c in zip(vals, cnt) if int(v) in (90, 95)) / tot, 4) if tot else 0.0
    return s


def inspect(path, meta, stride):
    kind, site, track, key, window = meta
    with rasterio.open(path) as ds:
        rec = {"file": path.name, "kind": kind, "site": site, "track": track, "key": key,
               "crs": ds.crs.to_string() if ds.crs else None, "w": ds.width, "h": ds.height,
               "transform": [round(x, 6) for x in ds.transform[:6]], "res": [abs(ds.transform.a), abs(ds.transform.e)],
               "count": ds.count, "dtype": ds.dtypes[0], "nodata": ds.nodata, "descriptions": list(ds.descriptions),
               "size_mb": round(path.stat().st_size / 1e6, 1)}
        a = read(ds, stride)
        if kind == "optical":
            if ds.count != len(OPT_BANDS[track]):
                rec["error"] = f"expected {len(OPT_BANDS[track])} bands"
                return rec, None
            scale = 1e-4 if track == "A" else 1.0
            st, ndvi = optical_stats(a, track, window, scale)
            rec.update(st)
            return rec, ndvi
        if kind == "S1":
            rec.update(s1_stats(a, ds.dtypes[0]))
        else:
            rec.update(static_stats(a, site, ds))
    return rec, None


# ----------------------------------------------------------------------------- checks
class Report:
    def __init__(self):
        self.rows, self.sections = [], []

    def add(self, check, status, detail=""):
        self.rows.append((check, status, detail))

    def section(self, title, lines):
        self.sections.append("\n".join([f"## {title}", "", *lines, ""]))


def robust_z(x):
    x = np.asarray(x, float)
    med = np.nanmedian(x)
    mad = np.nanmedian(np.abs(x - med)) * 1.4826
    return (x - med) / mad if mad > 0 else np.zeros_like(x)


def agg3(a):
    h, w = a.shape[0] // 3 * 3, a.shape[1] // 3 * 3
    return np.nanmean(a[:h, :w].reshape(h // 3, 3, w // 3, 3), axis=(1, 3))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stride", type=int, default=1, help="read every Nth pixel for per-file stats (1 = full)")
    ap.add_argument("--max-files", type=int)
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args()
    src, out = Path(a.dir), Path(a.out)
    (out / "cache").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(exist_ok=True)
    R = Report()
    exp = expected_files()

    # 1 inventory -------------------------------------------------------------
    present = sorted(p.name for p in src.glob("*.tif"))
    dup = [f for f in present if re.search(r" \(\d+\)\.tif$", f)]
    unknown = [f for f in present if f not in exp and f not in dup]
    missing = [f for f in exp if f not in present]
    R.add("1 Inventory: all expected files present", "PASS" if not missing else "FAIL",
          f"{len(exp) - len(missing)}/{len(exp)}" + (f"; missing: {', '.join(missing[:12])}" if missing else ""))
    R.add("1 Inventory: no duplicate copies", "PASS" if not dup else "WARN", ", ".join(dup[:12]))
    R.add("1 Inventory: no unexpected files", "PASS" if not unknown else "WARN", ", ".join(unknown[:12]))

    # per-file stats -------------------------------------------------------------
    todo = [f for f in exp if f in present][: a.max_files]
    recs, ndvi_maps = [], {}
    for i, f in enumerate(todo, 1):
        c = out / "cache" / f"{f[:-4]}.s{a.stride}.json"
        if c.exists():
            recs.append(json.loads(c.read_text()))
            continue
        print(f"[{i}/{len(todo)}] {f}", flush=True)
        try:
            rec, _ = inspect(src / f, exp[f], a.stride)
        except Exception as e:  # noqa: BLE001  (not cached: a re-run retries the file)
            recs.append({"file": f, "kind": exp[f][0], "site": exp[f][1], "track": exp[f][2], "key": exp[f][3],
                         "error": str(e)[:300]})
            continue
        c.write_text(json.dumps(rec, default=str))
        recs.append(rec)
    df = pd.DataFrame(recs)
    df.to_csv(out / "deep_checks_files.csv", index=False)
    errs = df[df.get("error").notna()] if "error" in df else df.iloc[0:0]
    R.add("Files readable", "PASS" if errs.empty else "FAIL", ", ".join(errs["file"].head(12)) if len(errs) else "")
    df = df[df.get("error").isna()] if "error" in df else df
    opt, s1, st = (df[df.kind == k].copy() for k in ("optical", "S1", "static"))

    # 2 grid -------------------------------------------------------------------
    lines = ["| Site / track | CRS | Size | Pixel | Origin (x, y) | Distinct grids |", "|---|---|---|---|---|---|"]
    grid_ok, nest_ok = True, True
    for (s, t), g in df.groupby(["site", "track"]):
        keys = g.apply(lambda r: (r.crs, r.w, r.h, tuple(r["transform"])), axis=1).unique()
        r0 = g.iloc[0]
        ok = len(keys) == 1 and r0.crs == SITES[s]["crs"] and abs(r0.res[0] - TRACKS[t]["res"]) < 1e-6 and abs(r0.res[0] - r0.res[1]) < 1e-6
        grid_ok &= ok
        lines.append(f"| {s} / {t} | {r0.crs} | {r0.w}×{r0.h} | {r0.res[0]:g}×{r0.res[1]:g} m | {r0['transform'][2]:.0f}, {r0['transform'][5]:.0f} | {len(keys)} |")
    for s in SITES:
        A, B = df[(df.site == s) & (df.track == "A")], df[(df.site == s) & (df.track == "B")]
        if len(A) and len(B):
            ra, rb = A.iloc[0], B.iloc[0]
            nest_ok &= (ra["transform"][2] == rb["transform"][2] and ra["transform"][5] == rb["transform"][5]
                        and ra.w == 3 * rb.w and ra.h == 3 * rb.h)
    R.add("2 Grid: one UTM grid per site/track, square pixels at 10/30 m", "PASS" if grid_ok else "FAIL")
    R.add("2 Grid: Track B nests exactly in Track A (3×3)", "PASS" if nest_ok else "FAIL")
    R.section("Grids", lines)

    # 3 bands & types ----------------------------------------------------------------
    bad = []
    for _, r in df.iterrows():
        want = {"optical": (len(OPT_BANDS[r.track]), "int16" if r.track == "A" else "float32"),
                "S1": (4, "int16"), "static": (2, "float32")}[r.kind]
        if (r["count"], r["dtype"]) != want or r.nodata != NODATA:
            bad.append(f"{r.file} ({r['count']} bands, {r['dtype']}, nodata {r.nodata})")
    R.add("3 Bands/types: count, dtype and nodata as specified", "PASS" if not bad else "FAIL", "; ".join(bad[:8]))
    desc = df["descriptions"].astype(str)
    named = desc.str.contains("Blue|VV|elevation").mean()
    R.add("3 Bands/types: band names stored in GeoTIFFs", "PASS" if named > 0.99 else "WARN",
          f"{named:.0%} of files carry band names; otherwise read names from reports/exports/manifest_*.json")

    # 4 values -------------------------------------------------------------------
    if len(opt):
        p99 = opt[["Blue_p99", "Green_p99", "Red_p99", "NIR_p99"]].max(axis=1)
        scale_ok = bool((p99.dropna() < 1.5).all() and (p99.dropna() > 0.02).all())
        R.add("4 Values: optical reflectance on a 0–1 scale after scaling (A ×1e-4)", "PASS" if scale_ok else "FAIL",
              f"p99 range {p99.min():.3f}–{p99.max():.3f}")
        neg = opt.groupby("track")["neg_refl"].max()
        R.add("4 Values: share of valid pixels with a reflectance ≤ 0", "PASS" if neg.max() < 0.02 else "WARN",
              ", ".join(f"Track {k} max {v:.2%}" for k, v in neg.items()) + " (masked as invalid for indices)")
        pm1 = opt[["ndvi_eq_pm1", "ndwi_eq_pm1", "ndmi_eq_pm1"]].max().max()
        R.add("4 Values: no NDVI/NDWI/NDMI = ±1 fill artefacts", "PASS" if pm1 < 0.001 else "FAIL", f"max share {pm1:.4%}")
    if len(s1):
        v = s1[s1.valid > 0]
        ok = v.vv_med.between(-25, 0).all() and v.vh_med.between(-32, -5).all() and (v.vh_med < v.vv_med).all()
        R.add("4 Values: SAR medians plausible (VV −25…0 dB, VH −32…−5 dB, VH < VV)", "PASS" if ok else "WARN",
              f"VV {v.vv_med.min():.1f}…{v.vv_med.max():.1f} dB, VH {v.vh_med.min():.1f}…{v.vh_med.max():.1f} dB")

    # 5 coverage ------------------------------------------------------------------
    cov_lines = []
    for (s, t), g in opt.groupby(["site", "track"]):
        g = g.sort_values("key")
        low = g[g.valid < 0.5]
        thin = g[g.n_clear_median < 2]
        R.add(f"5 Coverage: {s}/{t} optical valid ≥ 50% in each period",
              "PASS" if low.empty else "WARN", f"{len(low)}/{len(g)} below: {', '.join(low.key)}" if len(low) else "")
        R.add(f"5 Coverage: {s}/{t} median clear observations ≥ 2", "PASS" if thin.empty else "WARN",
              f"{len(thin)}/{len(g)} thin: {', '.join(thin.key)}" if len(thin) else "")
    for (s, t), g in s1.groupby(["site", "track"]):
        g2 = g[g.key.str[:4].astype(int) >= 2015]
        low = g2[g2.valid < 0.5]
        R.add(f"5 Coverage: {s}/{t} SAR valid ≥ 50% from 2015 on", "PASS" if len(low) <= 0.2 * len(g2) else "FAIL",
              f"{len(g2) - len(low)}/{len(g2)} periods OK" + (f"; low: {', '.join(low.key)}" if len(low) else ""))
        pre = g[g.key < "2014Q4"]
        if len(pre):
            R.add(f"5 Coverage: {s}/{t} SAR empty before Sentinel-1 (expected)", "PASS" if (pre.valid == 0).all() else "WARN",
                  f"{len(pre)} periods before 2014Q4")
    # coverage table
    keys_all = sorted(set(opt.key) | set(s1.key))
    cov_lines += ["| Period | " + " | ".join(f"{s[:3]} {t} opt / n / SAR / n" for s in SITES for t in TRACKS) + " |",
                  "|---|" + "---|" * (len(SITES) * len(TRACKS))]
    for k in keys_all:
        cells = []
        for s in SITES:
            for t in TRACKS:
                o = opt[(opt.site == s) & (opt.track == t) & (opt.key == k)]
                r = s1[(s1.site == s) & (s1.track == t) & (s1.key == k)]
                oc = f"{o.valid.iloc[0]:.0%} / {o.n_clear_median.iloc[0]:.0f}" if len(o) else "—"
                rc = f"{r.valid.iloc[0]:.0%} / {r.n_s1_median.iloc[0]:.0f}" if len(r) else "—"
                cells.append(f"{oc} / {rc}")
        cov_lines.append(f"| {k} | " + " | ".join(cells) + " |")
    R.section("Coverage per period (optical valid / median clear obs / SAR valid / median S1 obs)", cov_lines)

    # 6 date windows ----------------------------------------------------------------
    if "doy_outside" in opt:
        bad = opt[opt.doy_outside.fillna(0) > 0.001]
        R.add("6 Date windows: doy_mean inside each compositing window", "PASS" if bad.empty else "FAIL",
              ", ".join(f"{r.file} ({r.doy_outside:.1%} outside {r.doy_lo}–{r.doy_hi})" for _, r in bad.head(8).iterrows()))
        ev = opt[opt.key.str.contains("_PRE|_POST", regex=True)]
        R.section("Event-quarter partial composites", ["| File | window (day of year) | doy_mean range | valid | clear obs |", "|---|---|---|---|---|"]
                  + [f"| {r.file} | {r.doy_lo}–{r.doy_hi} | {r.doy_min:.0f}–{r.doy_max:.0f} | {r.valid:.0%} | {r.n_clear_median:.0f} |"
                     for _, r in ev.sort_values("file").iterrows() if pd.notna(r.get("doy_min"))])

    # 7 time series -------------------------------------------------------------------
    ts_lines = []
    for (s, t), g in opt.groupby(["site", "track"]):
        g = g[~g.key.str.contains("_")].sort_values("key").copy()
        g["season"] = g.key.str[-1]
        g["z"] = g.groupby("season")["ndvi_med"].transform(lambda x: robust_z(x.values))
        out_ = g[g.z.abs() > 3.5]
        R.add(f"7 Time series: {s}/{t} NDVI medians consistent within season", "PASS" if out_.empty else "WARN",
              ", ".join(f"{r.key} (NDVI {r.ndvi_med:.2f}, z {r.z:+.1f})" for _, r in out_.iterrows()))
    for (s, t), g in s1.groupby(["site", "track"]):
        g = g[(g.valid > 0) & ~g.key.str.contains("_")].sort_values("key").copy()
        if len(g) > 4:
            g["z"] = robust_z(g.vv_med.values)
            out_ = g[g.z.abs() > 3.5]
            R.add(f"7 Time series: {s}/{t} SAR VV medians stable", "PASS" if out_.empty else "WARN",
                  ", ".join(f"{r.key} ({r.vv_med:.1f} dB, z {r.z:+.1f})" for _, r in out_.iterrows()))
    R.section("Notes on time series", ["Outliers are flagged against other quarters of the same season (robust z > 3.5). "
                                       "Post-landfall drops are expected and are not errors.", *ts_lines])

    # 8 cross-track (A vs B NDVI) and 9 SAR A vs B ------------------------------------------------
    xt = []
    for s in SITES:
        common = sorted(set(opt[(opt.site == s) & (opt.track == "A")].key) & set(opt[(opt.site == s) & (opt.track == "B")].key))
        for k in [c for c in common if not c.endswith(("_PRE", "_POST"))][:: max(1, len(common) // 8)]:
            try:
                nd = {}
                for t in "AB":
                    with rasterio.open(src / f"{s}_{t}_{k}.tif") as ds:
                        arr = read(ds, 1)
                    sc = 1e-4 if t == "A" else 1.0
                    red, nir = arr[2] * sc, arr[3] * sc
                    ok = np.isfinite(red) & np.isfinite(nir) & (red > 0) & (nir > 0) & (arr[6] > 0)
                    nd[t] = index(nir, red, ok)
                a30 = agg3(nd["A"])
                b = nd["B"][: a30.shape[0], : a30.shape[1]]
                m = np.isfinite(a30) & np.isfinite(b)
                if m.sum() > 50:
                    r = float(np.corrcoef(a30[m], b[m])[0, 1])
                    xt.append({"site": s, "key": k, "r": r, "bias": float(np.mean(a30[m] - b[m])), "n": int(m.sum())})
            except Exception as e:  # noqa: BLE001
                xt.append({"site": s, "key": k, "r": np.nan, "bias": np.nan, "n": 0, "err": str(e)[:80]})
    if xt:
        x = pd.DataFrame(xt)
        R.add("8 Cross-track: Track A (aggregated to 30 m) vs Track B NDVI, r ≥ 0.8", "PASS" if (x.r >= 0.8).all() else "WARN",
              f"r {x.r.min():.2f}–{x.r.max():.2f}; mean bias (A − B) {x.bias.mean():+.3f} (S2 TOA vs HLS surface reflectance, so a bias is expected)")
        R.section("Track A vs Track B NDVI (sampled quarters)", ["| Site | Quarter | r | bias A−B | pixels |", "|---|---|---|---|---|"]
                  + [f"| {r.site} | {r.key} | {r.r:.3f} | {r.bias:+.3f} | {r.n} |" for _, r in x.iterrows()])
    sx = []
    for s in SITES:
        ks = sorted(set(s1[(s1.site == s) & (s1.track == "A") & (s1.valid > 0.5)].key) & set(s1[(s1.site == s) & (s1.track == "B")].key))
        for k in ks[:: max(1, len(ks) // 4)]:
            arrs = {}
            for t in "AB":
                with rasterio.open(src / f"{s}_{t}_S1_{k}.tif") as ds:
                    arrs[t] = read(ds, 1)[0] * 0.01
            lin = agg3(10 ** (arrs["A"] / 10))
            a30 = 10 * np.log10(lin)
            b = arrs["B"][: a30.shape[0], : a30.shape[1]]
            m = np.isfinite(a30) & np.isfinite(b)
            if m.any():
                sx.append({"site": s, "key": k, "mad_db": float(np.median(np.abs(a30[m] - b[m])))})
    if sx:
        x = pd.DataFrame(sx)
        R.add("9 SAR: 30 m VV matches 10 m VV aggregated in linear power (median |Δ| < 0.5 dB)",
              "PASS" if (x.mad_db < 0.5).all() else "WARN", f"median |Δ| {x.mad_db.min():.2f}–{x.mad_db.max():.2f} dB")

    # 10 static -------------------------------------------------------------------
    st_lines = ["| File | Elevation min / median / max (m) | Wetland share (AOI) | Classes in AOI |", "|---|---|---|---|"]
    for _, r in st.iterrows():
        cls = r.classes if isinstance(r.classes, dict) else json.loads(str(r.classes).replace("'", '"'))
        st_lines.append(f"| {r.file} | {r.elev_min:.1f} / {r.elev_med:.1f} / {r.elev_max:.1f} | {r.wetland_share:.0%} | "
                        + ", ".join(f"{k} {v:.0%}" for k, v in sorted(cls.items(), key=lambda kv: -kv[1]) if v >= 0.01) + " |")
    if len(st):
        ok = st.elev_min.between(-20, 5).all() and (st.elev_max < 60).all() and st.unknown_classes.apply(lambda u: not u).all()
        R.add("10 Static: elevation plausible for coastal wetland, only valid WorldCover classes", "PASS" if ok else "WARN")
        R.add("10 Static: wetland classes present in each AOI", "PASS" if (st.wetland_share > 0.1).all() else "WARN",
              ", ".join(f"{r.file} {r.wetland_share:.0%}" for _, r in st.iterrows()))
    R.section("Static layers", st_lines)

    # figures ----------------------------------------------------------------------
    if not a.no_figures:
        try:
            make_figures(opt, s1, src, out / "figures")
        except Exception as e:  # noqa: BLE001
            R.add("Figures", "WARN", f"figure step failed: {e}")

    # report ------------------------------------------------------------------------
    n = {k: sum(1 for r in R.rows if r[1] == k) for k in ("PASS", "WARN", "FAIL")}
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}
    md = ["# EcoRewind 2.0 — Deep checks of the re-exports", "",
          f"Generated {date.today().isoformat()} on `{src}` (stride {a.stride}). "
          f"{len(df)} files read. **{n['PASS']} pass, {n['WARN']} warn, {n['FAIL']} fail.**", "",
          "| Check | Result | Detail |", "|---|---|---|"]
    md += [f"| {c} | {icon[s]} {s} | {d} |" for c, s, d in R.rows]
    md += ["", *R.sections, "Figures: `figures/coverage.png`, `figures/timeseries.png`, `figures/quicklooks_*.png`."]
    (out / "deep_checks.md").write_text("\n".join(md))
    print(f"{n} -> {out / 'deep_checks.md'}")


def make_figures(opt, s1, src, figdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # coverage heatmap
    rows = [(s, t, kind) for s in SITES for t in TRACKS for kind in ("optical", "SAR")]
    keys = sorted(set(opt.key) | set(s1.key), key=lambda k: (int(k[:4]), int(k[5]), {"PRE": 0, "POST": 2}.get(k[7:], 1)))
    M = np.full((len(rows), len(keys)), np.nan)
    for i, (s, t, kind) in enumerate(rows):
        d = opt if kind == "optical" else s1
        for j, k in enumerate(keys):
            v = d[(d.site == s) & (d.track == t) & (d.key == k)]
            if len(v):
                M[i, j] = v.valid.iloc[0]
    fig, ax = plt.subplots(figsize=(max(10, len(keys) * 0.28), 3.6))
    im = ax.imshow(M, aspect="auto", cmap="viridis", vmin=0, vmax=1)
    ax.set_yticks(range(len(rows)), [f"{s} {t} {k}" for s, t, k in rows], fontsize=8)
    ax.set_xticks(range(len(keys)), keys, rotation=90, fontsize=6)
    fig.colorbar(im, ax=ax, label="valid pixel share")
    ax.set_title("Valid-pixel share per period")
    fig.tight_layout()
    fig.savefig(figdir / "coverage.png", dpi=130)
    plt.close(fig)

    # time series on one chronological axis (PRE before POST inside the event quarter)
    def korder(k):
        y, q = int(k[:4]), int(k[5])
        return y, q, {"PRE": 0, "POST": 2}.get(k[7:], 1)
    allk = sorted(set(opt.key) | set(s1.key), key=korder)
    pos = {k: i for i, k in enumerate(allk)}
    fig, axes = plt.subplots(2, 2, figsize=(14, 7))
    for i, s in enumerate(SITES):
        lf = SITES[s]["landfall"]
        evq = f"{lf.year}Q{(lf.month - 1) // 3 + 1}"
        for t, c in (("A", "tab:green"), ("B", "tab:olive")):
            g = opt[(opt.site == s) & (opt.track == t)].copy()
            g["x"] = g.key.map(pos)
            g = g.sort_values("x")
            axes[0, i].plot(g.x, g.ndvi_med, "o-", ms=3, color=c, label=f"NDVI Track {t}")
            axes[0, i].plot(g.x, g.ndmi_med, "s--", ms=2, color=c, alpha=0.6, label=f"NDMI Track {t}")
            r = s1[(s1.site == s) & (s1.track == t) & (s1.valid > 0)].copy()
            r["x"] = r.key.map(pos)
            r = r.sort_values("x")
            axes[1, i].plot(r.x, r.vv_med, "o-", ms=3, color=c, label=f"VV Track {t}")
            axes[1, i].plot(r.x, r.vh_med, "s--", ms=2, color=c, alpha=0.6, label=f"VH Track {t}")
        for ax in axes[:, i]:
            if f"{evq}_PRE" in pos:
                ax.axvline(pos[f"{evq}_PRE"] + 0.5, color="red", lw=1, alpha=0.7)
            ax.set_xticks(range(len(allk)), allk, rotation=90, fontsize=6)
            ax.legend(fontsize=7)
        axes[0, i].set_title(f"{s}: optical medians (red line = landfall {lf})")
        axes[1, i].set_title(f"{s}: SAR medians (dB)")
    fig.tight_layout()
    fig.savefig(figdir / "timeseries.png", dpi=130)
    plt.close(fig)

    # quicklooks: true colour before / around / after the event, both tracks
    for s in SITES:
        lf = SITES[s]["landfall"]
        evq = f"{lf.year}Q{(lf.month - 1) // 3 + 1}"
        y, q = map(int, evq.split("Q"))
        prev = f"{y - 1}Q{q}"
        nxt = f"{y}Q{q + 1}" if q < 4 else f"{y + 1}Q1"
        keys = [prev, f"{evq}_PRE", f"{evq}_POST", nxt]
        fig, axes = plt.subplots(2, 4, figsize=(16, 8.4))
        for i, t in enumerate("AB"):
            for j, k in enumerate(keys):
                ax = axes[i, j]
                ax.axis("off")
                p = src / f"{s}_{t}_{k}.tif"
                if not p.exists():
                    ax.set_title(f"{t} {k}: missing", fontsize=8)
                    continue
                with rasterio.open(p) as ds:
                    st = 4 if t == "A" else 1
                    arr = ds.read([3, 2, 1], out_shape=(3, ds.height // st, ds.width // st)).astype("float64")
                    arr[arr == ds.nodata] = np.nan
                arr *= 1e-4 if t == "A" else 1.0
                rgb = np.clip(arr / 0.15, 0, 1).transpose(1, 2, 0)
                ax.imshow(np.nan_to_num(rgb))
                ax.set_title(f"Track {t} {k}", fontsize=9)
        fig.suptitle(f"{s}: true colour around landfall {lf} (stretch 0–0.15 reflectance)")
        fig.tight_layout()
        fig.savefig(figdir / f"quicklooks_{s}.png", dpi=110)
        plt.close(fig)


if __name__ == "__main__":
    main()
