# Phase 4 report: placebo tests (the deciding experiment)

Rule (pre-registered + amendment A4): PASS iff the event's median NDVI deficit (per test fold) exceeds the 95th
percentile of the model's placebo distribution (windows × folds × seeds) AND placebo 90 % coverage ≥ 0.80.
Full tables: `MyDrive/EcoRewind2/reports/placebo_verdict.md` (+ `placebo_verdict_primary.csv`, `_lead0.csv`,
`placebo_in_space.csv`). 9 model families (6 baselines, 3 deep) × 3 site/track/event combinations.

## Verdict by the rule

| | Irma (Everglades B) | Ida (Mississippi A) | Ida (Mississippi B) | Total |
|---|---|---|---|---|
| Primary, leads 1–3 | 9 / 9 pass | 4 / 9 pass | 2 / 6 pass | **15 / 24** |
| Secondary, lead 0 | 7 / 9 pass | 9 / 9 pass | 6 / 6 pass | **22 / 24** |

Coverage ≥ 0.88 everywhere, so every verdict is decided by the exceedance criterion.

## Interpretation (beyond the mechanical rule)

1. **Ida, lead 0 — robust.** All 15 model × track combinations pass, 80–100 % of event folds above the placebo p95,
   event deficit +0.04 to +0.10 NDVI vs p95 +0.01 to +0.07. Placebo in space supports it: on Track B the
   least-exposed (inland) blocks show ≈ 0 for climatology / harmonic_notrend / lgbm / synth_control
   (−0.01 to +0.00) against +0.05 to +0.07 over all blocks; on Track A the inland deficit is about half the
   all-block value (storm footprint wider than the 22 km AOI).
2. **Leads 1–3 — no robust lasting signal, and the verdict depends on the model (claim C3).** For Ida the same event
   passes for climatology / harmonic_notrend / SimVP / EcoTransformer and fails for synth_control / LightGBM /
   ConvLSTM / harmonic / persistence. Passing event medians are near zero (−0.015 to +0.002); they pass because
   placebo years are biased negative. With 1–3 placebo years, p95 ≈ the placebo maximum.
3. **Irma — passes in time, fails in space.** Irma B passes 9/9 (leads 1–3) and 7/9 (lead 0), but the inland blocks
   show a *larger* lead-0 deficit than the site average (+0.05 to +0.12 vs −0.02 to +0.05) for every model.
   Damage would show the opposite gradient, so the Irma signal is not supported spatially. Plausible causes: the
   whole AOI was exposed (Irma's footprint), sparse 30 m Landsat-era composites, only 2 placebo years.
4. **Deep models add nothing to the verdict.** They pass/fail like the baselines; ConvLSTM's placebo distribution
   on Irma B is the widest (−0.26 to −0.03).

## Framing options (user's decision, MASTER_PROMPT §9)
- Method paper: not supported (deep models neither beat baselines nor pass more often).
- **Benchmark paper**: simple counterfactuals match or beat deep models with honest intervals; one robust finding
  (Ida, immediate post-landfall deficit, consistent across 7 model families and spatially coherent).
- **Cautionary paper**: lasting-damage verdicts flip with the model; Irma passes the time placebo but fails the
  space placebo; few placebo years make p95 fragile — attribution needs both placebo types and many models.
Recommended: benchmark + cautionary combined (they share the same evidence).
