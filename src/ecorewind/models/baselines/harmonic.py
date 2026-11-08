"""Rung 1: per-pixel harmonic regression, CCDC-style (MASTER_PROMPT §7.4).

y(t) = a + b (t - t0) + c1 cos(2 pi t / 4) + s1 sin(2 pi t / 4) [+ c2 cos(pi t)], t in quarters.
With quarterly sampling the semi-annual harmonic is at the Nyquist frequency, so only its cosine term exists.
Robust fit: Huber IRLS on valid pre-cutoff values only; pixels with fewer than `min_obs` valid values fall
back to seasonal climatology. Forecast = the fitted model evaluated at the target quarters.
`trend=False` (rung "harmonic_notrend", pre-registration amendment A1) drops the b (t - t0) term: with 8-33
quarterly points the fitted slope extrapolates poorly (Phase 2 report, issue 1). No parameter is tuned.
"""
from __future__ import annotations

import numpy as np

from ...data.periods import parse_q
from .simple import Baseline, Climatology


def qtime(key: str) -> float:
    y, q = parse_q(key)
    return y * 4 + (q - 1)


def design(t: np.ndarray, t0: float, semiannual: bool, trend: bool = True) -> np.ndarray:
    cols = [np.ones_like(t), *([(t - t0) / 4.0] if trend else []), np.cos(2 * np.pi * t / 4), np.sin(2 * np.pi * t / 4)]
    if semiannual:
        cols.append(np.cos(np.pi * t))
    return np.stack(cols, axis=1)


def huber_irls(X: np.ndarray, Y: np.ndarray, iters: int = 5, k: float = 1.345, ridge: float = 1e-6) -> np.ndarray:
    """X (T, P); Y (T, n) with NaN = missing. Returns coefficients (P, n)."""
    M = np.isfinite(Y)
    Yz = np.where(M, Y, 0.0)
    W = M.astype("float64")
    P = X.shape[1]
    beta = np.zeros((P, Y.shape[1]))
    for _ in range(iters):
        A = np.einsum("tp,tn,tq->npq", X, W, X) + ridge * np.eye(P)
        b = np.einsum("tp,tn,tn->np", X, W, Yz)
        beta = np.linalg.solve(A, b[..., None])[..., 0].T
        res = np.where(M, Yz - X @ beta, np.nan)
        scale = 1.4826 * np.nanmedian(np.abs(res), axis=0)
        scale = np.where(scale > 1e-9, scale, 1e-9)
        u = np.abs(res) / (k * scale)
        W = np.where(M, np.where(u <= 1, 1.0, 1.0 / np.maximum(u, 1e-12)), 0.0)
    return beta


class Harmonic(Baseline):
    name = "harmonic"

    def __init__(self, min_obs: int = 7, semiannual: bool = True, iters: int = 5, trend: bool = True):
        self.min_obs, self.semiannual, self.iters, self.trend = min_obs, semiannual, iters, trend
        if not trend:
            self.name = "harmonic_notrend"

    def predict(self, split, idx):
        H = split.hist(idx).astype("float64")                       # (T, C, n)
        th = np.array([qtime(k) for k in split.hist_keys])
        tt = np.array([qtime(k) for k in split.tgt_keys])
        t0 = th[-1]
        Xh, Xt = design(th, t0, self.semiannual, self.trend), design(tt, t0, self.semiannual, self.trend)
        clim = Climatology().predict(split, idx)[0]
        out = np.full((len(tt), H.shape[1], H.shape[2]), np.nan, dtype="float32")
        for ci in range(H.shape[1]):
            Y = H[:, ci]
            enough = np.isfinite(Y).sum(0) >= max(self.min_obs, Xh.shape[1] + 2)
            pred = np.full((len(tt), Y.shape[1]), np.nan)
            if enough.any():
                beta = huber_irls(Xh, Y[:, enough], self.iters)
                pred[:, enough] = Xt @ beta
            out[:, ci] = np.where(enough, pred, clim[:, ci])
        return out, out, out
