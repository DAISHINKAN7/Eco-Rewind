"""Rung 0 baselines (MASTER_PROMPT §7.4): persistence and per-pixel seasonal climatology.

Both use only the split's history (quarters before the cutoff quarter) of the pixels they predict.
"""
from __future__ import annotations

import warnings

import numpy as np


def season(key: str) -> int:
    return int(key[-1]) - 1


class Baseline:
    name = "base"
    quantile = False

    def fit(self, split):
        return self

    def predict(self, split, idx):  # -> q50, lo_base, hi_base, each (L, C, n)
        raise NotImplementedError


def seasonal_climatology(H: np.ndarray, hist_keys: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """H (T, C, n) -> per-season mean (4, C, n) and overall mean (C, n); NaN where never observed."""
    seasons = np.array([season(k) for k in hist_keys])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        seas = np.stack([np.nanmean(H[seasons == s], axis=0) if (seasons == s).any() else np.full(H.shape[1:], np.nan)
                         for s in range(4)])
        overall = np.nanmean(H, axis=0)
    return seas, overall


class Persistence(Baseline):
    """Last valid pre-cutoff value of each pixel and channel, for every lead."""
    name = "persistence"

    def predict(self, split, idx):
        H = split.hist(idx)
        last = np.full(H.shape[1:], np.nan, dtype="float32")
        for t in range(H.shape[0]):                      # oldest -> newest, newer valid values overwrite
            v = np.isfinite(H[t])
            last[v] = H[t][v]
        q = np.broadcast_to(last, (len(split.tgt_idx), *last.shape)).copy()
        return q, q, q


class Climatology(Baseline):
    """Mean of the pixel's pre-cutoff values in the same calendar quarter (fallback: overall pre-cutoff mean)."""
    name = "climatology"

    def predict(self, split, idx):
        seas, overall = seasonal_climatology(split.hist(idx), split.hist_keys)
        q = np.stack([np.where(np.isfinite(seas[season(k)]), seas[season(k)], overall) for k in split.tgt_keys])
        q = q.astype("float32")
        return q, q, q
