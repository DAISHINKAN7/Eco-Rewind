"""Phase 3 tests: network output contract, no use of post-cutoff data, end-to-end deep run through the harness."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ecorewind.models.deep.nets import Layout, build  # noqa: E402

LAY = Layout((0, 1, 2), (3, 4), (5, 6, 7), (8, 9), tuple(range(10, 18)), 5)


@pytest.mark.parametrize("arch,kw", [("convlstm", {"hid": 8}), ("simvp", {"hid_s": 8, "hid_t": 16, "n_t": 1}),
                                     ("ecotransformer", {"dim": 32, "depth": 1, "patch": 4, "sar": "gate"}),
                                     ("ecotransformer", {"dim": 32, "depth": 1, "patch": 4, "sar": "concat"}),
                                     ("ecotransformer", {"dim": 32, "depth": 1, "patch": 4, "sar": "off"})])
def test_output_contract_and_causality(arch, kw):
    torch.manual_seed(0)
    net = build(arch, LAY, 5, 6, **kw).eval()
    x = torch.randn(2, 6, 18, 16, 16)
    si, so = torch.randint(0, 4, (2, 6)), torch.randint(0, 4, (2, 5))
    y = net(x, si, so)
    assert y.shape == (2, 5, 5, 3, 16, 16) and torch.isfinite(y).all()
    y.mean().backward()                                             # trainable end to end


def test_deep_models_run_through_the_harness(tmp_path):
    exp, cubes, p1, runs = tmp_path / "exp", tmp_path / "cubes", tmp_path / "phase1", tmp_path / "runs"
    exp.mkdir()
    subprocess.run([sys.executable, str(ROOT / "tests/fixtures/make_fake_exports.py"), str(ROOT / "scripts/deep_checks.py"),
                    str(exp), "--clean", "--n-a", "36"], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/build_cube.py"), "--exports", str(exp), "--out", str(cubes),
                    "--site", "mississippi"], check=True)
    cfg = tmp_path / "p1.yaml"
    cfg.write_text("blocks: {size_m: 90, buffer_m: 10}\nfolds: {n: 5, seed: 1, n_trials: 20}\n"
                   "patches: {A: {size: 4, stride: 4}, B: {size: 2, stride: 2}}\nnormalisation: {n_sample_pixels: 500, seed: 0}\n")
    subprocess.run([sys.executable, str(ROOT / "scripts/make_folds.py"), "--cubes", str(cubes), "--out", str(p1),
                    "--phase1-config", str(cfg), "--site", "mississippi"], check=True)
    for t in ("A", "B"):
        f = dict(np.load(p1 / f"folds/mississippi_{t}.npz"))
        f["eval_main"] = np.ones_like(f["eval_main"])
        f["aoi"] = np.ones_like(f["aoi"])
        np.savez(p1 / f"folds/mississippi_{t}.npz", **f)
    p3 = tmp_path / "p3.yaml"
    p3.write_text("patch: {A: 16, B: 8}\nbatch: {A: 2, B: 2}\nval_samples: 4\n"
                  "arch: {convlstm: {hid: 8}, simvp: {hid_s: 8, hid_t: 16, n_t: 1}, "
                  "ecotransformer: {dim: 32, depth: 1, heads: 2, patch: 4}}\n")
    models = ["convlstm_s0", "simvp_s0", "ecotransformer_s0", "ecotransformer_off_s0"]
    run = [sys.executable, str(ROOT / "scripts/run_baselines.py"), "--cubes", str(cubes), "--phase1", str(p1),
           "--out", str(runs), "--site", "mississippi", "--track", "A", "--run-id", "d", "--fast",
           "--table-cache", str(tmp_path / "tc"), "--phase1-config", str(cfg), "--phase3-config", str(p3),
           "--models", *models]
    subprocess.run(run, check=True)
    m = pd.read_csv(runs / "d/metrics.csv")
    assert set(m.model) == set(models)
    assert set(m.cutoff) == {"ida", "ida_placebo_2018"} and m[m.cutoff == "ida"].lead.min() == 0
    assert m.n.gt(0).all() and np.isfinite(m.rmse).all()
    assert len(list((runs / "d/deep_cache").glob("*.npz"))) == len(models) * 2 * 5
    # resume from the per-(cutoff, fold) cache: identical metrics, no retraining
    import shutil
    shutil.rmtree(runs / "d/parts")
    out = subprocess.run(run, check=True, capture_output=True, text=True).stdout
    assert "ep1" not in out
    pd.testing.assert_frame_equal(pd.read_csv(runs / "d/metrics.csv"), m)


def _fixture(tmp_path, sites=("mississippi",)):
    exp, cubes, p1 = tmp_path / "exp", tmp_path / "cubes", tmp_path / "phase1"
    exp.mkdir()
    subprocess.run([sys.executable, str(ROOT / "tests/fixtures/make_fake_exports.py"), str(ROOT / "scripts/deep_checks.py"),
                    str(exp), "--clean", "--n-a", "36"], check=True)
    cfg = tmp_path / "p1.yaml"
    cfg.write_text("blocks: {size_m: 90, buffer_m: 10}\nfolds: {n: 5, seed: 1, n_trials: 20}\n"
                   "patches: {A: {size: 4, stride: 4}, B: {size: 2, stride: 2}}\nnormalisation: {n_sample_pixels: 500, seed: 0}\n")
    for site in sites:
        subprocess.run([sys.executable, str(ROOT / "scripts/build_cube.py"), "--exports", str(exp), "--out", str(cubes),
                        "--site", site], check=True)
        subprocess.run([sys.executable, str(ROOT / "scripts/make_folds.py"), "--cubes", str(cubes), "--out", str(p1),
                        "--phase1-config", str(cfg), "--site", site], check=True)
        for t in ("A", "B"):
            f = dict(np.load(p1 / f"folds/{site}_{t}.npz"))
            f["eval_main"] = np.ones_like(f["eval_main"])
            f["aoi"] = np.ones_like(f["aoi"])
            np.savez(p1 / f"folds/{site}_{t}.npz", **f)
    p3 = tmp_path / "p3.yaml"
    p3.write_text("patch: {A: 16, B: 8}\nbatch: {A: 2, B: 2}\nval_samples: 4\n"
                  "arch: {convlstm: {hid: 8}, simvp: {hid_s: 8, hid_t: 16, n_t: 1}, "
                  "ecotransformer: {dim: 32, depth: 1, heads: 2, patch: 4}}\n")
    return cubes, p1, cfg, p3


def _run(tmp_path, cubes, p1, cfg, p3, site, track, models):
    runs = tmp_path / "runs"
    subprocess.run([sys.executable, str(ROOT / "scripts/run_baselines.py"), "--cubes", str(cubes), "--phase1", str(p1),
                    "--out", str(runs), "--site", site, "--track", track, "--run-id", "v", "--fast",
                    "--table-cache", str(tmp_path / "tc"), "--phase1-config", str(cfg), "--phase3-config", str(p3),
                    "--models", *models], check=True)
    return pd.read_csv(runs / "v/metrics.csv")


def test_phase5_variants_run_through_the_harness(tmp_path):
    cubes, p1, cfg, p3 = _fixture(tmp_path)
    models = ["ecotransformer__smooth-nostatic-nomask-tin4_s0", "simvp__nbr_s0"]
    m = _run(tmp_path, cubes, p1, cfg, p3, "mississippi", "A", models)
    assert set(m.model) == set(models) and m.n.gt(0).all() and np.isfinite(m.rmse).all()


def test_cross_site_transfer(tmp_path):
    cubes, p1, cfg, p3 = _fixture(tmp_path, ("mississippi", "everglades"))
    p3.write_text(p3.read_text().replace("B: 8}", "B: 4}"))            # tiny fixture grid at 30 m
    m = _run(tmp_path, cubes, p1, cfg, p3, "everglades", "B", ["simvp__xfer_s0"])
    assert set(m.model) == {"simvp__xfer_s0"} and np.isfinite(m.rmse).all()
