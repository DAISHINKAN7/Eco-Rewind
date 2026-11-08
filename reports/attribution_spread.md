# Attribution spread across models (claim C3)

NDVI deficit (counterfactual − observed), mean over evaluated wetland pixels, all folds, seeds averaged; [90 % interval]; total = NDVI·ha. Placebo = Phase 4 verdict for the same statistic.

## irma — everglades / Track A — lead 0

| Model | Deficit | 90 % interval | Total (NDVI·ha) | Placebo |
|---|---|---|---|---|
| synth_control | -0.0014 | [+nan, +nan] | -25.0 | — |
| persistence | +0.0954 | [+nan, +nan] | +1678.3 | — |
| harmonic_notrend | +0.1167 | [+nan, +nan] | +2051.9 | — |
| climatology | +0.1167 | [+nan, +nan] | +2051.9 | — |
| lgbm | +0.1334 | [+nan, +nan] | +2346.3 | — |
| harmonic | +0.1361 | [+nan, +nan] | +2393.6 | — |

## irma — everglades / Track A — leads 1-3

| Model | Deficit | 90 % interval | Total (NDVI·ha) | Placebo |
|---|---|---|---|---|
| persistence | -0.0090 | [+nan, +nan] | -178.3 | — |
| harmonic_notrend | +0.0086 | [+nan, +nan] | +171.4 | — |
| climatology | +0.0086 | [+nan, +nan] | +171.4 | — |
| synth_control | +0.0202 | [+nan, +nan] | +401.6 | — |
| lgbm | +0.0341 | [+nan, +nan] | +679.5 | — |
| harmonic | +0.0383 | [+nan, +nan] | +762.4 | — |

## irma — everglades / Track B — lead 0

| Model | Deficit | 90 % interval | Total (NDVI·ha) | Placebo |
|---|---|---|---|---|
| climatology | -0.0150 | [-0.1663, +0.1363] | -197.9 | pass |
| harmonic_notrend | -0.0134 | [-0.1740, +0.1472] | -176.8 | pass |
| synth_control | +0.0087 | [-0.1288, +0.1462] | +115.0 | fail |
| simvp | +0.0221 | [-0.1470, +0.1838] | +292.1 | fail |
| harmonic | +0.0235 | [-0.1241, +0.1711] | +310.8 | pass |
| persistence | +0.0374 | [-0.1158, +0.1905] | +493.7 | pass |
| convlstm | +0.0476 | [-0.1358, +0.2276] | +629.1 | pass |
| ecotransformer | +0.0537 | [-0.1188, +0.2238] | +709.1 | pass |
| lgbm | +0.0550 | [-0.0841, +0.1890] | +726.7 | pass |

## irma — everglades / Track B — leads 1-3

| Model | Deficit | 90 % interval | Total (NDVI·ha) | Placebo |
|---|---|---|---|---|
| climatology | -0.0021 | [-0.1317, +0.1275] | -41.5 | pass |
| harmonic_notrend | +0.0018 | [-0.1219, +0.1254] | +35.4 | pass |
| persistence | +0.0053 | [-0.1372, +0.1477] | +105.0 | pass |
| synth_control | +0.0244 | [-0.0895, +0.1382] | +491.8 | pass |
| simvp | +0.0298 | [-0.1072, +0.1612] | +600.0 | pass |
| convlstm | +0.0327 | [-0.1918, +0.2584] | +659.2 | pass |
| ecotransformer | +0.0403 | [-0.1132, +0.1916] | +811.9 | pass |
| harmonic | +0.0406 | [-0.1031, +0.1843] | +819.6 | pass |
| lgbm | +0.0480 | [-0.0659, +0.1525] | +967.5 | pass |

## ida — mississippi / Track A — lead 0

| Model | Deficit | 90 % interval | Total (NDVI·ha) | Placebo |
|---|---|---|---|---|
| synth_control | +0.0347 | [-0.1184, +0.1878] | +258.2 | pass |
| lgbm | +0.0652 | [-0.0973, +0.2338] | +485.4 | pass |
| persistence | +0.0684 | [-0.1414, +0.2781] | +508.6 | pass |
| simvp | +0.0725 | [-0.0589, +0.2040] | +539.7 | pass |
| convlstm | +0.0737 | [-0.0598, +0.2070] | +548.5 | pass |
| ecotransformer | +0.0784 | [-0.0626, +0.2180] | +583.6 | pass |
| harmonic_notrend | +0.0883 | [-0.0748, +0.2513] | +656.9 | pass |
| climatology | +0.0885 | [-0.0752, +0.2522] | +658.4 | pass |
| harmonic | +0.0961 | [-0.1225, +0.3147] | +714.8 | pass |

## ida — mississippi / Track A — leads 1-3

