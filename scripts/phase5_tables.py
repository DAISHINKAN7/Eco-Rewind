"""Phase 5.3-5.5 tables -> reports/phase5_tables.md: ablations, cross-site transfer, resolution comparison.

    python scripts/phase5_tables.py --runs <drive>/runs/phase3_core_v1 <drive>/runs/phase5_ablations \
        <drive>/runs/phase5_transfer <drive>/runs/phase5_resolution --out <drive>/reports

Ablations are judged on VALIDATION NDVI R² (calibration fold, pre-cutoff pairs; from each trained fold's cache), as
pre-registered; held-out placebo-window test skill is shown next to it for information only.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from placebo_verdict import load_run  # noqa: E402

CACHE = re.compile(r"^(everglades|mississippi)_([AB])_(.+)_((?:ida|irma)\w*)_k(\d)_[0-9a-f]{8}$")


def parse_model(name: str) -> dict:
    m = re.fullmatch(r"(convlstm|simvp|ecotransformer)(?:_(gate|concat|off))?(?:__([a-z0-9-]+))?_s(\d+)", name)
    if not m:
        return {"arch": name, "sar": "", "variant": "", "seed": 0}
    return {"arch": m.group(1), "sar": m.group(2) or ("gate" if m.group(1) == "ecotransformer" else ""),
            "variant": m.group(3) or "", "seed": int(m.group(4))}


def val_table(run_dirs) -> pd.DataFrame:
    rows = []
    for rd in run_dirs:
        for f in (Path(rd) / "deep_cache").glob("*.npz"):
            m = CACHE.match(f.stem)
            if not m:
                continue
            site, track, model, cut, k = m.groups()
            info = json.loads(str(np.load(f)["info"]))
            rows.append({"mtime": f.stat().st_mtime, "site": site, "track": track, "model": model, "cutoff": cut, "fold": int(k),
                         "val_r2": info.get("best_val_ndvi_r2", np.nan), "epochs": info.get("epochs"),
                         "minutes": info.get("seconds", np.nan) / 60, "killed": info.get("killed", False),
                         **parse_model(model)})
    v = pd.DataFrame(rows)
    if v.empty:
        return v
    # stale caches from superseded configs (e.g. before the min_history fix): keep the newest per (cutoff, fold)
    return v.sort_values("mtime").drop_duplicates(["site", "track", "model", "cutoff", "fold"], keep="last")


def test_table(run_dirs) -> pd.DataFrame:
    ms = []
    for rd in run_dirs:
        try:
            ms.append(load_run(Path(rd), "metrics"))
        except FileNotFoundError:
            continue
    if not ms:
        return pd.DataFrame()
    m = pd.concat(ms, ignore_index=True)
    m = m[(m.kind == "placebo") & (m.lead >= 1) & (m.channel == "NDVI")]
    return m.groupby(["site", "track", "model", "fold"])["r2"].mean().groupby(["site", "track", "model"]).mean() \
        .reset_index(name="test_r2")


def label(r) -> str:
    parts = [r.arch]
    if r.arch == "ecotransformer" and r.sar != "gate":
        parts.append(f"SAR {r.sar}")
    if r.variant:
        parts.append(r.variant)
    return " · ".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    v = val_table(a.runs)
    t = test_table(a.runs)
    if v.empty:
        raise SystemExit("no deep_cache files found")
    g = v.groupby(["site", "track", "model"]).agg(val_r2=("val_r2", "mean"), val_sd=("val_r2", "std"),
                                                    n=("val_r2", "size"), minutes=("minutes", "sum"),
                                                    killed=("killed", "sum")).reset_index()
    g = g.merge(t, how="left", on=["site", "track", "model"])
    meta = g.model.map(parse_model).apply(pd.Series)
    g = pd.concat([g, meta], axis=1)
    g["label"] = g.apply(label, axis=1)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    g.to_csv(out / "phase5_models.csv", index=False)
    md = ["# Phase 5 — ablations, transfer, resolution", "",
          "Val R² = NDVI R² on the calibration fold (pre-cutoff pairs), mean ± sd over trained (cutoff × fold); "
          "this is the pre-registered ablation criterion. Test R² = placebo windows, held-out folds, leads ≥ 1 "
          "(information only). Δ is relative to the parent (same site/track, no variant, gate SAR, seeds pooled).", ""]
    for (site, track), gg in g.groupby(["site", "track"]):
        vs = v[(v.site == site) & (v.track == track)]
        md += [f"## {site} / Track {track}", "",
               "| Model | Cutoffs·folds | Val R² | Δ val vs parent (same cutoffs·folds) | Test R² | Δ test | GPU min | Killed |",
               "|---|---|---|---|---|---|---|---|"]
        for r in gg.sort_values(["arch", "variant", "sar", "seed"]).itertuples():
            is_child = bool(r.variant) or r.sar not in ("gate", "")
            dv = dt = "—"
            if is_child:
                mine = vs[vs.model == r.model][["cutoff", "fold"]]
                par = vs[(vs.arch == r.arch) & (vs.variant == "") & vs.sar.isin(["gate", ""])].merge(mine, on=["cutoff", "fold"])
                if len(par):
                    dv = f"{r.val_r2 - par.val_r2.mean():+.3f} (n={par.groupby(['cutoff', 'fold']).ngroups})"
                pt = gg[(gg.arch == r.arch) & (gg.variant == "") & gg.sar.isin(["gate", ""])].test_r2.mean()
                if np.isfinite(pt) and np.isfinite(r.test_r2):
                    dt = f"{r.test_r2 - pt:+.3f}"
            tr = f"{r.test_r2:.3f}" if np.isfinite(r.test_r2) else "—"
            md.append(f"| {r.label} (s{r.seed}) | {r.n} | {r.val_r2:.3f} ± {0 if np.isnan(r.val_sd) else r.val_sd:.3f} | "
                      f"{dv} | {tr} | {dt} | {r.minutes:.0f} | {r.killed} |")
        md.append("")
    md += ["Transfer rows (`xfer`) were trained on the other site's Track B event history and applied here; compare "
           "their test R² with the same architecture trained on site. Resolution: compare Mississippi Track A vs "
           "Track B rows of the same model (different pixels, same blocks).", ""]
    (out / "phase5_tables.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
