# Data (EcoRewind 2.0, Phase 0 re-export)

Raw v1 exports (`EcoRewind/Everglades`, `EcoRewind/Mississippi`, `EcoRewind/Mississippi_v2` on Drive) are kept
only for the v1-vs-v2 comparison figure. No code reads them. All modelling data comes from the re-export below.

## Collections

Collection IDs are the expected ones; `gee/preflight.py` checks each against the live catalogue
(exists + expected bands) and writes `reports/gee_preflight.md`. Paste its catalogue table here after the run.

| Use | Collection | Bands used |
|---|---|---|
| Track A optical | `COPERNICUS/S2_SR_HARMONIZED` **or** `COPERNICUS/S2_HARMONIZED` (one per site, whole series) | B2 B3 B4 B8 B11 B12 |
| Track A cloud mask | `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` | `cs_cdf` ≥ 0.6 (config) |
| Track B optical | `NASA/HLS/HLSL30/v002` + `NASA/HLS/HLSS30/v002` | L30 B2 B3 B4 B5 B6 B7; S30 B2 B3 B4 B8A B11 B12; `Fmask` |
| SAR | `COPERNICUS/S1_GRD` | VV, VH; IW; both orbit passes |
| Elevation | `COPERNICUS/DEM/GLO30_2024_1` (GLO30 is deprecated) | DEM |
| Land cover | `ESA/WorldCover/v200` (2021, post-Irma) | Map |

**S2 product decision:** recorded per site in `reports/exports/s2_product.json` by the preflight.
SR is used only if it has ≥ 90% of the TOA scene count in **every** Track A quarter (2015Q3–2023Q4);
otherwise TOA for the whole series of that site. Earth Engine SR coverage generally starts in 2017, so expect TOA.
Decision per site: _fill in after preflight_.

## Grids (`configs/sites.yaml`, `src/ecorewind/data/grid.py`)

AOI bounds + 1 km buffer, origin snapped to 30 m so Track A (10 m) and Track B (30 m) nest exactly
(one 30 m pixel = 3 × 3 10 m pixels). The origin is also on the native S2/HLS pixel lattice, so 10 m bands are not resampled.

| Site | CRS | Origin (x, y top-left) | Track A 10 m | Track B 30 m |
|---|---|---|---|---|
| everglades | EPSG:32617 | 509160, 2809200 | 2199 × 2202 | 733 × 734 |
| mississippi | EPSG:32615 | 711930, 3271230 | 2235 × 2238 | 745 × 746 |

## Calendar and event quarters (`configs/tracks.yaml`, `configs/events.yaml`)

Track A 2015Q3–2023Q4, Track B 2013Q2–2023Q4, calendar quarters. The event quarter has no regular composite; it is
exported as `_PRE` (quarter start → landfall − 1 day) and `_POST` (landfall + 3 days → quarter end).
Irma 2017-09-10 → `2017Q3_PRE` = Jul 1–Sep 9, `2017Q3_POST` = Sep 13–30. Ida 2021-08-29 → `2021Q3_PRE` = Jul 1–Aug 28,
`2021Q3_POST` = Sep 1–30.

## Files (Drive folder `EcoRewind2_exports/`)

| Pattern | Bands | Type / scale |
|---|---|---|
| `{site}_A_{period}.tif` | Blue Green Red NIR SWIR1 SWIR2 n_clear_obs doy_mean | int16; reflectance = DN × 1e-4 |
| `{site}_B_{period}.tif` | Blue Green Red NIR SWIR1 SWIR2 n_clear_obs doy_mean water_frac | float32; HLS as stored in EE (scale recorded by preflight probe) |
| `{site}_{A,B}_S1_{period}.tif` | VV VH VH_VV_ratio n_s1_obs | int16; dB = value × 0.01 |
| `{site}_{A,B}_static.tif` | elevation_m worldcover | float32 |

nodata = −32768 everywhere. Count bands (`n_clear_obs`, `n_s1_obs`) are 0, not nodata, where nothing was observed.
Band order and names per file are in `reports/exports/manifest_*.json`; always read bands by name.
320 files total (70 A + 88 B + 158 S1 + 4 static).

## Processing choices

- **Optical:** per-pixel masking (Cloud Score+ for S2; Fmask bits 1–4 for HLS: cloud, adjacent, shadow, snow/ice).
  No scene-level cloud filter. Any reflectance band = 0 → unclear. Same-day overlapping tiles are mosaicked first so
  `n_clear_obs` counts acquisitions, not tiles. Composite = per-pixel median. B11/B12 → 10 m bilinear.
