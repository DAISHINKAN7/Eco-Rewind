"""Phase 5.2: does attributed damage follow independent exposure / damage evidence? -> reports/external_evidence.md

    python scripts/external_evidence.py --runs <drive>/runs/phase2_baselines_v3 <drive>/runs/phase3_core_v1 \
        --cubes /content/cubes --phase1 <drive>/phase1 --out <drive>/reports \
        [--external everglades:A:path/to/irma_damage.tif] [--points mississippi:path/to/crms_sites.csv]

Unit of analysis: 3.84 km blocks (evaluable pixels >= 50). Attributed damage = block mean of the event deficit maps
(lead 0 and mean over leads) per model. Independent covariates:
  * distance to the storm's best track (NOAA HURDAT2, downloaded or --hurdat file) and the peak wind of the nearest
    track point (exposure; larger damage expected closer to the track),
  * distance to the coast (static layer; surge exposure),
  * optional external damage raster (e.g. published Irma mangrove-damage map) resampled to blocks,
  * optional point data (CSV with lat, lon, value; e.g. CRMS vegetation change) averaged per block.
Reported: Spearman rank correlation per model with a block-bootstrap 90 % interval. The expected sign is negative for
distances and positive for wind / external damage. Rank agreement, not pixel accuracy (MASTER_PROMPT §10.2).
"""
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from ecorewind.data.blocks import block_ids  # noqa: E402
from placebo_verdict import family, seed  # noqa: E402

STORMS = {"ida": ("IDA", 2021), "irma": ("IRMA", 2017)}


def track_points(hurdat_text: str, name: str, year: int) -> np.ndarray:
    import check_storm_record as C
    for s in C.parse(hurdat_text):
        if s["name"].upper() == name and s["points"] and s["points"][0][0].year == year:
            return np.array([(lat, lon, w) for t, lat, lon, w, st in s["points"]], dtype="float64")
    raise SystemExit(f"{name} {year} not found in HURDAT2")


def block_frame(site, track, cubes, phase1, block_m):
    import rasterio.transform as RT
    from affine import Affine
    from pyproj import Transformer
    from ecorewind.data.cube import Cube
    cube = Cube(Path(cubes) / f"{site}_{track}.zarr")
    H, W = cube.shape
    res = abs(cube.transform[0])
    bid = block_ids((H, W), res, block_m)
    rows, cols = np.mgrid[0:H, 0:W]
    xs, ys = RT.xy(Affine(*cube.transform[:6]), rows.ravel(), cols.ravel())
    lon, lat = Transformer.from_crs(cube.crs, "EPSG:4326", always_xy=True).transform(np.asarray(xs), np.asarray(ys))
    st = np.load(Path(phase1) / "static" / f"{site}_{track}.npz")
    ev = np.load(Path(phase1) / "folds" / f"{site}_{track}.npz")["eval_main"]
    return bid, lat.reshape(H, W), lon.reshape(H, W), st["coast_dist_m"], ev, cube


