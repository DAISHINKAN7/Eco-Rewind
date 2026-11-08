"""Per-channel validity rules (MASTER_PROMPT §6.2, decisions in reports/phase_0_report.md).

Optical: a pixel is observed where every reflectance band is finite, not nodata, and n_clear_obs > 0.
A reflectance band is valid where the pixel is observed and 0 < value < max_reflectance (HLS stores small
negative values over dark water; 0 is a fill). An index is valid only where all of its own input bands are.
SAR: valid where n_s1_obs > 0 and the value is finite and not nodata.
Invalid pixels are never filled here; values stay as they are and the mask decides.
"""
from __future__ import annotations

import numpy as np

REFLECTANCE = ("Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2")
SAR = ("VV", "VH", "VH_VV")
INDICES = {"NDVI": ("NIR", "Red"), "NDWI": ("Green", "NIR"), "NDMI": ("NIR", "SWIR1")}
CHANNELS = (*REFLECTANCE, *INDICES, *SAR)


def finite_not_nodata(a: np.ndarray, nodata) -> np.ndarray:
    m = np.isfinite(a)
    if nodata is not None:
        m &= a != nodata
    return m


def optical_valid(refl: dict[str, np.ndarray], n_clear: np.ndarray, nodata=None,
                  max_reflectance: float = 1.0) -> dict[str, np.ndarray]:
    """refl: reflectance (already scaled to 0-1) per band name. Returns validity per band."""
    observed = n_clear > 0
    for b in REFLECTANCE:
        observed &= finite_not_nodata(refl[b], nodata)
    return {b: observed & (refl[b] > 0) & (refl[b] < max_reflectance) for b in REFLECTANCE}


def sar_valid(vv: np.ndarray, vh: np.ndarray, n_s1: np.ndarray, nodata=None) -> np.ndarray:
    return (n_s1 > 0) & finite_not_nodata(vv, nodata) & finite_not_nodata(vh, nodata)
