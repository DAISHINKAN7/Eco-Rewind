"""Phase 1 tests (MASTER_PROMPT §12): leakage, temporal cutoff, masking, indices, grid nesting, SAR."""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ecorewind.data import blocks as B  # noqa: E402
from ecorewind.data import dataset as D  # noqa: E402
from ecorewind.data import normalise as N  # noqa: E402
from ecorewind.data.cube import Cube, period_keys  # noqa: E402
from ecorewind.data.events import Cutoff, split_indices  # noqa: E402
from ecorewind.data.indices import compute_indices, normalised_difference  # noqa: E402
from ecorewind.data.masks import CHANNELS, optical_valid, sar_valid  # noqa: E402

IDA = Cutoff("ida", "mississippi", date(2021, 8, 29), "event", 8)
KEYS_A = period_keys("2015Q3", "2023Q4", date(2021, 8, 29))[0]


# ----------------------------------------------------------------------------- indices and masks
def test_indices_match_hand_values_and_never_fake_minus_one():
    refl = {"Blue": np.array([.05, .05, .05, 0.0]), "Green": np.array([.08, .08, .08, .08]),
            "Red": np.array([.10, .04, 0.0, .05]), "NIR": np.array([.30, .04, .20, .30]),
            "SWIR1": np.array([.20, .02, .10, .10]), "SWIR2": np.array([.1, .1, .1, .1])}
    valid = optical_valid(refl, np.array([3, 3, 3, 3]))
    idx, ok = compute_indices(refl, valid)
    assert idx["NDVI"][0] == pytest.approx(0.5) and idx["NDVI"][1] == pytest.approx(0.0)
    assert idx["NDWI"][0] == pytest.approx((.08 - .30) / (.08 + .30))
    assert idx["NDMI"][0] == pytest.approx(0.2)
    assert np.isnan(idx["NDVI"][2]) and not ok["NDVI"][2]          # Red = 0 is a fill, not NDVI = 1
    assert ok["NDVI"][3] and not valid["Blue"][3]                  # Blue fill does not kill NDVI (own inputs only)
    for v in idx.values():
        f = v[np.isfinite(v)]
        assert np.all(np.abs(f) < 1) and not np.isinf(v).any()


def test_zero_denominator_is_invalid():
    v, ok = normalised_difference(np.array([1e-8]), np.array([-1e-8]), np.array([True]))
    assert np.isnan(v[0]) and not ok[0]


def test_optical_mask_rules():
    one = np.array([.1])
    refl = {b: one.copy() for b in ("Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2")}
    assert all(m[0] for m in optical_valid(refl, np.array([2])).values())
    assert not any(m[0] for m in optical_valid(refl, np.array([0])).values())        # no clear obs
    refl["SWIR1"] = np.array([-0.01])                                                   # HLS negative over water
    v = optical_valid(refl, np.array([2]))
    assert not v["SWIR1"][0] and v["NIR"][0]
    refl["Blue"] = np.array([np.nan])                                                   # missing band -> pixel unobserved
    assert not any(m[0] for m in optical_valid(refl, np.array([2])).values())
    refl = {b: np.array([1.2]) for b in refl}
    assert not any(m[0] for m in optical_valid(refl, np.array([2]), max_reflectance=1.0).values())


def test_sar_zero_acquisitions_is_masked():
    assert not sar_valid(np.array([-12.0]), np.array([-18.0]), np.array([0]))[0]
    assert sar_valid(np.array([-12.0]), np.array([-18.0]), np.array([5]))[0]
    assert not sar_valid(np.array([np.nan]), np.array([-18.0]), np.array([5]))[0]


# ----------------------------------------------------------------------------- temporal design
def test_event_split_excludes_event_quarter_and_respects_horizon():
    assert "2021Q3" not in KEYS_A
    hist, tgt = split_indices(KEYS_A, IDA)
    assert KEYS_A[hist[-1]] == "2021Q2" and KEYS_A[tgt[0]] == "2021Q4"
    assert len(tgt) == 8 and KEYS_A[tgt[-1]] == "2023Q3"
    plc = Cutoff("p", "mississippi", date(2018, 8, 29), "placebo", 3)
    h, t = split_indices(KEYS_A, plc)
    assert KEYS_A[h[-1]] == "2018Q2" and [KEYS_A[i] for i in t] == ["2018Q4", "2019Q1", "2019Q2"]
    assert all(i < t[0] for i in h) and "2018Q3" not in [KEYS_A[i] for i in h + t]


# ----------------------------------------------------------------------------- blocks, folds, buffers
def test_blocks_cover_the_same_ground_in_both_tracks():
    shape_a, shape_b = (2202, 2199), (734, 733)
    ia, ib = B.block_ids(shape_a, 10, 3840), B.block_ids(shape_b, 30, 3840)
    assert B.n_blocks(shape_a, 10, 3840) == B.n_blocks(shape_b, 30, 3840) == (6, 6)
    r, c = np.indices(shape_b)
    for dr in range(3):
        for dc in range(3):
            assert np.array_equal(ia[r * 3 + dr, c * 3 + dc], ib)      # each 30 m pixel = 3x3 10 m pixels, same block
    with pytest.raises(ValueError):
        B.block_ids(shape_a, 10, 2560)                                 # 2.56 km does not nest in 30 m


