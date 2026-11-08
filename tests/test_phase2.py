"""Phase 2 tests: metrics fixtures, conformal coverage, baselines, temporal cutoff, masking, harness end to end."""
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ecorewind.data.cube import period_keys  # noqa: E402
from ecorewind.data.events import Cutoff  # noqa: E402
from ecorewind.eval import attribution as A  # noqa: E402
from ecorewind.eval import conformal as CF  # noqa: E402
from ecorewind.eval.metrics import score  # noqa: E402
from ecorewind.eval.pixels import PixelTable  # noqa: E402
from ecorewind.eval.split import make_split  # noqa: E402
from ecorewind.models.baselines.harmonic import Harmonic, design, huber_irls, qtime  # noqa: E402
from ecorewind.models.baselines.lgbm import LGBM  # noqa: E402
from ecorewind.models.baselines.simple import Climatology, Persistence  # noqa: E402
from ecorewind.models.baselines.synth_control import SynthControl  # noqa: E402

KEYS = period_keys("2015Q3", "2023Q4", date(2021, 8, 29))[0]
IDA = Cutoff("ida", "mississippi", date(2021, 8, 29), "event", 8)
PLC = Cutoff("p", "mississippi", date(2018, 8, 29), "placebo", 3)


def table(n=400, seed=0, noise=0.02):
    """Seasonal + trend signal per pixel, 5 channels, on a 20 x 20 grid with 5 folds of 80 pixels."""
    rng = np.random.default_rng(seed)
    t = np.array([qtime(k) for k in KEYS])
    amp, base = rng.uniform(0.05, 0.15, n), rng.uniform(0.2, 0.6, n)
    sig = base + amp * np.cos(2 * np.pi * t[:, None] / 4) + 0.002 * (t[:, None] - t[0])
    Y = np.stack([sig + rng.normal(0, noise, sig.shape) for _ in range(5)], axis=1).astype("float32")
    r, c = np.divmod(np.arange(n), 20)
    static = {"lc_herb_wetland": (rng.random(n) > 0.5).astype("float32"), "elevation_m": rng.random(n).astype("float32")}
    static["lc_mangrove"] = 1 - static["lc_herb_wetland"]
    return PixelTable("mississippi", "A", list(KEYS), ["NDVI", "NDMI", "NDWI", "VV", "VH"], r.astype("int32"),
                      c.astype("int32"), (np.arange(n) % 5).astype("int8"), (np.arange(n) // 20).astype("int32"), Y, static,
                      (int(np.ceil(n / 20)), 20), 10.0, "hash")


# ----------------------------------------------------------------------------- metrics, conformal, attribution
def test_metrics_match_hand_computed_fixture():
    y = np.array([1.0, 2.0, 3.0, np.nan])
    p = np.array([1.5, 2.0, 2.0, 9.0])
    s = score(y, p, p - 0.8, p + 0.8)                              # errors 0.5, 0, 1 -> last one outside
    assert s["n"] == 3 and s["rmse"] == pytest.approx(np.sqrt((0.25 + 0 + 1) / 3))
    assert s["mae"] == pytest.approx(0.5) and s["bias"] == pytest.approx(-0.5 / 3)
    assert s["r2"] == pytest.approx(1 - 1.25 / 2.0)
    assert s["coverage"] == pytest.approx(2 / 3) and s["width"] == pytest.approx(1.6)


def test_conformal_coverage_is_nominal_on_synthetic_noise():
    rng = np.random.default_rng(1)
    cal, test = rng.normal(0, 1, 5000), rng.normal(0, 1, 20000)
    q = CF.qhat(CF.scores(cal, np.zeros_like(cal), np.zeros_like(cal)), 0.10)
    lo, hi = CF.interval(np.zeros_like(test), np.zeros_like(test), q)
    assert np.mean((test >= lo) & (test <= hi)) == pytest.approx(0.90, abs=0.015)


def test_attribution_deficit_and_area():
    d = A.deficit(np.array([0.4, 0.5, np.nan]), np.array([0.5, 0.5, 0.1]), np.array([0.45, 0.45, 0]), np.array([0.55, 0.55, 0]), 0.01)
    assert d["n"] == 2 and d["mean"] == pytest.approx(0.05) and d["total"] == pytest.approx(0.001)
    assert d["mean_lo"] == pytest.approx(0.0) and d["mean_hi"] == pytest.approx(0.1)


# ----------------------------------------------------------------------------- baselines
def test_harmonic_recovers_signal_and_resists_outliers():
    t = np.arange(24, dtype=float)
    X = design(t, t[-1], True)
    y = 0.4 + 0.01 * t / 4 * 4 / 4 + 0.1 * np.cos(2 * np.pi * t / 4)
    Y = np.stack([y, y.copy()], axis=1)
    Y[5, 1] = 5.0                                                   # gross outlier in pixel 2
    beta = huber_irls(X, Y, iters=8)
    np.testing.assert_allclose(X @ beta[:, 0], y, atol=1e-6)
    assert np.max(np.abs(X @ beta[:, 1] - y)) < 0.02


def test_harmonic_forecast_beats_climatology_on_trend_signal():
    tab = table(noise=0.005)
    s = make_split(tab, PLC, 0, 5)
    y = s.target(s.test)
    h, c = Harmonic().predict(s, s.test)[0], Climatology().predict(s, s.test)[0]
    assert np.nanmean(np.abs(h - y)) < np.nanmean(np.abs(c - y)) < 0.1


def test_persistence_takes_last_valid_value():
    tab = table()
    tab.Y[:, 0, 0] = np.arange(len(KEYS))
    s = make_split(tab, PLC, 0, 5)
    tab.Y[s.hist_idx[-1], 0, 0] = np.nan                            # last history value invalid
    q = Persistence().predict(s, np.array([0]))[0]
    assert np.all(q[:, 0, 0] == s.hist_idx[-2])


def test_lead0_targets_and_never_history():
    keys = list(KEYS) + ["2021Q3_POST"]
    from ecorewind.data.events import split_indices
    h, t = split_indices(keys, IDA, lead0=True)
    assert keys[t[0]] == "2021Q3_POST" and all(keys[i] < "2021Q3" for i in h)
    assert split_indices(keys, IDA)[1] == t[1:]
    h, t = split_indices(keys, PLC, lead0=True)
    assert keys[t[0]] == "2018Q3" and "2021Q3_POST" not in [keys[i] for i in t + h]
    keys.append("2018Q3_PPOST")                                     # A3: matched-days composite replaces the quarter
    h, t = split_indices(keys, PLC, lead0=True)
    assert keys[t[0]] == "2018Q3_PPOST" and "2018Q3" not in [keys[i] for i in t + h]


def test_trend_free_harmonic_ignores_drift():
    tab = table(noise=0.005)
    s = make_split(tab, PLC, 0, 5)
    assert Harmonic(trend=False).name == "harmonic_notrend"
    assert np.isfinite(Harmonic(trend=False).predict(s, s.test)[0][:, :3]).all()


@pytest.mark.parametrize("model", [Persistence(), Climatology(), Harmonic(), Harmonic(trend=False), SynthControl({}),
                                   LGBM(n_estimators=10, n_rows=2000)])
def test_predictions_never_use_data_at_or_after_the_cutoff(model):
    tab = table()
    s = make_split(tab, IDA, 0, 5)
    q1 = model.fit(s).predict(s, s.test)[0]
    cut = s.hist_idx[-1] + 1
    tab.Y[cut:, :, s.test] = 1e6                                    # test pixels' future
    if not isinstance(model, SynthControl):
        tab.Y[cut:] = -1e6                                          # everyone's future (history-only models)
    q2 = model.fit(s).predict(s, s.test)[0]
    np.testing.assert_array_equal(q1, q2)


def test_invalid_values_never_reach_metrics_or_models():
    tab = table()
    s = make_split(tab, PLC, 0, 5)
    q = Climatology().predict(s, s.test)[0]
    y = s.target(s.test)
    base = score(y[0, 0], q[0, 0])
    y2 = y.copy()
    y2[0, 0, :10] = np.nan                                          # invalid targets ...
    assert score(y2[0, 0], q[0, 0])["n"] == base["n"] - 10          # ... are simply excluded


def test_lgbm_learns_and_quantiles_are_ordered():
    tab = table(n=1000, noise=0.01)
    s = make_split(tab, PLC, 0, 5)
    q50, lo, hi = LGBM(n_estimators=60, n_rows=20000).fit(s).predict(s, s.test)
    assert np.all(lo[:, :3] <= q50[:, :3]) and np.all(q50[:, :3] <= hi[:, :3])
    y = s.target(s.test)
    clim = Climatology().predict(s, s.test)[0]
    assert np.nanmean(np.abs(q50[:, 0] - y[:, 0])) < 2 * np.nanmean(np.abs(clim[:, 0] - y[:, 0]))
    assert np.isnan(q50[:, 3:]).all()                               # SAR channels not modelled by LightGBM


# ----------------------------------------------------------------------------- harness end to end
def test_run_baselines_end_to_end(tmp_path):
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
    # fake grids lie outside the real AOI: evaluate every pixel for the test
    for t in ("A", "B"):
        f = dict(np.load(p1 / f"folds/mississippi_{t}.npz"))
        f["eval_main"] = np.ones_like(f["eval_main"])
        np.savez(p1 / f"folds/mississippi_{t}.npz", **f)
    pp = tmp_path / "ppost"                                         # A3: a matched-days placebo composite (Track B only)
    pp.mkdir()
    for sensor in ("", "S1_"):
        shutil.copy(exp / f"mississippi_B_{sensor}2018Q3.tif", pp / f"mississippi_B_{sensor}2018Q3_PPOST.tif")
    subprocess.run([sys.executable, str(ROOT / "scripts/run_baselines.py"), "--cubes", str(cubes), "--phase1", str(p1),
                    "--out", str(runs), "--site", "mississippi", "--run-id", "t", "--fast", "--table-cache", str(tmp_path / "tc"),
                    "--phase1-config", str(cfg), "--ppost-exports", str(pp)], check=True)
    out = runs / "t"
    m = pd.read_csv(out / "metrics.csv")
    assert set(m.model) == {"persistence", "climatology", "harmonic", "harmonic_notrend", "synth_control", "lgbm"}
    assert m[(m.cutoff == "ida") & (m.lead == 0)].quarter.eq("2021Q3_POST").all()               # lead 0 = POST partial
    p0 = m[(m.cutoff == "ida_placebo_2018") & (m.lead == 0)]
    assert p0[p0.track == "A"].quarter.eq("2018Q3").all() and p0[p0.track == "B"].quarter.eq("2018Q3_PPOST").all()
    assert set(m.cutoff) == {"ida", "ida_placebo_2018", "ida_placebo_2015", "ida_placebo_2016"}
    assert set(m[m.track == "A"].cutoff) == {"ida", "ida_placebo_2018"}                 # Track B-only placebos
    assert m[(m.cutoff == "ida")].lead.max() == 8 and m[(m.cutoff == "ida_placebo_2018")].lead.max() == 3
    ev = m[(m.cutoff == "ida") & (m.lead > 3)]
    assert ev.extrapolated_interval.all() and not m[m.lead <= 3].extrapolated_interval.any()
    plc = m[(m.kind == "placebo") & (m.channel == "NDVI") & (m.model == "climatology")]
    assert plc.coverage.between(0.5, 1.0).all()                                          # calibrated on the same windows
    a = pd.read_csv(out / "attribution.csv")
    assert {"all", "0"} <= set(a.fold.astype(str)) and (out / "summary.md").exists()
    assert (out / "maps/harmonic_mississippi_A_ida.npz").exists()
    assert (out / "git_commit.txt").read_text().strip() and (out / "data_hash.txt").exists()
    # resume: a second run with the same id reuses the finished parts and gives identical metrics
    subprocess.run([sys.executable, str(ROOT / "scripts/run_baselines.py"), "--cubes", str(cubes), "--phase1", str(p1),
                    "--out", str(runs), "--site", "mississippi", "--run-id", "t", "--fast", "--table-cache", str(tmp_path / "tc"),
                    "--phase1-config", str(cfg), "--ppost-exports", str(pp)], check=True, capture_output=True)
    pd.testing.assert_frame_equal(pd.read_csv(out / "metrics.csv"), m)


def test_placebo_verdict_rule():
    sys.path.insert(0, str(ROOT / "scripts"))
    import placebo_verdict as PV
    rows = []
    for m in ("simvp_s0", "simvp_s1"):
        for k in range(5):
            for lead in (1, 2, 3):
                rows.append({"model": m, "site": "s", "track": "A", "cutoff": "ev", "kind": "event", "fold": k,
                             "lead": lead, "channel": "NDVI", "mean": 0.10 + 0.001 * k})
                rows.append({"model": m, "site": "s", "track": "A", "cutoff": "pl", "kind": "placebo", "fold": k,
                             "lead": lead, "channel": "NDVI", "mean": 0.01 * (k - 2)})
    v = PV.fold_values(pd.DataFrame(rows), PV.LEADS)
    cov = pd.DataFrame({"site": ["s"], "track": ["A"], "family": ["simvp"], "coverage": [0.85]})
    r = PV.verdict(v, cov).iloc[0]
    assert r.model == "simvp" and r.n_event == 10 and r.n_placebo == 10 and r.PASS
    cov.loc[0, "coverage"] = 0.7
    assert not PV.verdict(v, cov).iloc[0].PASS                     # coverage rule
