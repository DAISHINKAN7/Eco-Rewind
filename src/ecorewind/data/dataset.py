"""Patch sampling and model inputs (MASTER_PROMPT §6.4, §6.7).

- Patches: size x size windows at `stride` inside a single block, fully inside the grid. Training patches
  come only from training-fold blocks; targets exclude buffer pixels via the loss mask.
- Inputs: the last T_in quarters strictly before the cutoff. Invalid input values are filled with the pixel's
  pre-cutoff seasonal climatology (same calendar quarter), else its pre-cutoff mean, else 0 after
  normalisation (= the training median); the validity mask is always passed alongside. Targets are never filled.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import normalise
from .blocks import n_blocks


@dataclass(frozen=True)
class Patch:
    row: int
    col: int
    size: int
    block: int
    fold: int


def patch_origins(shape, res, block_m, fold_of_block: np.ndarray, size: int, stride: int) -> list[Patch]:
    px = int(round(block_m / res))
    nbr, nbc = n_blocks(shape, res, block_m)
    out = []
    for br in range(nbr):
        for bc in range(nbc):
            r_end = min((br + 1) * px, shape[0])
            c_end = min((bc + 1) * px, shape[1])
            for r in range(br * px, r_end - size + 1, stride):
                for c in range(bc * px, c_end - size + 1, stride):
                    out.append(Patch(r, c, size, br * nbc + bc, int(fold_of_block[br, bc])))
    return out


def season(key: str) -> int:
    return int(key[-1]) - 1


def climatology(data, valid, keys: list[str], hist_idx: list[int], rs: slice, cs: slice):
    """Per-pixel pre-cutoff means by calendar quarter (4, C, h, w) and overall (C, h, w); NaN where unseen."""
    s_sum = s_n = None
    for t in hist_idx:
        d = np.asarray(data[t, :, rs, cs], dtype="float64")
        v = np.asarray(valid[t, :, rs, cs]) & np.isfinite(d)
        if s_sum is None:
            s_sum = np.zeros((4, *d.shape))
            s_n = np.zeros((4, *d.shape))
        q = season(keys[t])
        s_sum[q] += np.where(v, d, 0)
        s_n[q] += v
    with np.errstate(invalid="ignore", divide="ignore"):
        seas = s_sum / s_n
        overall = s_sum.sum(0) / s_n.sum(0)
    return seas.astype("float32"), overall.astype("float32")


def history_window(hist_idx: list[int], t_in: int) -> list[int]:
    if len(hist_idx) < t_in:
        raise ValueError(f"only {len(hist_idx)} pre-cutoff quarters, need {t_in}")
    return hist_idx[-t_in:]


def make_input(cube, hist_idx: list[int], t_in: int, p: Patch, stats: dict):
    """x (T_in, C, h, w) normalised and gap-filled; m (T_in, C, h, w) validity. Reads nothing at/after cutoff."""
    rs, cs = slice(p.row, p.row + p.size), slice(p.col, p.col + p.size)
    win = history_window(hist_idx, t_in)
    seas, overall = climatology(cube.data, cube.valid, cube.keys, hist_idx, rs, cs)
    xs, ms = [], []
    for t in win:
        d = np.asarray(cube.data[t, :, rs, cs], dtype="float32")
        m = np.asarray(cube.valid[t, :, rs, cs]) & np.isfinite(d)
        fill = np.where(np.isfinite(seas[season(cube.keys[t])]), seas[season(cube.keys[t])], overall)
        d = np.where(m, d, fill)
        xs.append(d)
        ms.append(m)
    x = normalise.apply(np.stack(xs), stats, cube.channels, axis=1)
    return np.nan_to_num(x, nan=0.0), np.stack(ms)


def make_target(cube, target_idx: list[int], p: Patch, loss_mask: np.ndarray):
    """y (H, C, h, w) raw values (NaN where invalid); ym validity & loss mask (buffers excluded)."""
    rs, cs = slice(p.row, p.row + p.size), slice(p.col, p.col + p.size)
    y = np.stack([np.asarray(cube.data[t, :, rs, cs], dtype="float32") for t in target_idx])
    ym = np.stack([np.asarray(cube.valid[t, :, rs, cs]) for t in target_idx]) & np.isfinite(y)
    return y, ym & loss_mask[rs, cs][None, None]
