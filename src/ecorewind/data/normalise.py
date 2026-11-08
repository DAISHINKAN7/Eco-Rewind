"""Robust per-channel normalisation statistics (MASTER_PROMPT §6.3, integrity rules 1-3).

Statistics come only from (a) pixels in training blocks, outside fold buffers, and (b) quarters strictly
before the cutoff quarter, and only from valid values. Indices (NDVI/NDWI/NDMI) stay in physical units
(median 0, scale 1). A fixed random sample of training pixels keeps memory bounded; the sample, the
quarters and the data hash are recorded with the statistics.
"""
from __future__ import annotations

import numpy as np

from .masks import INDICES

IDENTITY = set(INDICES)


def sample_pixels(train_mask: np.ndarray, n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    r, c = np.nonzero(train_mask)
    if len(r) > n:
        pick = np.sort(np.random.default_rng(seed).choice(len(r), n, replace=False))
        r, c = r[pick], c[pick]
    return r, c


def sample_values(data, valid, channels: list[str], t_idx: list[int], r: np.ndarray, c: np.ndarray):
    """Values and validity at fixed pixels: (T, C, n) arrays, read once per (t, channel) slice."""
    V = np.full((len(t_idx), len(channels), len(r)), np.nan, dtype="float32")
    M = np.zeros(V.shape, dtype=bool)
    for i, t in enumerate(t_idx):
        for ci, ch in enumerate(channels):
            if ch in IDENTITY:
                continue
            d = np.asarray(data[t, ci])[r, c]
            V[i, ci], M[i, ci] = d, np.asarray(valid[t, ci])[r, c] & np.isfinite(d)
    return V, M


def stats_from_sample(V, M, channels: list[str], rows_t: list[int], keep: np.ndarray) -> dict:
    """Robust stats from sampled values, using only time rows `rows_t` and sample pixels where `keep`."""
    stats = {}
    for ci, ch in enumerate(channels):
        if ch in IDENTITY:
            stats[ch] = {"median": 0.0, "scale": 1.0, "identity": True}
            continue
        x = V[rows_t][:, ci][:, keep][M[rows_t][:, ci][:, keep]]
        if x.size == 0:
            stats[ch] = {"median": 0.0, "scale": 1.0, "n": 0, "empty": True}
            continue
        q25, med, q75 = np.percentile(x, [25, 50, 75])
        stats[ch] = {"median": float(med), "scale": float(q75 - q25) or 1.0, "n": int(x.size)}
    return stats


def fit_stats(data, valid, channels: list[str], hist_idx: list[int], train_mask: np.ndarray,
              n_sample: int = 200_000, seed: int = 0) -> dict:
    """data/valid: array-likes (T, C, H, W) (numpy or zarr). Reads only time indices in hist_idx."""
    r, c = sample_pixels(train_mask, n_sample, seed)
    V, M = sample_values(data, valid, channels, list(hist_idx), r, c)
    stats = stats_from_sample(V, M, channels, list(range(len(hist_idx))), np.ones(len(r), bool))
    return {"channels": stats, "n_sample_pixels": int(len(r)), "hist_idx": list(map(int, hist_idx))}


def apply(x: np.ndarray, stats: dict, channels: list[str], axis: int) -> np.ndarray:
    shape = [1] * x.ndim
    shape[axis] = len(channels)
    med = np.array([stats["channels"][c]["median"] for c in channels], dtype="float32").reshape(shape)
    sc = np.array([stats["channels"][c]["scale"] for c in channels], dtype="float32").reshape(shape)
    return (x - med) / sc
