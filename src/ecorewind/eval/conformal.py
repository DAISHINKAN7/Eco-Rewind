"""Split conformal intervals, model-agnostic (MASTER_PROMPT §7.2).

Score s = max(lo_base - y, y - hi_base). For point models lo_base = hi_base = median, so s = |y - median|
(split conformal); for quantile models it is conformalised quantile regression. The interval is
[lo_base - qhat, hi_base + qhat], with qhat the ceil((n+1)(1-alpha))/n empirical quantile of calibration scores.
Calibration uses only undisturbed data: calibration-fold pixels in the pre-registered placebo windows.
"""
from __future__ import annotations

import numpy as np


def scores(y, lo, hi) -> np.ndarray:
    s = np.maximum(lo - y, y - hi)
    return s[np.isfinite(s)]


def qhat(s: np.ndarray, alpha: float = 0.10) -> float:
    n = len(s)
    if n == 0:
        return np.nan
    level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(s, level, method="higher"))


def interval(lo, hi, q: float):
    return lo - q, hi + q
