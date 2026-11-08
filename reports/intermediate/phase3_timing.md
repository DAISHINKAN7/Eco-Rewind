# Phase 3 timing run (2026-10-28, Colab T4)

EcoTransformer v2, seed 0, test fold 0, Mississippi Track A (ida_placebo_2018 + ida). Wall time 57.8 min.

| Cutoff | History | Speed | Training | Grid prediction | Best val NDVI R² (calib fold, in-history) | GPU mem |
|---|---|---|---|---|---|---|
| ida_placebo_2018 | 12 q, 4 anchors, D=4 | 4.2 it/s | 24.2 min (40 epochs) | 57 s | 0.748 | 1.3 GB |
| ida | 24 q, 16 anchors, D=9 | 3.5 it/s | 28.9 min (40 epochs) | 104 s | 0.757 | 1.7 GB |

Test fold 0, placebo windows (leads ≥ 1): NDVI R² 0.589, NDMI 0.430, NDWI 0.656, 90 % coverage 0.911 (one fold, one seed:
not comparable yet with the 5-fold baseline means; synth_control 0.716, climatology 0.699).
Lead-0 NDVI deficit: ida +0.084 vs placebo 2018 +0.006 (baselines: +0.089 vs +0.032).
Early stopping never triggered (val R² still creeping up at epoch 40); kept as configured — no retuning.

## Projected cost (measured T4 High-RAM rate 1.27 CCU/h; balance 396.32)
- Ida Track A: 3 models × 2 cutoffs × 5 folds × 2 seeds = 60 trainings × ~27 min ≈ 27 h ≈ 34 CCU.
- Irma Track B (grid 1/9 the area, 64-px tiles): 3 models × 3 cutoffs × 5 × 2 = 90 × ~8 min ≈ 12 h ≈ 15 CCU (estimate).
- Third seed ≈ +25 CCU; Ida Track B ≈ +16 CCU. Placebo retraining for Phase 4 is already included (placebo cutoffs are trained here).
