"""Sentinel-1 quarterly composites on both track grids (fixes the v1 SAR export bug).

Filter: instrumentMode == IW, VV and VH present, BOTH orbit directions, no relative-orbit
or platform filter. Mean in linear power per pixel, then back to dB.
Output bands (int16, dB x 100, i.e. multiply by 0.01): VV, VH, VH_VV_ratio (dB difference =
linear ratio); n_s1_obs (count, unscaled). Quarters before S1A (Oct 2014) export with n_s1_obs = 0 and SAR nodata.

    python gee/export_s1.py --dry-run | --limit 1 | (no flag: all)
"""
from common import ee_region, ee_window, mosaic_by, run, with_empty_fallback

OUT_BANDS = ["VV", "VH", "VH_VV_ratio", "n_s1_obs"]


def s1_collection(ee, cfg, region, start, end):
    s = cfg["s1"]
    col = (ee.ImageCollection(s["collection"]).filterBounds(region).filterDate(start, end)
           .filter(ee.Filter.eq("instrumentMode", s["instrument_mode"])))
    for pol in s["polarisations"]:
        col = col.filter(ee.Filter.listContains("transmitterReceiverPolarisation", pol))
    return col


def build(ee, cfg, task):
    s = cfg["s1"]
    region = ee_region(ee, task.grid)
    start, end = ee_window(task.period)

    def to_linear(img):
        lin = ee.Image(10).pow(img.select(s["polarisations"]).divide(10))
        if s.get("focal_median_3x3"):
            lin = lin.focalMedian(1, "square", "pixels")
        return ee.Image(lin.copyProperties(img, ["system:time_start", "orbitProperties_pass"]))

    col = mosaic_by(ee, s1_collection(ee, cfg, region, start, end).map(to_linear), "orbitProperties_pass")
    col = with_empty_fallback(ee, col, s["polarisations"])
    mean = col.mean()
    n = col.select("VV").count().unmask(0).toFloat()
    if task.track == "B":   # aggregate 10 m linear power to the 30 m grid (mean), before dB
        g10 = [10, 0, task.grid.xmin, 0, -10, task.grid.ymax]
        agg = lambda im: (im.setDefaultProjection(task.grid.crs, g10)  # noqa: E731
                          .reduceResolution(ee.Reducer.mean(), maxPixels=64)
                          .reproject(task.grid.crs, task.grid.crs_transform))
        mean, n = agg(mean), agg(n).round()
    db = mean.log10().multiply(10)
    vv, vh = db.select("VV"), db.select("VH")
    nod = cfg["export"]["nodata"]
    sar = vv.addBands(vh).addBands(vh.subtract(vv).rename("VH_VV_ratio")).multiply(100).round()
    img = sar.unmask(nod, False).addBands(n.rename("n_s1_obs")).toInt16().select(OUT_BANDS)
    return img, OUT_BANDS


def extra(cfg, task):
    s = cfg["s1"]
    return {"product": s["collection"], "dtype": "int16", "units": "dB", "scale_factor": 0.01,
            "filter": f"instrumentMode={s['instrument_mode']}, pols={s['polarisations']}, both orbits",
            "focal_median_3x3": s.get("focal_median_3x3", False)}


if __name__ == "__main__":
    run("S1", build, __doc__, extra)
