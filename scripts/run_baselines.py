"""Phase 2: CPU baselines through the shared evaluation harness (MASTER_PROMPT §7).

    python scripts/run_baselines.py --cubes /content/cubes --phase1 /content/drive/MyDrive/EcoRewind2/phase1 \
        --out /content/drive/MyDrive/EcoRewind2/runs [--models persistence climatology harmonic synth_control lgbm]

For each site x track, every pre-registered cutoff (event and placebos) x every test fold:
fit -> predict the test fold -> (placebo windows) conformal scores on the calibration fold.
Intervals: split conformal / CQR, calibrated per fold and lead on placebo windows only (undisturbed);
leads beyond the longest placebo horizon reuse its calibration and are flagged `extrapolated`.
Writes runs/<run_id>/{config.yaml, git_commit.txt, data_hash.txt, metrics.csv, attribution.csv,
calibration.csv, summary.md, maps/*.npz, predictions/*.npz (with --save-predictions)}.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from ecorewind.data.cube import Cube  # noqa: E402
from ecorewind.data.events import load_cutoffs  # noqa: E402
from ecorewind.eval import attribution as A  # noqa: E402
from ecorewind.eval import conformal as CF  # noqa: E402
from ecorewind.eval.metrics import score  # noqa: E402
from ecorewind.eval.pixels import PixelTable, build_table  # noqa: E402
from ecorewind.eval.split import make_split  # noqa: E402
from ecorewind.models.baselines.harmonic import Harmonic  # noqa: E402
from ecorewind.models.baselines.lgbm import LGBM  # noqa: E402
from ecorewind.models.baselines.simple import Climatology, Persistence  # noqa: E402
from ecorewind.models.baselines.synth_control import SynthControl  # noqa: E402

ALL_MODELS = ("persistence", "climatology", "harmonic", "harmonic_notrend", "synth_control", "lgbm")
ATTR_CHANNELS = ("NDVI", "NDMI", "NDWI")


def load_cfg():
    cfg = {}
    for n in ("sites", "tracks", "events", "phase1"):
        cfg.update(yaml.safe_load((REPO / "configs" / f"{n}.yaml").read_text()))
    cfg["prereg"] = yaml.safe_load((REPO / "configs" / "preregistration.yaml").read_text())
    p2 = REPO / "configs" / "phase2.yaml"
    cfg["phase2"] = yaml.safe_load(p2.read_text()) if p2.exists() else {}
    cfg["phase3"] = yaml.safe_load((REPO / "configs" / "phase3.yaml").read_text())
    return cfg


def make_model(name, cfg, block_proxy, fast):
    p = cfg["phase2"].get("lgbm", {})
    if name == "persistence":
        return Persistence()
    if name == "climatology":
        return Climatology()
    if name == "harmonic":
        return Harmonic(**cfg["phase2"].get("harmonic", {}))
    if name == "harmonic_notrend":                       # amendment A1
        return Harmonic(**{**cfg["phase2"].get("harmonic", {}), "trend": False})
    if name == "synth_control":
        return SynthControl(block_proxy)
    if name == "lgbm":
        if fast:
            p = {**p, "n_estimators": 30, "n_rows": 5000}
        return LGBM(**p)
    m = re.fullmatch(r"(convlstm|simvp|ecotransformer)(?:_(gate|concat|off))?(?:__([a-z0-9-]+))?_s(\d+)", name)
    if m:          # deep models: ecotransformer_s0, ecotransformer_off_s1, simvp__nbr_s0, ecotransformer__tin4_s0
        from ecorewind.models.deep.trainer import DeepModel
        return DeepModel(m.group(1), cfg["phase3"], cfg["_ctx"], int(m.group(4)), m.group(2) or "gate", fast,
                         m.group(3) or "")
    raise ValueError(name)


def _json(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def run_model(name, table, cutoffs, n_folds, cfg, block_proxy, fast, alpha, log, lead0=True):
    """Returns per-cutoff predictions (q50, lo, hi: (L, C, n)), calibration rows."""
    C, n = len(table.channels), table.n
    preds = {cut.name: None for cut in cutoffs}
    cal_scores = {}                                   # (k, lead, ci) -> list of arrays
    for cut in cutoffs:
        for k in cfg.get("_folds") or range(n_folds):
            s = make_split(table, cut, k, n_folds, lead0)
            if preds[cut.name] is None:
                L = len(s.tgt_idx)
                preds[cut.name] = {"q50": np.full((L, C, n), np.nan, "float32"), "lo": np.full((L, C, n), np.nan, "float32"),
                                   "hi": np.full((L, C, n), np.nan, "float32"), "lo_base": np.full((L, C, n), np.nan, "float32"),
                                   "hi_base": np.full((L, C, n), np.nan, "float32"), "leads": s.leads, "keys": [table.keys[i] for i in s.tgt_idx],
                                   "kind": cut.kind}
            if len(s.hist_idx) < 2 or not len(s.tgt_idx):
                continue
            t0 = time.time()
            m = make_model(name, cfg, block_proxy, fast).fit(s)
            q, lo, hi = m.predict(s, s.test)
            P = preds[cut.name]
            P["q50"][:, :, s.test], P["lo_base"][:, :, s.test], P["hi_base"][:, :, s.test] = q, lo, hi
            if cut.kind == "placebo" and len(s.calib):
                qc, loc, hic = m.predict(s, s.calib)
                y = s.target(s.calib)
                for li, lead in enumerate(s.leads):
                    for ci in range(C):
                        sc = CF.scores(y[li, ci], loc[li, ci], hic[li, ci])
                        cal_scores.setdefault((k, lead, ci), []).append(sc)
            log(f"    {name} {cut.name} fold {k}: {time.time() - t0:.1f}s")
    # conformal quantiles per fold x lead x channel, pooled over placebo windows
    calib_rows, qhat = [], {}
    max_lead = max((ld for (_, ld, _) in cal_scores), default=None)
    for (k, lead, ci), arrs in cal_scores.items():
        s = np.concatenate(arrs)
        qhat[(k, lead, ci)] = CF.qhat(s, alpha)
        calib_rows.append({"model": name, "fold": k, "lead": lead, "channel": table.channels[ci], "n_scores": len(s),
                           "qhat": qhat[(k, lead, ci)]})
    for cut in cutoffs:
        P = preds[cut.name]
        P["extrapolated"] = []
        for li, lead in enumerate(P["leads"]):
            use = lead if max_lead is not None and lead <= max_lead else max_lead
            if use is None:
                continue
            if use != lead:
                P["extrapolated"].append(lead)
            for k in range(n_folds):
                sel = table.fold == k
                for ci in range(C):
                    qq = qhat.get((k, use, ci), np.nan)
                    P["lo"][li, ci, sel], P["hi"][li, ci, sel] = CF.interval(P["lo_base"][li, ci, sel], P["hi_base"][li, ci, sel], qq)
    return preds, calib_rows


def evaluate(name, table, preds, n_folds):
    rows, attr = [], []
    ha = table.res ** 2 / 1e4
    for cut_name, P in preds.items():
        Yt = table.Y[[table.keys.index(k) for k in P["keys"]]]
        for k in list(range(n_folds)) + ["all"]:
            sel = np.ones(table.n, bool) if k == "all" else table.fold == k
            for li, lead in enumerate(P["leads"]):
                for ci, ch in enumerate(table.channels):
                    y, q, lo, hi = (a[li, ci, sel] for a in (Yt, P["q50"], P["lo"], P["hi"]))
                    if k != "all":
                        rows.append({"model": name, "site": table.site, "track": table.track, "cutoff": cut_name,
                                     "kind": P["kind"], "fold": k, "lead": lead, "quarter": P["keys"][li], "channel": ch,
                                     "extrapolated_interval": lead in P["extrapolated"], **score(y, q, lo, hi)})
                    if ch in ATTR_CHANNELS:
                        attr.append({"model": name, "site": table.site, "track": table.track, "cutoff": cut_name,
                                     "kind": P["kind"], "fold": k, "lead": lead, "quarter": P["keys"][li], "channel": ch,
                                     **A.deficit(y, q, lo, hi, ha)})
    return rows, attr


def save_maps(out_dir, name, table, preds):
    for cut_name, P in preds.items():
        if P["kind"] != "event":
            continue
        Yt = table.Y[[table.keys.index(k) for k in P["keys"]]]
        maps = {}
        for ch in ATTR_CHANNELS:
            ci = table.channels.index(ch)
            d = P["q50"][:, ci] - Yt[:, ci]                                       # (L, n)
            for tag, v in (("lead1", d[0]), ("mean", np.nanmean(d, axis=0) if np.isfinite(d).any() else d[0])):
                g = np.full(table.shape, np.nan, dtype="float16")
                g[table.r, table.c] = v.astype("float16")
                maps[f"{ch}_{tag}"] = g
        np.savez_compressed(out_dir / f"{name}_{table.site}_{table.track}_{cut_name}.npz", leads=np.array(P["leads"]), **maps)


def summary_md(metrics: pd.DataFrame, attr: pd.DataFrame, run_id: str) -> str:
    md = [f"# Phase 2 baselines — run `{run_id}`", "",
          "Skill (C1) is measured on the pre-registered **placebo windows** (undisturbed), on held-out test folds. "
          "Values: mean ± std over the 5 folds (each fold's value averaged over windows and leads >= 1; lead 0 is "
          "the secondary analysis of amendment A2).", ""]
    plc = metrics[(metrics.kind == "placebo") & (metrics.lead >= 1)]
    for (site, track), g in plc.groupby(["site", "track"]):
        md += [f"## {site} / Track {track}", "", "| Model | NDVI R² | NDMI R² | NDWI R² | NDVI RMSE | 90% coverage (NDVI) | width (NDVI) |",
               "|---|---|---|---|---|---|---|"]
        for model, gm in g.groupby("model"):
            def ms(ch, col):
                v = gm[gm.channel == ch].groupby("fold")[col].mean()
                return f"{v.mean():.3f} ± {v.std():.3f}" if len(v) else "—"
            md.append(f"| {model} | {ms('NDVI', 'r2')} | {ms('NDMI', 'r2')} | {ms('NDWI', 'r2')} | {ms('NDVI', 'rmse')} | "
                      f"{ms('NDVI', 'coverage')} | {ms('NDVI', 'width')} |")
        md.append("")
    md += ["## Attributed NDVI deficit (counterfactual − observed), all folds", "",
           "Mean over evaluated wetland pixels; [interval] from conformal bounds. Placebo windows should be ≈ 0.", "",
           "| Site / track | Cutoff | Kind | Model | Lead 0 (A2) | Lead 1 | Mean over leads ≥ 1 | Lead-1 interval |",
           "|---|---|---|---|---|---|---|---|"]
    a = attr[(attr.fold == "all") & (attr.channel == "NDVI")]
    for (site, track, cut, kind, model), g in a.groupby(["site", "track", "cutoff", "kind", "model"]):
        g0, g = g[g.lead == 0], g[g.lead >= 1].sort_values("lead")
        if g.empty:
            continue
        l1 = g.iloc[0]
        z = f"{g0['mean'].iloc[0]:+.4f}" if len(g0) else "—"
        md.append(f"| {site} / {track} | {cut} | {kind} | {model} | {z} | {l1['mean']:+.4f} | {g['mean'].mean():+.4f} | "
                  f"[{l1['mean_lo']:+.4f}, {l1['mean_hi']:+.4f}] |")
    return "\n".join(md) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cubes", required=True)
    ap.add_argument("--phase1", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--site", nargs="*")
    ap.add_argument("--track", nargs="*")
    ap.add_argument("--models", nargs="*", default=list(ALL_MODELS))
    ap.add_argument("--table-cache", default="/tmp/ecorewind_tables")
    ap.add_argument("--run-id", help="default phase2_baselines_<UTC date>; re-running with the same id resumes")
    ap.add_argument("--save-predictions", action="store_true")
    ap.add_argument("--fast", action="store_true", help="tiny LightGBM (tests / smoke runs)")
    ap.add_argument("--phase1-config")
    ap.add_argument("--folds", nargs="*", type=int, help="only these test folds (timing / smoke runs)")
    ap.add_argument("--phase3-config", help="override configs/phase3.yaml (tests, ablations)")
    ap.add_argument("--ppost-exports", help="folder with placebo _PPOST GeoTIFFs (amendment A3) for lead 0")
    ap.add_argument("--no-lead0", action="store_true", help="skip lead 0 (cutoff quarter; amendment A2)")
    a = ap.parse_args()
    cfg = load_cfg()
    if a.phase1_config:
        cfg.update(yaml.safe_load(Path(a.phase1_config).read_text()))
    if a.phase3_config:
        cfg["phase3"] = {**cfg["phase3"], **yaml.safe_load(Path(a.phase3_config).read_text())}
    cfg["_folds"] = a.folds
    alpha = 1 - cfg["prereg"]["evaluation"]["interval"]
    n_folds = cfg["folds"]["n"]
    run_id = a.run_id or "phase2_baselines_" + datetime.now(timezone.utc).strftime("%Y%m%d")   # same day = resume
    out = Path(a.out) / run_id
    (out / "maps").mkdir(parents=True, exist_ok=True)
    if a.save_predictions:
        (out / "predictions").mkdir(exist_ok=True)
    Path(a.table_cache).mkdir(parents=True, exist_ok=True)
    (out / "config.yaml").write_text(yaml.safe_dump({"models": a.models, "alpha": alpha, "fast": a.fast,
                                                     "phase2": cfg["phase2"], "phase3": cfg["phase3"], "blocks": cfg["blocks"], "folds": cfg["folds"]}))
    (out / "git_commit.txt").write_text(git_commit() + "\n")
    log = lambda m: print(m, flush=True)  # noqa: E731
    all_m, all_a, all_c, hashes = [], [], [], {}
    cutoffs_all = load_cutoffs(cfg["prereg"])

    def get_table(site, track):
        cache = Path(a.table_cache) / f"{site}_{track}_v{3 if a.ppost_exports else 2}.npz"
        if cache.exists():
            return PixelTable.load(cache)
        log(f"building pixel table {site} {track}")
        cube = Cube(Path(a.cubes) / f"{site}_{track}.zarr")
        t = build_table(cube, Path(a.phase1) / "folds" / f"{site}_{track}.npz",
                        Path(a.phase1) / "static" / f"{site}_{track}.npz", cfg["blocks"]["size_m"],
                        extra_exports=a.ppost_exports)
        t.save(cache)
        return t

    def make_source(split):
        """Cross-site transfer: the other site's Track B event cutoff, same test fold index."""
        src_site = next(s for s in cfg["sites"] if s != split.table.site)
        st = get_table(src_site, "B")
        cut = next(c for c in cutoffs_all if c.site == src_site and c.kind == "event")
        sp = make_split(st, cut, split.k, n_folds)
        ctx = {"cube": Path(a.cubes) / f"{src_site}_B.zarr", "folds": Path(a.phase1) / "folds" / f"{src_site}_B.npz",
               "static": Path(a.phase1) / "static" / f"{src_site}_B.npz", "res": st.res,
               "block_m": cfg["blocks"]["size_m"], "buffer_m": cfg["blocks"]["buffer_m"]}
        return sp, ctx
    for site in a.site or list(cfg["sites"]):
        blocks = pd.read_csv(Path(a.phase1) / "folds" / f"{site}_blocks.csv")
        block_proxy = dict(zip(blocks.block.astype(int), blocks.proxy))
        for track in a.track or ["A", "B"]:
            table = get_table(site, track)                     # v2: + _POST rows; v3: + _PPOST
            hashes[f"{site}_{track}"] = table.data_hash
            cfg["_ctx"] = {"cube": Path(a.cubes) / f"{site}_{track}.zarr", "folds": Path(a.phase1) / "folds" / f"{site}_{track}.npz",
                           "static": Path(a.phase1) / "static" / f"{site}_{track}.npz", "res": table.res,
                           "block_m": cfg["blocks"]["size_m"], "buffer_m": cfg["blocks"]["buffer_m"],
                           "cache": out / "deep_cache", "log": log,
                           "make_source": make_source}
            tracks_of = {**{k: v["tracks"] for k, v in cfg["prereg"]["events"].items()},
                         **{k: v["tracks"] for k, v in cfg["prereg"]["placebos"].items()}}
            cuts = sorted([c for c in cutoffs_all if c.site == site and track in tracks_of[c.name]], key=lambda c: c.kind != "placebo")
            log(f"{site} {track}: {table.n:,} evaluable pixels; cutoffs {[c.name for c in cuts]}")
            for name in a.models:
                part = out / "parts" / f"{site}_{track}_{name}.json"
                have_pred = not a.save_predictions or any((out / "predictions").glob(f"{name}_{site}_{track}_*.npz"))
                if part.exists() and have_pred:                     # resume: finished earlier in this run
                    d = json.loads(part.read_text())
                    all_m, all_a, all_c = all_m + d["metrics"], all_a + d["attribution"], all_c + d["calibration"]
                    log(f"  {name}: done earlier, skipping")
                    continue
                preds, calib = run_model(name, table, cuts, n_folds, cfg, block_proxy, a.fast, alpha, log, not a.no_lead0)
                rows, attr = evaluate(name, table, preds, n_folds)
                calib = [{**r, "site": site, "track": track} for r in calib]
                save_maps(out / "maps", name, table, preds)
                part.parent.mkdir(exist_ok=True)
                part.write_text(json.dumps({"metrics": rows, "attribution": attr, "calibration": calib}, default=_json))
                all_m, all_a, all_c = all_m + rows, all_a + attr, all_c + calib
                if a.save_predictions:
                    for cn, P in preds.items():
                        np.savez_compressed(out / "predictions" / f"{name}_{site}_{track}_{cn}.npz",
                                            q50=P["q50"].astype("float16"), lo=P["lo"].astype("float16"),
                                            hi=P["hi"].astype("float16"), r=table.r, c=table.c,
                                            leads=np.array(P["leads"]), channels=np.array(table.channels))
    metrics, attr = pd.DataFrame(all_m), pd.DataFrame(all_a)
    attr["fold"] = attr["fold"].astype(str)
    metrics.to_csv(out / "metrics.csv", index=False)
    attr.to_csv(out / "attribution.csv", index=False)
    pd.DataFrame(all_c).to_csv(out / "calibration.csv", index=False)
    (out / "data_hash.txt").write_text(json.dumps(hashes, indent=1) + "\n")
    md = summary_md(metrics, attr, run_id)
    (out / "summary.md").write_text(md)
    print(md)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
