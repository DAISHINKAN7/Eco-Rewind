"""Rung 1: matched difference-in-differences / synthetic-control style counterfactual (MASTER_PROMPT §7.4).

Donors: training-fold pixels in blocks with the LEAST damage-exposure (block NDVI-drop proxy above the
median of training blocks), matched to the test pixel's land-cover class (herbaceous wetland / mangrove /
other). For every quarter, the donor anomaly = donor mean - donor pre-cutoff seasonal mean. Counterfactual
for a test pixel = its own pre-cutoff seasonal climatology + the donor anomaly of its class.
Donors' post-cutoff observations are used by design (they are the untreated controls); the test pixels'
post-cutoff observations never are. Caveat: if the event affected the donors too, attribution is
conservative (biased towards zero) — reported with the results.
"""
from __future__ import annotations

import warnings

import numpy as np

from .simple import Baseline, Climatology, season, seasonal_climatology

CLASSES = ("lc_herb_wetland", "lc_mangrove")


def lc_class(static: dict, idx: np.ndarray) -> np.ndarray:
    out = np.full(len(idx), len(CLASSES), dtype=int)               # "other"
    for i, k in enumerate(CLASSES):
        if k in static:
            out[static[k][idx] > 0.5] = i
    return out


class SynthControl(Baseline):
    name = "synth_control"

    def __init__(self, block_proxy: dict | None = None, min_donors: int = 200):
        self.block_proxy = block_proxy or {}
        self.min_donors = min_donors

    def fit(self, split):
        tab = split.table
        tr = split.train
        prox = np.array([self.block_proxy.get(int(b), np.nan) for b in tab.block[tr]])
        if np.isfinite(prox).any():
            thr = np.nanmedian(prox)
            donors = tr[np.isfinite(prox) & (prox >= thr)]
        else:
            donors = tr
        self.donor_cls = lc_class(tab.static, donors)
        self.donors = donors
        keys = split.hist_keys + split.tgt_keys
        allY = tab.Y[split.hist_idx + split.tgt_idx]                # donors only: (T, C, n_donors) below
        D = allY[:, :, donors]
        self.anom = {}
        for cls in range(len(CLASSES) + 1):
            sel = self.donor_cls == cls
            if sel.sum() < self.min_donors:
                sel = np.ones(len(donors), bool)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                mean_t = np.nanmean(D[:, :, sel], axis=2)            # (T, C)
            seas, overall = seasonal_climatology(mean_t[: len(split.hist_idx), :, None], split.hist_keys)
            seas, overall = seas[..., 0], overall[..., 0]
            base = np.stack([np.where(np.isfinite(seas[season(k)]), seas[season(k)], overall) for k in keys])
            self.anom[cls] = (mean_t - base)[len(split.hist_idx):]   # (L, C) anomalies at target quarters
        return self

    def predict(self, split, idx):
        clim = Climatology().predict(split, idx)[0]                  # (L, C, n) pixel's own seasonal climatology
        cls = lc_class(split.table.static, idx)
        q = clim.copy()
        for k, a in self.anom.items():
            sel = cls == k
            q[:, :, sel] += a[:, :, None]
        return q, q, q
