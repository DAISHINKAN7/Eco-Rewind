"""Build the static data the website reads (web/public/data) from the demo export and the reports.

    python scripts/build_web_data.py --reports <drive>/reports --demo <drive>/demo --out web/public/data
    python scripts/build_web_data.py --reports reports --out web/public/data        # numbers only (no maps)

Sources, in order of preference: the CSVs in --reports (written by the Phase 4/5 scripts), else the markdown
tables in --reports (the committed copies in this repo). Maps come from the demo export (scripts/export_demo.py):
each 8-bit COG layer becomes a colourised, downsampled PNG with its 4 corner coordinates (lon/lat) for MapLibre.
Every number on the site is read from these files; nothing is typed into the frontend.
"""
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]


# ----------------------------------------------------------------------------- markdown fallback
def md_tables(path: Path):
    """[(heading, [row dicts])] for every pipe table in a markdown file."""
    if not path.exists():
        return []
    out, head, lines = [], "", path.read_text().splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("#"):
            head = ln.lstrip("#").strip()
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[-| :]+\|$", lines[i + 1]):
            cols = [c.strip() for c in ln.strip("|").split("|")]
            rows, i = [], i + 2
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip("|").split("|")]
                rows.append(dict(zip(cols, cells)))
                i += 1
            out.append((head, rows))
            continue
        i += 1
    return out


def num(s):
    if s is None:
        return None
    m = re.search(r"[-+−]?\d+(?:\.\d+)?", str(s).replace(",", "").replace("−", "-"))
    return float(m.group()) if m else None


def nums(s):
    return [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d+)?", str(s).replace("−", "-").replace(",", ""))]


def strip(s):
    return re.sub(r"[*`]", "", str(s)).strip()


def site_track(s):
    m = re.search(r"(everglades|mississippi)\s*/\s*(?:Track\s*)?([AB])", s)
    return (m.group(1), m.group(2)) if m else (None, None)


def family(m):
    return re.sub(r"_s\d+$", "", m)


# ----------------------------------------------------------------------------- sections
def verdict(rep: Path):
    rows = []
    for stat, csv in (("primary", "placebo_verdict_primary.csv"), ("lead0", "placebo_verdict_lead0.csv")):
        f = rep / csv
        if f.exists():
            import pandas as pd
            for r in pd.read_csv(f).to_dict("records"):
                rows.append({"stat": stat, "site": r["site"], "track": r["track"], "event": r["event"], "model": r["model"],
                             "event_median": r["event_median"], "event_min": r["event_min"], "placebo_p95": r["placebo_p95"],
                             "placebo_min": r["placebo_min"], "placebo_max": r["placebo_max"],
                             "frac_above": r["frac_event_above"], "coverage": r["coverage"], "pass": bool(r["PASS"]),
                             "n_event": r["n_event"], "n_placebo": r["n_placebo"]})
    if rows:
        return rows
    for head, tab in md_tables(rep / "placebo_verdict.md"):
        stat = "primary" if head.startswith("Primary") else "lead0" if head.startswith("Secondary") else None
        if not stat:
            continue
        for r in tab:
            site, track = site_track(r["Site / track"])
            em, pl = nums(r["Event median (min)"]), nums(r["Placebo p95 [range]"])
            ne, npl = nums(r["n ev / plc"])
            rows.append({"stat": stat, "site": site, "track": track, "event": r["Event"], "model": r["Model"],
                         "event_median": em[0], "event_min": em[1], "placebo_p95": pl[0], "placebo_min": pl[1],
                         "placebo_max": pl[2], "frac_above": num(r["Event folds > p95"]) / 100,
                         "coverage": num(r["Placebo coverage"]), "pass": "PASS" in r["**Verdict**"],
                         "n_event": int(ne), "n_placebo": int(npl)})
    return rows


