"""Track B: HLS (Landsat 8/9 + Sentinel-2) quarterly median composites, 30 m, UTM, Fmask per pixel.

Output bands (float32): Blue Green Red NIR SWIR1 SWIR2 (HLS reflectance as stored in
Earth Engine; preflight records the scale), n_clear_obs, doy_mean, water_frac
(fraction of clear observations flagged water by Fmask; water is not masked).

    python gee/export_trackB_hls.py --dry-run | --limit 1 | (no flag: all)
"""
from common import ee_region, ee_window, mosaic_by, run, with_empty_fallback

REFL = ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]
OUT_BANDS = REFL + ["n_clear_obs", "doy_mean", "water_frac"]


def build(ee, cfg, task):
    t = cfg["tracks"]["B"]
    region = ee_region(ee, task.grid)
    start, end = ee_window(task.period)
    mask_bits = sum(1 << b for b in t["fmask_bits"])

    def prep(sensor, mapping):
        def f(img):
            fm = img.select("Fmask")
            bands = img.select(list(mapping.values()), list(mapping.keys()))
            clear = fm.bitwiseAnd(mask_bits).eq(0)
            water = fm.rightShift(t["fmask_water_bit"]).bitwiseAnd(1).rename("water").toFloat()
            doy = ee.Image.constant(ee.Date(img.get("system:time_start")).getRelative("day", "year").add(1))
            return ee.Image(bands.toFloat().addBands(doy.rename("doy").toFloat()).addBands(water)
                            .updateMask(clear).set("sensor", sensor)
                            .copyProperties(img, ["system:time_start"]))
        return f

    l30 = ee.ImageCollection(t["hls_l30"]).filterBounds(region).filterDate(start, end).map(prep("L30", t["bands_l30"]))
    s30 = ee.ImageCollection(t["hls_s30"]).filterBounds(region).filterDate(start, end).map(prep("S30", t["bands_s30"]))
    clear = with_empty_fallback(ee, mosaic_by(ee, l30.merge(s30), "sensor"), REFL + ["doy", "water"])
    nod = cfg["export"]["nodata"]
    comp = clear.select(REFL).median()
    n = clear.select("Blue").count().unmask(0).rename("n_clear_obs").toFloat()
    doy = clear.select("doy").mean().round().rename("doy_mean")
    water = clear.select("water").mean().rename("water_frac")
    img = comp.addBands(doy).addBands(water).unmask(nod, False).addBands(n).toFloat().select(OUT_BANDS)
    return img, OUT_BANDS


def extra(cfg, task):
    return {"product": [cfg["tracks"]["B"]["hls_l30"], cfg["tracks"]["B"]["hls_s30"]], "dtype": "float32"}


if __name__ == "__main__":
    run("B", build, __doc__, extra)
