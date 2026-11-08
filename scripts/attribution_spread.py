"""Phase 5.1: attribution sensitivity across models (claim C3) -> reports/attribution_spread.md.

    python scripts/attribution_spread.py --runs <drive>/runs/phase2_baselines_v3 <drive>/runs/phase3_core_v1 \
        --verdict <drive>/reports --out <drive>/reports

Per event x site/track x model family (seeds averaged): attributed NDVI deficit over all evaluated wetland pixels
(mean, 90 % interval, area-integrated NDVI·ha) at lead 0 and averaged over leads 1-3. Spread across models: range and
max/min ratio (ratio only when all models agree in sign), for all models and for models that passed the placebo
test for that event and statistic (Phase 4 verdict CSVs).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from placebo_verdict import family, load_run  # noqa: E402

STATS = {"lead 0": (0,), "leads 1-3": (1, 2, 3)}


def per_model(attr: pd.DataFrame) -> pd.DataFrame:
    a = attr[(attr.kind == "event") & (attr.channel == "NDVI") & (attr.fold.astype(str) == "all")].copy()
    a["family"] = a.model.map(family)
    rows = []
    for stat, leads in STATS.items():
        g = a[a.lead.isin(leads)].groupby(["site", "track", "cutoff", "family"])
        s = g[["mean", "mean_lo", "mean_hi", "total"]].mean().reset_index()
        s["stat"] = stat
        rows.append(s)
    return pd.concat(rows, ignore_index=True)


def spread(v: pd.Series) -> dict:
    v = v.dropna()
    if not len(v):
        return {"n": 0, "min": np.nan, "max": np.nan, "range": np.nan, "ratio": np.nan}
    same_sign = (v > 0).all() or (v < 0).all()
    return {"n": len(v), "min": v.min(), "max": v.max(), "range": v.max() - v.min(),
            "ratio": (v.abs().max() / v.abs().min()) if same_sign else np.nan}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--verdict", required=True, help="folder with placebo_verdict_primary.csv / _lead0.csv")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    attr = pd.concat([load_run(Path(r), "attribution") for r in a.runs], ignore_index=True)
    attr = attr.drop_duplicates(["model", "site", "track", "cutoff", "fold", "lead", "channel"], keep="last")
    pm = per_model(attr)
    vd = {"leads 1-3": pd.read_csv(Path(a.verdict) / "placebo_verdict_primary.csv"),
          "lead 0": pd.read_csv(Path(a.verdict) / "placebo_verdict_lead0.csv")}
    passed = pd.concat([d.assign(stat=s)[["site", "track", "event", "model", "PASS", "stat"]] for s, d in vd.items()])
    pm = pm.merge(passed.rename(columns={"event": "cutoff", "model": "family"}), how="left",
                  on=["site", "track", "cutoff", "family", "stat"])
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pm.to_csv(out / "attribution_per_model.csv", index=False)
    md = ["# Attribution spread across models (claim C3)", "",
          "NDVI deficit (counterfactual − observed), mean over evaluated wetland pixels, all folds, seeds averaged; "
          "[90 % interval]; total = NDVI·ha. Placebo = Phase 4 verdict for the same statistic.", ""]
    srows = []
    for (site, track, cut, stat), g in pm.groupby(["site", "track", "cutoff", "stat"]):
        md += [f"## {cut} — {site} / Track {track} — {stat}", "",
               "| Model | Deficit | 90 % interval | Total (NDVI·ha) | Placebo |", "|---|---|---|---|---|"]
        for r in g.sort_values("mean").itertuples():
            p = "—" if pd.isna(r.PASS) else ("pass" if r.PASS else "fail")
            md.append(f"| {r.family} | {r.mean:+.4f} | [{r.mean_lo:+.4f}, {r.mean_hi:+.4f}] | {r.total:+.1f} | {p} |")
        for subset, gg in (("all models", g), ("placebo-passing", g[g.PASS == True])):  # noqa: E712
            s = spread(gg["mean"])
            srows.append({"event": cut, "site": site, "track": track, "stat": stat, "subset": subset, **s})
        md.append("")
    sp = pd.DataFrame(srows)
    sp.to_csv(out / "attribution_spread.csv", index=False)
    md += ["## Spread summary", "", "Ratio = max |deficit| / min |deficit|, only when all models agree in sign "
           "(v1 reported ≈ 20× across models).", "",
           "| Event | Site / track | Statistic | Models | n | Min | Max | Range | Ratio |", "|---|---|---|---|---|---|---|---|---|"]
    md += [f"| {r.event} | {r.site} / {r.track} | {r.stat} | {r.subset} | {r.n} | {r.min:+.4f} | {r.max:+.4f} | "
           f"{r.range:.4f} | {'—' if pd.isna(r.ratio) else f'{r.ratio:.1f}×'} |" for r in sp.itertuples()]
    (out / "attribution_spread.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
