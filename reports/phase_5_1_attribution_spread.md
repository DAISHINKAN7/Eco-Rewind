# Phase 5.1 — attribution spread across models (C3)

Full tables: `MyDrive/EcoRewind2/reports/attribution_spread.md` (+ `attribution_per_model.csv`, `attribution_spread.csv`).

| Event / track | Statistic | All models: range [ratio] | Placebo-passing only: range [ratio] |
|---|---|---|---|
| Ida A | lead 0 | +0.035 … +0.096 [2.8×] | same (9/9 pass) |
| Ida B | lead 0 | +0.021 … +0.101 [4.9×] | same (6/6 pass) |
| Ida A | leads 1–3 | −0.010 … +0.071 (signs differ) | −0.005 … +0.002 (4 models) |
| Ida B | leads 1–3 | −0.024 … +0.073 (signs differ) | −0.016 … −0.011 [1.5×] (2 models) |
| Irma B | lead 0 | −0.015 … +0.055 (signs differ) | same, signs differ (7/9 pass) |
| Irma B | leads 1–3 | −0.002 … +0.048 (signs differ) | same (9/9 pass) |

Findings
1. **Ida lead 0:** every model agrees on the sign; magnitude varies 2.8–4.9× (v1: ≈ 20×). Synth-control (uses
   post-storm neighbours) and persistence give the smallest estimates, trended harmonic the largest.
2. **Placebo filtering collapses the lasting-damage spread for Ida:** all models span ≈ 0.08–0.10 NDVI at leads 1–3,
   placebo-passing models span ≤ 0.007, all ≈ 0. The models that pass agree there is **no lasting damage**; the
   apparent lasting damage comes from placebo-failing models (persistence +0.07 with an equal placebo bias).
3. **Irma:** placebo-passing models disagree in **sign**, so passing the time placebo alone does not make the
   estimate meaningful (consistent with the failed space placebo).
4. **Caveat for the paper:** the "90 % interval" here is the mean of per-pixel conformal bounds, i.e. the typical
   pixel uncertainty, not an interval for the site mean. Site-mean uncertainty must come from fold-to-fold and
   seed variation (Phase 4 distributions); report both and label them.
5. Everglades Track A has no placebo window, so no interval and no verdict (report-only).
