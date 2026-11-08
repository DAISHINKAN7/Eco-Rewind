import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ecorewind.data import audit as A  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BANDS = ["Blue", "Green", "Red", "NIR", "NDVI", "NDWI", "SAR_VV"]


def write_tif(path, *, shift=0.0, ndvi_fill=False, sar_zero=False, nan_frac=0.0, seed=0):
    rng = np.random.default_rng(seed)
    h = w = 64
    a = rng.uniform(0.01, 0.3, (7, h, w)).astype("float32")
    a[4] = rng.uniform(0.2, 0.6, (h, w))
    a[5] = rng.uniform(-0.5, 0.1, (h, w))
    a[6] = rng.uniform(-20, -5, (h, w))
    if ndvi_fill:
        a[4, :32] = -1.0
    if sar_zero:
        a[6] = 0
    if nan_frac:
        a[:4, : int(h * nan_frac)] = np.nan
    with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=7, dtype="float32",
                       crs="EPSG:32615", transform=from_origin(780000 + shift, 3265000, 10, 10)) as ds:
        ds.write(a)
        for i, b in enumerate(BANDS, 1):
            ds.set_band_description(i, b)


def test_parse_name():
    n = A.parse_name("Everglades_2017_Q2_AprJun_INTERPOLATED.tif")
    assert (n.site, n.version, n.key, n.is_interpolated) == ("everglades", "v1", "2017Q2", True)
    n = A.parse_name("Mississippi_v2_2021_Q3_JulSep.tif")
    assert (n.version, n.key, n.is_mask) == ("v2", "2021Q3", False)
    assert A.parse_name("Everglades_2016_Q2_AprJun_mask.tif").is_mask
    assert A.parse_name("qc_report.json") is None


def test_calendar_and_phase():
    cal = A.quarter_range("2016Q1", "2023Q4")
    assert len(cal) == 32 and cal[0] == "2016Q1" and cal[-1] == "2023Q4"
    ida = date(2021, 8, 29)
    assert A.quarter_of(ida) == "2021Q3"
    assert [A.event_phase(k, ida) for k in ("2021Q2", "2021Q3", "2021Q4")] == ["pre", "event", "post"]


def test_completeness_flags_missing_and_interpolated():
    names = [A.parse_name(f"X_{k[:4]}_Q{k[-1]}_AprJun.tif") for k in ("2016Q1", "2016Q3")]
    names.append(A.parse_name("X_2016_Q4_OctDec_INTERPOLATED.tif"))
    c = A.completeness(names, A.quarter_range("2016Q1", "2016Q4"))
    assert c["missing"] == ["2016Q2"] and c["interpolated"] == ["2016Q4"]


def test_inspect_detects_fill_sar_and_nan(tmp_path):
    p = tmp_path / "S_2016_Q1_JanMar.tif"
    write_tif(p, ndvi_fill=True, sar_zero=True, nan_frac=0.25)
    r = A.inspect_file(p)
    assert r["bands"] == BANDS
    assert r["pixel_m"] == (10.0, 10.0)
    assert r["coverage"]["ndvi_eq_minus1"] == pytest.approx(0.5)
    assert r["coverage"]["SAR_VV_valid"] == 0
    assert r["coverage"]["optical_valid"] == pytest.approx(0.75)
    assert r["scale"] == {"optical": "0-1 (reflectance)", "SAR_VV": "zero-filled"}


def test_alignment_catches_shifted_file(tmp_path):
    recs = []
    for i, s in enumerate([0, 0, 10]):
        p = tmp_path / f"S_2016_Q{i + 1}_X.tif"
        write_tif(p, shift=s)
        recs.append(A.inspect_file(p, stride=4))
    ok, _ = A.check_alignment(recs)
    assert list(ok.values()) == [True, True, False]


def test_cli_end_to_end(tmp_path):
    d = tmp_path / "ms"
    d.mkdir()
    for k in A.quarter_range("2016Q1", "2016Q4"):
        if k != "2016Q2":
            write_tif(d / f"Mississippi_v2_{k[:4]}_Q{k[-1]}_X.tif", seed=int(k[-1]))
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "drive_root: /nope\ncalendar: {start: 2016Q1, end: 2016Q4}\n"
        "sources:\n  - {name: mississippi_v2, site: mississippi, path: null, glob: 'Mississippi_v2_*.tif'}\n"
        "sites: {mississippi: {event: Ida, landfall: 2016-08-29}}\n"
        f"expected_bands: {BANDS}\nexpected_pixel_m: 10\n"
    )
    out = tmp_path / "rep"
    subprocess.run([sys.executable, str(ROOT / "scripts/audit_data.py"), "--config", str(cfg),
                    "--source", f"mississippi_v2={d}", "--out", str(out)], check=True)
    md = (out / "data_audit.md").read_text()
    assert "Missing: 2016Q2" in md and "event quarter **2016Q3**" in md
    assert "No SWIR" in md and "No SAR VH" in md
    summ = json.loads((out / "data_audit.json").read_text())
    assert summ["mississippi_v2"]["completeness"]["missing"] == ["2016Q2"]
    assert len(list((out / "audit_cache/mississippi_v2").glob("*.json"))) == 3
