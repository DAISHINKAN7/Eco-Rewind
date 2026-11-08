# Phase 3 report: deep models (run `phase3_core_v1`, Colab T4)

Status: **core runs complete** — ConvLSTM, SimVP, EcoTransformer v2 × 5 folds × 2 seeds, on Irma (Everglades Track B)
and Ida (Mississippi Track A). Presto, third seed and Ida Track B not run (see "Not done").

## Gate question: does any deep model beat the baselines on held-out blocks? **No.**

Placebo-window skill (held-out test folds, leads ≥ 1, mean over 5 folds; baselines from `phase2_baselines_v3`):

| Model | Irma B NDVI R² | Ida A NDVI R² | Ida A NDMI R² | Ida A NDWI R² | 90 % coverage |
|---|---|---|---|---|---|
| synth_control (best baseline) | **0.765** | **0.716** | **0.643** | **0.780** | 0.90 |
| harmonic_notrend | 0.708 | 0.703 | 0.637 | 0.773 | 0.89–0.90 |
| climatology | 0.702 | 0.699 | 0.639 | 0.771 | 0.89–0.90 |
| harmonic (trended) | 0.594 | 0.534 | 0.365 | 0.655 | 0.90 |
| SimVP (s0 / s1) | 0.694 / 0.664 | 0.661 / 0.669 | 0.535 / 0.524 | 0.762 / 0.772 | 0.89–0.90 |
| ConvLSTM (s0 / s1) | 0.173 / 0.099 | 0.638 / 0.657 | 0.547 / 0.561 | 0.753 / 0.752 | 0.88–0.90 |
| EcoTransformer v2 (s0 / s1) | 0.603 / 0.594 | 0.583 / 0.583 | 0.459 / 0.464 | 0.690 / 0.688 | 0.89–0.90 |

- Every deep model beats the pre-registered comparison (trended harmonic) on Ida A, but none beats the strongest
  baseline (synth_control) or even climatology on either site. Best deep model: SimVP.
- Seeds agree (≤ 0.03 apart) except ConvLSTM on Irma B, which is unstable.
- Validation R² during training (0.7–0.9, in-history pairs) overstates test skill on placebo windows: forecasting a
  new year is harder than fitting the history.
- Conformal coverage is nominal for every model: intervals stay honest even where skill is lower.

## Attribution (NDVI deficit, counterfactual − observed)

Ida, Track A, lead 0 (post-landfall composite, A2/A3) — **consistent across all 12 model runs**:

| | Event | Placebo 2018 (matched days) | Gap |
|---|---|---|---|
| Deep models (6 runs) | +0.071 to +0.079 | +0.017 to +0.027 | ≈ +0.05 |
| Climatology / harmonic_notrend | +0.089 | +0.032 | +0.057 |
| synth_control | +0.035 | +0.003 | +0.032 |

Leads ≥ 1 for Ida: −0.003 to +0.008 (deep), ≈ 0 for baselines: the signal is immediate and transient.
Irma B: EcoTransformer +0.05 (above both placebos), SimVP +0.02 (inside its placebo range); see `intermediate/phase_3_interim_irma.md`.

## Not done (deliberately, pending the user's decision)
- Presto head (checkpoint/licence/band mapping check), third seed, Ida Track B resolution comparison.
- No hyperparameter changes after seeing results.

## Compute
T4 High-RAM: 396.32 -> 331.5 CCU (~64.8 used incl. timing run and restarts; projection was ~49). Running total since Phase 0 (excluding the monthly top-up): ~66 CCU.
