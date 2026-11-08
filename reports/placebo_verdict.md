# Phase 4 — placebo verdict

Pre-registered rule: a model PASSES for an event if its median attributed NDVI deficit exceeds the 95th percentile of its placebo distribution (placebo windows × folds × seeds) **and** its 90 % intervals cover ≥ 80 % of placebo truth. Statistic and pooling: amendment A4 (`configs/preregistration.yaml`).

## Primary: leads 1–3 (first three full quarters after the event)

| Site / track | Event | Model | Event median (min) | Placebo p95 [range] | n ev / plc | Event folds > p95 | Placebo coverage | Exceeds | Coverage ≥ 0.80 | **Verdict** |
|---|---|---|---|---|---|---|---|---|---|---|
| everglades / B | irma | climatology | -0.0001 (-0.0155) | -0.0003 [-0.0555, +0.0009] | 5 / 10 | 60% | 0.890 | yes | yes | **PASS** |
| everglades / B | irma | convlstm | +0.0326 (+0.0076) | -0.0302 [-0.2607, -0.0263] | 10 / 20 | 100% | 0.885 | yes | yes | **PASS** |
| everglades / B | irma | ecotransformer | +0.0397 (+0.0218) | +0.0115 [-0.0462, +0.0121] | 10 / 20 | 100% | 0.902 | yes | yes | **PASS** |
| everglades / B | irma | harmonic | +0.0364 (+0.0264) | +0.0269 [-0.0352, +0.0280] | 5 / 10 | 80% | 0.896 | yes | yes | **PASS** |
| everglades / B | irma | harmonic_notrend | +0.0057 (-0.0112) | +0.0033 [-0.0532, +0.0063] | 5 / 10 | 60% | 0.890 | yes | yes | **PASS** |
| everglades / B | irma | lgbm | +0.0475 (+0.0324) | +0.0042 [-0.0323, +0.0043] | 5 / 10 | 100% | 0.892 | yes | yes | **PASS** |
| everglades / B | irma | persistence | +0.0030 (-0.0076) | -0.0305 [-0.0665, -0.0302] | 5 / 10 | 100% | 0.891 | yes | yes | **PASS** |
| everglades / B | irma | simvp | +0.0293 (-0.0014) | +0.0207 [-0.0521, +0.0245] | 10 / 20 | 80% | 0.897 | yes | yes | **PASS** |
| everglades / B | irma | synth_control | +0.0248 (+0.0130) | +0.0188 [-0.0311, +0.0206] | 5 / 10 | 60% | 0.895 | yes | yes | **PASS** |
| mississippi / A | ida | climatology | +0.0001 (-0.0128) | -0.0089 [-0.0375, -0.0073] | 5 / 5 | 60% | 0.896 | yes | yes | **PASS** |
| mississippi / A | ida | convlstm | -0.0039 (-0.0132) | +0.0117 [-0.0388, +0.0152] | 10 / 10 | 20% | 0.893 | no | yes | **FAIL** |
| mississippi / A | ida | ecotransformer | -0.0055 (-0.0191) | -0.0057 [-0.0324, -0.0055] | 10 / 10 | 60% | 0.894 | yes | yes | **PASS** |
| mississippi / A | ida | harmonic | +0.0036 (-0.0045) | +0.0251 [-0.0066, +0.0275] | 5 / 5 | 20% | 0.897 | no | yes | **FAIL** |
| mississippi / A | ida | harmonic_notrend | +0.0005 (-0.0108) | -0.0063 [-0.0347, -0.0048] | 5 / 5 | 60% | 0.895 | yes | yes | **PASS** |
| mississippi / A | ida | lgbm | -0.0085 (-0.0281) | -0.0068 [-0.0301, -0.0047] | 5 / 5 | 40% | 0.892 | no | yes | **FAIL** |
| mississippi / A | ida | persistence | +0.0661 (+0.0471) | +0.0757 [+0.0235, +0.0761] | 5 / 5 | 40% | 0.888 | no | yes | **FAIL** |
| mississippi / A | ida | simvp | +0.0017 (-0.0228) | -0.0022 [-0.0258, -0.0018] | 10 / 10 | 60% | 0.893 | yes | yes | **PASS** |
| mississippi / A | ida | synth_control | +0.0138 (-0.0025) | +0.0190 [-0.0086, +0.0203] | 5 / 5 | 20% | 0.899 | no | yes | **FAIL** |
| mississippi / B | ida | climatology | -0.0153 (-0.0338) | -0.0205 [-0.0820, -0.0144] | 5 / 15 | 60% | 0.899 | yes | yes | **PASS** |
| mississippi / B | ida | harmonic | +0.0219 (+0.0030) | +0.0297 [-0.0480, +0.0319] | 5 / 15 | 20% | 0.898 | no | yes | **FAIL** |
| mississippi / B | ida | harmonic_notrend | -0.0119 (-0.0295) | -0.0174 [-0.0747, -0.0141] | 5 / 15 | 60% | 0.898 | yes | yes | **PASS** |
| mississippi / B | ida | lgbm | -0.0240 (-0.0397) | +0.0015 [-0.0851, +0.0112] | 5 / 15 | 0% | 0.895 | no | yes | **FAIL** |
| mississippi / B | ida | persistence | +0.0694 (+0.0432) | +0.0872 [+0.0039, +0.0918] | 5 / 15 | 40% | 0.896 | no | yes | **FAIL** |
| mississippi / B | ida | synth_control | +0.0152 (+0.0001) | +0.0164 [-0.0167, +0.0184] | 5 / 15 | 40% | 0.898 | no | yes | **FAIL** |

