# Phase 2 report: evaluation harness + CPU baselines

Status: **gate PASS** (baseline table on all folds and both tracks, placebo runs for every baseline, conformal
coverage reported). Run `phase2_baselines_v1`, 2026-10-28, Colab CPU. Full table: `reports/intermediate/phase2_baselines_v1_summary.md`.

## What changed

- Shared harness (`src/ecorewind/eval/`): pixel table, splits (test / calibration / training folds), metrics,
  split-conformal / CQR intervals calibrated on placebo windows only, attribution, per-pixel maps.
- Baselines: persistence, seasonal climatology, harmonic regression (Huber IRLS), matched DiD / synthetic control,
  LightGBM quantile (direct multi-horizon). Resumable runner `scripts/run_baselines.py`.
- `scripts/cubes_cache.py`: cubes saved to Drive once and restored in later sessions.

## Measured (placebo windows, held-out test folds; mean ± std over 5 folds)

| Site / track | Best baseline | NDVI R² | NDMI R² | NDWI R² | Climatology NDVI R² | Harmonic NDVI R² |
|---|---|---|---|---|---|---|
| Everglades B | synth_control | 0.765 ± 0.060 | 0.732 ± 0.046 | 0.546 ± 0.116 | 0.702 | 0.594 |
| Mississippi A | synth_control | 0.716 ± 0.086 | 0.643 ± 0.086 | 0.780 ± 0.087 | 0.699 | 0.534 |
| Mississippi B | synth_control | 0.458 ± 0.102 | 0.310 ± 0.160 | 0.497 ± 0.093 | 0.183 | 0.032 |

- **Conformal coverage of the 90 % intervals: 0.888–0.899 for every model, site and track** (nominal 0.90).
  Intervals are calibrated on placebo calibration folds and evaluated on placebo test folds of the same windows,
  so this confirms the procedure, not yet transfer to the event (leads 4–8 for Ida are extrapolated).
- Ranking is consistent across sites: synth_control ≥ climatology ≈ LightGBM > harmonic > persistence.

## Surprises and open issues

1. **Harmonic regression (the CCDC-style, "domain-standard" baseline) is worse than plain climatology everywhere.**
   With 8–33 quarterly points, the trend term extrapolates poorly. A trend-free / damped variant is a fair addition
   to the ladder (it must be decided before Phase 3 and logged).
2. **Mississippi Track B is weak** (best NDVI R² 0.46): early HLS is Landsat-only with 1–2 clear observations per
   quarter, and the site is 35 % water with fragmented marsh at 30 m. Track A is the primary track for Ida.
3. **Preliminary attribution signal is small compared with placebo spread.** Mean NDVI deficits over all wetland
   pixels: Irma (Track B) −0.012 to +0.056 across models; Irma placebos −0.083 to +0.048. Ida (Track A) −0.009 to
   +0.064; Ida placebos −0.111 to +0.074 (Track B). Persistence and harmonic are biased in placebo windows too.
   This is not the pre-registered Phase 4 test (per-model distributions over windows × folds × seeds), but it says
   the site-mean, quarterly signal is weak; damage may be spatially concentrated (coastal mangrove, outer marsh)
   and may have partly recovered by the first full quarter. Not used to choose or tune anything.
4. **Model spread is already large** (e.g. Irma B lead 1: −0.012 to +0.056), which supports claim C3 whatever
   Phase 4 shows.
5. The event-quarter `_POST` partial (the most immediate post-storm observation) is not evaluated: the harness starts
   at the first full quarter, as pre-registered. Adding it as "lead 0" would be a pre-registration change.

## Compute used

Colab CPU: 0.28 CCU (198.93 → 198.65). Running total: 1.35 of 200 CCU; Earth Engine 96.6 of 150 EECU-h; no GPU yet.

## Addendum — run `phase2_baselines_v2` (amendments A1, A2; 2026-10-27)

Full table: `reports/intermediate/phase2_baselines_v2_summary.md`. Leads ≥ 1 are identical to v1 for the original five baselines.

- **A1:** `harmonic_notrend` ≈ climatology (NDVI R² 0.708 / 0.703 / 0.225 vs 0.702 / 0.699 / 0.183) and far above trended
  harmonic. synth_control is still the strongest rung everywhere; it is the bar for Phase 3.
- **A2, lead 0 (secondary):** the first look at a signal. NDVI deficit, climatology / harmonic_notrend:
  Ida Track A +0.089 (placebo 2018: +0.020); Ida Track B +0.067 (placebos −0.071 to −0.005);
  Irma Track A +0.117 (no Track A placebo). Irma Track B ≈ 0 (−0.015; sparse HLS in the ~1-month POST window).
  synth_control is smaller (Ida A +0.035 vs +0.001; Irma A −0.001, consistent with donor blocks also being hit).
- **Main confound:** the event lead 0 is a ~1-month post-landfall composite; placebo lead 0 is a full quarter. Part of
  the deficit may be seasonal/compositing mismatch, not damage. Control needed before any claim: export
  post-date-equivalent composites (same days of year) for the placebo years, so placebo and event lead 0 match.

## Addendum — run `phase2_baselines_v3` (amendment A3: matched-days placebo lead 0; 2026-10-28)

Leads ≥ 1 unchanged. Lead-0 NDVI deficit, climatology / harmonic_notrend (event vs matched-days placebos):

| Site / track | Event | Placebos (lead 0, `_PPOST`) |
|---|---|---|
| Mississippi A (Ida) | +0.089 | +0.032 (2018) |
| Mississippi B (Ida) | +0.067 | +0.008 (2015), −0.073 (2016), −0.008 (2018) |
| Everglades B (Irma) | −0.015 | −0.068 (2015), −0.067 (2016) |

- Matching the compositing window shrank the Ida A gap (placebo +0.020 → +0.032) but did not remove it: the Ida event
  still sits above every placebo on both tracks (by ~0.06). Irma B is above both placebos by ~0.05, but the placebos
  themselves are biased negative (short 18-day Landsat-only composites), so that comparison is weak.
- synth_control is the most conservative (Ida A +0.035 vs +0.003; Ida B +0.051 vs −0.026 to +0.014). Its Everglades
  2015 lead 0 is NaN: too few valid donor pixels in that 18-day composite.
- Only 1–3 placebo windows per site/track: this is suggestive, not the Phase 4 test (windows × folds × seeds).
