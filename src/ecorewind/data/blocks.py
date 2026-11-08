"""Spatial blocks and fold buffers (MASTER_PROMPT §6.6).

Blocks are squares of `block_m` metres counted from the shared grid origin, so a block covers exactly
the same ground in Track A (10 m) and Track B (30 m). block_m must be a multiple of 30 m. Edge blocks
may be partial. A pixel is a buffer pixel when it lies within `buffer_m` of an edge (or corner) shared
with a block of a different fold.

Buffers are split-specific: for CV split k only boundaries between the test fold k and the training folds
matter (a boundary between two training folds leaks nothing). `split_buffer(k)` is excluded from training
targets and normalisation in split k; a test pixel is evaluated only outside `split_buffer(k)`. The union
over splits of the test-side buffers equals `buffer_mask` (the evaluation exclusion).
"""
from __future__ import annotations

import numpy as np


def block_index(shape: tuple[int, int], res: float, block_m: float) -> tuple[np.ndarray, np.ndarray]:
    """Per-pixel block row and column."""
    if block_m % 30:
        raise ValueError("block_m must be a multiple of 30 so blocks nest in both tracks")
    px = int(round(block_m / res))
    rows, cols = np.indices(shape)
    return rows // px, cols // px


def n_blocks(shape: tuple[int, int], res: float, block_m: float) -> tuple[int, int]:
    px = int(round(block_m / res))
    return -(-shape[0] // px), -(-shape[1] // px)


def block_ids(shape, res, block_m) -> np.ndarray:
    br, bc = block_index(shape, res, block_m)
    return br * n_blocks(shape, res, block_m)[1] + bc


def fold_raster(fold_of_block: np.ndarray, shape, res, block_m) -> np.ndarray:
    """fold_of_block: (n_block_rows, n_block_cols) int array -> per-pixel fold."""
    br, bc = block_index(shape, res, block_m)
    return fold_of_block[br, bc]


def buffer_mask(fold_of_block: np.ndarray, shape, res, block_m, buffer_m) -> np.ndarray:
    px = block_m / res
    br, bc = block_index(shape, res, block_m)
    rows, cols = np.indices(shape)
    # distance (m) from pixel centre to the four edges of its own block
    d_top = (rows + 0.5 - br * px) * res
    d_bot = ((br + 1) * px - rows - 0.5) * res
    d_left = (cols + 0.5 - bc * px) * res
    d_right = ((bc + 1) * px - cols - 0.5) * res
    F = np.pad(fold_of_block, 1, constant_values=-1)       # -1 = outside the grid: never a boundary
    own = F[br + 1, bc + 1]

    def differs(dr, dc):
        nb = F[br + 1 + dr, bc + 1 + dc]
        return (nb != own) & (nb != -1)

    near = {"t": d_top < buffer_m, "b": d_bot < buffer_m, "l": d_left < buffer_m, "r": d_right < buffer_m}
    buf = (near["t"] & differs(-1, 0)) | (near["b"] & differs(1, 0)) | (near["l"] & differs(0, -1)) | (near["r"] & differs(0, 1))
    buf |= (near["t"] & near["l"] & differs(-1, -1)) | (near["t"] & near["r"] & differs(-1, 1))
    buf |= (near["b"] & near["l"] & differs(1, -1)) | (near["b"] & near["r"] & differs(1, 1))
    return buf


def split_buffer(fold_of_block: np.ndarray, k: int, shape, res, block_m, buffer_m) -> np.ndarray:
    """Buffer for CV split k: within buffer_m of a boundary between fold k and any other fold (both sides)."""
    return buffer_mask((fold_of_block == k).astype(int), shape, res, block_m, buffer_m)