- **HLS water:** Fmask water (bit 5) is not masked; `water_frac` = share of clear observations flagged water.
- **SAR:** dB → linear, same-day same-pass slices mosaicked, per-pixel mean in linear power, → dB. Track B: 10 m linear
  means aggregated (mean) to 30 m before dB. Optional 3×3 focal median (off by default).
- **NDVI / NDWI / NDMI are not exported.** They are computed locally from bands with validity masks (no −1 fill artefact).
- **Static:** DEM bilinear; WorldCover mode-aggregated to 30 m for Track B. Distance to coast is computed locally in
  Phase 1 (distance to WorldCover class 80 within the buffered AOI); EE's distance kernel is limited to 512 px.

## Known limitations

WorldCover post-dates Irma (use only to exclude permanent water / built-up / cropland). S1B failed Dec 2021, so fewer
SAR acquisitions after that. HLS S30 and Track A S2 differ in processing (BRDF/bandpass harmonisation in HLS).
If a site uses S2 TOA, Track A is top-of-atmosphere reflectance.

## Phase 0 outcome (2026-10-27)

- S2 product: **TOA for both sites** (preflight: SR ≈ half the TOA scene count before 2017).
- Validity rule for indices: invalid where any input band of that index is ≤ 0 (HLS has negative reflectance over water).
- Track A NDVI is lower than Track B by 0.06–0.23 (TOA vs surface reflectance); r = 0.84–0.95 between tracks.
- Details and open issues: `reports/phase_0_report.md`.

## Phase 1 design (cube, masks, blocks, folds)

- **Cube** (`scripts/build_cube.py`, `src/ecorewind/data/cube.py`): Zarr per site × track, `(T, C, H, W)` float32 +
  per-channel validity. Channels: Blue, Green, Red, NIR, SWIR1, SWIR2 (reflectance 0–1), NDVI, NDWI (McFeeters),
  NDMI, VV, VH, VH/VV (dB). T = regular quarters; the event quarter exists only as `_PRE` / `_POST` partials.
  `data_hash` = SHA-256 of the source GeoTIFFs, recorded with every derived artefact.
- **Validity** (`masks.py`): optical pixel observed if all bands finite and `n_clear_obs > 0`; a band is valid if
  0 < reflectance < 1.0; an index only where its own inputs are valid; SAR valid where `n_s1_obs > 0`.
- **Blocks: 3.84 km, not the plan's 2.56 km.** 2.56 km is 85.33 px at 30 m, so blocks could not cover identical
  ground in both tracks. 3.84 km = 384 px (Track A, 3 × 128-px patches) = 128 px (Track B, 2 × 64-px patches).
- **Buffers: 640 m each side of a fold boundary** (1.28 km gap = one Track A patch width), **split-specific**:
  in CV split k only boundaries touching the test fold are buffered (excluded from training targets and
  normalisation in that split, and from evaluation). Boundaries between two training folds leak nothing and are kept.
- **Folds**: 5 per site, assigned on the block grid (identical for both tracks), stratified by wetland share and a
  damage-exposure proxy (Track B NDVI drop in the first full post-event quarter vs the same quarter of the two
  previous years), used for nothing else.
- **Normalisation**: median / IQR per channel, per site × track × cutoff × fold, from training-fold pixels outside the
  split buffer and quarters strictly before the cutoff quarter; indices stay in physical units.
- **Gap filling (inputs only)**: pre-cutoff per-pixel seasonal climatology, then pre-cutoff pixel mean, then the
  training median (0 after normalisation); validity masks always passed to the model. Targets are never filled.
- **Distance to coast**: Euclidean distance to WorldCover class 80 inside the buffered grid (proxy; inland water counts).

## Phase 2 evaluation design

- Pixel table per site × track: all evaluable pixels (AOI ∩ wetland_main ∩ not buffer), channels NDVI, NDMI, NDWI,
  VV, VH. Every model is scored on the same pixels; each pixel is predicted once (when its fold is the test fold).
- Split k: test fold k, calibration fold (k+1) mod 5, training folds = the other three.
- Lead = quarters after the cutoff quarter (lead 1 = first full post-event quarter).
- Conformal intervals (90 %): split conformal for point models, CQR for LightGBM; scores from calibration-fold pixels
  in the **placebo windows only** (post-event calibration pixels are damaged). Leads beyond the longest placebo
  horizon reuse its calibration and are flagged `extrapolated_interval` (Ida leads 4–8). Irma Track A has no placebo
  window, so it has point predictions only.
- Skill (claim C1) is reported on placebo windows; metrics on the real-event quarters measure the disturbance,
  not skill, and are never used to rank models.
- Attribution: deficit = counterfactual − observed (positive = loss), mean per pixel and area total (ha);
  interval bounds summed assuming fully correlated errors (conservative).
