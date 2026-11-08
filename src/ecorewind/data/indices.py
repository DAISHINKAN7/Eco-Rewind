"""Normalised-difference indices computed locally from bands (never exported; no -1 fill artefacts).

NDVI = (NIR - Red) / (NIR + Red); NDWI (McFeeters) = (Green - NIR) / (Green + NIR);
NDMI = (NIR - SWIR1) / (NIR + SWIR1). Invalid wherever an input is invalid or the denominator is ~0;
invalid outputs are NaN so they can never be mistaken for a physical value.
"""
from __future__ import annotations

import numpy as np

from .masks import INDICES

EPS = 1e-6


def normalised_difference(a: np.ndarray, b: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a = a.astype("float32", copy=False)
    b = b.astype("float32", copy=False)
    den = a + b
    ok = valid & (np.abs(den) > EPS)
    out = np.full(a.shape, np.nan, dtype="float32")
    out[ok] = (a[ok] - b[ok]) / den[ok]
    return out, ok


def compute_indices(refl: dict[str, np.ndarray], valid: dict[str, np.ndarray]) -> tuple[dict, dict]:
    vals, oks = {}, {}
    for name, (a, b) in INDICES.items():
        vals[name], oks[name] = normalised_difference(refl[a], refl[b], valid[a] & valid[b])
    return vals, oks
