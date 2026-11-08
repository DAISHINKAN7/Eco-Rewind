"""Audit the Phase 0 Earth Engine re-exports and write reports/data_audit_v2.md.

    python scripts/audit_exports.py --dir /content/drive/MyDrive/EcoRewind2_exports \
        --out /content/drive/MyDrive/EcoRewind2/reports --stride 2

Per-file results are cached in <out>/audit_v2_cache/ so a dropped session resumes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
REPORTS = Path(os.environ.get("ECOREWIND_REPORTS", REPO / "reports"))
sys.path.insert(0, str(REPO / "src"))
from ecorewind.data import audit_exports as X  # noqa: E402
from ecorewind.data.periods import periods  # noqa: E402


def expected_periods(config_dir: Path) -> dict[tuple[str, str], list[str]]:
    cfg = {}
    for n in ("sites", "tracks", "events"):
        cfg.update(yaml.safe_load((config_dir / f"{n}.yaml").read_text()))
    landfall = {ev["site"]: date.fromisoformat(str(ev["landfall"])) for ev in cfg["events"].values()}
    return {(s, tr): [p.key for p in periods(t["start"], t["end"], landfall.get(s), cfg.get("post_offset_days", 3))]
            for s in cfg["sites"] for tr, t in cfg["tracks"].items()}


def manifest_bands(manifest_dir: Path) -> dict[str, list[str]]:
    out = {}
    for f in manifest_dir.glob("manifest_*.json"):
        out.update({r["file"]: r["bands"] for r in json.loads(f.read_text())})
    return out


def fmt(x, p=1, pct=False):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    return f"{100 * x:.{p}f}%" if pct else f"{x:.{p}f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="folder with the exported GeoTIFFs")
    ap.add_argument("--config-dir", default=str(REPO / "configs"))
    ap.add_argument("--manifest-dir", default=str(REPORTS / "exports"))
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--out", default=str(REPORTS))
    ap.add_argument("--max-files", type=int)
    a = ap.parse_args()

    out = Path(a.out)
    cache = out / "audit_v2_cache"
    cache.mkdir(parents=True, exist_ok=True)
    mb = manifest_bands(Path(a.manifest_dir))
    files = sorted(f for f in Path(a.dir).glob("*.tif") if X.parse(f.name))
    skipped = sorted(f.name for f in Path(a.dir).glob("*.tif") if not X.parse(f.name))
    if a.max_files:
        files = files[: a.max_files]
    recs = []
    for i, f in enumerate(files, 1):
        c = cache / f"{f.stem}.s{a.stride}.json"
        if c.exists():
            recs.append(json.loads(c.read_text()))
            continue
        print(f"[{i}/{len(files)}] {f.name}", flush=True)
        r = X.inspect(f, mb.get(f.name), a.stride)
        c.write_text(json.dumps(r, default=str))
        recs.append(r)

    expected = expected_periods(Path(a.config_dir))
    checks = X.gate_checks(recs, expected)
    passed = all(ok for _, ok, _ in checks)
    df = pd.DataFrame(recs)
    md = ["# EcoRewind 2.0 — Re-export audit (Phase 0 gate)", "",
          f"Generated {date.today().isoformat()} by `scripts/audit_exports.py` (stride={a.stride}) "
          f"on `{a.dir}`: {len(recs)} files.", "",
          f"## Gate: **{'PASS' if passed else 'FAIL'}**", "", "| Check | Result | Detail |", "|---|---|---|"]
    md += [f"| {n} | {'✅' if ok else '❌'} | {d} |" for n, ok, d in checks]
    if skipped:
        md += ["", f"Files not matching the naming scheme (ignored): {', '.join(skipped)}"]
    for (site, track), keys in sorted(expected.items()):
        sub = df[(df.get("site") == site) & (df.get("track") == track)] if len(df) else df
        if not len(sub):
            continue
        opt = {r["key"]: r for _, r in sub[sub["sensor"] == "optical"].iterrows()}
        s1 = {r["key"]: r for _, r in sub[sub["sensor"] == "S1"].iterrows()}
        r0 = sub.iloc[0]
        md += ["", f"## {site} / Track {track}", "",
               f"Grid `{r0['crs']}` {r0['width']}×{r0['height']} @ {r0['res'][0]:g} m. "
               f"Optical bands: {next(iter(opt.values()))['bands'] if opt else '—'}. "
               f"Scale: {next(iter(opt.values())).get('optical_scale') if opt else '—'}.", "",
               "| Period | clear obs (median) | optical valid | NDVI median | NDVI=−1 | S1 obs (median) | SAR valid | VV median dB |",
               "|---|---|---|---|---|---|---|---|"]
        for k in keys:
            o, s = opt.get(k, {}), s1.get(k, {})
            g = lambda d, f, **kw: fmt(d.get(f), **kw) if len(d) else "missing"  # noqa: E731
            md.append(f"| {k} | {g(o, 'n_clear_median', p=0)} | {g(o, 'optical_valid', pct=True)} "
                      f"| {g(o, 'ndvi_median', p=3)} | {g(o, 'ndvi_eq_minus1', p=2, pct=True)} "
                      f"| {g(s, 'n_s1_median', p=0)} | {g(s, 'sar_valid', pct=True)} | {g(s, 'vv_median_db', p=1)} |")
    statics = df[df["sensor"] == "static"]["file"].tolist() if len(df) else []
    md += ["", f"Static files: {', '.join(statics) or 'none'}", ""]
    (out / "data_audit_v2.md").write_text("\n".join(md))
    df.to_csv(out / "data_audit_v2_files.csv", index=False)
    (out / "data_audit_v2.json").write_text(json.dumps({"gate_pass": passed, "checks": checks}, indent=1))
    print(f"Gate {'PASS' if passed else 'FAIL'}; wrote {out / 'data_audit_v2.md'}")


if __name__ == "__main__":
    main()
