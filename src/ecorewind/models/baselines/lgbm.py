"""Rung 2: gradient-boosted trees on per-pixel lags (MASTER_PROMPT §7.4).

Direct multi-horizon: one LightGBM model per target channel and quantile (q10 / q50 / q90), with the
distance to the target as a feature. Training pairs live entirely inside the pre-cutoff history of
training-fold pixels: features from quarters <= anchor, target at anchor + d (d in the split's distances).
Features: last `n_lags` values of every channel, target-season sin/cos, distance, static context, and the
3x3 / 7x7 neighbourhood mean of the target channel at the anchor (over evaluable pixels only).
"""
from __future__ import annotations

import os
import warnings

import numpy as np
from scipy import ndimage

from .simple import Baseline, season

QUANTILES = (0.1, 0.5, 0.9)


def neighbourhood(table, values: np.ndarray, size: int) -> np.ndarray:
    """Valid-weighted mean over a size x size window of the grid, evaluated at the table's pixels."""
    g = np.zeros(table.shape, dtype="float32")
    w = np.zeros(table.shape, dtype="float32")
    ok = np.isfinite(values)
    g[table.r[ok], table.c[ok]] = values[ok]
    w[table.r[ok], table.c[ok]] = 1.0
    num = ndimage.uniform_filter(g, size, mode="constant")
    den = ndimage.uniform_filter(w, size, mode="constant")
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den
    out = np.where(den > 1e-6, out, np.nan)
    return out[table.r, table.c]                               # (n,) aligned with the table


class LGBM(Baseline):
    name = "lgbm"
    quantile = True

    def __init__(self, channels=("NDVI", "NDMI", "NDWI"), n_lags: int = 4, n_rows: int = 120_000, max_anchors: int = 12,
                 n_estimators: int = 300, learning_rate: float = 0.05, num_leaves: int = 31, seed: int = 0):
        self.channels, self.n_lags, self.n_rows, self.max_anchors = list(channels), n_lags, n_rows, max_anchors
        self.n_estimators = n_estimators
        self.params = dict(objective="quantile", learning_rate=learning_rate, num_leaves=num_leaves,
                           min_data_in_leaf=100, bagging_fraction=0.8, bagging_freq=1, feature_fraction=0.8,
                           seed=seed, deterministic=True, verbose=-1, num_threads=os.cpu_count())
        self.seed = seed

    # --------------------------------------------------------------------------------------------------
    def _nb_cache(self, split, pos: int):
        """Neighbourhood means of each modelled channel at history position `pos`, for all table pixels."""
        key = (id(split), pos)
        if key not in self._nb:
            H = split.table.Y[split.hist_idx[pos]]
            self._nb[key] = {ch: (neighbourhood(split.table, H[split.table.channels.index(ch)], 3),
                                  neighbourhood(split.table, H[split.table.channels.index(ch)], 7))
                             for ch in self.channels}
        return self._nb[key]

    def _features(self, split, idx: np.ndarray, pos: int, d: int, ch: str) -> np.ndarray:
        tab = split.table
        C = len(tab.channels)
        lags = []
        for l in range(self.n_lags):
            p = pos - l
            lags.append(tab.Y[split.hist_idx[p]][:, idx].T if p >= 0 else np.full((len(idx), C), np.nan))   # (n, C)
        tgt_season = (season(split.hist_keys[pos]) + d) % 4
        nb3, nb7 = self._nb_cache(split, pos)[ch]
        extra = np.stack([np.full(len(idx), np.sin(2 * np.pi * tgt_season / 4)),
                          np.full(len(idx), np.cos(2 * np.pi * tgt_season / 4)),
                          np.full(len(idx), float(d)), nb3[idx], nb7[idx],
                          *[tab.static[k][idx] for k in sorted(tab.static)]], axis=1)
        return np.concatenate([*lags, extra], axis=1).astype("float32")

    def fit(self, split):
        import lightgbm as lgb
        self._nb = {}
        rng = np.random.default_rng(self.seed)
        n_hist = len(split.hist_idx)
        dists = sorted(set(split.distance()))
        anchors = [p for p in range(n_hist) if p >= self.n_lags - 1][-self.max_anchors:]
        pairs = [(p, d) for p in anchors for d in dists if p + d <= n_hist - 1]
        self.models = {}
        if not pairs or len(split.train) == 0:
            return self
        per = max(1, self.n_rows // len(pairs))
        for ch in self.channels:
            ci = split.table.channels.index(ch)
            X, y = [], []
            for p, d in pairs:
                idx = rng.choice(split.train, min(per, len(split.train)), replace=False)
                t = split.table.Y[split.hist_idx[p + d], ci, idx]
                ok = np.isfinite(t)
                if ok.any():
                    X.append(self._features(split, idx[ok], p, d, ch))
                    y.append(t[ok])
            if not X:
                continue
            X, y = np.concatenate(X), np.concatenate(y)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ds = lgb.Dataset(X, y, free_raw_data=False)
                self.models[ch] = {q: lgb.train({**self.params, "alpha": q}, ds, num_boost_round=self.n_estimators)
                                   for q in QUANTILES}
        return self

    def predict(self, split, idx):
        L, C = len(split.tgt_idx), len(split.table.channels)
        out = {q: np.full((L, C, len(idx)), np.nan, dtype="float32") for q in QUANTILES}
        pos = len(split.hist_idx) - 1
        for li, d in enumerate(split.distance()):
            for ch, ms in self.models.items():
                X = self._features(split, idx, pos, d, ch)
                ci = split.table.channels.index(ch)
                preds = np.sort(np.stack([ms[q].predict(X) for q in QUANTILES]), axis=0)   # no quantile crossing
                for qi, q in enumerate(QUANTILES):
                    out[q][li, ci] = preds[qi]
        return out[0.5], out[0.1], out[0.9]