def haversine(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


def boot_spearman(x, y, n=1000, seed=0):
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if len(x) < 8:
        return np.nan, np.nan, np.nan, len(x)
    r = spearmanr(x, y).statistic
    rng = np.random.default_rng(seed)
    bs = [spearmanr(x[i], y[i]).statistic for i in (rng.integers(0, len(x), len(x)) for _ in range(n))]
    return r, np.nanpercentile(bs, 5), np.nanpercentile(bs, 95), len(x)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--cubes", required=True)
    ap.add_argument("--phase1", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hurdat", help="local HURDAT2 text file (default: download from NOAA)")
    ap.add_argument("--external", nargs="*", default=[], help="site:track:raster.tif (damage, any CRS)")
    ap.add_argument("--points", nargs="*", default=[], help="site:file.csv with columns lat, lon, value")
    ap.add_argument("--block-m", type=float, default=3840)
    ap.add_argument("--min-px", type=int, default=50, help="minimum evaluable pixels per block")
    a = ap.parse_args()
    import check_storm_record as C
    text = Path(a.hurdat).read_text() if a.hurdat else C.fetch_hurdat()[0]
    ext = {tuple(e.split(":")[:2]): e.split(":", 2)[2] for e in a.external}
    pts = {p.split(":")[0]: p.split(":", 1)[1] for p in a.points}
    rows, frames = [], {}
    for rd in a.runs:
        for f in sorted((Path(rd) / "maps").glob("*.npz")):
            m = re.match(r"(.+)_(everglades|mississippi)_([AB])_(ida|irma)$", f.stem)
            if not m:
                continue
            model, site, track, ev = m.groups()
            if (site, track) not in frames:
                bid, lat, lon, coast, evm, cube = block_frame(site, track, a.cubes, a.phase1, a.block_m)
                tp = track_points(text, *STORMS[ev])
                # distance of each pixel to the nearest best-track point (6-hourly points; coarse but independent)
                step = 8 if lat.shape[0] > 200 else 1
                d = np.full(lat.shape, np.inf)
                wind = np.zeros(lat.shape)
                for la, lo, w in tp:
                    dd = haversine(lat[::step, ::step], lon[::step, ::step], la, lo)
                    better = dd < d[::step, ::step]
                    sub_d, sub_w = d[::step, ::step], wind[::step, ::step]
                    sub_d[better], sub_w[better] = dd[better], w
                    d[::step, ::step], wind[::step, ::step] = sub_d, sub_w
                cov = pd.DataFrame({"b": bid[::step, ::step].ravel(), "track_km": d[::step, ::step].ravel(),
                                    "wind_kt": wind[::step, ::step].ravel(), "coast_m": coast[::step, ::step].ravel()})
                cov = cov.groupby("b").median()
                if (site, track) in ext:
                    import rasterio
                    from rasterio.warp import Resampling, reproject
                    with rasterio.open(ext[(site, track)]) as src:
                        dst = np.full(bid.shape, np.nan, "float32")
                        reproject(rasterio.band(src, 1), dst, dst_transform=__import__("affine").Affine(*cube.transform[:6]),
                                  dst_crs=cube.crs, resampling=Resampling.average)
                    cov["external"] = pd.Series(dst.ravel()).groupby(bid.ravel()).mean()
                if site in pts:
                    p = pd.read_csv(pts[site])
                    import rasterio.transform as RT
                    from affine import Affine
                    from pyproj import Transformer
                    x, y = Transformer.from_crs("EPSG:4326", cube.crs, always_xy=True).transform(p.lon.values, p.lat.values)
                    r, c = RT.rowcol(Affine(*cube.transform[:6]), x, y)
                    r, c = np.asarray(r), np.asarray(c)
                    ok = (r >= 0) & (r < bid.shape[0]) & (c >= 0) & (c < bid.shape[1])
                    cov["points"] = pd.Series(p.value.values[ok]).groupby(bid[r[ok], c[ok]]).mean()
                frames[(site, track)] = (bid, evm, cov)
            bid, evm, cov = frames[(site, track)]
            z = np.load(f)
            for tag, name in (("NDVI_lead1", "lead 0"), ("NDVI_mean", "mean over leads")):
                if tag not in z.files:
                    continue
                dm = z[tag].astype("float64")
                ok = np.isfinite(dm) & evm
                blk = pd.DataFrame({"b": bid[ok], "d": dm[ok]}).groupby("b").agg(d=("d", "mean"), n=("d", "size"))
                blk = blk[blk.n >= a.min_px].join(cov, how="left")
                for covname, expect in (("track_km", "−"), ("wind_kt", "+"), ("coast_m", "−"),
                                        ("external", "+"), ("points", "+")):
                    if covname not in blk:
                        continue
                    r, lo, hi, n = boot_spearman(blk.d.values, blk[covname].values)
                    rows.append({"event": ev, "site": site, "track": track, "model": family(model), "seed": seed(model),
                                 "map": name, "covariate": covname, "expected": expect, "rho": r, "lo": lo, "hi": hi,
                                 "blocks": n})
    res = pd.DataFrame(rows)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res.to_csv(out / "external_evidence.csv", index=False)
    s = res.groupby(["event", "site", "track", "map", "covariate", "expected", "model"])[["rho", "lo", "hi", "blocks"]].mean().reset_index()
    md = ["# External evidence: does attributed damage follow independent exposure?", "",
          "Spearman ρ between block-mean attributed NDVI deficit and each covariate [block-bootstrap 90 % interval]; "
          "seeds averaged. Expected sign: − for distance to the track / coast, + for wind and external damage.", ""]
    for (ev, site, track, mp), g in s.groupby(["event", "site", "track", "map"]):
        md += [f"## {ev} — {site} / Track {track} — {mp}", "", "| Model | " + " | ".join(
            f"{c} ({e})" for c, e in g[["covariate", "expected"]].drop_duplicates().itertuples(index=False)) + " |",
            "|---|" + "---|" * g.covariate.nunique()]
        covs = g[["covariate"]].drop_duplicates().covariate.tolist()
        for mdl, gm in g.groupby("model"):
            cells = []
            for c in covs:
                r = gm[gm.covariate == c]
                cells.append("—" if r.empty or not np.isfinite(r.rho.iloc[0]) else
                             f"{r.rho.iloc[0]:+.2f} [{r.lo.iloc[0]:+.2f}, {r.hi.iloc[0]:+.2f}]")
            md.append(f"| {mdl} | " + " | ".join(cells) + " |")
        md.append(f"\nBlocks: {int(g.blocks.max())}\n")
    (out / "external_evidence.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
