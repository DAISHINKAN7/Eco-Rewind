# Phase 5 report (interim: CPU analyses done; GPU sections A–D running)

## 5.2 External evidence — **independent exposure corroborates Ida and contradicts Irma**

Spearman ρ, block-mean attributed NDVI deficit vs NOAA HURDAT2 best-track distance / peak wind, and coast distance
(36 blocks; block-bootstrap 90 % intervals; `reports/external_evidence.md`).

| Event / track, lead 0 | Distance to track (expect −) | Distance to coast (expect −) | Wind (expect +) |
|---|---|---|---|
| Ida A, 8 non-persistence models | −0.59 … −0.78, all intervals < 0 | −0.43 … −0.65, all < 0 | +0.21 … +0.39 (7/8 intervals > 0) |
| Ida B, 5 non-persistence models | −0.49 … −0.69, all < 0 | −0.49 … −0.66, all < 0 | +0.16 … +0.39 |
| Irma B, all 9 models | **+0.24 … +0.49 (wrong sign)** | −0.08 … +0.10 (≈ 0) | +0.01 … +0.31 |
| Irma A, 6 models | +0.07 … +0.33 (wrong sign) | −0.31 … +0.01 | −0.09 … +0.18 |

- Ida: attributed damage is larger closer to the storm's track, closer to the coast and under stronger wind, for
  every model that passed the placebo test. Persistence (placebo-failing at leads 1–3) is the only model without it.
- Irma: attributed "damage" increases *away* from the track: a third independent check (after the space placebo
  and the sign disagreement) that the Irma signal is not storm damage.

## 5.1 Attribution spread — see `reports/phase_5_1_attribution_spread.md` (2.8–4.9× for Ida lead 0; placebo filtering
collapses the lasting-damage spread to ≤ 0.007).

## 5.6 Carbon — ILLUSTRATIVE, densities unverified
Ida lead 0, placebo-passing models: relative NDVI loss 9–22 % (Track A) / 3–15 % (Track B) over ~7,000 ha.
Carbon numbers use placeholder densities (`configs/carbon.yaml`, verified: false) and must not be quoted until
cited values are filled in. Irma rows are excluded from any interpretation (Irma fails the space placebo and the
external-evidence check).

## 5.3–5.5 + neighbour-informed — pending GPU runs (`notebooks/50_phase5_gpu_colab.ipynb`)
`phase5_tables.md` so far lists the Phase 3 parents only. Fix applied: stale per-fold caches from superseded configs
(pre-`min_history` fix) are now ignored (EcoTransformer Irma B showed 19 instead of 15 cutoff·folds).
