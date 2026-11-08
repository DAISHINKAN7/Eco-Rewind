# Phase 2 baselines — run `phase3_core_v1`

Skill (C1) is measured on the pre-registered **placebo windows** (undisturbed), on held-out test folds. Values: mean ± std over the 5 folds (each fold's value averaged over windows and leads >= 1; lead 0 is the secondary analysis of amendment A2).

## everglades / Track B

| Model | NDVI R² | NDMI R² | NDWI R² | NDVI RMSE | 90% coverage (NDVI) | width (NDVI) |
|---|---|---|---|---|---|---|
| convlstm_s0 | 0.173 ± 0.361 | -0.357 ± 0.638 | -0.279 ± 0.467 | 0.146 ± 0.046 | 0.895 ± 0.035 | 0.458 ± 0.119 |
| convlstm_s1 | 0.099 ± 0.323 | -0.008 ± 0.330 | -0.621 ± 0.445 | 0.149 ± 0.024 | 0.875 ± 0.027 | 0.479 ± 0.092 |
| ecotransformer_s0 | 0.603 ± 0.098 | 0.545 ± 0.090 | 0.218 ± 0.249 | 0.098 ± 0.016 | 0.903 ± 0.023 | 0.297 ± 0.042 |
| ecotransformer_s1 | 0.594 ± 0.118 | 0.505 ± 0.078 | 0.171 ± 0.315 | 0.099 ± 0.018 | 0.901 ± 0.026 | 0.293 ± 0.047 |
| simvp_s0 | 0.694 ± 0.084 | 0.525 ± 0.109 | 0.426 ± 0.196 | 0.090 ± 0.014 | 0.900 ± 0.022 | 0.259 ± 0.026 |
| simvp_s1 | 0.664 ± 0.116 | 0.570 ± 0.097 | 0.388 ± 0.243 | 0.093 ± 0.016 | 0.893 ± 0.021 | 0.258 ± 0.037 |

## Attributed NDVI deficit (counterfactual − observed), all folds

Mean over evaluated wetland pixels; [interval] from conformal bounds. Placebo windows should be ≈ 0.

| Site / track | Cutoff | Kind | Model | Lead 0 (A2) | Lead 1 | Mean over leads ≥ 1 | Lead-1 interval |
|---|---|---|---|---|---|---|---|
| everglades / B | irma | event | convlstm_s0 | +0.0500 | +0.0331 | +0.0305 | [-0.1682, +0.2328] |
| everglades / B | irma | event | convlstm_s1 | +0.0453 | +0.0397 | +0.0349 | [-0.2154, +0.2923] |
| everglades / B | irma | event | ecotransformer_s0 | +0.0511 | +0.0509 | +0.0398 | [-0.1438, +0.2431] |
| everglades / B | irma | event | ecotransformer_s1 | +0.0563 | +0.0532 | +0.0408 | [-0.1329, +0.2363] |
| everglades / B | irma | event | simvp_s0 | +0.0191 | +0.0170 | +0.0252 | [-0.1402, +0.1638] |
| everglades / B | irma | event | simvp_s1 | +0.0251 | +0.0274 | +0.0344 | [-0.1359, +0.1831] |
| everglades / B | irma_placebo_2015 | placebo | convlstm_s0 | +0.0112 | -0.1142 | -0.1206 | [-0.3224, +0.0884] |
| everglades / B | irma_placebo_2015 | placebo | convlstm_s1 | -0.0332 | -0.1660 | -0.1344 | [-0.4279, +0.0852] |
| everglades / B | irma_placebo_2015 | placebo | ecotransformer_s0 | -0.0127 | +0.0188 | -0.0149 | [-0.1537, +0.1904] |
| everglades / B | irma_placebo_2015 | placebo | ecotransformer_s1 | -0.0048 | +0.0247 | -0.0121 | [-0.1407, +0.1874] |
| everglades / B | irma_placebo_2015 | placebo | simvp_s0 | +0.0337 | +0.0441 | -0.0022 | [-0.0790, +0.1612] |
| everglades / B | irma_placebo_2015 | placebo | simvp_s1 | +0.0233 | +0.0433 | -0.0019 | [-0.0761, +0.1611] |
| everglades / B | irma_placebo_2016 | placebo | convlstm_s0 | -0.0254 | -0.0886 | -0.0733 | [-0.3177, +0.1162] |
| everglades / B | irma_placebo_2016 | placebo | convlstm_s1 | -0.0306 | -0.0913 | -0.0608 | [-0.3568, +0.1811] |
| everglades / B | irma_placebo_2016 | placebo | ecotransformer_s0 | -0.0465 | -0.0704 | -0.0288 | [-0.2768, +0.1314] |
| everglades / B | irma_placebo_2016 | placebo | ecotransformer_s1 | -0.0437 | -0.0684 | -0.0270 | [-0.2617, +0.1203] |
| everglades / B | irma_placebo_2016 | placebo | simvp_s0 | -0.0347 | -0.0423 | -0.0144 | [-0.2008, +0.1076] |
| everglades / B | irma_placebo_2016 | placebo | simvp_s1 | -0.0307 | -0.0456 | -0.0198 | [-0.2097, +0.1117] |
