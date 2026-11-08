import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_deep_checks_catch_planted_faults(tmp_path):
    exp, out = tmp_path / "exp", tmp_path / "out"
    exp.mkdir()
    subprocess.run([sys.executable, str(ROOT / "tests/fixtures/make_fake_exports.py"),
                    str(ROOT / "scripts/deep_checks.py"), str(exp)], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/deep_checks.py"), "--dir", str(exp), "--out", str(out),
                    "--no-figures"], check=True)
    md = (out / "deep_checks.md").read_text()
    assert "| 1 Inventory: all expected files present | ❌ FAIL | 319/320; missing: mississippi_B_S1_2020Q1.tif |" in md
    assert "everglades_B_2016Q4 (1).tif" in md
    assert "| 6 Date windows: doy_mean inside each compositing window | ❌ FAIL | everglades_A_2017Q3_POST.tif" in md
    assert "| 2 Grid: Track B nests exactly in Track A (3×3) | ✅ PASS |" in md
    assert "| 4 Values: no NDVI/NDWI/NDMI = ±1 fill artefacts | ✅ PASS |" in md     # zero bands -> invalid, not -1
    assert "| everglades_A_2017Q3_PRE.tif | 182.0–252.0 |" in md                   # Jul 1 - Sep 9, 2017
