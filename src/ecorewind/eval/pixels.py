"""Pixel table: the time series of every evaluable pixel, extracted once per site x track (Phase 2).

Every model on the ladder reads from the same table, so they are evaluated on exactly the same pixels.
Values are NaN wherever the cube's validity mask is False; nothing is filled here.
The event-quarter _POST partial is appended after the regular quarters (key 'YYYYQn_POST') for lead-0 evaluation;
it is never model history.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..data import blocks as B

PRED_CHANNELS = ("NDVI", "NDMI", "NDWI", "VV", "VH")
STATIC_FEATURES = ("elevation_m", "coast_dist_m", "lc_tree", "lc_grass", "lc_water", "lc_herb_wetland",
                   "lc_mangrove", "lc_other")


@dataclass
class PixelTable:
    site: str
    track: str
    keys: list[str]
    channels: list[str]
    r: np.ndarray          # (n,) row in the grid
    c: np.ndarray          # (n,) column
    fold: np.ndarray       # (n,) CV fold of the pixel's block
    block: np.ndarray      # (n,) block id
    Y: np.ndarray          # (T, C, n) float32, NaN where invalid
    static: dict = field(default_factory=dict)   # name -> (n,)
    shape: tuple = ()
    res: float = 10.0
    data_hash: str = ""

    @property
    def n(self) -> int:
        return len(self.r)

    def save(self, path: str | Path):
        np.savez(path, r=self.r, c=self.c, fold=self.fold, block=self.block, Y=self.Y,
                 meta=np.array([self.site, self.track, self.data_hash, str(self.res), *map(str, self.shape)]),
                 keys=np.array(self.keys), channels=np.array(self.channels),
                 **{f"static__{k}": v for k, v in self.static.items()})

    @classmethod
    def load(cls, path: str | Path) -> "PixelTable":
        z = np.load(path)
        m = list(z["meta"])
        static = {k[len("static__"):]: z[k] for k in z.files if k.startswith("static__")}
        return cls(m[0], m[1], list(z["keys"]), list(z["channels"]), z["r"], z["c"], z["fold"], z["block"],
                   z["Y"], static, (int(m[4]), int(m[5])), float(m[3]), m[2])


def build_table(cube, folds_npz: str | Path, static_npz: str | Path, block_m: float,
                channels=PRED_CHANNELS, mask_key: str = "eval_main", extra_exports: str | Path | None = None,
                max_reflectance: float = 1.0) -> PixelTable:
    """extra_exports: folder with placebo _PPOST GeoTIFFs (amendment A3), appended as rows like the _POST partial."""
    f = np.load(folds_npz)
    r, c = np.nonzero(f[mask_key])
    res = abs(cube.transform[0])
    src = [(k, cube.data, cube.valid, t) for t, k in enumerate(cube.keys)]
    src += [(k, cube.g["partial_data"], cube.g["partial_valid"], t) for t, k in enumerate(cube.partial_keys)
            if k.endswith("_POST")]
    if extra_exports:
        from ..data.cube import load_period
        for tif in sorted(Path(extra_exports).glob(f"{cube.site}_{cube.track}_*_PPOST.tif")):
            k = tif.stem.split("_", 2)[2]
            if k.startswith("S1_"):
                continue
            d, v, *_ = load_period(Path(extra_exports), cube.site, cube.track, k, cube.g.attrs.get("max_reflectance", max_reflectance))
            src.append((k, d[None], v[None], 0))
    Y = np.full((len(src), len(channels), len(r)), np.nan, dtype="float32")
    for j, (_, D, V, t) in enumerate(src):
        for i, ch in enumerate(channels):
            ci = cube.channel(ch)
            Y[j, i] = np.where(np.asarray(V[t, ci])[r, c], np.asarray(D[t, ci])[r, c], np.nan)
    st = np.load(static_npz)
    static = {k: st[k][r, c].astype("float32") for k in STATIC_FEATURES if k in st.files}
    bid = B.block_ids(cube.shape, res, block_m)[r, c]
    return PixelTable(cube.site, cube.track, [k for k, *_ in src], list(channels), r.astype("int32"), c.astype("int32"),
                      f["fold"][r, c].astype("int8"), bid.astype("int32"), Y, static, tuple(cube.shape), res,
                      cube.data_hash)
