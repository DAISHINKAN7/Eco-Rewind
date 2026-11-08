# EcoRewind 2.0

**What would these wetlands look like if the hurricane had never happened?** EcoRewind generates storm-free
*counterfactual* satellite time series for coastal wetlands. Hurricane Ida hit Barataria Bay, Louisiana, in 2021;
Hurricane Irma hit the Everglades, Florida, in 2017. The difference between what happened and what would have
happened is the damage attributed to the storm. The project then tries to break its own result: placebo
hurricanes in calm years, inland areas the storm barely reached, and nine competing models.

> Benchmark + cautionary study, pre-registered (`configs/preregistration.yaml`, amendments A1–A5 logged in
> `RESULTS_CHANGELOG.md` before the results they could affect).

## Findings

| | Result |
|---|---|
| Skill | No deep model (ConvLSTM, SimVP, EcoTransformer v2) beats the best simple baseline on held-out spatial blocks. Synth-control: NDVI R² 0.77 / 0.72; best deep model (SimVP): 0.69 / 0.67. Conformal 90 % intervals hit 0.88–0.90 coverage for every model. |
| Robust finding | **Ida, immediately after landfall:** NDVI deficit +0.04 to +0.10. It passes the placebo-in-time test for all 7 model families on both resolutions, and follows a coast-to-inland gradient (placebo in space). |
| Lasting damage | Over the first three full quarters the verdict depends on the model. Placebo-passing models agree on ≈ 0 (spread ≤ 0.007 NDVI); the apparent lasting damage comes from placebo-failing models. |
| Irma | Passes the time placebo, fails the space placebo (inland > coast), and placebo-passing models disagree in sign, so it is not credible evidence. |
| Model dependence (C3) | Ida lead-0 estimates vary 2.8–4.9× across models (v1: ≈ 20×). |

Reports: `reports/phase_2_report.md` … `reports/phase_4_report.md`, `reports/phase_5_1_attribution_spread.md`.
v1 → v2: v1's R² 0.901 came from a leaky random split. The v1 SAR export was broken and the Mississippi AOI was
wrong. All three were found and fixed here (`reports/phase_0_report.md`).

## How it works

```
Earth Engine exports (S2 10 m · HLS 30 m · S1 SAR, quarterly, cloud-masked)       gee/
  → audit → Zarr cubes (T, C, H, W) with validity masks                          src/ecorewind/data/
  → 3.84 km spatial blocks, buffers, 5 stratified folds                          scripts/make_folds.py
  → baselines + deep models through one harness                                  src/ecorewind/{eval,models}/
  → split-conformal intervals calibrated on placebo windows
  → placebo tests in time and space → attribution, spread, external evidence     scripts/placebo_verdict.py …
  → demo export (COG layers + JSON)                                              scripts/export_demo.py
```

Models: persistence, seasonal climatology, harmonic regression (± trend), synthetic control (matched DiD),
LightGBM quantile, ConvLSTM, SimVP, EcoTransformer v2 (SAR-gated factorised attention, direct multi-horizon
quantile heads). Phase 5 adds ablations, cross-site transfer, a resolution comparison and an exploratory
neighbour-informed SimVP. The model list is in `configs/model_registry.json`.

## Reproduce (Google Colab + Google Drive; nothing is downloaded locally)

Needs: an Earth Engine project, Google Drive, a GitHub token in Colab Secrets as `GITHUB_TOKEN`.

