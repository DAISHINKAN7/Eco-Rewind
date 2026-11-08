"""Run the week-1 data audit and write reports/data_audit.md.

Example (Colab, Drive mounted):
    python scripts/audit_data.py --config configs/data_sources.yaml \
        --source "mississippi_v2=/content/drive/MyDrive/<resolved v2 folder>" \
        --out reports --stride 2

Per-file results are cached in <out>/audit_cache/, so a dropped Colab session
resumes where it stopped.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ecorewind.data import audit as A  # noqa: E402


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default="configs/data_sources.yaml")
    p.add_argument("--source", action="append", default=[], metavar="NAME=DIR",
                   help="override or set a source directory (repeatable)")
    p.add_argument("--only", nargs="*", help="audit only these source names")
    p.add_argument("--stride", type=int, default=1, help="read every Nth pixel (1 = full resolution)")
    p.add_argument("--out", default="reports")
    p.add_argument("--max-files", type=int, default=None, help="smoke-test on a few files per source")
    return p.parse_args()


def resolve_sources(cfg: dict, overrides: list[str]) -> list[dict]:
    over = dict(o.split("=", 1) for o in overrides)
    out = []
    for s in cfg["sources"]:
        d = over.get(s["name"]) or (s["path"] and str(Path(cfg["drive_root"]) / s["path"]))
        out.append({**s, "dir": d})
    return out


def audit_source(src: dict, stride: int, cache: Path, max_files: int | None) -> list[dict]:
    files = sorted(Path(src["dir"]).glob(src["glob"]))
    files = [f for f in files if (n := A.parse_name(f.name)) and not n.is_mask]
    if max_files:
        files = files[:max_files]
    recs = []
    for i, f in enumerate(files, 1):
        c = cache / src["name"] / f"{f.stem}.s{stride}.json"
        if c.exists():
            rec = json.loads(c.read_text())
        else:
            print(f"  [{src['name']}] {i}/{len(files)} {f.name}", flush=True)
            rec = A.inspect_file(f, stride=stride)
            c.parent.mkdir(parents=True, exist_ok=True)
            c.write_text(json.dumps(rec, default=str))
        recs.append(rec)
    return recs


def pct(x) -> str:
    return "—" if x is None or pd.isna(x) else f"{100 * x:.1f}%"


def summarise(src, recs, all_names, calendar, landfall, expected_bands, expected_px) -> tuple[str, pd.DataFrame, dict]:
    comp = A.completeness(all_names, calendar)
    aligned, ref = A.check_alignment(recs) if recs else ({}, None)
    flags: list[str] = []
    rows = []
    for r in recs:
        n = A.parse_name(r["file"])
        cov = r["coverage"]
        rows.append({
            "source": src["name"], "file": r["file"], "quarter": n.key,
            "phase": A.event_phase(n.key, landfall), "interpolated": n.is_interpolated,
            "size_mb": r["size_mb"], "crs": r["crs"], "w": r["width"], "h": r["height"],
            "pixel_m": f"{r['pixel_m'][0]:.1f}x{r['pixel_m'][1]:.1f}", "aligned": aligned[r["file"]],
            "bands": ",".join(r["bands"]), "dtype": r["dtype"], "nodata": r["nodata"],
            "optical_valid": cov.get("optical_valid"), "sar_vv_valid": cov.get("SAR_VV_valid"),
            "sar_vh_valid": cov.get("SAR_VH_valid"), "ndvi_eq_-1": cov.get("ndvi_eq_minus1"),
            "ndvi_out_of_range": cov.get("ndvi_out_of_range"),
            "ndvi_median": r["stats"].get("NDVI", {}).get("median"),
            "optical_scale": r["scale"].get("optical"), "sar_scale": r["scale"].get("SAR_VV"),
        })
    df = pd.DataFrame(rows).sort_values("quarter", key=lambda s: s.map(A._qkey)) if rows else pd.DataFrame()

    # ---- flags
    if comp["missing"]:
        flags.append(f"Missing quarters: {', '.join(comp['missing'])}")
    if comp["interpolated"]:
        flags.append(f"Synthetic (interpolated) quarters, not observations: {', '.join(comp['interpolated'])}")
    if comp["duplicates"]:
        flags.append(f"Duplicate quarters: {', '.join(comp['duplicates'])}")
    if not df.empty:
        if (~df["aligned"]).any():
            flags.append(f"Misaligned grids vs reference: {', '.join(df.loc[~df['aligned'], 'file'])}")
        if df["crs"].nunique() > 1:
            flags.append(f"Multiple CRSs: {sorted(df['crs'].unique())}")
        if any(r["geographic"] for r in recs):
            flags.append("Geographic CRS (degrees): pixels are not a true 10 m grid; reproject to UTM before blocking")
        px = [r["pixel_m"][0] for r in recs]
        if max(abs(p - expected_px) for p in px) > 1.0:
            flags.append(f"Pixel size deviates from {expected_px} m (range {min(px):.1f}–{max(px):.1f} m)")
        band_sets = df["bands"].unique()
        if len(band_sets) > 1:
            flags.append(f"Band names differ across files: {list(band_sets)}")
        if list(recs[0]["bands"]) != expected_bands:
            flags.append(f"Band names {recs[0]['bands']} != expected {expected_bands} (check descriptions)")
        b = set(recs[0]["bands"])
        if not {"B11", "B12", "SWIR1", "SWIR2"} & b:
            flags.append("No SWIR bands (B11/B12): re-export recommended")
        if "SAR_VH" not in b and "VH" not in b:
            flags.append("No SAR VH band: re-export recommended")
        if df["ndvi_eq_-1"].fillna(0).max() > 0.01:
            flags.append(f"NDVI == -1 on >1% of pixels in {int((df['ndvi_eq_-1'] > 0.01).sum())} files (v1 fill bug)")
        if df["ndvi_out_of_range"].fillna(0).max() > 0:
            flags.append("NDVI outside [-1, 1] present")
        low_sar = df[df["sar_vv_valid"].fillna(0) < 0.5]
        if len(low_sar):
            flags.append(f"SAR VV valid <50% in {len(low_sar)}/{len(df)} quarters: {', '.join(low_sar['quarter'])}")
        low_opt = df[df["optical_valid"].fillna(0) < 0.5]
        if len(low_opt):
            flags.append(f"Optical valid <50% in {len(low_opt)}/{len(df)} quarters: {', '.join(low_opt['quarter'])}")
        if df["optical_scale"].nunique() > 1 or df["sar_scale"].nunique() > 1:
            flags.append("Inconsistent value scale across files (optical or SAR)")

    ev = A.quarter_of(landfall)
    pre = [k for k in comp["present"] if A._qkey(k) < A._qkey(ev)]
    post = [k for k in comp["present"] if A._qkey(k) > A._qkey(ev)]

    md = [f"## Source `{src['name']}` ({src['site']})", "",
          f"Directory: `{src['dir']}`", "",
          "### 1. Completeness",
          f"- Present: {len(comp['present'])}/{len(calendar)} quarters",
          f"- Missing: {', '.join(comp['missing']) or 'none'}",
          f"- Interpolated (synthetic): {', '.join(comp['interpolated']) or 'none'}",
          f"- Separate mask files: {', '.join(comp['masks']) or 'none'}", ""]
    if recs:
        r0 = recs[0]
        md += ["### 2. Geometry",
               f"- Reference grid: CRS `{ref[0]}`, {ref[1]}×{ref[2]} px, transform `{ref[3]}`",
               f"- Pixel size ≈ {r0['pixel_m'][0]:.2f} × {r0['pixel_m'][1]:.2f} m; bounds `{r0['bounds']}`",
               f"- Files aligned to reference: {int(df['aligned'].sum())}/{len(df)}", "",
               "### 3. Bands",
               f"- {r0['count']} bands, dtype `{r0['dtype']}`, nodata `{r0['nodata']}`: {', '.join(r0['bands'])}", "",
               "### 4–5. Value ranges and coverage (per quarter)", "",
               "| Quarter | Phase | Optical valid | SAR VV valid | NDVI median | NDVI = −1 | Optical scale | SAR scale |",
               "|---|---|---|---|---|---|---|---|"]
        for _, x in df.iterrows():
            nd = "—" if pd.isna(x["ndvi_median"]) else f"{x['ndvi_median']:.3f}"
            tag = " (interp)" if x["interpolated"] else ""
            md.append(f"| {x['quarter']}{tag} | {x['phase']} | {pct(x['optical_valid'])} | {pct(x['sar_vv_valid'])} "
                      f"| {nd} | {pct(x['ndvi_eq_-1'])} | {x['optical_scale']} | {x['sar_scale']} |")
        md += ["", "Per-band ranges (first file): ", "",
               "| Band | min | p1 | median | p99 | max | NaN | suspect fills |", "|---|---|---|---|---|---|---|---|"]
        for b, s in r0["stats"].items():
            f = lambda k: f"{s[k]:.4g}" if k in s else "—"  # noqa: E731
            md.append(f"| {b} | {f('min')} | {f('p1')} | {f('median')} | {f('p99')} | {f('max')} "
                      f"| {pct(s['nan_frac'])} | {s['fills'] or ''} |")
    md += ["", "### 6. Event timing",
           f"- Landfall {landfall.isoformat()} → event quarter **{ev}**",
           f"- Pre-event quarters available: {len(pre)} ({pre[0] if pre else '—'} … {pre[-1] if pre else '—'})",
           f"- Post-event quarters available: {len(post)}", "",
           "### Flags", *([f"- ⚠️ {f}" for f in flags] or ["- none"]), ""]
    summary = {"source": src["name"], "completeness": comp, "flags": flags,
               "grid": ref, "bounds": recs[0]["bounds"] if recs else None, "crs": recs[0]["crs"] if recs else None}
    return "\n".join(md), df, summary


def compare_mississippi(summaries: dict) -> list[str]:
    a, b = summaries.get("mississippi_v1"), summaries.get("mississippi_v2")
    if not (a and b and a["bounds"] and b["bounds"]):
        return []
    from rasterio.warp import transform_bounds
    bb = [transform_bounds(s["crs"], "EPSG:4326", *s["bounds"]) for s in (a, b)]
    ix = max(0, min(bb[0][2], bb[1][2]) - max(bb[0][0], bb[1][0])) * max(0, min(bb[0][3], bb[1][3]) - max(bb[0][1], bb[1][1]))
    area = lambda x: (x[2] - x[0]) * (x[3] - x[1])  # noqa: E731
    iou = ix / (area(bb[0]) + area(bb[1]) - ix)
    c = [((x[0] + x[2]) / 2, (x[1] + x[3]) / 2) for x in bb]
    return ["## Mississippi v1 vs v2", "",
            f"- v1 lon/lat bounds: `{tuple(round(v, 4) for v in bb[0])}` centre ({c[0][1]:.3f}, {c[0][0]:.3f})",
            f"- v2 lon/lat bounds: `{tuple(round(v, 4) for v in bb[1])}` centre ({c[1][1]:.3f}, {c[1][0]:.3f})",
            f"- Footprint IoU: {iou:.2f} ({'same AOI' if iou > 0.8 else 'DIFFERENT AOI'})",
            f"- v1 flags: {len(a['flags'])}, v2 flags: {len(b['flags'])}", ""]


def main():
    args = parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())
    calendar = A.quarter_range(cfg["calendar"]["start"], cfg["calendar"]["end"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sections, frames, summaries = [], [], {}
    for src in resolve_sources(cfg, args.source):
        if args.only and src["name"] not in args.only:
            continue
        if not src["dir"] or not Path(src["dir"]).is_dir():
            print(f"skip {src['name']}: directory not found ({src['dir']})")
            continue
        print(f"Auditing {src['name']} in {src['dir']}")
        names = [n for f in Path(src["dir"]).glob(src["glob"]) if (n := A.parse_name(f.name))]
        recs = audit_source(src, args.stride, out / "audit_cache", args.max_files)
        landfall = date.fromisoformat(str(cfg["sites"][src["site"]]["landfall"]))
        md, df, summ = summarise(src, recs, names, calendar, landfall, cfg["expected_bands"], cfg["expected_pixel_m"])
        sections.append(md)
        frames.append(df)
        summaries[src["name"]] = summ

    header = ["# EcoRewind 2.0 — Data audit", "",
              f"Generated {date.today().isoformat()} by `scripts/audit_data.py` (stride={args.stride}).",
              f"Calendar: {calendar[0]}–{calendar[-1]} ({len(calendar)} quarters).", ""]
    (out / "data_audit.md").write_text("\n".join(header + compare_mississippi(summaries) + sections))
    if frames:
        pd.concat(frames).to_csv(out / "data_audit_files.csv", index=False)
    (out / "data_audit.json").write_text(json.dumps(summaries, indent=2, default=str))
    print(f"Wrote {out / 'data_audit.md'}")


if __name__ == "__main__":
    main()
