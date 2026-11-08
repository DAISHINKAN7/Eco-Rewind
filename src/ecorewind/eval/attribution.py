"""Attributed loss (MASTER_PROMPT §7.3).

Deficit = counterfactual - observed, per valid pixel and target quarter (positive = observed is lower than
expected, i.e. loss). Reported as the mean deficit over evaluated pixels and as an area-weighted total
(deficit x hectares). Interval bounds use the conformal interval: [lo - y, hi - y]; summing bounds over
pixels assumes perfectly correlated errors, so total intervals are conservative.
"""
from __future__ import annotations

import numpy as np


def deficit(y, q50, lo=None, hi=None, pixel_ha: float = 0.01) -> dict:
    m = np.isfinite(y) & np.isfinite(q50)
    if not m.any():
        return {"n": 0, "mean": np.nan, "total": np.nan, "mean_lo": np.nan, "mean_hi": np.nan, "total_lo": np.nan, "total_hi": np.nan}
    d = q50[m] - y[m]
    out = {"n": int(m.sum()), "mean": float(d.mean()), "total": float(d.sum() * pixel_ha)}
    if lo is not None and hi is not None and np.isfinite(lo[m]).all() and np.isfinite(hi[m]).all():
        dl, dh = lo[m] - y[m], hi[m] - y[m]
        out.update(mean_lo=float(dl.mean()), mean_hi=float(dh.mean()), total_lo=float(dl.sum() * pixel_ha),
                   total_hi=float(dh.sum() * pixel_ha))
    else:
        out.update(mean_lo=np.nan, mean_hi=np.nan, total_lo=np.nan, total_hi=np.nan)
    return out
