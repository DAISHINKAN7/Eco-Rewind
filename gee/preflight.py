"""Phase 0 preflight: verify the Earth Engine catalogue and count scenes before any export.

For each site it checks that every collection exists and has the expected bands, then
counts per quarter: S2 SR, S2 TOA, Cloud Score+, HLS L30, HLS S30, and distinct S1 IW
VV+VH acquisitions (by date and orbit direction). It then:
  * picks the Sentinel-2 product per site (SR only if SR covers every Track A quarter about
    as well as TOA; otherwise TOA for the whole series) -> reports/exports/s2_product.json
  * applies the SAR sanity check (median S1 acquisitions per pre-2022 quarter >= min_expected_obs)
  * writes reports/gee_preflight.md

    python gee/preflight.py --project <ee-project-id>
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import date

from common import REPORTS, S2_PRODUCT_FILE, ee_init, ee_region, grid_for, load_configs, site_periods

SR_COVERAGE_RATIO = 0.9   # SR must have >= 90% of TOA scenes in every quarter to be used


def expected_bands(cfg) -> dict[str, list[str]]:
    a, b, s = cfg["tracks"]["A"], cfg["tracks"]["B"], cfg["s1"]
    return {
        a["s2_sr"]: list(a["bands"].values()),
        a["s2_toa"]: list(a["bands"].values()),
        a["cloud_score_plus"]: [a["cs_band"]],
        b["hls_l30"]: list(b["bands_l30"].values()) + ["Fmask"],
        b["hls_s30"]: list(b["bands_s30"].values()) + ["Fmask"],
        s["collection"]: s["polarisations"],
        cfg["static"]["dem"]: ["DEM"],
        cfg["static"]["worldcover"]: ["Map"],
    }


def check_catalogue(ee, cfg) -> list[dict]:
    rows = []
    for cid, need in expected_bands(cfg).items():
        try:
            col = ee.ImageCollection(cid)
            if cid == cfg["s1"]["collection"]:
                # S1_GRD mixes modes/polarisations (the first image is often HH/HV); check the subset we use
                col = col.filter(ee.Filter.eq("instrumentMode", cfg["s1"]["instrument_mode"]))
                for pol in cfg["s1"]["polarisations"]:
                    col = col.filter(ee.Filter.listContains("transmitterReceiverPolarisation", pol))
            have = col.first().bandNames().getInfo()
            miss = [b for b in need if b not in have]
            rows.append({"id": cid, "ok": not miss, "missing": miss, "bands": have})
        except Exception as e:  # noqa: BLE001
            rows.append({"id": cid, "ok": False, "missing": need, "error": str(e)[:200]})
    return rows


def counts(ee, col, windows, distinct_key: str | None = None) -> list[int]:
    """Images per window in one server call; with distinct_key, count distinct (date, key)."""
    def n(w):
        w = ee.List(w)
        sub = col.filterDate(w.get(0), w.get(1))
        if distinct_key is None:
            return sub.size()
        keys = sub.map(lambda i: i.set("_k", ee.Date(i.get("system:time_start")).format("YYYY-MM-dd")
                                       .cat(ee.String(i.get(distinct_key)))))
        return keys.aggregate_array("_k").distinct().size()
    return ee.List(windows).map(n).getInfo()


def hls_scale_probe(ee, cfg, region) -> dict:
    """Median Red over the AOI of one clear-ish HLS scene, to record the stored reflectance scale."""
    out = {}
    for key in ("hls_l30", "hls_s30"):
        col = ee.ImageCollection(cfg["tracks"]["B"][key]).filterBounds(region).filterDate("2020-01-01", "2020-04-01")
        img = col.first()
        v = img.select("B4").reduceRegion(ee.Reducer.median(), region, 30, maxPixels=1e8).get("B4").getInfo()
        out[key] = v
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project")
    p.add_argument("--site", nargs="*")
    args = p.parse_args()
    cfg = load_configs()
    ee = ee_init(cfg, args.project)
    a, b, s1 = cfg["tracks"]["A"], cfg["tracks"]["B"], cfg["s1"]

    cat = check_catalogue(ee, cfg)
    md = ["# Earth Engine preflight", "", f"Run {date.today().isoformat()}.", "", "## Catalogue", "",
          "| Collection | OK | Missing bands |", "|---|---|---|"]
    md += [f"| `{r['id']}` | {'yes' if r['ok'] else '**NO**'} | {', '.join(r['missing']) or ''} {r.get('error', '')} |"
           for r in cat]
    products, gate = {}, []
    for site in args.site or list(cfg["sites"]):
        region = ee_region(ee, grid_for(cfg, site, "A"))
        pa, pb = site_periods(cfg, site, "A"), site_periods(cfg, site, "B")
        wa = [[p.start.isoformat(), p.end.isoformat()] for p in pa]
        wb = [[p.start.isoformat(), p.end.isoformat()] for p in pb]
        sr = counts(ee, ee.ImageCollection(a["s2_sr"]).filterBounds(region), wa)
        toa = counts(ee, ee.ImageCollection(a["s2_toa"]).filterBounds(region), wa)
        csp = counts(ee, ee.ImageCollection(a["cloud_score_plus"]).filterBounds(region), wa)
        l30 = counts(ee, ee.ImageCollection(b["hls_l30"]).filterBounds(region), wb)
        s30 = counts(ee, ee.ImageCollection(b["hls_s30"]).filterBounds(region), wb)
        s1c = ee.ImageCollection(s1["collection"]).filterBounds(region).filter(
            ee.Filter.eq("instrumentMode", s1["instrument_mode"]))
        for pol in s1["polarisations"]:
            s1c = s1c.filter(ee.Filter.listContains("transmitterReceiverPolarisation", pol))
        s1n = counts(ee, s1c, wb, "orbitProperties_pass")

        sr_ok = all(t == 0 or s >= SR_COVERAGE_RATIO * t for s, t in zip(sr, toa)) and all(s > 0 for s in sr)
        products[site] = "sr" if sr_ok else "toa"
        pre22 = [n for p, n in zip(pb, s1n) if date(2015, 1, 1) <= p.start < date(2022, 1, 1)]
        s1_med = statistics.median(pre22) if pre22 else 0
        s1_pass = s1_med >= s1["min_expected_obs"]
        gate.append((site, s1_med, s1_pass))
        zero_a = [p.key for p, n in zip(pa, toa) if n == 0]

        md += ["", f"## {site}", "",
               f"- Sentinel-2 product for Track A: **{products[site].upper()}** "
               f"({'SR covers every quarter' if sr_ok else 'SR missing or thin in some quarters, so TOA for the whole series'})",
               f"- Track A quarters with 0 S2 scenes: {', '.join(zero_a) or 'none'}",
               f"- S1 IW VV+VH acquisitions per quarter 2015–2021: median {s1_med} "
               f"→ {'PASS' if s1_pass else '**FAIL: filter still wrong, stop**'}", "",
               "| Period | S2 SR | S2 TOA | CS+ | HLS L30 | HLS S30 | S1 |", "|---|---|---|---|---|---|---|"]
        a_idx = {p.key: i for i, p in enumerate(pa)}
        for j, p in enumerate(pb):
            i = a_idx.get(p.key)
            f = (lambda v: str(v[i]) if i is not None else "")  # noqa: E731
            md.append(f"| {p.key} | {f(sr)} | {f(toa)} | {f(csp)} | {l30[j]} | {s30[j]} | {s1n[j]} |")
        try:
            md.append(f"\nHLS stored scale probe (median Red, 2020Q1 first scene): {hls_scale_probe(ee, cfg, region)} "
                      "(≈0.0x → reflectance; ≈ hundreds → DN ×1e-4)")
        except Exception as e:  # noqa: BLE001
            md.append(f"\nHLS scale probe failed: {e}")

    S2_PRODUCT_FILE.parent.mkdir(parents=True, exist_ok=True)
    S2_PRODUCT_FILE.write_text(json.dumps(products, indent=1))
    ok = all(r["ok"] for r in cat) and all(g[2] for g in gate)
    md[4:4] = ["## Verdict", "", f"**{'GO' if ok else 'STOP'}**: catalogue "
               f"{'ok' if all(r['ok'] for r in cat) else 'has problems'}; SAR check "
               + ", ".join(f"{s} median {m} ({'pass' if g else 'fail'})" for s, m, g in gate)
               + f". S2 product per site: {products}.", ""]
    if len(set(products.values())) > 1:
        md.insert(8, "⚠️ The two sites use different S2 products; this affects cross-site comparability. Decide before exporting.\n")
    out = REPORTS / "gee_preflight.md"
    out.write_text("\n".join(md) + "\n")
    print("\n".join(md[:10]))
    print(f"\nWrote {out} and {S2_PRODUCT_FILE}")


if __name__ == "__main__":
    main()
