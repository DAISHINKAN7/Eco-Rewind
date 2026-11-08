"""Export real networks for the in-browser Lab (docs/archive/FRONTEND_SPEC.md §5.3) -> web/public/data/lab/

    python scripts/export_lab_model.py --cubes /content/cubes --phase1 <drive>/phase1 --table-cache /content/tables \
        --ppost-exports /content/ppost --out <drive>/web_data/lab --tiles     # T4, ~15 min per architecture

Writes {arch}.onnx for each of --archs (default SimVP, ConvLSTM, EcoTransformer v2), curated patches with each
network's PyTorch reference output, optional --tiles (model inputs for a grid of tiles over the whole AOI, so the
browser can run a network anywhere), and meta.json (input layout, normalisation incl. static layers, models).

Trains SimVP (seed 0, Phase 3 config) on Mississippi Track B (HLS 30 m), cutoff = Ida, test fold 0, exactly as in the
paper runs, exports it to ONNX, and writes 6 curated 64 x 64 patches (inputs, observed future, the PyTorch reference
output, RGB thumbnails) so the browser can run and verify the same model. Illustrative: the published numbers come
from the 5-fold runs, not from this single model.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cubes", required=True)
    ap.add_argument("--phase1", required=True)
    ap.add_argument("--table-cache", required=True)
    ap.add_argument("--ppost-exports")
    ap.add_argument("--out", required=True)
    ap.add_argument("--site", default="mississippi")
    ap.add_argument("--track", default="B", help="B (30 m) fits in Colab RAM; A (10 m) needs > 50 GB")
    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--phase3-config", help="override configs/phase3.yaml (tests)")
    ap.add_argument("--phase1-config", help="override configs/phase1.yaml (tests)")
    ap.add_argument("--fast", action="store_true", help="1 epoch (tests)")
    ap.add_argument("--archs", nargs="+", default=["simvp", "convlstm", "ecotransformer"])
    ap.add_argument("--tiles", action="store_true", help="also export inputs for a grid of tiles over the AOI")
    ap.add_argument("--tile-min-cover", type=float, default=0.3, help="minimum fraction of evaluable pixels per tile")
    ap.add_argument("--tiles-only", action="store_true",
                    help="only (re)write tiles into an existing export and update its meta.json; no training (CPU, minutes)")
    a = ap.parse_args()
    import torch
    from PIL import Image
    import run_baselines as RB
    from ecorewind.data.cube import Cube
    from ecorewind.data.events import load_cutoffs
    from ecorewind.eval.pixels import PixelTable, build_table
    from ecorewind.eval.split import make_split
    from ecorewind.models.deep.trainer import STATIC, DeepModel, _robust

    cfg = RB.load_cfg()
    if a.phase1_config:
        import yaml
        cfg.update(yaml.safe_load(Path(a.phase1_config).read_text()))
    if a.phase3_config:
        import yaml
        cfg["phase3"] = {**cfg["phase3"], **yaml.safe_load(Path(a.phase3_config).read_text())}
    out = Path(a.out)
    if a.tiles_only:
        if not (out / "meta.json").exists():
            raise SystemExit(f"{out}/meta.json not found: run the full export first")
    elif all((out / f"{x}.onnx").exists() for x in a.archs) and (out / "meta.json").exists() and not a.fast:
        print(f"{out} already has {', '.join(x + '.onnx' for x in a.archs)} + meta.json; delete them to re-export"); return
    (out / "patches").mkdir(parents=True, exist_ok=True)
    tabs = sorted(Path(a.table_cache).glob(f"{a.site}_{a.track}_v*.npz"))
    cube = Cube(Path(a.cubes) / f"{a.site}_{a.track}.zarr")
    table = PixelTable.load(tabs[-1]) if tabs else build_table(
        cube, Path(a.phase1) / "folds" / f"{a.site}_{a.track}.npz", Path(a.phase1) / "static" / f"{a.site}_{a.track}.npz",
        cfg["blocks"]["size_m"], extra_exports=a.ppost_exports)
    cut = next(c for c in load_cutoffs(cfg["prereg"]) if c.site == a.site and c.kind == "event")
    split = make_split(table, cut, 0, cfg["folds"]["n"], lead0=True)
    ctx = {"cube": Path(a.cubes) / f"{a.site}_{a.track}.zarr", "folds": Path(a.phase1) / "folds" / f"{a.site}_{a.track}.npz",
           "static": Path(a.phase1) / "static" / f"{a.site}_{a.track}.npz", "res": table.res,
           "block_m": cfg["blocks"]["size_m"], "buffer_m": cfg["blocks"]["buffer_m"],
           "cache": out / "_cache", "log": lambda m: print(m, flush=True), "keep_net": True}
    if a.tiles_only:                                       # inputs only: History is rebuilt deterministically (same
        m = DeepModel(a.archs[0], cfg["phase3"], ctx, 0, fast=a.fast)   # train mask and normalisation as training)
        h = m._history(split, m._masks(split)[0])
        meta = json.loads((out / "meta.json").read_text())
        S, T_in, p = meta["size"], meta["T_in"], len(h.seasons) - 1
        if meta.get("track") != a.track or meta.get("site") != a.site:
            raise SystemExit(f"meta.json is for {meta.get('site')} {meta.get('track')}; pass --site/--track to match")
        meta["tiles"], meta["grid"] = write_tiles(m, h, p, table, split, out, S, T_in, a.tile_min_cover), {"H": h.shape[0], "W": h.shape[1]}
        (out / "meta.json").write_text(json.dumps(meta, indent=1, default=float))
        print(f"wrote {len(meta['tiles'])} tiles into {out}")
        return
    nets, infos = {}, {}
    for arch in a.archs:                                   # same split, seed and config as the published runs
        mm = DeepModel(arch, cfg["phase3"], {**ctx, "cache": out / "_cache" / arch}, 0, fast=a.fast)
        mm.fit(split)
        mm.predict(split, split.test[:1])                  # trains (~10-20 min each on a T4)
        nets[arch] = mm.net.float().cpu().eval()
        infos[arch] = {"id": arch, "file": f"{arch}.onnx", "val_r2": mm.info.get("best_val_ndvi_r2"),
                       "params": int(sum(p_.numel() for p_ in nets[arch].parameters()))}
        m = mm
    net = nets[a.archs[0]]
    h = m._history(split, m._masks(split)[0])
    st_npz = np.load(ctx["static"])
    train_mask = m._masks(split)[0]
    static_stats = [list(_robust(st_npz[k].astype("float32")[train_mask])) if (k in st_npz.files and not k.startswith("lc_")) else None
                    for k in STATIC]
    T_in = cfg["phase3"]["T_in"][a.track]
    D = max(split.distance())
    p = len(h.seasons) - 1
    si = m._seasons_in(h, p, T_in)
    so = np.array([(h.seasons[p] + d) % 4 for d in range(1, D + 1)])
    S = a.size
    # curated patches: mostly-wetland 64 px windows ranked by coast distance
    H, W = h.shape
    ev = np.zeros(h.shape, bool)
    ev[table.r, table.c] = True
    coast = h.static[STATIC.index("coast_dist_m")].astype("float32")
    cand = [(r, c) for r in range(0, H - S + 1, S // 2) for c in range(0, W - S + 1, S // 2) if ev[r:r + S, c:c + S].mean() > 0.6]
    cand.sort(key=lambda rc: float(coast[rc[0]:rc[0] + S, rc[1]:rc[1] + S].mean()))
    picks = {"Coastal marsh A": cand[0], "Coastal marsh B": cand[len(cand) // 10],
             "Mid-basin marsh": cand[len(cand) // 2], "Mid-basin marsh B": cand[len(cand) * 2 // 3],
             "Inland marsh": cand[-len(cand) // 10], "Most inland marsh": cand[-1]}
    keys_out = {d: table.keys[t] for d, t in zip(split.distance(), split.tgt_idx)}
    ndvi = table.channels.index("NDVI")
    grid_obs = {}
    for d, k in keys_out.items():
        g = np.full(h.shape, np.nan, "float32")
        g[table.r, table.c] = table.Y[table.keys.index(k), ndvi]
        grid_obs[d] = g
    in_keys = [h_k for h_k in [table.keys[i] for i in split.hist_idx][-T_in:]]
    patches = []
    for i, (label, (r, c)) in enumerate(picks.items()):
        x = m._input(h, p, r, c, S, T_in)[None].astype("float32")
        x.astype("float16").tofile(out / "patches" / f"p{i}_x.f16")
        for arch, nt in nets.items():
            with torch.no_grad():
                ref = nt(torch.from_numpy(x), torch.from_numpy(si[None]).long(), torch.from_numpy(so[None]).long()).numpy()[0]
            ref = np.sort(ref, axis=2).astype("float16")
            ref.tofile(out / "patches" / f"p{i}_ref_{arch}.f16")
            if arch == a.archs[0]:
                ref.tofile(out / "patches" / f"p{i}_ref.f16")   # back-compat with older pages
        np.stack([grid_obs[d][r:r + S, c:c + S] for d in range(1, D + 1) if d in grid_obs]).astype("float16") \
            .tofile(out / "patches" / f"p{i}_obs.f16")
        thumbs = []
        for k in in_keys:
            t = cube.keys.index(k)
            rgb = np.stack([np.asarray(cube.data[t, cube.channel(b), r:r + S, c:c + S]) for b in ("Red", "Green", "Blue")], -1)
            img = (np.clip(np.nan_to_num(rgb) / 0.15, 0, 1) ** (1 / 1.6) * 255).astype("uint8")
            name = f"p{i}_{k}.png"
            Image.fromarray(img).resize((128, 128), Image.NEAREST).save(out / "patches" / name)
            thumbs.append(name)
        patches.append({"id": f"p{i}", "label": label, "row": int(r), "col": int(c),
                        "coast_z": float(coast[r:r + S, c:c + S].mean()),
                        "thumbs": thumbs})
    for arch, nt in nets.items():
        torch.onnx.export(nt, (torch.zeros(1, T_in, x.shape[2], S, S), torch.zeros(1, T_in, dtype=torch.long),
                               torch.zeros(1, D, dtype=torch.long)), str(out / f"{arch}.onnx"),
                          input_names=["x", "s_in", "s_out"], output_names=["y"], opset_version=17, dynamo=False)
        torch.save({"state_dict": nt.state_dict(), "arch": arch, "arch_kwargs": cfg["phase3"]["arch"].get(arch, {}),
                    "T_in": T_in, "D": D, "n_in": int(x.shape[2]), "channels": h.channels, "site": a.site, "track": a.track,
                    "cutoff": cut.name, "fold": 0, "seed": 0}, out / f"{arch}.pt")   # PyTorch weights (not shipped to the site)
        infos[arch]["weights"] = f"{arch}.pt"
    tiles = write_tiles(m, h, p, table, split, out, S, T_in, a.tile_min_cover) if a.tiles else []
    meta = {"model": f"{a.archs[0]}_s0", "models": [infos[x] for x in a.archs], "static_stats": static_stats,
            "grid": {"H": H, "W": W}, "tiles": tiles, "site": a.site, "track": a.track, "cutoff": cut.name, "fold": 0, "size": S,
            "T_in": T_in, "D": D, "channels": h.channels, "stats": h.stats, "n_in": int(x.shape[2]),
            "layout": {"values": [0, 1, 2, 3, 4], "masks": [5, 6, 7, 8, 9], "static": list(range(10, 18)),
                       "sar": [h.channels.index("VV"), h.channels.index("VH")]},
            "s_in": si.tolist(), "s_out": so.tolist(), "in_keys": in_keys,
            "out_keys": [keys_out.get(d) for d in range(1, D + 1)], "leads": [d - 1 for d in range(1, D + 1)],
            "val_r2": infos[a.archs[0]]["val_r2"], "patches": patches,
            "note": f"Illustrative live model: {a.site} Track {a.track}, {cut.name} cutoff, fold 0, seed 0."}
    (out / "meta.json").write_text(json.dumps(meta, indent=1, default=float))
    print(f"wrote {out}")


def write_tiles(m, h, p, table, split, out, S, T_in, min_cover):
    """Model inputs + observed NDVI for every S x S tile with >= min_cover evaluable pixels (stride S)."""
    import numpy as np
    H, W = h.shape
    ev = np.zeros(h.shape, bool)
    ev[table.r, table.c] = True
    ndvi = table.channels.index("NDVI")
    keys_out = {d: table.keys[t] for d, t in zip(split.distance(), split.tgt_idx)}
    D = max(split.distance())
    grid_obs = {}
    for d, k in keys_out.items():
        g = np.full(h.shape, np.nan, "float32")
        g[table.r, table.c] = table.Y[table.keys.index(k), ndvi]
        grid_obs[d] = g
    (out / "tiles").mkdir(parents=True, exist_ok=True)
    tiles = []
    for r in range(0, H - S + 1, S):
        for c in range(0, W - S + 1, S):
            cover = float(ev[r:r + S, c:c + S].mean())
            if cover < min_cover:
                continue
            tid = f"t{r}_{c}"
            m._input(h, p, r, c, S, T_in).astype("float16").tofile(out / "tiles" / f"{tid}_x.f16")
            np.stack([grid_obs[d][r:r + S, c:c + S] for d in range(1, D + 1) if d in grid_obs]).astype("float16") \
                .tofile(out / "tiles" / f"{tid}_obs.f16")
            tiles.append({"id": tid, "row": r, "col": c, "cover": round(cover, 3)})
    print(f"{len(tiles)} tiles (cover >= {min_cover})", flush=True)
    return tiles


if __name__ == "__main__":
    main()