## Secondary: lead 0 (post-landfall composite vs matched-days placebo composite, A2/A3)

| Site / track | Event | Model | Event median (min) | Placebo p95 [range] | n ev / plc | Event folds > p95 | Placebo coverage | Exceeds | Coverage ≥ 0.80 | **Verdict** |
|---|---|---|---|---|---|---|---|---|---|---|
| everglades / B | irma | climatology | +0.0030 (-0.0687) | -0.0564 [-0.0793, -0.0560] | 5 / 6 | 80% | 0.890 | yes | yes | **PASS** |
| everglades / B | irma | convlstm | +0.0459 (-0.0057) | +0.0270 [-0.1007, +0.0630] | 10 / 20 | 70% | 0.885 | yes | yes | **PASS** |
| everglades / B | irma | ecotransformer | +0.0611 (-0.0055) | +0.0153 [-0.0753, +0.0208] | 10 / 20 | 80% | 0.902 | yes | yes | **PASS** |
| everglades / B | irma | harmonic | +0.0339 (-0.0244) | -0.0467 [-0.0773, -0.0453] | 5 / 6 | 100% | 0.896 | yes | yes | **PASS** |
| everglades / B | irma | harmonic_notrend | +0.0009 (-0.0662) | -0.0589 [-0.0875, -0.0588] | 5 / 6 | 80% | 0.890 | yes | yes | **PASS** |
| everglades / B | irma | lgbm | +0.0609 (+0.0109) | -0.0516 [-0.0948, -0.0505] | 5 / 6 | 100% | 0.892 | yes | yes | **PASS** |
| everglades / B | irma | persistence | +0.0420 (-0.0096) | -0.0135 [-0.0940, -0.0002] | 5 / 6 | 100% | 0.891 | yes | yes | **PASS** |
| everglades / B | irma | simvp | +0.0317 (-0.0281) | +0.0431 [-0.0780, +0.0441] | 10 / 20 | 20% | 0.897 | no | yes | **FAIL** |
| everglades / B | irma | synth_control | +0.0133 (-0.1106) | +0.0763 [+0.0024, +0.0773] | 5 / 5 | 0% | 0.895 | no | yes | **FAIL** |
| mississippi / A | ida | climatology | +0.0897 (+0.0661) | +0.0404 [+0.0197, +0.0408] | 5 / 5 | 100% | 0.896 | yes | yes | **PASS** |
| mississippi / A | ida | convlstm | +0.0730 (+0.0623) | +0.0376 [-0.0138, +0.0392] | 10 / 10 | 100% | 0.893 | yes | yes | **PASS** |
| mississippi / A | ida | ecotransformer | +0.0767 (+0.0703) | +0.0310 [-0.0080, +0.0321] | 10 / 10 | 100% | 0.894 | yes | yes | **PASS** |
| mississippi / A | ida | harmonic | +0.0920 (+0.0678) | +0.0738 [+0.0479, +0.0745] | 5 / 5 | 80% | 0.897 | yes | yes | **PASS** |
| mississippi / A | ida | harmonic_notrend | +0.0897 (+0.0648) | +0.0404 [+0.0199, +0.0407] | 5 / 5 | 100% | 0.895 | yes | yes | **PASS** |
| mississippi / A | ida | lgbm | +0.0647 (+0.0513) | +0.0380 [+0.0012, +0.0399] | 5 / 5 | 100% | 0.892 | yes | yes | **PASS** |
| mississippi / A | ida | persistence | +0.0821 (+0.0378) | +0.0286 [-0.0421, +0.0301] | 5 / 5 | 100% | 0.888 | yes | yes | **PASS** |
| mississippi / A | ida | simvp | +0.0693 (+0.0571) | +0.0372 [-0.0115, +0.0389] | 10 / 10 | 100% | 0.893 | yes | yes | **PASS** |
| mississippi / A | ida | synth_control | +0.0413 (+0.0050) | +0.0128 [-0.0042, +0.0138] | 5 / 5 | 80% | 0.899 | yes | yes | **PASS** |
| mississippi / B | ida | climatology | +0.0678 (+0.0631) | +0.0144 [-0.0881, +0.0192] | 5 / 15 | 100% | 0.899 | yes | yes | **PASS** |
| mississippi / B | ida | harmonic | +0.1027 (+0.0899) | +0.0622 [-0.0714, +0.0689] | 5 / 15 | 100% | 0.898 | yes | yes | **PASS** |
| mississippi / B | ida | harmonic_notrend | +0.0687 (+0.0638) | +0.0144 [-0.0883, +0.0192] | 5 / 15 | 100% | 0.898 | yes | yes | **PASS** |
| mississippi / B | ida | lgbm | +0.0570 (+0.0424) | +0.0144 [-0.0675, +0.0155] | 5 / 15 | 100% | 0.895 | yes | yes | **PASS** |
| mississippi / B | ida | persistence | +0.0239 (+0.0092) | -0.0290 [-0.1108, -0.0271] | 5 / 15 | 100% | 0.896 | yes | yes | **PASS** |
| mississippi / B | ida | synth_control | +0.0499 (+0.0394) | +0.0254 [-0.0453, +0.0326] | 5 / 15 | 100% | 0.898 | yes | yes | **PASS** |

