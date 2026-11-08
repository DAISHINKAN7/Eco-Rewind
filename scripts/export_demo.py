"""Export everything the web demo needs (docs/archive/FRONTEND_SPEC.md §6) from the run outputs.

    python scripts/export_demo.py --cubes /content/cubes --phase1 <drive>/phase1 --table-cache /content/tables \
        --deep-runs <drive>/runs/phase3_core_v1 [<drive>/runs/phase5_*] \
        --baseline-runs <drive>/runs/phase2_baselines_v3_pred --reports <drive>/reports --out <drive>/demo

Writes (8-bit Cloud-Optimised GeoTIFFs in the cube's UTM grid; scales in manifest.json):
  layers/{site}_{track}/obs_rgb_{Q}.tif, obs_ndvi_{Q}.tif                              every quarter
  layers/{site}_{track}/{model}/{cutoff}/cf_ndvi_L{l}.tif, deficit_L{l}.tif, width_L{l}.tif   leads 0..--max-lead
  layers/{site}_{track}/disagreement/{cutoff}/sd_L{l}.tif                                  SD of deficit across models
  pixels/{site}_{track}.json        sampled pixels: observed NDVI series + counterfactual median/q10/q90 per model
  evidence/*.json, metrics/leaderboard.json, training/curves.json, models/registry.json, manifest.json
A counterfactual pixel always comes from the model trained without that pixel's fold (held-out prediction).
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from ecorewind.data.cube import Cube  # noqa: E402
from ecorewind.data.events import load_cutoffs  # noqa: E402
from ecorewind.eval.pixels import PixelTable  # noqa: E402
from ecorewind.eval.split import make_split  # noqa: E402
from placebo_verdict import family, load_run  # noqa: E402

SCALES = {"ndvi": (-0.2, 1.0), "deficit": (-0.3, 0.3), "width": (0.0, 0.6)}
CACHE = re.compile(r"^(everglades|mississippi)_([AB])_(.+)_((?:ida|irma)\w*)_k(\d)_[0-9a-f]{8}$")


def _np(o):
    return o.item() if hasattr(o, "item") else str(o)


def to_u8(v, kind):
    lo, hi = SCALES[kind]
    q = np.clip((v - lo) / (hi - lo) * 254, 0, 254)
    return np.where(np.isfinite(v), q, 255).astype("uint8")


def write_cog(path, arr, cube, bands=1):
    import rasterio
    from affine import Affine
    path.parent.mkdir(parents=True, exist_ok=True)
    a = arr if arr.ndim == 3 else arr[None]
    prof = dict(driver="COG", dtype="uint8", count=a.shape[0], height=a.shape[1], width=a.shape[2], crs=cube.crs,
                transform=Affine(*cube.transform[:6]), nodata=None if a.shape[0] == 3 else 255, compress="deflate")
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(a)


def deep_predictions(run_dirs, table, cutoffs, site, track):
    """{model: {cutoff: {"keys", "leads", "q": (3, L, n)}}} from deep_cache, held-out fold per pixel."""
    out = {}
    for rd in run_dirs:
        for f in sorted((Path(rd) / "deep_cache").glob(f"{site}_{track}_*.npz")):
            m = CACHE.match(f.stem)
            if not m:
                continue
            _, _, model, cut, k = m.groups()
            k = int(k)
            c = next((c for c in cutoffs if c.name == cut), None)
            if c is None:
                continue
            s = make_split(table, c, k, 5, lead0=True)
            z = np.load(f)
            o, dists = z["out"].astype("float32"), list(z["dists"])
            ci = table.channels.index("NDVI")
            pos = {d: i for i, d in enumerate(dists)}
            sel = [pos[d] for d in s.distance()]
            e = out.setdefault(model, {}).setdefault(cut, {
                "keys": [table.keys[i] for i in s.tgt_idx], "leads": list(s.leads),
                "q": np.full((3, len(s.tgt_idx), table.n), np.nan, "float32")})
            px = table.fold == k
            e["q"][:, :, px] = np.transpose(o[sel][:, ci][:, :, px], (1, 0, 2))
    return out


def baseline_predictions(run_dirs, table, cutoffs, site, track):
    out = {}
    for rd in run_dirs:
        for f in sorted((Path(rd) / "predictions").glob(f"*_{site}_{track}_*.npz")):
            m = re.match(rf"(.+)_{site}_{track}_(.+)$", f.stem)
            model, cut = m.groups()
            z = np.load(f)
            ci = list(z["channels"]).index("NDVI")
            leads = list(z["leads"])
            c = next((c for c in cutoffs if c.name == cut), None)
            if c is None:
                continue
            s = make_split(table, c, 0, 5, lead0=0 in leads)
            out.setdefault(model, {})[cut] = {
                "keys": [table.keys[i] for i in s.tgt_idx], "leads": leads,
                "q": np.stack([z["lo"][:, ci], z["q50"][:, ci], z["hi"][:, ci]]).astype("float32")}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cubes", required=True)
    ap.add_argument("--phase1", required=True)
    ap.add_argument("--table-cache", required=True)
    ap.add_argument("--deep-runs", nargs="*", default=[])
    ap.add_argument("--baseline-runs", nargs="*", default=[])
    ap.add_argument("--reports", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-lead", type=int, default=4)
    ap.add_argument("--n-pixels", type=int, default=3000)
    ap.add_argument("--site", nargs="*")
    ap.add_argument("--no-rasters", action="store_true", help="JSON only (fast)")
    a = ap.parse_args()
    out = Path(a.out)
    prereg = yaml.safe_load((REPO / "configs/preregistration.yaml").read_text())
    sites = yaml.safe_load((REPO / "configs/sites.yaml").read_text())["sites"]
    cutoffs = load_cutoffs(prereg)
    manifest = {"git_commit": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True,
                                             text=True).stdout.strip(), "scales": SCALES, "sites": {}}
    for site in a.site or list(sites):
        for track in ("A", "B"):
            tabs = sorted(Path(a.table_cache).glob(f"{site}_{track}_v*.npz"))
            cube_p = Path(a.cubes) / f"{site}_{track}.zarr"
            if not tabs or not cube_p.exists():
                continue
            table, cube = PixelTable.load(tabs[-1]), Cube(cube_p)
            print(f"{site} {track}: {table.n:,} pixels", flush=True)
            preds = deep_predictions(a.deep_runs, table, cutoffs, site, track)
            for m, d in baseline_predictions(a.baseline_runs, table, cutoffs, site, track).items():
                preds[m] = d
            fam = {}
            for m, d in preds.items():                              # average seeds per model family
                f = family(m)
                for cut, e in d.items():
                    g = fam.setdefault(f, {}).setdefault(cut, {"keys": e["keys"], "leads": e["leads"], "qs": []})
                    g["qs"].append(e["q"])
            for f in fam.values():
                for cut, g in f.items():
                    with np.errstate(invalid="ignore"), __import__("warnings").catch_warnings():
                        __import__("warnings").simplefilter("ignore", RuntimeWarning)
                        g["q"] = np.nanmean(np.stack(g.pop("qs")), axis=0)
            ndvi = table.channels.index("NDVI")
            layer_dir = out / "layers" / f"{site}_{track}"
            info = {"keys": cube.keys, "crs": str(cube.crs), "transform": list(cube.transform[:6]),
                    "shape": list(cube.shape), "models": sorted(fam), "cutoffs": {}}
            if not a.no_rasters:
                ch = cube.channels
                for t, k in enumerate(cube.keys):                   # observed layers
                    rgb = np.stack([np.asarray(cube.data[t, ch.index(b)]) for b in ("Red", "Green", "Blue")])
                    rgb = np.clip(np.nan_to_num(rgb) / 0.15, 0, 1) ** (1 / 1.6) * 255
                    write_cog(layer_dir / f"obs_rgb_{k}.tif", rgb.astype("uint8"), cube)
                    write_cog(layer_dir / f"obs_ndvi_{k}.tif", to_u8(np.asarray(cube.data[t, ch.index("NDVI")]), "ndvi"), cube)
            for cut in sorted({c for f in fam.values() for c in f}):
                defs = []
                for model, f in fam.items():
                    if cut not in f:
                        continue
                    g = f[cut]
                    info["cutoffs"].setdefault(cut, {"leads": [int(l) for l in g["leads"] if l <= a.max_lead]})
                    for li, lead in enumerate(g["leads"]):
                        if lead > a.max_lead:
                            continue
                        key = g["keys"][li] if g["keys"] else None
                        obs = table.Y[table.keys.index(key), ndvi] if key in table.keys else np.full(table.n, np.nan)
                        lo, q50, hi = g["q"][:, li]
                        d = q50 - obs
                        defs.append((lead, d))
                        if a.no_rasters:
                            continue
                        obs_f = layer_dir / "observed" / cut / f"ndvi_L{lead}.tif"
                        if not obs_f.exists():                       # observed NDVI at this lead (model-independent)
                            grid = np.full(cube.shape, np.nan, "float32")
                            grid[table.r, table.c] = obs
                            write_cog(obs_f, to_u8(grid, "ndvi"), cube)
                        for name, v, kind in (("cf_ndvi", q50, "ndvi"), ("deficit", d, "deficit"), ("width", hi - lo, "width")):
                            grid = np.full(cube.shape, np.nan, "float32")
                            grid[table.r, table.c] = v
                            write_cog(layer_dir / model / cut / f"{name}_L{lead}.tif", to_u8(grid, kind), cube)
                if not a.no_rasters:
                    for lead in sorted({l for l, _ in defs}):
                        st = np.stack([d for l, d in defs if l == lead])
                        if len(st) < 2:
                            continue
                        with np.errstate(invalid="ignore"), __import__("warnings").catch_warnings():
                            __import__("warnings").simplefilter("ignore", RuntimeWarning)
                            sd = np.nanstd(st, axis=0)
                        grid = np.full(cube.shape, np.nan, "float32")
                        grid[table.r, table.c] = sd
                        write_cog(layer_dir / "disagreement" / cut / f"sd_L{lead}.tif", to_u8(grid, "width"), cube)
            # sampled pixel time series
            rng = np.random.default_rng(0)
            idx = np.sort(rng.choice(table.n, min(a.n_pixels, table.n), replace=False))
            px = {"keys": table.keys, "r": table.r[idx].tolist(), "c": table.c[idx].tolist(),
                  "fold": table.fold[idx].tolist(), "observed": np.round(table.Y[:, ndvi, idx].T, 3).tolist(), "cf": {}}
            for model, f in fam.items():
                for cut, g in f.items():
                    px["cf"].setdefault(model, {})[cut] = {"keys": g["keys"], "leads": g["leads"],
                                                          "q10": np.round(g["q"][0][:, idx].T, 3).tolist(),
                                                          "q50": np.round(g["q"][1][:, idx].T, 3).tolist(),
                                                          "q90": np.round(g["q"][2][:, idx].T, 3).tolist()}
            (out / "pixels").mkdir(parents=True, exist_ok=True)
            (out / "pixels" / f"{site}_{track}.json").write_text(json.dumps(px, default=_np).replace("NaN", "null"))
            manifest["sites"][f"{site}_{track}"] = info
    # evidence, metrics, curves
    rep = Path(a.reports)
    (out / "evidence").mkdir(parents=True, exist_ok=True)
    for name in ("placebo_verdict_primary", "placebo_verdict_lead0", "placebo_in_space", "attribution_per_model",
                 "attribution_spread", "external_evidence", "phase5_models", "carbon_illustrative"):
        f = rep / f"{name}.csv"
        if f.exists() and f.stat().st_size > 1:
            pd.read_csv(f).to_json(out / "evidence" / f"{name}.json", orient="records")
    mets = [load_run(Path(r), "metrics") for r in a.deep_runs + a.baseline_runs if (Path(r) / "parts").exists()]
    if mets:
        m = pd.concat(mets, ignore_index=True)
        m["family"] = m.model.map(family)
        lb = m[(m.kind == "placebo") & (m.lead >= 1)].groupby(["site", "track", "family", "channel"]) \
            .agg(r2=("r2", "mean"), rmse=("rmse", "mean"), coverage=("coverage", "mean")).reset_index()
        (out / "metrics").mkdir(parents=True, exist_ok=True)
        lb.to_json(out / "metrics" / "leaderboard.json", orient="records")
    curves = []
    for rd in a.deep_runs:
        for f in (Path(rd) / "deep_cache").glob("*.npz"):
            mm = CACHE.match(f.stem)
            if mm:
                i = json.loads(str(np.load(f)["info"]))
                curves.append({"site": mm.group(1), "track": mm.group(2), "model": mm.group(3), "cutoff": mm.group(4),
                               "fold": int(mm.group(5)), "val_r2": i.get("val_r2", []), "best": i.get("best_val_ndvi_r2")})
    (out / "training").mkdir(parents=True, exist_ok=True)
    (out / "training" / "curves.json").write_text(json.dumps(curves, default=_np).replace("NaN", "null"))
    reg = REPO / "configs" / "model_registry.json"
    if reg.exists():
        (out / "models").mkdir(parents=True, exist_ok=True)
        (out / "models" / "registry.json").write_text(reg.read_text())
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, default=_np))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
