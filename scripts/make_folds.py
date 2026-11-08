"""Static layers, spatial blocks, folds, buffers, normalisation stats and fold maps (MASTER_PROMPT §6).

    python scripts/make_folds.py --cubes /content/cubes --out /content/drive/MyDrive/EcoRewind2/phase1

Outputs under --out:
  folds/<site>_<track>.npz      fold (H, W), buffer, aoi, eval_main, eval_strict, fold_of_block
  folds/<site>_blocks.csv       per-block table: wetland share, proxy, evaluable pixels, fold
  static/<site>_<track>.npz     elevation_m, coast_dist_m, land-cover one-hot
  norm/<site>_<track>_<cutoff>_fold<k>.json   median / IQR per channel (training blocks, pre-cutoff only)
  figures/folds_<site>.png      fold map with buffers, AOI and wetland mask
  phase1_summary.md / .json     folds, patch counts, history lengths, hashes
Folds are assigned once per site on the block grid and are identical for Track A and Track B.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from ecorewind.data import blocks as B  # noqa: E402
from ecorewind.data import folds as F  # noqa: E402
from ecorewind.data import normalise as N  # noqa: E402
from ecorewind.data.cube import Cube  # noqa: E402
from ecorewind.data.dataset import patch_origins  # noqa: E402
from ecorewind.data.events import load_cutoffs, split_indices  # noqa: E402
from ecorewind.data.static import static_layers  # noqa: E402


def load_cfg(phase1_config=None):
    cfg = {}
    for n in ("sites", "tracks", "events", "phase1"):
        cfg.update(yaml.safe_load((REPO / "configs" / f"{n}.yaml").read_text()))
    if phase1_config:
        cfg.update(yaml.safe_load(Path(phase1_config).read_text()))
    cfg["prereg"] = yaml.safe_load((REPO / "configs" / "preregistration.yaml").read_text())
    return cfg


def ndvi_drop_proxy(cube: Cube, first_post: str, years: int) -> np.ndarray:
    """NDVI(first full post-event quarter) minus mean NDVI of the same quarter in the preceding years."""
    ci = cube.channel("NDVI")
    t_post = cube.keys.index(first_post)
    y, q = int(first_post[:4]), first_post[-1]
    base = [cube.keys.index(f"{y - k}Q{q}") for k in range(1, years + 1) if f"{y - k}Q{q}" in cube.keys]
    post = np.where(cube.valid[t_post, ci], cube.data[t_post, ci], np.nan)
    stack = np.stack([np.where(cube.valid[t, ci], cube.data[t, ci], np.nan) for t in base])
    with np.errstate(invalid="ignore"):
        return post - np.nanmean(stack, axis=0)


def fold_figure(path, site, fold, buf, aoi, wet, transform, n_folds):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    cmap = ListedColormap(["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#b07aa1"][:n_folds])
    a, _, c, _, e, f = transform
    ext = [c, c + fold.shape[1] * a, f + fold.shape[0] * e, f]
    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    ax = axes[0]
    ax.imshow(fold, cmap=cmap, vmin=-0.5, vmax=n_folds - 0.5, extent=ext, interpolation="nearest")
    ax.imshow(np.where(buf, 1, np.nan), cmap=ListedColormap(["black"]), alpha=0.55, extent=ext, interpolation="nearest")
    ax.contour(aoi.astype(float), levels=[0.5], colors="white", linewidths=1.5, extent=[ext[0], ext[1], ext[3], ext[2]], origin="upper")
    ax.set_title(f"{site}: folds (colour), buffers (dark), AOI (white line)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=cmap(k)) for k in range(n_folds)]
    ax.legend(handles, [f"fold {k}" for k in range(n_folds)], loc="lower left", fontsize=8)
    ax2 = axes[1]
    ev = np.where(aoi & wet & ~buf, fold, np.nan)
    ax2.imshow(ev, cmap=cmap, vmin=-0.5, vmax=n_folds - 0.5, extent=ext, interpolation="nearest")
    ax2.set_title("evaluable pixels: AOI ∩ wetland_main ∩ not buffer")
    for x in ax, ax2:
        x.set_xlabel("UTM x (m)")
        x.set_ylabel("UTM y (m)")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cubes", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--site", nargs="*")
    ap.add_argument("--phase1-config", help="override configs/phase1.yaml (tests)")
    a = ap.parse_args()
    cfg = load_cfg(a.phase1_config)
    out = Path(a.out)
    for d in ("folds", "static", "norm", "figures"):
        (out / d).mkdir(parents=True, exist_ok=True)
    bm, buf_m = cfg["blocks"]["size_m"], cfg["blocks"]["buffer_m"]
    nf = cfg["folds"]["n"]
    cutoffs = load_cutoffs(cfg["prereg"])
    summary = {"blocks": cfg["blocks"], "folds": cfg["folds"], "sites": {}}
    md = ["# Phase 1 summary: blocks, folds, normalisation", "",
          f"Blocks {bm / 1000:.2f} km, buffer {buf_m} m each side of a fold boundary, {nf} folds "
          f"(seed {cfg['folds']['seed']}). Folds are shared by Track A and Track B.", ""]
    for site in a.site or list(cfg["sites"]):
        ev_name, ev = next((k, e) for k, e in cfg["prereg"]["events"].items() if e["site"] == site)
        cubes = {t: Cube(Path(a.cubes) / f"{site}_{t}.zarr") for t in ("A", "B")}
        # --- fold assignment on the block grid, using Track B for the proxy
        cb = cubes["B"]
        res_b = abs(cb.transform[0])
        st_b = static_layers(cb, cfg["sites"][site]["bounds_lonlat"], cfg["static"]["wetland_strict_erode_px"])
        nbr, nbc = B.n_blocks(cb.shape, res_b, bm)
        bid = B.block_ids(cb.shape, res_b, bm)
        proxy = ndvi_drop_proxy(cb, cfg["prereg"]["evaluation"]["first_full_post"][ev_name], cfg["stratify_proxy"]["baseline_years"])
        table = F.block_table(bid, nbr, nbc, st_b["wetland_main"], st_b["aoi"], proxy)
        folds = F.assign_folds(table, nf, cfg["folds"]["seed"], cfg["folds"]["n_trials"])
        fob = folds.reshape(nbr, nbc)
        table.assign(fold=folds).to_csv(out / "folds" / f"{site}_blocks.csv", index=False)
        summ = F.fold_summary(table, folds, nf)
        site_sum = {"event": ev_name, "block_grid": [nbr, nbc], "fold_of_block": fob.tolist(),
                    "fold_summary": summ.reset_index().to_dict("records"), "tracks": {}}
        md += [f"## {site} ({ev_name})", "", f"Block grid {nbr} × {nbc}.", "",
               "| Fold | Blocks | Evaluable px (Track B) | Mean wetland share | Mean NDVI-drop proxy |", "|---|---|---|---|---|"]
        md += [f"| {k} | {r.blocks} | {int(r.eval_pixels)} | {r.wetland_frac:.2f} | {r.proxy:+.3f} |" for k, r in summ.iterrows()]
        for t, cube in cubes.items():
            res = abs(cube.transform[0])
            if B.n_blocks(cube.shape, res, bm) != (nbr, nbc):
                raise ValueError(f"{site} {t}: block grid differs from Track B")
            st = static_layers(cube, cfg["sites"][site]["bounds_lonlat"], cfg["static"]["wetland_strict_erode_px"])
            fold = B.fold_raster(fob, cube.shape, res, bm).astype("int8")
            buf = B.buffer_mask(fob, cube.shape, res, bm, buf_m)                  # evaluation exclusion
            split_buf = np.stack([B.split_buffer(fob, k, cube.shape, res, bm, buf_m) for k in range(nf)])
            assert np.array_equal(buf, np.any(split_buf & (fold[None] == np.arange(nf)[:, None, None]), axis=0))
            eval_main = st["aoi"] & st["wetland_main"] & ~buf
            eval_strict = st["aoi"] & st["wetland_strict"] & ~buf
            np.savez_compressed(out / "folds" / f"{site}_{t}.npz", fold=fold, buffer=buf, aoi=st["aoi"],
                                eval_main=eval_main, eval_strict=eval_strict, fold_of_block=fob,
                                split_buffer=split_buf)
            np.savez_compressed(out / "static" / f"{site}_{t}.npz",
                                **{k: v for k, v in st.items() if k not in ("aoi", "wetland_main", "wetland_strict")})
            if t == "A":
                fold_figure(out / "figures" / f"folds_{site}.png", site, fold, buf, st["aoi"], st["wetland_main"], cube.transform, nf)
            # patches per fold
            pc = cfg["patches"][t]
            patches = patch_origins(cube.shape, res, bm, fob, pc["size"], pc["stride"])
            per_fold = pd.Series([p.fold for p in patches]).value_counts().reindex(range(nf), fill_value=0)
            # normalisation per cutoff x fold, from one fixed pixel sample; split k keeps training-fold
            # pixels outside the split-k buffer
            r, c = N.sample_pixels(np.ones(cube.shape, bool), cfg["normalisation"]["n_sample_pixels"], cfg["normalisation"]["seed"])
            keys = cube.keys
            needed = sorted({i for cut in cutoffs if cut.site == site for i in split_indices(keys, cut)[0]})
            V, M = N.sample_values(cube.data, cube.valid, cube.channels, needed, r, c)
            row_of = {t_: i for i, t_ in enumerate(needed)}
            sample_fold = fold[r, c]
            hist_lens = {}
            for cut in cutoffs:
                tracks = (cfg["prereg"]["events"].get(cut.name) or cfg["prereg"]["placebos"].get(cut.name))["tracks"]
                if cut.site != site or t not in tracks:
                    continue
                hist, target = split_indices(keys, cut)
                hist_lens[cut.name] = {"history": len(hist), "targets": len(target),
                                       "first_target": keys[target[0]] if target else None,
                                       "last_history": keys[hist[-1]] if hist else None}
                for k in range(nf):
                    keep = (sample_fold != k) & ~split_buf[k][r, c]
                    stats = N.stats_from_sample(V, M, cube.channels, [row_of[i] for i in hist], keep)
                    rec = {"site": site, "track": t, "cutoff": cut.name, "cutoff_quarter": cut.quarter, "fold": k,
                           "train_folds": [j for j in range(nf) if j != k], "hist_keys": [keys[i] for i in hist],
                           "n_sample_pixels": int(keep.sum()), "data_hash": cube.data_hash, "channels": stats}
                    (out / "norm" / f"{site}_{t}_{cut.name}_fold{k}.json").write_text(json.dumps(rec, indent=1))
            site_sum["tracks"][t] = {"shape": list(cube.shape), "data_hash": cube.data_hash,
                                     "eval_main_px": int(eval_main.sum()), "eval_strict_px": int(eval_strict.sum()),
                                     "eval_buffer_share": float(buf.mean()),
                                     "train_buffer_share_per_split": [float((split_buf[k] & (fold != k)).mean()) for k in range(nf)],
                                     "patches_per_fold": per_fold.tolist(),
                                     "cutoffs": hist_lens}
            md += ["", f"**Track {t}** ({res:g} m, {cube.shape[0]}×{cube.shape[1]}): evaluable pixels "
                   f"{int(eval_main.sum()):,} (strict {int(eval_strict.sum()):,}); evaluation buffer {buf.mean():.1%} of grid, "
                   f"training loses {np.mean([(split_buf[k] & (fold != k)).mean() for k in range(nf)]):.1%} per split; "
                   f"patches {pc['size']}px/stride {pc['stride']} per fold {per_fold.tolist()}.", "",
                   "| Cutoff | History quarters | Last history | Targets | First target |", "|---|---|---|---|---|"]
            md += [f"| {n} | {h['history']} | {h['last_history']} | {h['targets']} | {h['first_target']} |" for n, h in hist_lens.items()]
            print(f"{site} {t}: done")
        summary["sites"][site] = site_sum
        md.append("")
    (out / "phase1_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    (out / "phase1_summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