## Placebo in space: event deficit in the least-exposed blocks (farthest 20 % from the coast)

Should be ≈ 0 / inside the placebo range. Seeds averaged.

| Site / track | Event | Model | Map | Least-exposed blocks | Deficit there | Deficit, all blocks |
|---|---|---|---|---|---|---|
| everglades / A | irma | climatology | lead 0 | 8 | +0.0962 | +0.1167 |
| everglades / A | irma | climatology | mean over leads | 8 | +0.0225 | +0.0330 |
| everglades / A | irma | harmonic | lead 0 | 8 | +0.1119 | +0.1361 |
| everglades / A | irma | harmonic | mean over leads | 8 | +0.0501 | +0.0605 |
| everglades / A | irma | harmonic_notrend | lead 0 | 8 | +0.0962 | +0.1167 |
| everglades / A | irma | harmonic_notrend | mean over leads | 8 | +0.0225 | +0.0330 |
| everglades / A | irma | lgbm | lead 0 | 8 | +0.1132 | +0.1334 |
| everglades / A | irma | lgbm | mean over leads | 8 | +0.0465 | +0.0564 |
| everglades / A | irma | persistence | lead 0 | 8 | +0.0884 | +0.0954 |
| everglades / A | irma | persistence | mean over leads | 8 | +0.0123 | +0.0146 |
| everglades / A | irma | synth_control | lead 0 | 8 | -0.0314 | -0.0014 |
| everglades / A | irma | synth_control | mean over leads | 8 | +0.0119 | +0.0159 |
| everglades / B | irma | climatology | lead 0 | 7 | +0.0514 | -0.0150 |
| everglades / B | irma | climatology | mean over leads | 8 | +0.0000 | -0.0030 |
| everglades / B | irma | convlstm | lead 0 | 7 | +0.1132 | +0.0476 |
| everglades / B | irma | convlstm | mean over leads | 8 | +0.0317 | +0.0360 |
| everglades / B | irma | ecotransformer | lead 0 | 7 | +0.1241 | +0.0537 |
| everglades / B | irma | ecotransformer | mean over leads | 8 | +0.0393 | +0.0432 |
| everglades / B | irma | harmonic | lead 0 | 7 | +0.0742 | +0.0235 |
| everglades / B | irma | harmonic | mean over leads | 8 | +0.0258 | +0.0387 |
| everglades / B | irma | harmonic_notrend | lead 0 | 7 | +0.0534 | -0.0134 |
| everglades / B | irma | harmonic_notrend | mean over leads | 8 | +0.0036 | +0.0004 |
| everglades / B | irma | lgbm | lead 0 | 7 | +0.1142 | +0.0550 |
| everglades / B | irma | lgbm | mean over leads | 8 | +0.0426 | +0.0501 |
| everglades / B | irma | persistence | lead 0 | 7 | +0.1222 | +0.0374 |
| everglades / B | irma | persistence | mean over leads | 8 | +0.0180 | +0.0111 |
| everglades / B | irma | simvp | lead 0 | 7 | +0.0733 | +0.0221 |
| everglades / B | irma | simvp | mean over leads | 8 | +0.0184 | +0.0295 |
| everglades / B | irma | synth_control | lead 0 | 7 | +0.0617 | +0.0087 |
| everglades / B | irma | synth_control | mean over leads | 8 | +0.0280 | +0.0230 |
| mississippi / A | ida | climatology | lead 0 | 8 | +0.0412 | +0.0885 |
| mississippi / A | ida | climatology | mean over leads | 8 | -0.0140 | +0.0142 |
| mississippi / A | ida | convlstm | lead 0 | 8 | +0.0434 | +0.0737 |
| mississippi / A | ida | convlstm | mean over leads | 8 | -0.0104 | +0.0091 |
| mississippi / A | ida | ecotransformer | lead 0 | 8 | +0.0414 | +0.0784 |
| mississippi / A | ida | ecotransformer | mean over leads | 8 | -0.0121 | +0.0071 |
| mississippi / A | ida | harmonic | lead 0 | 8 | +0.0483 | +0.0961 |
| mississippi / A | ida | harmonic | mean over leads | 8 | -0.0039 | +0.0247 |
| mississippi / A | ida | harmonic_notrend | lead 0 | 8 | +0.0410 | +0.0883 |
| mississippi / A | ida | harmonic_notrend | mean over leads | 8 | -0.0126 | +0.0153 |
| mississippi / A | ida | lgbm | lead 0 | 8 | +0.0307 | +0.0652 |
| mississippi / A | ida | lgbm | mean over leads | 8 | -0.0278 | -0.0011 |
| mississippi / A | ida | persistence | lead 0 | 8 | +0.0812 | +0.0684 |
| mississippi / A | ida | persistence | mean over leads | 8 | +0.0824 | +0.0561 |
| mississippi / A | ida | simvp | lead 0 | 8 | +0.0348 | +0.0725 |
| mississippi / A | ida | simvp | mean over leads | 8 | -0.0029 | +0.0143 |
| mississippi / A | ida | synth_control | lead 0 | 8 | -0.0138 | +0.0347 |
| mississippi / A | ida | synth_control | mean over leads | 8 | -0.0118 | +0.0196 |
| mississippi / B | ida | climatology | lead 0 | 7 | +0.0012 | +0.0674 |
| mississippi / B | ida | climatology | mean over leads | 7 | -0.0227 | +0.0068 |
| mississippi / B | ida | harmonic | lead 0 | 7 | +0.0350 | +0.1005 |
| mississippi / B | ida | harmonic | mean over leads | 7 | +0.0191 | +0.0460 |
| mississippi / B | ida | harmonic_notrend | lead 0 | 7 | +0.0020 | +0.0686 |
| mississippi / B | ida | harmonic_notrend | mean over leads | 7 | -0.0184 | +0.0105 |
| mississippi / B | ida | lgbm | lead 0 | 7 | -0.0069 | +0.0552 |
| mississippi / B | ida | lgbm | mean over leads | 7 | -0.0389 | -0.0077 |
| mississippi / B | ida | persistence | lead 0 | 7 | +0.0208 | +0.0206 |
| mississippi / B | ida | persistence | mean over leads | 7 | +0.0791 | +0.0498 |
| mississippi / B | ida | synth_control | lead 0 | 7 | -0.0123 | +0.0509 |
| mississippi / B | ida | synth_control | mean over leads | 7 | -0.0062 | +0.0248 |

**Primary: 15 of 24 model × event combinations pass. Secondary (lead 0): 22 of 24.**
