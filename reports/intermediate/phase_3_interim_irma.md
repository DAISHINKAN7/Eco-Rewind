# Phase 3 interim: Irma, Everglades Track B (run `phase3_core_v1`, 2 seeds; Ida Track A still running)

Placebo-window skill (held-out test folds, leads ≥ 1, mean ± std over 5 folds), against v3 baselines:

| Model | NDVI R² | NDMI R² | NDWI R² | 90 % coverage |
|---|---|---|---|---|
| synth_control (best baseline) | 0.765 ± 0.060 | 0.732 | 0.546 | 0.895 |
| lgbm | 0.737 | 0.601 | 0.494 | 0.892 |
| harmonic_notrend | 0.708 | 0.700 | 0.467 | 0.890 |
| climatology | 0.702 | 0.705 | 0.436 | 0.890 |
| simvp s0 / s1 | 0.694 / 0.664 | 0.525 / 0.570 | 0.426 / 0.388 | 0.900 / 0.893 |
| ecotransformer s0 / s1 | 0.603 / 0.594 | 0.545 / 0.505 | 0.218 / 0.171 | 0.903 / 0.901 |
| convlstm s0 / s1 | 0.173 / 0.099 | −0.357 / −0.008 | −0.279 / −0.621 | 0.895 / 0.875 |

- **No deep model beats the baselines on Irma Track B.** SimVP comes closest (≈ climatology); EcoTransformer v2 is
  ~0.16 NDVI R² below synth_control; ConvLSTM is poor and seed-unstable (fold std 0.3). Seeds agree for the other two.
- Conformal coverage stays nominal (0.88–0.90) for every model, so the intervals are honest even where skill is low.
- Placebo deficits: ConvLSTM is strongly biased (−0.07 to −0.17 NDVI at leads ≥ 1); EcoTransformer and SimVP within
  ±0.07, comparable to baselines.
- Irma NDVI deficit (lead 0 / lead 1): EcoTransformer +0.05 / +0.05 (placebos −0.05…−0.00 / −0.07…+0.02);
  SimVP +0.02 / +0.02 (placebos −0.03…+0.03 / −0.05…+0.04). Model spread for the same event: +0.017 to +0.053 (C3).
- Context: Track B is 30 m HLS with 13 quarters of history before Irma, the smallest training set in the study.
