"""Track A: Sentinel-2 quarterly median composites, 10 m, UTM, per-pixel Cloud Score+ masking.

Output bands (int16): Blue Green Red NIR SWIR1 SWIR2 (DN, reflectance = DN * 1e-4),
n_clear_obs, doy_mean. Masked pixels = nodata (-32768); n_clear_obs is 0 there.

    python gee/export_trackA_s2.py --dry-run
    python gee/export_trackA_s2.py --limit 1       # one test file first
    python gee/export_trackA_s2.py                 # everything (skips already-submitted)
"""
import json

from common import S2_PRODUCT_FILE, ee_region, ee_window, mosaic_by, run, with_empty_fallback

OUT_BANDS = ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2", "n_clear_obs", "doy_mean"]


def s2_product(cfg, site: str) -> str:
    """Collection id for the whole series of a site. 'auto' must be resolved by preflight first."""
    t = cfg["tracks"]["A"]
    choice = t["s2_product"][site]
    if choice == "auto":
        if not S2_PRODUCT_FILE.exists():
            raise SystemExit("s2_product is 'auto': run gee/preflight.py first (it writes reports/exports/s2_product.json)")
        choice = json.loads(S2_PRODUCT_FILE.read_text())[site]
    return {"sr": t["s2_sr"], "toa": t["s2_toa"]}.get(choice, choice)


def build(ee, cfg, task):
    t = cfg["tracks"]["A"]
    src, out = list(t["bands"].values()), list(t["bands"].keys())
    region = ee_region(ee, task.grid)
    start, end = ee_window(task.period)
    csp = ee.ImageCollection(t["cloud_score_plus"])
    col = (ee.ImageCollection(s2_product(cfg, task.site)).filterBounds(region).filterDate(start, end)
           .linkCollection(csp, [t["cs_band"]]))

    def prep(img):
        # toFloat: every image in the collection must share band types (the empty-quarter placeholder is float)
        bands = img.select(src, out).toFloat().resample("bilinear")   # B11/B12 20 m -> 10 m; 10 m bands unchanged on-grid
        clear = img.select(t["cs_band"]).gte(t["cs_threshold"]).And(bands.reduce(ee.Reducer.min()).gt(0))
        doy = ee.Image.constant(ee.Date(img.get("system:time_start")).getRelative("day", "year").add(1))
        return ee.Image(bands.addBands(doy.rename("doy").toFloat()).updateMask(clear)
                        .copyProperties(img, ["system:time_start", "SPACECRAFT_NAME"]))

    clear = with_empty_fallback(ee, mosaic_by(ee, col.map(prep), "SPACECRAFT_NAME"), out + ["doy"])
    nod = cfg["export"]["nodata"]
    comp = clear.select(out).median().round()
    n = clear.select("Blue").count().unmask(0).rename("n_clear_obs")
    doy = clear.select("doy").mean().round().rename("doy_mean")
    img = comp.addBands(doy).unmask(nod, False).addBands(n).toInt16().select(OUT_BANDS)
    return img, OUT_BANDS


def extra(cfg, task):
    return {"product": s2_product(cfg, task.site), "dtype": "int16", "scale_factor": 1e-4,
            "cs_band": cfg["tracks"]["A"]["cs_band"], "cs_threshold": cfg["tracks"]["A"]["cs_threshold"]}


if __name__ == "__main__":
    run("A", build, __doc__, extra)