def space(rep: Path):
    f = rep / "placebo_in_space.csv"
    if f.exists():
        import pandas as pd
        d = pd.read_csv(f).groupby(["site", "track", "event", "model", "map"]).agg(
            inland=("least_exposed_deficit", "mean"), all=("all_blocks_deficit", "mean")).reset_index()
        return d.to_dict("records")
    rows = []
    for head, tab in md_tables(rep / "placebo_verdict.md"):
        if not head.startswith("Placebo in space"):
            continue
        for r in tab:
            site, track = site_track(r["Site / track"])
            rows.append({"site": site, "track": track, "event": r["Event"], "model": r["Model"], "map": r["Map"],
                         "inland": num(r["Deficit there"]), "all": num(r["Deficit, all blocks"])})
    return rows


def attribution(rep: Path):
    rows = []
    for head, tab in md_tables(rep / "attribution_spread.md"):
        m = re.match(r"(ida|irma) — (\w+) / Track ([AB]) — (.+)", head)
        if not m:
            continue
        ev, site, track, stat = m.groups()
        for r in tab:
            iv = nums(r["90 % interval"])
            rows.append({"event": ev, "site": site, "track": track, "stat": stat, "model": r["Model"],
                         "deficit": num(r["Deficit"]), "lo": iv[0] if len(iv) == 2 else None,
                         "hi": iv[1] if len(iv) == 2 else None, "total": num(r["Total (NDVI·ha)"]),
                         "placebo": r["Placebo"] if r["Placebo"] in ("pass", "fail") else None})
    return rows


def external(rep: Path):
    f = rep / "external_evidence.csv"
    if f.exists():
        import pandas as pd
        d = pd.read_csv(f).groupby(["event", "site", "track", "map", "covariate", "model"])[["rho", "lo", "hi", "blocks"]] \
            .mean().reset_index()
        return d.to_dict("records")
    rows = []
    for head, tab in md_tables(rep / "external_evidence.md"):
        m = re.match(r"(ida|irma) — (\w+) / Track ([AB]) — (.+)", head)
        if not m:
            continue
        ev, site, track, mp = m.groups()
        for r in tab:
            for col, v in r.items():
                if col == "Model" or v in ("—", ""):
                    continue
                x = nums(v)
                rows.append({"event": ev, "site": site, "track": track, "map": mp, "model": r["Model"],
                             "covariate": col.split(" ")[0], "rho": x[0], "lo": x[1], "hi": x[2]})
    return rows


MAIN = {"persistence", "climatology", "harmonic", "harmonic_notrend", "synth_control", "lgbm", "convlstm", "simvp",
        "ecotransformer"}


def leaderboard(rep: Path, demo: Path | None):
    if demo and (demo / "metrics" / "leaderboard.json").exists():
        d = [r for r in json.loads((demo / "metrics" / "leaderboard.json").read_text()) if r["family"] in MAIN]
        out = {}
        for r in d:
            k = (r["site"], r["track"], r["family"])
            out.setdefault(k, {"site": r["site"], "track": r["track"], "model": r["family"]})[r["channel"]] = r["r2"]
            if r["channel"] == "NDVI":
                out[k].update(rmse=r["rmse"], coverage=r["coverage"])
        return list(out.values())
    rows = {}
    for f in ("phase2_baselines_v3_summary.md", "phase3_core_v1_irmaB_summary.md", "phase3_core_v1_idaA_summary.md"):
        for head, tab in md_tables(rep / f):
            site, track = site_track(head)
            if not site or "Model" not in (tab[0] if tab else {}) or "NDVI R²" not in tab[0]:
                continue
            for r in tab:
                fam = family(r["Model"])
                k = (site, track, fam)
                e = rows.setdefault(k, {"site": site, "track": track, "model": fam, "_n": 0, "NDVI": 0, "NDMI": 0,
                                        "NDWI": 0, "rmse": 0, "coverage": 0, "width": 0, "seeds": []})
                e["_n"] += 1
                e["seeds"].append(num(r["NDVI R²"]))
                for col, key in (("NDVI R²", "NDVI"), ("NDMI R²", "NDMI"), ("NDWI R²", "NDWI"), ("NDVI RMSE", "rmse"),
                                 ("90% coverage (NDVI)", "coverage"), ("width (NDVI)", "width")):
                    e[key] += num(r[col])
    out = []
    for e in rows.values():
        n = e.pop("_n")
        for key in ("NDVI", "NDMI", "NDWI", "rmse", "coverage", "width"):
            e[key] = round(e[key] / n, 4)
        out.append(e)
    return out


