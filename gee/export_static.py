"""Static layers per site per track grid: elevation and WorldCover class.

Output bands (float32): elevation_m (Copernicus GLO-30, bilinear), worldcover (class code; mode
when aggregated to 30 m). Distance to coast is computed locally in Phase 1 from the WorldCover
water class (an Earth Engine distance kernel of 30 km at 10 m exceeds EE's 512-pixel kernel limit). WorldCover is 2021, i.e. after Irma: use it only to exclude
permanent water / built-up / cropland, and report that limitation.

    python gee/export_static.py --dry-run | (no flag: all)
"""
from common import ee_region, run

OUT_BANDS = ["elevation_m", "worldcover"]


def build(ee, cfg, task):
    st = cfg["static"]
    region = ee_region(ee, task.grid).buffer(1000)
    g10 = [10, 0, task.grid.xmin, 0, -10, task.grid.ymax]
    dem_col = ee.ImageCollection(st["dem"]).filterBounds(region)
    dem = dem_col.select("DEM").mosaic().setDefaultProjection(dem_col.first().projection()).resample("bilinear")
    wc = ee.ImageCollection(st["worldcover"]).first().select("Map")
    if task.track == "B":
        wc = (wc.setDefaultProjection(task.grid.crs, g10)
              .reduceResolution(ee.Reducer.mode(), maxPixels=64)
              .reproject(task.grid.crs, task.grid.crs_transform))
    img = dem.rename("elevation_m").addBands(wc.rename("worldcover"))
    return img.toFloat().unmask(cfg["export"]["nodata"], False), OUT_BANDS


def extra(cfg, task):
    return {"product": [cfg["static"]["dem"], cfg["static"]["worldcover"]], "dtype": "float32"}


if __name__ == "__main__":
    run("static", build, __doc__, extra)