| Model | Deficit | 90 % interval | Total (NDVI·ha) | Placebo |
|---|---|---|---|---|
| lgbm | -0.0096 | [-0.1438, +0.1307] | -71.6 | fail |
| ecotransformer | -0.0047 | [-0.1614, +0.1532] | -35.3 | pass |
| climatology | -0.0020 | [-0.1337, +0.1297] | -15.0 | pass |
| convlstm | -0.0011 | [-0.1483, +0.1557] | -7.9 | fail |
| harmonic_notrend | -0.0002 | [-0.1292, +0.1288] | -1.7 | pass |
| simvp | +0.0022 | [-0.1437, +0.1540] | +16.2 | pass |
| harmonic | +0.0076 | [-0.1634, +0.1786] | +56.5 | fail |
| synth_control | +0.0132 | [-0.1188, +0.1451] | +98.0 | fail |
| persistence | +0.0709 | [-0.1525, +0.2943] | +527.5 | fail |

## ida — mississippi / Track B — lead 0

| Model | Deficit | 90 % interval | Total (NDVI·ha) | Placebo |
|---|---|---|---|---|
| persistence | +0.0205 | [-0.2506, +0.2916] | +142.8 | pass |
| synth_control | +0.0509 | [-0.0916, +0.1933] | +354.2 | pass |
| lgbm | +0.0552 | [-0.1026, +0.2175] | +384.1 | pass |
| climatology | +0.0674 | [-0.0908, +0.2256] | +469.3 | pass |
| harmonic_notrend | +0.0686 | [-0.0886, +0.2258] | +477.6 | pass |
| harmonic | +0.1005 | [-0.0924, +0.2934] | +699.8 | pass |

## ida — mississippi / Track B — leads 1-3

| Model | Deficit | 90 % interval | Total (NDVI·ha) | Placebo |
|---|---|---|---|---|
| lgbm | -0.0241 | [-0.1703, +0.1310] | -182.1 | fail |
| climatology | -0.0156 | [-0.1968, +0.1655] | -118.1 | pass |
| harmonic_notrend | -0.0107 | [-0.1879, +0.1664] | -81.1 | pass |
| synth_control | +0.0183 | [-0.1334, +0.1700] | +138.5 | fail |
| harmonic | +0.0199 | [-0.1763, +0.2161] | +150.3 | fail |
| persistence | +0.0729 | [-0.2044, +0.3502] | +550.1 | fail |

## Spread summary

Ratio = max |deficit| / min |deficit|, only when all models agree in sign (v1 reported ≈ 20× across models).

| Event | Site / track | Statistic | Models | n | Min | Max | Range | Ratio |
|---|---|---|---|---|---|---|---|---|
| irma | everglades / A | lead 0 | all models | 6 | -0.0014 | +0.1361 | 0.1375 | — |
| irma | everglades / A | lead 0 | placebo-passing | 0 | +nan | +nan | nan | — |
| irma | everglades / A | leads 1-3 | all models | 6 | -0.0090 | +0.0383 | 0.0472 | — |
| irma | everglades / A | leads 1-3 | placebo-passing | 0 | +nan | +nan | nan | — |
| irma | everglades / B | lead 0 | all models | 9 | -0.0150 | +0.0550 | 0.0700 | — |
| irma | everglades / B | lead 0 | placebo-passing | 7 | -0.0150 | +0.0550 | 0.0700 | — |
| irma | everglades / B | leads 1-3 | all models | 9 | -0.0021 | +0.0480 | 0.0500 | — |
| irma | everglades / B | leads 1-3 | placebo-passing | 9 | -0.0021 | +0.0480 | 0.0500 | — |
| ida | mississippi / A | lead 0 | all models | 9 | +0.0347 | +0.0961 | 0.0614 | 2.8× |
| ida | mississippi / A | lead 0 | placebo-passing | 9 | +0.0347 | +0.0961 | 0.0614 | 2.8× |
| ida | mississippi / A | leads 1-3 | all models | 9 | -0.0096 | +0.0709 | 0.0805 | — |
| ida | mississippi / A | leads 1-3 | placebo-passing | 4 | -0.0047 | +0.0022 | 0.0069 | — |
| ida | mississippi / B | lead 0 | all models | 6 | +0.0205 | +0.1005 | 0.0800 | 4.9× |
| ida | mississippi / B | lead 0 | placebo-passing | 6 | +0.0205 | +0.1005 | 0.0800 | 4.9× |
| ida | mississippi / B | leads 1-3 | all models | 6 | -0.0241 | +0.0729 | 0.0970 | — |
| ida | mississippi / B | leads 1-3 | placebo-passing | 2 | -0.0156 | -0.0107 | 0.0049 | 1.5× |
