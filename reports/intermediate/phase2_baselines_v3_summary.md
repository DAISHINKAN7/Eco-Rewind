# Phase 2 baselines — run `phase2_baselines_v3`

Skill (C1) is measured on the pre-registered **placebo windows** (undisturbed), on held-out test folds. Values: mean ± std over the 5 folds (each fold's value averaged over windows and leads >= 1; lead 0 is the secondary analysis of amendment A2).

## everglades / Track B

| Model | NDVI R² | NDMI R² | NDWI R² | NDVI RMSE | 90% coverage (NDVI) | width (NDVI) |
|---|---|---|---|---|---|---|
| climatology | 0.702 ± 0.084 | 0.705 ± 0.058 | 0.436 ± 0.164 | 0.088 ± 0.018 | 0.890 ± 0.054 | 0.270 ± 0.060 |
| harmonic | 0.594 ± 0.088 | 0.172 ± 0.391 | 0.214 ± 0.218 | 0.105 ± 0.018 | 0.896 ± 0.032 | 0.304 ± 0.051 |
| harmonic_notrend | 0.708 ± 0.075 | 0.700 ± 0.064 | 0.467 ± 0.145 | 0.088 ± 0.017 | 0.890 ± 0.054 | 0.265 ± 0.060 |
| lgbm | 0.737 ± 0.055 | 0.601 ± 0.102 | 0.494 ± 0.147 | 0.083 ± 0.010 | 0.892 ± 0.025 | 0.220 ± 0.010 |
| persistence | 0.613 ± 0.077 | 0.098 ± 0.483 | 0.272 ± 0.195 | 0.100 ± 0.011 | 0.891 ± 0.039 | 0.293 ± 0.026 |
| synth_control | 0.765 ± 0.060 | 0.732 ± 0.046 | 0.546 ± 0.116 | 0.080 ± 0.017 | 0.895 ± 0.058 | 0.237 ± 0.046 |

## mississippi / Track A

| Model | NDVI R² | NDMI R² | NDWI R² | NDVI RMSE | 90% coverage (NDVI) | width (NDVI) |
|---|---|---|---|---|---|---|
| climatology | 0.699 ± 0.108 | 0.639 ± 0.083 | 0.771 ± 0.108 | 0.091 ± 0.019 | 0.896 ± 0.047 | 0.262 ± 0.052 |
| harmonic | 0.534 ± 0.095 | 0.365 ± 0.145 | 0.655 ± 0.102 | 0.115 ± 0.014 | 0.897 ± 0.031 | 0.341 ± 0.039 |
| harmonic_notrend | 0.703 ± 0.109 | 0.637 ± 0.087 | 0.773 ± 0.108 | 0.091 ± 0.020 | 0.895 ± 0.048 | 0.256 ± 0.054 |
| lgbm | 0.687 ± 0.098 | 0.585 ± 0.097 | 0.770 ± 0.096 | 0.094 ± 0.017 | 0.892 ± 0.034 | 0.252 ± 0.028 |
| persistence | 0.107 ± 0.170 | -0.511 ± 0.277 | 0.608 ± 0.066 | 0.143 ± 0.012 | 0.888 ± 0.035 | 0.449 ± 0.043 |
| synth_control | 0.716 ± 0.086 | 0.643 ± 0.086 | 0.780 ± 0.087 | 0.089 ± 0.016 | 0.899 ± 0.041 | 0.263 ± 0.038 |

## mississippi / Track B

| Model | NDVI R² | NDMI R² | NDWI R² | NDVI RMSE | 90% coverage (NDVI) | width (NDVI) |
|---|---|---|---|---|---|---|
| climatology | 0.183 ± 0.139 | 0.218 ± 0.165 | 0.304 ± 0.124 | 0.122 ± 0.020 | 0.899 ± 0.035 | 0.362 ± 0.042 |
| harmonic | 0.032 ± 0.159 | -0.110 ± 0.174 | 0.181 ± 0.176 | 0.136 ± 0.024 | 0.898 ± 0.027 | 0.392 ± 0.036 |
| harmonic_notrend | 0.225 ± 0.136 | 0.222 ± 0.170 | 0.356 ± 0.122 | 0.119 ± 0.020 | 0.898 ± 0.037 | 0.354 ± 0.044 |
| lgbm | 0.134 ± 0.244 | 0.184 ± 0.086 | 0.120 ± 0.344 | 0.128 ± 0.024 | 0.895 ± 0.008 | 0.367 ± 0.032 |
| persistence | -0.691 ± 0.480 | -1.656 ± 0.520 | 0.103 ± 0.187 | 0.172 ± 0.017 | 0.896 ± 0.032 | 0.558 ± 0.050 |
| synth_control | 0.458 ± 0.102 | 0.310 ± 0.160 | 0.497 ± 0.093 | 0.106 ± 0.022 | 0.898 ± 0.038 | 0.302 ± 0.045 |

## Attributed NDVI deficit (counterfactual − observed), all folds

Mean over evaluated wetland pixels; [interval] from conformal bounds. Placebo windows should be ≈ 0.

| Site / track | Cutoff | Kind | Model | Lead 0 (A2) | Lead 1 | Mean over leads ≥ 1 | Lead-1 interval |
|---|---|---|---|---|---|---|---|
| everglades / A | irma | event | climatology | +0.1167 | +0.0056 | +0.0086 | [+nan, +nan] |
| everglades / A | irma | event | harmonic | +0.1361 | +0.0353 | +0.0383 | [+nan, +nan] |
| everglades / A | irma | event | harmonic_notrend | +0.1167 | +0.0056 | +0.0086 | [+nan, +nan] |
| everglades / A | irma | event | lgbm | +0.1334 | +0.0387 | +0.0341 | [+nan, +nan] |
| everglades / A | irma | event | persistence | +0.0954 | -0.0102 | -0.0090 | [+nan, +nan] |
| everglades / A | irma | event | synth_control | -0.0014 | +0.0346 | +0.0202 | [+nan, +nan] |
| everglades / B | irma | event | climatology | -0.0150 | +0.0082 | -0.0021 | [-0.1438, +0.1603] |
| everglades / B | irma | event | harmonic | +0.0235 | +0.0493 | +0.0406 | [-0.1153, +0.2139] |
| everglades / B | irma | event | harmonic_notrend | -0.0134 | +0.0107 | +0.0018 | [-0.1371, +0.1585] |
| everglades / B | irma | event | lgbm | +0.0550 | +0.0544 | +0.0480 | [-0.0749, +0.1668] |
| everglades / B | irma | event | persistence | +0.0374 | -0.0120 | +0.0053 | [-0.1786, +0.1546] |
| everglades / B | irma | event | synth_control | +0.0087 | +0.0397 | +0.0244 | [-0.1053, +0.1846] |
| everglades / B | irma_placebo_2015 | placebo | climatology | -0.0683 | +0.0290 | -0.0185 | [-0.1101, +0.1681] |
| everglades / B | irma_placebo_2015 | placebo | harmonic | -0.0509 | +0.0483 | +0.0052 | [-0.1067, +0.2034] |
| everglades / B | irma_placebo_2015 | placebo | harmonic_notrend | -0.0683 | +0.0290 | -0.0178 | [-0.1065, +0.1646] |
| everglades / B | irma_placebo_2015 | placebo | lgbm | -0.0714 | +0.0212 | -0.0132 | [-0.0899, +0.1261] |
| everglades / B | irma_placebo_2015 | placebo | persistence | -0.0940 | -0.0369 | -0.0404 | [-0.2024, +0.1286] |
| everglades / B | irma_placebo_2015 | placebo | synth_control | +nan | -0.0246 | -0.0112 | [-0.1610, +0.1117] |
| everglades / B | irma_placebo_2016 | placebo | climatology | -0.0673 | -0.0479 | -0.0418 | [-0.1999, +0.1040] |
| everglades / B | irma_placebo_2016 | placebo | harmonic | -0.0592 | -0.0276 | -0.0200 | [-0.1922, +0.1370] |
| everglades / B | irma_placebo_2016 | placebo | harmonic_notrend | -0.0718 | -0.0451 | -0.0381 | [-0.1928, +0.1026] |
| everglades / B | irma_placebo_2016 | placebo | lgbm | -0.0677 | -0.0516 | -0.0280 | [-0.1956, +0.0716] |
| everglades / B | irma_placebo_2016 | placebo | persistence | -0.0567 | -0.0827 | -0.0529 | [-0.2493, +0.0839] |
| everglades / B | irma_placebo_2016 | placebo | synth_control | +0.0479 | +0.0079 | +0.0100 | [-0.1370, +0.1528] |
| mississippi / A | ida | event | climatology | +0.0885 | -0.0033 | +0.0049 | [-0.1434, +0.1369] |
| mississippi / A | ida | event | harmonic | +0.0961 | +0.0082 | +0.0158 | [-0.1581, +0.1745] |
| mississippi / A | ida | event | harmonic_notrend | +0.0883 | +0.0007 | +0.0062 | [-0.1329, +0.1343] |
| mississippi / A | ida | event | lgbm | +0.0652 | -0.0042 | -0.0093 | [-0.1392, +0.1451] |
| mississippi / A | ida | event | persistence | +0.0684 | +0.0639 | +0.0546 | [-0.1585, +0.2862] |
| mississippi / A | ida | event | synth_control | +0.0347 | +0.0305 | +0.0177 | [-0.1093, +0.1703] |
| mississippi / A | ida_placebo_2018 | placebo | climatology | +0.0315 | -0.0272 | -0.0211 | [-0.1674, +0.1129] |
| mississippi / A | ida_placebo_2018 | placebo | harmonic | +0.0641 | +0.0063 | +0.0118 | [-0.1600, +0.1726] |
| mississippi / A | ida_placebo_2018 | placebo | harmonic_notrend | +0.0316 | -0.0218 | -0.0189 | [-0.1554, +0.1118] |
| mississippi / A | ida_placebo_2018 | placebo | lgbm | +0.0216 | -0.0142 | -0.0178 | [-0.1407, +0.1223] |
| mississippi / A | ida_placebo_2018 | placebo | persistence | -0.0026 | +0.0512 | +0.0572 | [-0.1712, +0.2736] |
| mississippi / A | ida_placebo_2018 | placebo | synth_control | +0.0030 | +0.0062 | +0.0065 | [-0.1336, +0.1460] |
| mississippi / B | ida | event | climatology | +0.0674 | -0.0226 | -0.0008 | [-0.1898, +0.1447] |
| mississippi / B | ida | event | harmonic | +0.1005 | +0.0110 | +0.0392 | [-0.1724, +0.1945] |
| mississippi / B | ida | event | harmonic_notrend | +0.0686 | -0.0188 | +0.0032 | [-0.1844, +0.1468] |
| mississippi / B | ida | event | lgbm | +0.0552 | -0.0198 | -0.0156 | [-0.1609, +0.1350] |
| mississippi / B | ida | event | persistence | +0.0205 | +0.0553 | +0.0530 | [-0.1892, +0.2998] |
| mississippi / B | ida | event | synth_control | +0.0509 | +0.0343 | +0.0211 | [-0.0906, +0.1592] |
| mississippi / B | ida_placebo_2015 | placebo | climatology | +0.0083 | -0.0139 | -0.0280 | [-0.1811, +0.1533] |
| mississippi / B | ida_placebo_2015 | placebo | harmonic | +0.0356 | +0.0212 | +0.0110 | [-0.1623, +0.2047] |
| mississippi / B | ida_placebo_2015 | placebo | harmonic_notrend | +0.0083 | -0.0139 | -0.0274 | [-0.1795, +0.1517] |
| mississippi / B | ida_placebo_2015 | placebo | lgbm | -0.0050 | -0.0182 | -0.0388 | [-0.2869, +0.1770] |
| mississippi / B | ida_placebo_2015 | placebo | persistence | -0.0867 | +0.0405 | +0.0239 | [-0.2040, +0.2850] |
| mississippi / B | ida_placebo_2015 | placebo | synth_control | +0.0141 | -0.0048 | +0.0039 | [-0.1297, +0.1201] |
| mississippi / B | ida_placebo_2016 | placebo | climatology | -0.0733 | -0.1114 | -0.0719 | [-0.2786, +0.0558] |
| mississippi / B | ida_placebo_2016 | placebo | harmonic | -0.0504 | -0.0858 | -0.0417 | [-0.2693, +0.0977] |
| mississippi / B | ida_placebo_2016 | placebo | harmonic_notrend | -0.0732 | -0.1104 | -0.0658 | [-0.2760, +0.0551] |
| mississippi / B | ida_placebo_2016 | placebo | lgbm | -0.0598 | -0.1055 | -0.0512 | [-0.2585, +0.0639] |
| mississippi / B | ida_placebo_2016 | placebo | persistence | -0.0919 | +0.0327 | +0.0640 | [-0.2118, +0.2772] |
| mississippi / B | ida_placebo_2016 | placebo | synth_control | -0.0264 | -0.0101 | -0.0060 | [-0.1351, +0.1148] |
| mississippi / B | ida_placebo_2018 | placebo | climatology | -0.0077 | -0.0456 | -0.0369 | [-0.2128, +0.1216] |
| mississippi / B | ida_placebo_2018 | placebo | harmonic | +0.0439 | +0.0070 | +0.0192 | [-0.1765, +0.1905] |
| mississippi / B | ida_placebo_2018 | placebo | harmonic_notrend | -0.0073 | -0.0438 | -0.0314 | [-0.2094, +0.1218] |
| mississippi / B | ida_placebo_2018 | placebo | lgbm | -0.0027 | -0.0109 | -0.0187 | [-0.1480, +0.1344] |
| mississippi / B | ida_placebo_2018 | placebo | persistence | -0.0467 | +0.0599 | +0.0739 | [-0.1846, +0.3044] |
| mississippi / B | ida_placebo_2018 | placebo | synth_control | -0.0029 | +0.0002 | +0.0064 | [-0.1247, +0.1252] |
