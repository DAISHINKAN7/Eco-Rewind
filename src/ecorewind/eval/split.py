"""One evaluation split: a cutoff (event or placebo) x a test fold, over a pixel table.

Roles: test fold k (predicted and scored), calibration fold (k+1) mod n_folds (conformal scores only),
training folds = the rest (used by models that learn across pixels, e.g. LightGBM, and as DiD donors).
Leads count quarters after the cutoff quarter: lead 1 = first full quarter after the event / fake event;
lead 0 (optional, amendment A2) = the cutoff quarter itself (event: post-landfall partial composite).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..data.events import Cutoff, quarters_between, split_indices
from ..data.periods import parse_q


@dataclass
class Split:
    table: object
    cutoff: Cutoff
    k: int
    n_folds: int
    hist_idx: list[int]
    tgt_idx: list[int]
    leads: list[int]
    test: np.ndarray
    calib: np.ndarray
    train: np.ndarray

    @property
    def cal_fold(self) -> int:
        return (self.k + 1) % self.n_folds

    def hist(self, idx: np.ndarray) -> np.ndarray:
        """(T_hist, C, len(idx)) history values; never touches quarters at/after the cutoff."""
        return self.table.Y[self.hist_idx][:, :, idx]

    def target(self, idx: np.ndarray) -> np.ndarray:
        return self.table.Y[self.tgt_idx][:, :, idx]

    @property
    def hist_keys(self) -> list[str]:
        return [self.table.keys[i] for i in self.hist_idx]

    @property
    def tgt_keys(self) -> list[str]:
        return [self.table.keys[i].partition("_")[0] for i in self.tgt_idx]     # "2021Q3_POST" -> "2021Q3"

    def distance(self) -> list[int]:
        """Quarters from the last history quarter to each target quarter (cutoff quarter is skipped)."""
        last = parse_q(self.hist_keys[-1])
        return [quarters_between(last, parse_q(k)) for k in self.tgt_keys]


def make_split(table, cutoff: Cutoff, k: int, n_folds: int, lead0: bool = False) -> Split:
    hist, tgt = split_indices(table.keys, cutoff, lead0)
    cq = parse_q(cutoff.quarter)
    leads = [quarters_between(cq, parse_q(table.keys[i].partition("_")[0])) for i in tgt]
    cal = (k + 1) % n_folds
    f = table.fold
    return Split(table, cutoff, k, n_folds, hist, tgt, leads,
                 np.nonzero(f == k)[0], np.nonzero(f == cal)[0], np.nonzero((f != k) & (f != cal))[0])
