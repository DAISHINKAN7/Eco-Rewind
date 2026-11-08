"""Stratified spatial fold assignment (MASTER_PROMPT §6.6).

Blocks are sorted by the damage-exposure proxy and dealt to folds in groups of n_folds, with a random
order inside each group; among `n_trials` such deals the one with the most even folds (wetland share,
proxy, evaluable area) is kept. Deterministic for a given seed. The proxy is used for nothing but
stratification (documented in configs/phase1.yaml and the Phase 1 report).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def block_table(block_id: np.ndarray, n_rows: int, n_cols: int, wetland: np.ndarray, aoi: np.ndarray,
                proxy_px: np.ndarray | None = None) -> pd.DataFrame:
    nb = n_rows * n_cols
    ids = block_id.ravel()
    ev = (aoi & wetland).ravel()
    n_aoi = np.bincount(ids, weights=aoi.ravel(), minlength=nb)
    n_wet = np.bincount(ids, weights=ev, minlength=nb)
    df = pd.DataFrame({"block": np.arange(nb), "brow": np.arange(nb) // n_cols, "bcol": np.arange(nb) % n_cols,
                       "n_pixels": np.bincount(ids, minlength=nb), "n_aoi": n_aoi, "n_eval": n_wet})
    df["wetland_frac"] = np.where(df.n_aoi > 0, df.n_eval / df.n_aoi.clip(lower=1), 0.0)
    if proxy_px is not None:
        p = proxy_px.ravel()
        ok = ev & np.isfinite(p)
        df["proxy"] = [float(np.median(p[ok & (ids == b)])) if (ok & (ids == b)).any() else np.nan for b in range(nb)]
    else:
        df["proxy"] = np.nan
    return df


def _score(df: pd.DataFrame, folds: np.ndarray, n_folds: int) -> float:
    """Imbalance across folds (lower is better); NaN-safe (blocks without evaluable pixels have no proxy)."""
    s = 0.0
    for col in ("wetland_frac", "proxy"):
        v = df[col].to_numpy(dtype=float)
        if not np.isfinite(v).any():
            continue
        means = [np.nanmean(v[folds == k]) if np.isfinite(v[folds == k]).any() else np.nanmean(v) for k in range(n_folds)]
        sd = np.nanstd(v)
        s += np.std(means) / sd if sd > 0 else 0.0
    tot = df.n_eval.sum()
    if tot > 0:
        shares = [df.n_eval.to_numpy()[folds == k].sum() / tot for k in range(n_folds)]
        s += 2.0 * np.std(shares) * n_folds
    return float(s)


def assign_folds(df: pd.DataFrame, n_folds: int, seed: int, n_trials: int = 500) -> np.ndarray:
    """Return fold per block (aligned with df rows)."""
    rng = np.random.default_rng(seed)
    key = df.proxy.fillna(df.proxy.median() if df.proxy.notna().any() else 0).to_numpy()
    order = np.lexsort((-df.n_eval.to_numpy(), key))
    best, best_s = None, np.inf
    for _ in range(n_trials):
        folds = np.empty(len(df), dtype=int)
        start = rng.integers(n_folds)
        for g in range(0, len(order), n_folds):
            idx = order[g:g + n_folds]
            folds[idx] = (rng.permutation(n_folds)[: len(idx)] + start) % n_folds
        s = _score(df, folds, n_folds)
        if best is None or s < best_s:
            best, best_s = folds.copy(), s
    return best


def fold_summary(df: pd.DataFrame, folds: np.ndarray, n_folds: int) -> pd.DataFrame:
    d = df.assign(fold=folds)
    return d.groupby("fold").agg(blocks=("block", "size"), eval_pixels=("n_eval", "sum"),
                                 wetland_frac=("wetland_frac", "mean"), proxy=("proxy", "mean")).reindex(range(n_folds))