def test_buffer_only_on_boundaries_between_different_folds():
    # 2 x 2 blocks of 12 px (120 m at 10 m); folds TL=0, TR=0, BL=1, BR=0; buffer 20 m = 2 px each side
    fob = np.array([[0, 0], [1, 0]])
    buf = B.buffer_mask(fob, (24, 24), 10, 120, 20)
    expect = np.zeros((24, 24), bool)
    expect[10:12, 0:12] = expect[12:14, 0:12] = True        # TL | BL edge, both sides
    expect[12:24, 10:12] = expect[12:24, 12:14] = True      # BL | BR edge, both sides
    expect[10:12, 12:14] = True                             # TR corner touching BL diagonally
    assert np.array_equal(buf, expect)
    assert not buf[:10].any()                                # TL | TR share a fold: no buffer
    assert not buf[0].any() and not buf[:, 23].any() and not buf[23, 14:].any()   # grid edges never buffer


def test_patches_never_cross_blocks_or_folds():
    fob = np.array([[0, 1, 2, 3], [4, 0, 1, 2], [3, 4, 0, 1]])        # 3 x 4 blocks incl. partial edges
    shape = (70, 100)                                                    # partial edge blocks too
    fold = B.fold_raster(fob, shape, 10, 330)                            # 33 px blocks
    ps = D.patch_origins(shape, 10, 330, fob, 16, 8)
    assert ps
    for p in ps:
        win = fold[p.row:p.row + p.size, p.col:p.col + p.size]
        assert win.min() == win.max() == p.fold
        assert p.row + p.size <= shape[0] and p.col + p.size <= shape[1]
        assert len({tuple(x) for x in np.stack(B.block_index(shape, 10, 330))[:, p.row:p.row + p.size, p.col:p.col + p.size].reshape(2, -1).T}) == 1


# ----------------------------------------------------------------------------- leakage via normalisation / inputs
class FakeCube:
    def __init__(self, T=12, H=24, W=24, seed=0):
        rng = np.random.default_rng(seed)
        self.channels = list(CHANNELS)
        self.keys = KEYS_A[:T]
        self.data = rng.normal(0.2, 0.05, (T, len(CHANNELS), H, W)).astype("float32")
        self.valid = rng.random(self.data.shape) > 0.1
        self.data[~self.valid] = np.nan


def _stats(c, hist, train):
    return N.fit_stats(c.data, c.valid, c.channels, hist, train, n_sample=10_000, seed=1)


def test_normalisation_ignores_test_folds_future_quarters_and_invalid_pixels():
    c = FakeCube()
    train = np.zeros((24, 24), bool)
    train[:, :12] = True
    hist = list(range(8))
    base = _stats(c, hist, train)
    c2 = FakeCube()
    c2.data[:, :, :, 12:] = 1e6                                          # test-fold pixels
    c2.data[8:] = -1e6                                                   # quarters at/after the cutoff
    c2.data[:8][~c2.valid[:8]] = 9e9                                     # invalid pixels with extreme values
    assert _stats(c2, hist, train) == base
    assert base["channels"]["NDVI"]["identity"]                          # indices stay physical


def test_inputs_unchanged_when_data_after_cutoff_changes():
    c = FakeCube()
    stats = _stats(c, list(range(8)), np.ones((24, 24), bool))
    p = D.Patch(4, 4, 16, 0, 0)
    x1, m1 = D.make_input(c, list(range(8)), 6, p, stats)
    c.data[8:] = 1e6
    c.valid[8:] = ~c.valid[8:]
    x2, m2 = D.make_input(c, list(range(8)), 6, p, stats)
    assert np.array_equal(x1, x2) and np.array_equal(m1, m2)
    assert np.isfinite(x1).all()                                         # gaps filled, mask carries validity
    assert (~m1).any()
    with pytest.raises(ValueError):
        D.make_input(c, list(range(4)), 6, p, stats)                     # not enough history


def test_target_mask_excludes_buffer_and_invalid():
    c = FakeCube()
    loss = np.ones((24, 24), bool)
    loss[:, 10:14] = False
    y, ym = D.make_target(c, [8, 9], D.Patch(0, 0, 24, 0, 0), loss)
    assert not ym[:, :, :, 10:14].any() and not ym[np.isnan(y)].any()


