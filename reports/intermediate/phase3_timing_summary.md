# Phase 2 baselines — run `phase3_timing`

Skill (C1) is measured on the pre-registered **placebo windows** (undisturbed), on held-out test folds. Values: mean ± std over the 5 folds (each fold's value averaged over windows and leads >= 1; lead 0 is the secondary analysis of amendment A2).

## mississippi / Track A

| Model | NDVI R² | NDMI R² | NDWI R² | NDVI RMSE | 90% coverage (NDVI) | width (NDVI) |
|---|---|---|---|---|---|---|
| ecotransformer_s0 | 0.589 ± nan | 0.430 ± nan | 0.656 ± nan | 0.114 ± nan | 0.911 ± nan | 0.350 ± nan |

## Attributed NDVI deficit (counterfactual − observed), all folds

Mean over evaluated wetland pixels; [interval] from conformal bounds. Placebo windows should be ≈ 0.

| Site / track | Cutoff | Kind | Model | Lead 0 (A2) | Lead 1 | Mean over leads ≥ 1 | Lead-1 interval |
|---|---|---|---|---|---|---|---|
| mississippi / A | ida | event | ecotransformer_s0 | +0.0842 | -0.0049 | -0.0028 | [-0.1792, +0.1707] |
| mississippi / A | ida_placebo_2018 | placebo | ecotransformer_s0 | +0.0057 | -0.0189 | -0.0279 | [-0.1846, +0.1467] |