def phase5(rep: Path):
    f = rep / "phase5_models.csv"
    if f.exists():
        import pandas as pd
        return json.loads(pd.read_csv(f).to_json(orient="records"))
    rows = []
    for head, tab in md_tables(rep / "phase5_tables.md"):
        site, track = site_track(head)
        if not site:
            continue
        for r in tab:
            rows.append({"site": site, "track": track, "label": r["Model"], "val_r2": num(r["Val R²"]),
                         "test_r2": num(r["Test R²"]), "minutes": num(r["GPU min"])})
    return rows


def carbon(rep: Path):
    rows, verified = [], "UNVERIFIED" not in (rep / "carbon_illustrative.md").read_text() \
        if (rep / "carbon_illustrative.md").exists() else False
    for _, tab in md_tables(rep / "carbon_illustrative.md"):
        for r in tab:
            site, track = site_track(r["Site / track"])
            lo_hi = nums(r["t C (low–high)"])
            rows.append({"site": site, "track": track, "event": r["Event"], "model": r["Model"],
                         "deficit": num(r["Deficit"]), "relative_loss": num(r["Relative loss"]) / 100,
                         "area_ha": num(r["Area (ha)"]), "tC_low": lo_hi[0] if lo_hi else None,
                         "tC_high": lo_hi[1] if len(lo_hi) > 1 else None})
    return {"verified": verified, "rows": rows}


def slim_json(text: str, nd: int = 3) -> str:
    """Round every float in a JSON document to `nd` decimals and drop whitespace."""
    def rnd(o):
        if isinstance(o, float):
            return round(o, nd)
        if isinstance(o, list):
            return [rnd(x) for x in o]
        if isinstance(o, dict):
            return {k: rnd(v) for k, v in o.items()}
        return o
    return json.dumps(rnd(json.loads(text)), separators=(",", ":"), allow_nan=False)


def compute(rep: Path):
    import csv
    f = rep / "compute_log.csv"
    if not f.exists():
        f = REPO / "reports" / "compute_log.csv"          # the log is committed with the code
    if not f.exists():
        return []
    with open(f) as fh:
        r = list(csv.reader(fh))
    return [dict(zip(["date", "platform", "hardware", "task", "hours", "units", "note"], x + [""] * 7)) for x in r if x and x[0] != "date"]


# ----------------------------------------------------------------------------- rasters
CMAPS = {
    "ndvi": [(0, (120, 72, 36)), (0.35, (200, 170, 90)), (0.6, (110, 170, 80)), (1, (20, 95, 50))],
    "deficit": [(0, (38, 70, 83)), (0.35, (42, 157, 143)), (0.5, (240, 240, 230)), (0.65, (244, 162, 97)),
                (0.85, (231, 111, 81)), (1, (155, 34, 38))],
    "width": [(0, (13, 8, 135)), (0.5, (204, 71, 120)), (1, (240, 249, 33))],
}


def colourise(u8, kind):
    stops = CMAPS[kind]
    v = u8.astype("float32") / 254
    rgb = np.zeros((*u8.shape, 4), "uint8")
    xs = [s[0] for s in stops]
    for ch in range(3):
        rgb[..., ch] = np.interp(v, xs, [s[1][ch] for s in stops]).astype("uint8")
    alpha = np.where(u8 == 255, 0, 235)
    if kind == "deficit":                                     # fade near-zero deficits so the basemap shows
        alpha = np.where(u8 == 255, 0, np.clip(np.abs(v - 0.5) * 2 * 255 * 2.2, 40, 235))
    rgb[..., 3] = alpha.astype("uint8")
    return rgb


