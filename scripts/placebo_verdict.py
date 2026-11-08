"""Phase 4: pre-registered placebo test (MASTER_PROMPT §9) -> reports/placebo_verdict.md.

    python scripts/placebo_verdict.py --runs <drive>/runs/phase2_baselines_v3 <drive>/runs/phase3_core_v1 \
        --phase1 <drive>/phase1 --out reports

Operationalisation (amendment A4, fixed before this script was first run on real results):
- Statistic: NDVI attributed deficit (counterfactual - observed), mean over evaluable wetland pixels of one test
  fold, averaged over leads 1..3 (the horizon every event and placebo window shares; Irma is capped at 3).
- Placebo distribution per model: all placebo windows x 5 test folds x seeds (seeds pooled: `simvp_s0`, `simvp_s1`
  -> `simvp`). Event values: 5 folds x seeds.
- PASS (placebo in time) iff (1) median event value > 95th percentile of the placebo distribution and
  (2) 90 % interval coverage on placebo windows (NDVI, leads >= 1) >= 0.80.
- Secondary (A2/A3): the same rule at lead 0 (post-landfall composite vs matched-days placebo composite).
- Placebo in space: event deficit in the least-exposed blocks (top 20 % by median coast distance, an
  outcome-independent proxy), lead-0 and mean-over-leads maps; should lie inside the placebo range.
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from ecorewind.data.blocks import block_ids  # noqa: E402

LEADS = (1, 2, 3)


def family(model: str) -> str:
    return re.sub(r"_s\d+$", "", model)


def seed(model: str) -> int:
    m = re.search(r"_s(\d+)$", model)
    return int(m.group(1)) if m else 0


def fold_values(attr: pd.DataFrame, leads) -> pd.DataFrame:
    a = attr[(attr.channel == "NDVI") & (attr.fold.astype(str) != "all") & attr.lead.isin(leads)]
    v = a.groupby(["model", "site", "track", "cutoff", "kind", "fold"])["mean"].mean().reset_index(name="value")
    v["family"], v["seed"] = v.model.map(family), v.model.map(seed)
    return v


def verdict(vals: pd.DataFrame, cov: pd.DataFrame, q: float = 0.95, cov_min: float = 0.80) -> pd.DataFrame:
    rows = []
    for (site, track, fam), g in vals.groupby(["site", "track", "family"]):
        plc = g[g.kind == "placebo"].value.dropna().to_numpy()
        for ev, ge in g[g.kind == "event"].groupby("cutoff"):
            e = ge.value.dropna().to_numpy()
            if not len(plc) or not len(e):
                continue
            thr = float(np.percentile(plc, q * 100))
            c = cov[(cov.site == site) & (cov.track == track) & (cov.family == fam)].coverage
            c = float(c.iloc[0]) if len(c) else float("nan")
            rows.append({"site": site, "track": track, "event": ev, "model": fam, "n_event": len(e),
                         "n_placebo": len(plc), "event_median": float(np.median(e)), "event_min": float(e.min()),
                         "placebo_p95": thr, "placebo_min": float(plc.min()), "placebo_max": float(plc.max()),
                         "frac_event_above": float(np.mean(e > thr)), "coverage": c,
                         "pass_exceeds": bool(np.median(e) > thr), "pass_coverage": bool(c >= cov_min),
                         "PASS": bool(np.median(e) > thr and c >= cov_min)})
    return pd.DataFrame(rows)


def coverage(metrics: pd.DataFrame) -> pd.DataFrame:
    m = metrics[(metrics.kind == "placebo") & (metrics.channel == "NDVI") & (metrics.lead >= 1)].copy()
    m["family"] = m.model.map(family)
    return m.groupby(["site", "track", "family"])["coverage"].mean().reset_index()


def placebo_in_space(run_dirs, phase1: Path, block_m: float, frac: float = 0.2, min_px: int = 50) -> pd.DataFrame:
    rows = []
    for rd in run_dirs:
        for f in sorted((Path(rd) / "maps").glob("*.npz")):
            m = re.match(r"(.+)_(everglades|mississippi)_([AB])_(.+)$", f.stem)
            if not m:
                continue
            model, site, track, cut = m.groups()
            st = np.load(phase1 / "static" / f"{site}_{track}.npz")
            if "coast_dist_m" not in st.files:
                continue
            z = np.load(f)
            coast = st["coast_dist_m"].astype("float64")
            bid = block_ids(coast.shape, 30.0 if track == "B" else 10.0, block_m)
            for tag in ("lead1", "mean"):
                key = f"NDVI_{tag}"
                if key not in z.files:
                    continue
                d = z[key].astype("float64")
                ok = np.isfinite(d) & np.isfinite(coast)
                if not ok.any():
                    continue
                b = pd.DataFrame({"b": bid[ok], "d": d[ok], "c": coast[ok]}).groupby("b").agg(d=("d", "mean"), c=("c", "median"), n=("d", "size"))
                b = b[b.n >= min_px]
                far = b[b.c >= b.c.quantile(1 - frac)] if len(b) else b
                if far.empty:
                    continue
                rows.append({"site": site, "track": track, "event": cut, "model": family(model), "seed": seed(model),
                             "map": "lead 0" if tag == "lead1" else "mean over leads", "blocks": len(far),
                             "least_exposed_deficit": float(np.average(far.d, weights=far.n)),
                             "all_blocks_deficit": float(np.average(b.d, weights=b.n))})
    return pd.DataFrame(rows)


def render(prim: pd.DataFrame, sec: pd.DataFrame, space: pd.DataFrame) -> str:
    def table(v):
        md = ["| Site / track | Event | Model | Event median (min) | Placebo p95 [range] | n ev / plc | Event folds > p95 | "
              "Placebo coverage | Exceeds | Coverage ≥ 0.80 | **Verdict** |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in v.sort_values(["site", "track", "model"]).itertuples():
            md.append(f"| {r.site} / {r.track} | {r.event} | {r.model} | {r.event_median:+.4f} ({r.event_min:+.4f}) | "
                      f"{r.placebo_p95:+.4f} [{r.placebo_min:+.4f}, {r.placebo_max:+.4f}] | {r.n_event} / {r.n_placebo} | "
                      f"{r.frac_event_above:.0%} | {r.coverage:.3f} | {'yes' if r.pass_exceeds else 'no'} | "
                      f"{'yes' if r.pass_coverage else 'no'} | **{'PASS' if r.PASS else 'FAIL'}** |")
        return md
    md = ["# Phase 4 — placebo verdict", "",
          "Pre-registered rule: a model PASSES for an event if its median attributed NDVI deficit exceeds the 95th "
          "percentile of its placebo distribution (placebo windows × folds × seeds) **and** its 90 % intervals cover "
          "≥ 80 % of placebo truth. Statistic and pooling: amendment A4 (`configs/preregistration.yaml`).", "",
          "## Primary: leads 1–3 (first three full quarters after the event)", "", *table(prim), "",
          "## Secondary: lead 0 (post-landfall composite vs matched-days placebo composite, A2/A3)", "", *table(sec), ""]
    if len(space):
        md += ["## Placebo in space: event deficit in the least-exposed blocks (farthest 20 % from the coast)", "",
               "Should be ≈ 0 / inside the placebo range. Seeds averaged.", "",
               "| Site / track | Event | Model | Map | Least-exposed blocks | Deficit there | Deficit, all blocks |",
               "|---|---|---|---|---|---|---|"]
        s = space.groupby(["site", "track", "event", "model", "map"]).agg(
            blocks=("blocks", "first"), le=("least_exposed_deficit", "mean"), al=("all_blocks_deficit", "mean")).reset_index()
        md += [f"| {r.site} / {r.track} | {r.event} | {r.model} | {r.map} | {r.blocks} | {r.le:+.4f} | {r.al:+.4f} |"
               for r in s.itertuples()]
    n_pass = int(prim.PASS.sum()) if len(prim) else 0
    md += ["", f"**Primary: {n_pass} of {len(prim)} model × event combinations pass. Secondary (lead 0): "
               f"{int(sec.PASS.sum()) if len(sec) else 0} of {len(sec)}.**", ""]
    return "\n".join(md)


def load_run(rd: Path, key: str) -> pd.DataFrame:
    """All results of a run: the per-model parts/*.json (complete across invocations), else the run's CSV
    (a run invoked once per site keeps only the last invocation's sites in metrics.csv / attribution.csv)."""
    import json
    parts = sorted((rd / "parts").glob("*.json"))
    if parts:
        return pd.concat([pd.DataFrame(json.loads(p.read_text())[key]) for p in parts], ignore_index=True)
    return pd.read_csv(rd / ("attribution.csv" if key == "attribution" else "metrics.csv"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--phase1", required=True)
    ap.add_argument("--out", default=str(REPO / "reports"))
    ap.add_argument("--block-m", type=float, default=3840)
    a = ap.parse_args()
    attr = pd.concat([load_run(Path(r), "attribution") for r in a.runs], ignore_index=True)
    metrics = pd.concat([load_run(Path(r), "metrics") for r in a.runs], ignore_index=True)
    attr = attr.drop_duplicates(["model", "site", "track", "cutoff", "fold", "lead", "channel"], keep="last")
    metrics = metrics.drop_duplicates(["model", "site", "track", "cutoff", "fold", "lead", "channel"], keep="last")
    cov = coverage(metrics)
    prim, sec = verdict(fold_values(attr, LEADS), cov), verdict(fold_values(attr, (0,)), cov)
    space = placebo_in_space(a.runs, Path(a.phase1), a.block_m, min_px=1 if a.block_m < 1000 else 50)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prim.to_csv(out / "placebo_verdict_primary.csv", index=False)
    sec.to_csv(out / "placebo_verdict_lead0.csv", index=False)
    space.to_csv(out / "placebo_in_space.csv", index=False)
    md = render(prim, sec, space)
    (out / "placebo_verdict.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