| Phase | Notebook | Runtime | Output |
|---|---|---|---|
| 0 Export + audit | `notebooks/01_gee_export_colab.ipynb`, `02_audit_exports_colab.ipynb` | CPU | `MyDrive/EcoRewind2_exports/` (320 files) |
| 1 Cubes + folds | `notebooks/10_phase1_colab.ipynb` | CPU | `MyDrive/EcoRewind2/{cubes,phase1}/` |
| 2 Baselines | `notebooks/20_phase2_colab.ipynb`, `21_placebo_post_colab.ipynb` | CPU | `runs/phase2_baselines_v3` |
| 3 Deep models | `notebooks/30_phase3_colab.ipynb` (section 4) | T4 | `runs/phase3_core_v1` |
| 4 Placebo verdict | `scripts/placebo_verdict.py` (cell in `51_…`) | CPU | `reports/placebo_verdict.md` |
| 5 GPU experiments | `notebooks/50_phase5_gpu_colab.ipynb` | T4 | `runs/phase5_*` |
| 5 Analyses + demo export | `notebooks/51_phase5_analysis_colab.ipynb` | CPU | `reports/*`, `MyDrive/EcoRewind2/demo/` |
| 6 Website data + lab networks | `notebooks/60_web_build_colab.ipynb` | T4 (cell 2), else CPU | `web/public/data`, `MyDrive/EcoRewind2/web_data/lab/` |

Every training run is resumable (per-fold cache on Drive). Compute used so far: Earth Engine 96.6 EECU-h; Colab
≈ 66 CCU (`reports/compute_log.csv`).

Tests: `python -m pytest -q` (55 tests: leakage, temporal cutoff, masking, conformal coverage, harness end to end,
every model and Phase 5 variant through the harness on fixtures).

## Website (`web/`)

Static Vite + React + onnxruntime-web app; every map is the project's own imagery and model output. Pages: a scroll-driven
Ida sequence (Home), a studio to compare all 19 models' maps, ensembles and the full record (Explore), a Lab where the
statistical baselines (exact JS ports) and the SimVP / ConvLSTM / EcoTransformer networks (ONNX) run in the browser on any
study pixel, your own series, your own satellite images or an `.npy` tensor, per-model dossiers (Models), and Evidence,
Pipeline, Story, Reports.

- Run locally: `cd web && npm ci && bash scripts/fetch-data.sh && npm run dev` (details: [`web/README.md`](web/README.md)).
- Deploy for free (Vercel for the app + Cloudflare Pages for the ~1 GB of data): [`DEPLOYMENT.md`](DEPLOYMENT.md).

## Models and weights

- The published results (19 models × sites × folds × seeds) are predictions and metrics stored with each run on Drive
  (`runs/*/deep_cache`, `metrics.csv`, `attribution.csv`); the training loop keeps the best weights in memory only.
- `scripts/export_lab_model.py` trains SimVP, ConvLSTM and EcoTransformer v2 in the published configuration (Louisiana 30 m,
  Ida, fold 0, seed 0) and writes `*.onnx` (run by the website) and `*.pt` (PyTorch weights) to
  `MyDrive/EcoRewind2/web_data/lab/`. Loading either is shown in [`DEPLOYMENT.md` §8](DEPLOYMENT.md#8-the-trained-models-where-they-are-how-to-use-them).

## Repository

```
configs/          sites, tracks, events, phase configs, preregistration.yaml, model_registry.json, carbon.yaml
gee/              Earth Engine export scripts
src/ecorewind/    data/ (cube, masks, folds, normalisation) · eval/ (harness, conformal, attribution) · models/
scripts/          build_cube, make_folds, run_baselines (all models), placebo_verdict, attribution_spread,
                  external_evidence, phase5_tables, carbon_illustrative, export_demo, export_lab_model, build_web_data
notebooks/        Colab runbooks per phase (outputs stripped; results live in reports/)
reports/          phase reports, final analyses, compute log · intermediate/ (superseded run summaries, timings)
tests/            55 tests on synthetic fixtures (python -m pytest -q)
web/              the website (see web/README.md)
docs/             MASTER_PROMPT.md (the project specification cited as "MASTER_PROMPT §…" in the code), DATA.md,
                  archive/ (original plan, first frontend spec)
RESULTS_CHANGELOG.md   amendments A1–A5 and every decision, dated
DEPLOYMENT.md          free deployment guide
```

## Data and credits
Copernicus Sentinel-1/2 (ESA), NASA HLS, ESA WorldCover, Copernicus DEM GLO-30, NOAA HURDAT2. Processed via Google
Earth Engine. See `docs/DATA.md`.