# ----------------------------------------------------------------------------- end to end on fake exports
def test_build_cube_and_make_folds_end_to_end(tmp_path):
    exp, cubes, out = tmp_path / "exp", tmp_path / "cubes", tmp_path / "phase1"
    exp.mkdir()
    subprocess.run([sys.executable, str(ROOT / "tests/fixtures/make_fake_exports.py"), str(ROOT / "scripts/deep_checks.py"),
                    str(exp), "--clean", "--n-a", "36"], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/build_cube.py"), "--exports", str(exp), "--out", str(cubes)], check=True)
    c = Cube(cubes / "mississippi_A.zarr")
    assert c.keys == KEYS_A and c.partial_keys == ["2021Q3_PRE", "2021Q3_POST"]
    assert c.data.shape == (len(KEYS_A), len(CHANNELS), 36, 36) and c.g["partial_data"].shape[0] == 2
    ndvi = np.asarray(c.data[5, c.channel("NDVI")])
    assert np.nanmax(np.abs(ndvi)) < 1 and np.asarray(c.valid[5, c.channel("NDVI")]).any()
    cb = Cube(cubes / "everglades_B.zarr")
    assert not np.asarray(cb.valid[0, cb.channel("VV")]).any()          # 2013Q2: before Sentinel-1
    cfg = tmp_path / "p1.yaml"
    cfg.write_text("blocks: {size_m: 90, buffer_m: 10}\nfolds: {n: 3, seed: 1, n_trials: 20}\n"
                   "patches: {A: {size: 4, stride: 4}, B: {size: 2, stride: 2}}\nnormalisation: {n_sample_pixels: 500, seed: 0}\n")
    subprocess.run([sys.executable, str(ROOT / "scripts/make_folds.py"), "--cubes", str(cubes), "--out", str(out),
                    "--phase1-config", str(cfg)], check=True)
    fa, fb = np.load(out / "folds/mississippi_A.npz"), np.load(out / "folds/mississippi_B.npz")
    assert np.array_equal(fa["fold"][::3, ::3], fb["fold"])                # identical folds across tracks
    assert not (fa["eval_main"] & fa["buffer"]).any()
    norm = json.loads((out / "norm/mississippi_A_ida_fold0.json").read_text())
    assert norm["hist_keys"][-1] == "2021Q2" and 0 not in norm["train_folds"]
    assert (out / "figures/folds_mississippi.png").exists() and (out / "phase1_summary.md").exists()


def test_fold_assignment_is_balanced_complete_and_deterministic():
    import pandas as pd
    from ecorewind.data import folds as F
    rng = np.random.default_rng(3)
    df = pd.DataFrame({"block": range(36), "n_eval": rng.integers(0, 1000, 36).astype(float),
                       "wetland_frac": rng.random(36), "proxy": rng.normal(-0.05, 0.05, 36)})
    f1, f2 = F.assign_folds(df, 5, seed=7, n_trials=200), F.assign_folds(df, 5, seed=7, n_trials=200)
    assert np.array_equal(f1, f2) and set(f1) == set(range(5))
    counts = np.bincount(f1, minlength=5)
    assert counts.max() - counts.min() <= 1                       # dealt in groups of n_folds
    shares = np.array([df.n_eval[f1 == k].sum() for k in range(5)]) / df.n_eval.sum()
    assert shares.min() > 0.1                                     # no fold starved of evaluable pixels


def test_hurdat_parser_and_distance():
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_storm_record as S
    text = ("AL092021,                IDA,     40,\n"
            "20210829, 1655, L, HU, 29.1N,  90.2W, 130,  930,\n"
            "20210830, 0000,  , HU, 29.9N,  90.6W, 105,  944,\n"
            "AL012020,          ARTHUR,      2,\n"
            "20200517, 0000,  , TS, 34.0N,  77.0W,  40, 1000,\n")
    storms = S.parse(text)
    assert [s["name"] for s in storms] == ["IDA", "ARTHUR"] and storms[0]["points"][0][3] == 130
    hits = S.nearby(storms, (-90.70, 29.45), date(2021, 7, 1), date(2021, 10, 1), 200)
    assert len(hits) == 1 and hits[0]["name"] == "IDA" and hits[0]["closest_km"] < 70
    assert S.haversine_km(29.45, -90.70, 29.45, -90.70) == 0


def test_split_buffers_only_guard_the_test_fold():
    fob = np.array([[0, 1, 2], [2, 0, 1], [1, 2, 0]])
    shape, res, bm, bf = (36, 36), 10, 120, 20
    fold = B.fold_raster(fob, shape, res, bm)
    glob = B.buffer_mask(fob, shape, res, bm, bf)
    union = np.zeros(shape, bool)
    for k in range(3):
        sb = B.split_buffer(fob, k, shape, res, bm, bf)
        union |= sb & (fold == k)
        # leak check: every training pixel within buffer_m of a test pixel is in the split buffer
        test = fold == k
        from scipy import ndimage
        near_test = ndimage.binary_dilation(test, iterations=bf // res) & ~test
        assert not (near_test & ~sb).any()
        # a boundary between two training folds is not buffered in this split
        assert (glob & ~sb & (fold != k)).any()
    assert np.array_equal(union, glob)
