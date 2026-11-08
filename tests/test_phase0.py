import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "gee"))
import common  # noqa: E402
from ecorewind.data import audit_exports as X  # noqa: E402
from ecorewind.data.grid import site_grid  # noqa: E402
from ecorewind.data.periods import periods, quarter_window  # noqa: E402

CFG = common.load_configs()


@pytest.mark.parametrize("site", ["everglades", "mississippi"])
def test_grids_nest_cover_aoi_and_snap(site):
    a, b = common.grid_for(CFG, site, "A"), common.grid_for(CFG, site, "B")
    assert (a.xmin, a.ymax) == (b.xmin, b.ymax)
    assert (a.width, a.height) == (3 * b.width, 3 * b.height)
    assert a.xmin % 30 == 0 and a.ymax % 30 == 0
    s = CFG["sites"][site]
    tight = site_grid(s["bounds_lonlat"], s["crs"], 10)
    assert a.xmin <= tight.xmin - 990 and a.xmax >= tight.xmax + 990   # 1 km buffer kept
    assert a.crs == s["crs"] and a.crs_transform[0] == 10 and a.crs_transform[4] == -10


def test_event_quarter_split():
    ps = periods("2021Q2", "2021Q4", date(2021, 8, 29), 3)
    assert [p.key for p in ps] == ["2021Q2", "2021Q3_PRE", "2021Q3_POST", "2021Q4"]
    pre, post = ps[1], ps[2]
    assert (pre.start, pre.end) == (date(2021, 7, 1), date(2021, 8, 29))      # end exclusive: landfall day excluded
    assert (post.start, post.end) == (date(2021, 9, 1), date(2021, 10, 1))
    assert quarter_window("2023Q4") == (date(2023, 10, 1), date(2024, 1, 1))


def test_task_plan_counts_and_names():
    a, b = common.plan(CFG, "A"), common.plan(CFG, "B")
    s1, st = common.plan(CFG, "S1"), common.plan(CFG, "static")
    # Track A 2015Q3-2023Q4 = 34 quarters, event quarter -> PRE+POST = 35 per site
    assert len(a) == 70 and len(b) == 2 * 44 and len(s1) == 70 + 88 and len(st) == 4
    names = [t.file for t in a + b + s1 + st]
    assert len(names) == len(set(names))
    assert all(len(t.description) <= 100 for t in a + b + s1 + st)
    assert "everglades_A_2017Q3_PRE" in names and "everglades_A_2017Q3" not in names
    assert "mississippi_B_S1_2013Q2" in names
    for t in a + b + s1 + st:
        assert X.parse(t.file + ".tif") is not None


def test_ndvi_never_minus_one_on_fills():
    red = np.array([0, 100, 500, 0.0])
    nir = np.array([0, 300, 500, 400.0])
    valid = (red > 0) & (nir > 0)
    nd = X.ndvi(red, nir, valid)
    assert np.isnan(nd[0]) and np.isnan(nd[3])          # fills -> NaN, not -1 / +1
    assert nd[1] == pytest.approx(0.5) and nd[2] == 0


def _write(path, bands, arrs, res, x0=509160, y0=2809200, crs="EPSG:32617", dtype="int16", nodata=-32768):
    h, w = arrs[0].shape
    with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=len(bands), dtype=dtype,
                       crs=crs, transform=from_origin(x0, y0, res, res), nodata=nodata) as ds:
        ds.write(np.stack(arrs).astype(dtype))
        for i, b in enumerate(bands, 1):
            ds.set_band_description(i, b)


def _optical(path, res, n, dtype="int16"):
    rng = np.random.default_rng(0)
    h = 30 // (res // 10)
    refl = [rng.integers(200, 3000, (h, h)) for _ in range(6)]
    refl[3] = refl[2] + 1000                                   # NIR > Red -> NDVI > 0
    _write(path, ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2", "n_clear_obs", "doy_mean"],
           refl + [np.full((h, h), n), np.full((h, h), 120)], res, dtype=dtype)


def _s1(path, res, n):
    h = 30 // (res // 10)
    vv, vh = np.full((h, h), -1200), np.full((h, h), -1900)       # dB x 100, int16
    if n == 0:
        vv[:], vh[:] = -32768, -32768
    _write(path, ["VV", "VH", "VH_VV_ratio", "n_s1_obs"], [vv, vh, vh - vv, np.full((h, h), n)], res)


def test_audit_exports_gate_end_to_end(tmp_path):
    cfgd = tmp_path / "cfg"
    cfgd.mkdir()
    (cfgd / "sites.yaml").write_text("sites: {everglades: {bounds_lonlat: [0,0,1,1], crs: EPSG:32617}}\n")
    (cfgd / "events.yaml").write_text("post_offset_days: 3\nevents: {irma: {site: everglades, landfall: 2017-09-10}}\n")
    (cfgd / "tracks.yaml").write_text("tracks: {A: {res: 10, start: 2017Q2, end: 2017Q4}, B: {res: 30, start: 2017Q2, end: 2017Q4}}\n")
    d = tmp_path / "exp"
    d.mkdir()
    keys = ["2017Q2", "2017Q3_PRE", "2017Q3_POST", "2017Q4"]
    for tr, res in (("A", 10), ("B", 30)):
        for k in keys:
            _optical(d / f"everglades_{tr}_{k}.tif", res, 5, "int16" if tr == "A" else "float32")
            _s1(d / f"everglades_{tr}_S1_{k}.tif", res, 0 if k == "2017Q4" else 8)
    out = tmp_path / "rep"
    subprocess.run([sys.executable, str(ROOT / "scripts/audit_exports.py"), "--dir", str(d), "--config-dir", str(cfgd),
                    "--manifest-dir", str(tmp_path), "--out", str(out)], check=True)
    md = (out / "data_audit_v2.md").read_text()
    assert "Gate: **FAIL**" in md                       # SAR valid in 3/4 periods < 80%
    assert "| everglades/A: SAR valid in ≥80% of periods from 2015Q1 | ❌ | 3/4 periods |" in md
    assert "| everglades: Track B grid nests in Track A (3×3) | ✅ |" in md
    assert "| everglades/A/optical: all 4 periods present | ✅ |" in md
    assert "| everglades/A: no NDVI = −1 / out-of-range artefacts | ✅ |" in md
    assert "| 2017Q2 | 5 | 100.0% |" in md and "| 8 | 100.0% | -12.0 |" in md   # S1 rescaled from dB x 100


def test_negative_reflectance_never_gives_out_of_range_ndvi(tmp_path):
    # HLS has small negative reflectances over dark water; red=-0.01, nir=0.02 would give NDVI = 3
    p = tmp_path / "everglades_B_2013Q2.tif"
    bands = ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2", "n_clear_obs", "doy_mean", "water_frac"]
    a = [np.full((10, 10), 0.05) for _ in bands]
    a[2][:], a[3][:], a[6][:] = -0.01, 0.02, 3
    _write(p, bands, a, 30, dtype="float32")
    r = X.inspect(p)
    assert r["ndvi_out_of_range"] == 0 and r["optical_valid"] == 1.0
