# Phase 1 report: data cube, masks, blocks, folds

Status: **Phase 1 gate PASS.** Pre-registration final at commit `869a2bc` (`configs/preregistration.yaml`).
Run 2026-10-27 in Colab (CPU). Outputs: `MyDrive/EcoRewind2/phase1/` (folds, static, norm, figures, summary).

## What changed

- Zarr cubes per site × track (`scripts/build_cube.py`): 12 channels (6 bands, NDVI, NDWI, NDMI, VV, VH, VH/VV),
  per-channel validity, clear-observation and S1 counts; event quarter only as PRE/POST partials; source hash recorded.
  Cubes live on the Colab VM (not saved to Drive for space); rebuilt per session.
- Validity: indices only where their own inputs are > 0 (HLS negative reflectance); SAR masked where no acquisitions.
- Static layers: elevation, coast distance (local), WorldCover one-hot, wetland masks (main 90|95; strict = eroded 1 px),
  evaluation restricted to the original AOI.
- **Blocks 3.84 km** (deviation from 2.56 km: 2.56 km does not nest at 30 m). **Split-specific buffers**, 640 m each
  side: only boundaries touching the test fold are buffered in each split (leak test added).
- 5 folds per site, identical for both tracks, stratified by wetland share and an NDVI-drop proxy (stratification only).
- Normalisation per site × track × cutoff × fold from training-fold pixels outside the split buffer and pre-cutoff quarters.
- Pre-registration (`configs/preregistration.yaml`) and a HURDAT2 storm check (`scripts/check_storm_record.py`).
- Bug fixed: `.gitignore` excluded `src/ecorewind/data/`; Phase 0 modules were missing from git.

## Measured

| | Everglades A | Everglades B | Mississippi A | Mississippi B |
|---|---|---|---|---|
| Grid | 2202 × 2199 (10 m) | 734 × 733 (30 m) | 2238 × 2235 | 746 × 745 |
| Blocks / folds | 6 × 6 / 7–8 blocks per fold | same | 6 × 6 / 7–8 per fold | same |
| Evaluable px (main / strict) | 1,991,268 / 1,940,460 | 224,577 / 214,234 | 744,218 / 619,360 | 83,914 / 56,419 |
| Evaluation buffer | 42.5 % of grid | 42.0 % | 43.2 % | 42.6 % |
| Training pixels lost per split | 10.4 % | 10.2 % | 10.3 % | 10.2 % |
| Patches per fold | 54–66 (128 px) | 22–28 (64 px) | 54–63 | 22–26 |

Folds are balanced: evaluable pixels per fold within ±10 % of the mean; mean wetland share 0.91–0.95 (Everglades)
and 0.34–0.38 (Mississippi); proxy means within 0.02 across folds.

Storm check (NOAA HURDAT2 to 2025, 200 km radius): ida_placebo_2018 and both Irma placebos clean;
**ida_placebo_2019 conflicted** (Barry 65 kt at 99 km inside the cutoff quarter; Olga 45 kt at 87 km);
**TS Gordon (50 kt) passed 15 km from the Everglades site on 2018-09-03**, inside Irma's original window.

## Decisions (user, 2026-10-27)

1. `ida_placebo_2019` excluded; replaced by Track B-only Ida placebos on 2015-08-29 and 2016-08-29 (H ≤ 3),
   — storm check clean. Track A keeps `ida_placebo_2018` plus the placebo-in-space test.
2. `irma` capped at `max_horizon: 3` (2017Q4–2018Q2); horizons 4–8 only as a labelled Irma + Gordon compound period.

## Surprises and open issues

1. **Evaluation loses ~42 % of each grid to buffers** (one Track A patch width between folds, as the plan requires).
   Remaining evaluable area is still large (0.74–1.99 M pixels at 10 m).
2. **Track B has few patches** (~95 training patches of 64 px per split). Phase 3 should sample Track B at stride 32
   inside training blocks (overlap within a block is allowed by the plan); to be fixed in the experiment configs.
3. **Mississippi strict wetland mask is much smaller at 30 m** (56k vs 84k px): fragmented marsh loses edge pixels.
4. **Everglades Track A Irma history = 8 quarters, the first (2015Q3) empty**: the first input step is fully gap-filled.
5. The NDVI-drop proxy is near zero at block scale in Mississippi (+0.01) and slightly negative in the Everglades (−0.02).
   Used only for stratification; not interpreted (no post-event analysis before the models exist).

## Gate

Cubes built ✅ · folds visualised (`figures/folds_*.png`) ✅ · 29 tests green (leakage, temporal cutoff, masking,
indices, grid nesting, SAR, buffers, folds) ✅ · pre-registration final (commit `869a2bc`, storm re-check clean for all 7 windows) ✅.

## Compute used

Colab Pro CPU runtime: **0.05 compute units** (198.98 → 198.93). No GPU. Earth Engine: none this phase.
Running total: Colab 1.07 CCU of 200; Earth Engine 96.6 EECU-h of 150.
