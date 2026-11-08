"""Forecast metrics on valid pixels only (MASTER_PROMPT §7.1)."""
from __future__ import annotations

import numpy as np


def score(y: np.ndarray, q50: np.ndarray, lo: np.ndarray | None = None, hi: np.ndarray | None = None) -> dict:
    """R2, RMSE, MAE, bias (pred - obs), interval coverage and mean width, over pixels where both are finite."""
    m = np.isfinite(y) & np.isfinite(q50)
    out = {"n": int(m.sum()), "n_total": int(np.isfinite(y).sum())}
    if out["n"] < 2:
        return {**out, "r2": np.nan, "rmse": np.nan, "mae": np.nan, "bias": np.nan, "coverage": np.nan, "width": np.nan}
    yy, pp = y[m].astype("float64"), q50[m].astype("float64")
    err = pp - yy
    sst = np.sum((yy - yy.mean()) ** 2)
    out.update(r2=float(1 - np.sum(err ** 2) / sst) if sst > 0 else np.nan, rmse=float(np.sqrt(np.mean(err ** 2))),
               mae=float(np.mean(np.abs(err))), bias=float(err.mean()))
    if lo is not None and hi is not None:
        mi = m & np.isfinite(lo) & np.isfinite(hi)
        out["coverage"] = float(np.mean((y[mi] >= lo[mi]) & (y[mi] <= hi[mi]))) if mi.any() else np.nan
        out["width"] = float(np.mean(hi[mi] - lo[mi])) if mi.any() else np.nan
    else:
        out["coverage"] = out["width"] = np.nan
    return out