def corners(transform, crs, shape):
    from pyproj import Transformer
    a, b, c, d, e, f = transform[:6]
    H, W = shape
    pts = [(0, 0), (W, 0), (W, H), (0, H)]
    tr = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    return [list(tr.transform(c + a * x + b * y, f + d * x + e * y)) for x, y in pts]


def rasters(demo: Path, out: Path, max_px: int):
    import rasterio
    from PIL import Image
    man = json.loads((demo / "manifest.json").read_text())
    index = {}
    for st, info in man["sites"].items():
        src = demo / "layers" / st
        if not src.exists():
            continue
        coords = corners(info["transform"], info["crs"], info["shape"])
        entry = {"coordinates": coords, "shape": info["shape"], "keys": info["keys"], "models": info["models"], "cutoffs": info["cutoffs"],
                 "layers": {}}
        for f in sorted(src.rglob("*.tif")):
            rel = f.relative_to(src).with_suffix(".png")
            with rasterio.open(f) as ds:
                scale = max(1, int(np.ceil(max(ds.height, ds.width) / max_px)))
                a = ds.read(out_shape=(ds.count, ds.height // scale, ds.width // scale),
                            resampling=rasterio.enums.Resampling.nearest)
            name = rel.name
            if name.startswith("obs_rgb"):
                img = Image.fromarray(np.moveaxis(a, 0, -1))
            else:
                kind = "ndvi" if "ndvi" in name else "deficit" if name.startswith("deficit") else "width"
                img = Image.fromarray(colourise(a[0], kind), "RGBA")
            dst = out / "layers" / st / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            img.save(dst, optimize=True)
            entry["layers"][str(rel)] = True
        index[st] = entry
        print(f"{st}: {len(entry['layers'])} layers", flush=True)
    return index


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", default=str(REPO / "reports"))
    ap.add_argument("--demo")
    ap.add_argument("--lab", help="folder written by scripts/export_lab_model.py")
    ap.add_argument("--out", default=str(REPO / "web/public/data"))
    ap.add_argument("--max-px", type=int, default=1100)
    ap.add_argument("--no-rasters", action="store_true")
    a = ap.parse_args()
    rep, out = Path(a.reports), Path(a.out)
    demo = Path(a.demo) if a.demo else None
    out.mkdir(parents=True, exist_ok=True)
    reg = json.loads((REPO / "configs/model_registry.json").read_text())
    p5 = phase5(rep)
    done_variants = {re.sub(r"_s\d+$", "", r.get("model", "")) for r in p5 if r.get("model")}
    for m in reg:                                             # registry status from what actually ran
        if m["status"] == "planned" and m["id"] in done_variants:
            m["status"] = "done"
    data = {
        "generated": subprocess.run(["git", "-C", str(REPO), "log", "-1", "--format=%h %cs"], capture_output=True,
                                    text=True).stdout.strip(),
        "registry": reg, "leaderboard": leaderboard(rep, demo), "verdict": verdict(rep), "space": space(rep),
        "attribution": attribution(rep), "external": external(rep), "phase5": p5, "carbon": carbon(rep),
        "compute": compute(rep),
    }
    (out / "results.json").write_text(json.dumps(data, default=float).replace("NaN", "null"))
    print({k: len(v) if isinstance(v, list) else "…" for k, v in data.items()})
    if demo:
        if (demo / "training").exists():
            shutil.copytree(demo / "training", out / "training", dirs_exist_ok=True)
        for f in sorted((demo / "pixels").glob("*.json")):     # 3-decimal rounding: ~3x smaller downloads
            (out / "pixels").mkdir(parents=True, exist_ok=True)
            (out / "pixels" / f.name).write_text(slim_json(f.read_text()))
        if not a.no_rasters and (demo / "manifest.json").exists():
            (out / "maps.json").write_text(json.dumps(rasters(demo, out, a.max_px)))
    if a.lab:
        shutil.copytree(a.lab, out / "lab", dirs_exist_ok=True, ignore=shutil.ignore_patterns("_cache", "*.pt"))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
