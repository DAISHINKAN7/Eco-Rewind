"""Phase 5.6: ILLUSTRATIVE aboveground-carbon equivalent of the attributed NDVI loss -> reports/carbon_illustrative.md

    python scripts/carbon_illustrative.py --runs <drive>/runs/phase2_baselines_v3 <drive>/runs/phase3_core_v1 \
        --verdict <drive>/reports --table-cache /content/tables --out <drive>/reports

Relative loss = attributed NDVI deficit / counterfactual NDVI (site means over evaluated wetland pixels, at the
configured statistic); carbon-equivalent = relative loss x evaluated area x aboveground-carbon density (low/high).
A crude proxy (NDVI is not biomass); only placebo-passing models; values are labelled ILLUSTRATIVE and carry the
config's verification status.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from ecorewind.eval.pixels import PixelTable  # noqa: E402
from placebo_verdict import family, load_run  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--verdict", required=True)
    ap.add_argument("--table-cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default=str(REPO / "configs/carbon.yaml"))
    a = ap.parse_args()
    cfg = yaml.safe_load(Path(a.config).read_text())
    lead = 0 if cfg["statistic"] == "lead 0" else 1
    attr = pd.concat([load_run(Path(r), "attribution") for r in a.runs], ignore_index=True)
    attr = attr[(attr.kind == "event") & (attr.channel == "NDVI") & (attr.fold.astype(str) == "all") & (attr.lead == lead)]
    attr = attr.assign(family=attr.model.map(family)).groupby(["site", "track", "cutoff", "family", "quarter"]) \
        .agg(deficit=("mean", "mean"), n=("n", "mean")).reset_index()
    vd = pd.read_csv(Path(a.verdict) / ("placebo_verdict_lead0.csv" if lead == 0 else "placebo_verdict_primary.csv"))
    attr = attr.merge(vd[["site", "track", "event", "model", "PASS"]].rename(columns={"event": "cutoff", "model": "family"}),
                      on=["site", "track", "cutoff", "family"], how="inner")
    attr = attr[attr.PASS]
    rows = []
    for (site, track), g in attr.groupby(["site", "track"]):
        tabs = sorted(Path(a.table_cache).glob(f"{site}_{track}_v*.npz"))
        if not tabs or site not in cfg["sites"]:
            continue
        tab = PixelTable.load(tabs[-1])
        sc = cfg["sites"][site]
        for r in g.itertuples():
            obs = float(np.nanmean(tab.Y[tab.keys.index(r.quarter), tab.channels.index("NDVI")]))
            cf = obs + r.deficit
            rel = r.deficit / cf if cf > 0 else np.nan
            area_ha = r.n * tab.res ** 2 / 1e4
            lo, hi = (rel * area_ha * sc["agb_carbon_t_per_ha"][k] for k in ("low", "high"))
            rows.append({"site": site, "track": track, "event": r.cutoff, "model": r.family, "deficit": r.deficit,
                         "observed": obs, "counterfactual": cf, "relative_loss": rel, "area_ha": area_ha,
                         "tC_low": lo, "tC_high": hi})
    res = pd.DataFrame(rows)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res.to_csv(out / "carbon_illustrative.csv", index=False)
    flag = "" if cfg.get("verified") else " — **UNVERIFIED PLACEHOLDER DENSITIES, NOT FOR PUBLICATION**"
    md = [f"# ILLUSTRATIVE carbon equivalent ({cfg['statistic']}){flag}", "",
          "Relative NDVI loss × evaluated wetland area × aboveground carbon density (low–high). NDVI is not biomass; "
          "this is an order-of-magnitude illustration for placebo-passing models only.", "",
          "| Site / track | Event | Model | Deficit | Relative loss | Area (ha) | t C (low–high) |", "|---|---|---|---|---|---|---|"]
    md += [f"| {r.site} / {r.track} | {r.event} | {r.model} | {r.deficit:+.4f} | {r.relative_loss:.1%} | {r.area_ha:,.0f} | "
           f"{r.tC_low:,.0f} – {r.tC_high:,.0f} |" for r in res.itertuples()]
    (out / "carbon_illustrative.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
