"""Write a complete, tiny fake Phase 0 export (all 320 files) with planted faults, for tests."""
import sys, importlib.util, numpy as np, rasterio
from rasterio.transform import from_origin
from datetime import timedelta
spec = importlib.util.spec_from_file_location("dc", sys.argv[1]); dc = importlib.util.module_from_spec(spec); spec.loader.exec_module(dc)
out = sys.argv[2]
ORIG = {"everglades": (509160, 2809200), "mississippi": (711930, 3271230)}
rng = np.random.default_rng(0)
def w(path, arrs, res, site, dtype, names):
    x0, y0 = ORIG[site]
    with rasterio.open(path, "w", driver="GTiff", height=arrs[0].shape[0], width=arrs[0].shape[1], count=len(arrs),
                       dtype=dtype, crs=dc.SITES[site]["crs"], transform=from_origin(x0, y0, res, res), nodata=-32768) as ds:
        ds.write(np.stack(arrs).astype(dtype))
        for i, n in enumerate(names, 1): ds.set_band_description(i, n)
for f, (kind, site, tr, key, win) in dc.expected_files().items():
    NA = int(sys.argv[sys.argv.index("--n-a") + 1]) if "--n-a" in sys.argv else 30
    n = NA if tr == "A" else NA // 3; res = dc.TRACKS[tr]["res"]
    if kind == "optical":
        base = rng.uniform(0.02, 0.05, (n, n)); nir = base + 0.15 + rng.normal(0, 0.01, (n, n))
        refl = [base, base*1.4, base*1.2, nir, nir*0.5, nir*0.25]
        if tr == "B":   # B = A aggregated -> ndvi correlated
            refl = [r for r in refl]
        sc = 1e4 if tr == "A" else 1.0
        mid = win[0] + (win[1] - win[0]) / 2
        doy = np.full((n, n), mid.timetuple().tm_yday)
        if f == "everglades_A_2017Q3_POST.tif": doy[:] = 200          # planted: doy outside window
        arrs = [r*sc for r in refl] + [np.full((n, n), 5), doy] + ([np.zeros((n, n))] if tr == "B" else [])
        if f == "mississippi_A_2019Q2.tif": arrs[2][:5] = 0; arrs[3][:5] = 0   # zeros -> invalid, not -1
        w(f"{out}/{f}", arrs, res, site, "int16" if tr == "A" else "float32", dc.OPT_BANDS[tr])
    elif kind == "S1":
        pre = key < "2014Q4"
        vv = np.full((n, n), -32768.0 if pre else -1200.0); vh = np.full((n, n), -32768.0 if pre else -1800.0)
        w(f"{out}/{f}", [vv, vh, np.where(pre, -32768, vh - vv), np.full((n, n), 0 if pre else 9)], res, site, "int16", dc.S1_BANDS)
    else:
        wc = np.full((n, n), 90.0); wc[:, :n//3] = 95
        w(f"{out}/{f}", [rng.uniform(-1, 3, (n, n)), wc], res, site, "float32", dc.STATIC_BANDS)
if "--clean" not in sys.argv:
    import shutil; shutil.copy(f"{out}/everglades_B_2016Q4.tif", f"{out}/everglades_B_2016Q4 (1).tif")   # planted duplicate
    import os; os.remove(f"{out}/mississippi_B_S1_2020Q1.tif")                                          # planted missing
