# Results changelog

Every change to the pre-registered analysis, with the reason and what had been seen when it was made.

## 2026-10-27 — amendments A1, A2 (before Phase 3)

Seen at the time: Phase 2 baseline run `phase2_baselines_v1` (placebo skill, coverage, preliminary event deficits).
No deep model trained.

- **A1 — `harmonic_notrend` rung.** The trended harmonic baseline was worse than climatology everywhere; the trend
  term extrapolates poorly from short quarterly histories. Added the trend-free variant (no tuned parameter). The
  deep-vs-baseline comparison is against the best rung on the ladder.
- **A2 — lead 0, secondary.** Evaluate the event-quarter `_POST` partial (placebos: the full cutoff quarter).
  Primary claims unchanged (leads ≥ 1). Caveat: placebo lead 0 covers a full quarter, the event composite ~1 month.
- Re-run: `phase2_baselines_v2` (v1 kept unchanged on Drive).

## 2026-10-27 — amendment A3 (after seeing v2 lead 0)

- **A3 — matched placebo lead 0.** v2 showed lead-0 event deficits of +0.07 to +0.12 NDVI against full-quarter
  placebo lead 0. Because the event composite is ~1 month, the placebo lead 0 is now exported over the same days
  (`*_PPOST`). Made after seeing v2; it can only remove spurious signal, not add it. Re-run: `phase2_baselines_v3`.

## 2026-10-28 — Phase 3 training pairs for short histories (implementation fix, before any deep result was evaluated)

- `irma_placebo_2015` (9 history quarters, T_in 8) had one training anchor, so only target distance 1 was ever
  supervised and leads 1–4 came from untrained output heads. Anchors now start once 4 quarters are observed
  (`min_history: 4`), with inputs zero-padded to T_in and validity 0; validation uses every anchor so every distance is
  checked. T_in stays 8 (pre-registered); the prediction anchor is unchanged. Runs started before this were discarded
  (the cache key includes the config, so they retrain automatically).

## 2026-11-02 — amendment A4 (Phase 4 operationalisation, before running it)

- The pre-registered placebo rule did not fix the statistic or pooling. Fixed now, before computing: per-fold NDVI
  deficit averaged over leads 1–3; placebo distribution = windows × folds × seeds per model family; lead 0 as the
  secondary analysis; placebo-in-space by coast distance (the NDVI-drop proxy is outcome-based, hence circular).
  Seen at the time: Phase 3 tables (site means), not the per-fold distributions this test uses.

## 2026-11-02 — paper framing (user decision after Phase 4)

- **Benchmark + cautionary paper.** Basis: reports/phase_4_report.md (deep models do not beat baselines; Ida lead-0
  signal robust in time and space; lasting-damage verdicts model-dependent; Irma fails the space placebo).

## 2026-11-02 — amendment A5 (Phase 5 experiments, before any Phase 5 GPU run)

- Ablations, cross-site transfer, resolution comparison and the **exploratory** neighbour-informed SimVP declared in
  `configs/preregistration.yaml` (A5), with the comparison each one is judged on. The neighbour-informed model is
  labelled post hoc everywhere (designed after seeing Phase 3/4 results).
