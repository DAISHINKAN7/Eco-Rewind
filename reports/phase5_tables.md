# Phase 5 — ablations, transfer, resolution

Val R² = NDVI R² on the calibration fold (pre-cutoff pairs), mean ± sd over trained (cutoff × fold); this is the pre-registered ablation criterion. Test R² = placebo windows, held-out folds, leads ≥ 1 (information only). Δ is relative to the parent (same site/track, no variant, gate SAR, seeds pooled).

## everglades / Track B

| Model | Cutoffs·folds | Val R² | Δ val vs parent (same cutoffs·folds) | Test R² | Δ test | GPU min | Killed |
|---|---|---|---|---|---|---|---|
| convlstm (s0) | 15 | 0.885 ± 0.039 | — | 0.173 | — | 181 | 0 |
| convlstm (s1) | 15 | 0.888 ± 0.034 | — | 0.099 | — | 178 | 0 |
| ecotransformer (s0) | 19 | 0.842 ± 0.037 | — | 0.603 | — | 174 | 0 |
| ecotransformer (s1) | 15 | 0.842 ± 0.035 | — | 0.594 | — | 148 | 0 |
| simvp (s0) | 15 | 0.871 ± 0.037 | — | 0.694 | — | 116 | 0 |
| simvp (s1) | 15 | 0.873 ± 0.034 | — | 0.664 | — | 111 | 0 |

## mississippi / Track A

| Model | Cutoffs·folds | Val R² | Δ val vs parent (same cutoffs·folds) | Test R² | Δ test | GPU min | Killed |
|---|---|---|---|---|---|---|---|
| convlstm (s0) | 10 | 0.792 ± 0.079 | — | 0.638 | — | 311 | 0 |
| convlstm (s1) | 10 | 0.795 ± 0.076 | — | 0.657 | — | 306 | 0 |
| ecotransformer (s0) | 10 | 0.753 ± 0.075 | — | 0.583 | — | 240 | 0 |
| ecotransformer (s1) | 10 | 0.756 ± 0.069 | — | 0.583 | — | 238 | 0 |
| simvp (s0) | 10 | 0.799 ± 0.066 | — | 0.661 | — | 219 | 0 |
| simvp (s1) | 10 | 0.796 ± 0.066 | — | 0.669 | — | 212 | 0 |

Transfer rows (`xfer`) were trained on the other site's Track B event history and applied here; compare their test R² with the same architecture trained on site. Resolution: compare Mississippi Track A vs Track B rows of the same model (different pixels, same blocks).
