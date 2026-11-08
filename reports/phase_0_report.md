# Phase 0 report: Earth Engine re-export

Status: **Phase 0 gate PASS** (`data_audit_v2.md`, 2026-10-27). Dates: 2026-10-25 → 2026-10-27.

## What changed

- Re-exported both sites from Earth Engine with committed scripts (`gee/`): 320 Cloud-Optimised GeoTIFFs in
  `MyDrive/EcoRewind2_exports/`. Track A = Sentinel-2 10 m 2015Q3–2023Q4, Track B = HLS 30 m 2013Q2–2023Q4,
  Sentinel-1 on both grids, static layers per grid. Event quarters split into `_PRE` / `_POST` at landfall.
- Grids: UTM per site, origin snapped to 30 m; Track B nests exactly in Track A (3 × 3).
  Everglades EPSG:32617 2199 × 2202 (A) / 733 × 734 (B); Mississippi EPSG:32615 2235 × 2238 / 745 × 746.
- Sentinel-2 product: **TOA (`COPERNICUS/S2_HARMONIZED`) for both sites**, whole series, chosen by the preflight rule
  (SR has about half the scenes before 2017). Cloud Score+ `cs_cdf ≥ 0.6` per pixel; no scene-level filter.
- DEM: `COPERNICUS/DEM/GLO30` is deprecated; switched to `COPERNICUS/DEM/GLO30_2024_1` (band `DEM` verified).
- Distance to coast removed from the export (EE distance kernel limit of 512 px); computed locally in Phase 1.
- Export bugs found and fixed during the run: int/float band mix in Track A composites (empty-quarter placeholder);
  preflight checked S1 bands on the first `S1_GRD` image (often HH/HV) instead of the IW VV+VH subset.

## What was measured (`data_audit_v2.md`, `deep_checks/deep_checks.md`)

| Check | Result |
|---|---|
| Files | 320/320, no duplicates, all readable |
| Grids | one UTM grid per site/track, square 10 / 30 m pixels, B nests in A |
| Bands / types | as specified; band names stored in every GeoTIFF |
| Date windows | every file's mean acquisition day inside its window; PRE ends before, POST starts after landfall |
| **SAR (the v1 bug)** | valid in 34/35 (A) and 35–36/37 (B) periods from 2015; median 6–18 acquisitions per quarter after 2016Q3 (v1: 0 in 27 of 31 quarters). SAR 30 m vs 10 m aggregated: median difference 0.00 dB |
| **NDVI = −1 fills (the v1 bug)** | none in any file |
| Track A vs Track B NDVI | r = 0.84–0.95 on 17 sampled quarters; A lower by 0.06–0.23 (TOA vs surface reflectance) |
| Static | Everglades AOI 93 % wetland (59 % herbaceous, 33 % mangrove); Mississippi 38 % herbaceous wetland, 35 % water, 17 % "tree" |

## Surprises and open issues

1. **Everglades Track A is thin before Irma.** 2015Q3 has no Sentinel-2 data (file exists, fully masked);
   2016Q1, 2017Q2 and 2017Q3_POST have a median of 1 clear observation. Effective pre-event history is 7 quarters.
   Confirms the plan: **Track B is the primary track for Irma** (17 pre-event quarters).
2. **Everglades SAR is sparse before 2016Q4** (1–3 acquisitions per quarter, none in 2016Q1). Mississippi SAR has
   gaps in 2015Q2 (B) and 2015Q4. These become SAR masks; relevant for the SAR ablation.
3. **TOA compresses NDVI strongly** (Everglades Track A NDVI ≈ 0.3 vs 0.55 in HLS). Consistent within a track, and
   r ≥ 0.84 with Track B, so usable for counterfactuals, but absolute NDVI is not comparable across tracks. Report as
   a limitation; candidate ablation: SR-only Track A from 2017.
4. **HLS has negative reflectances** over dark water and shadow, up to 23 % of valid pixels in some Track B
   files (mostly SWIR over water). Rule adopted: an index is invalid where any of its own input bands is ≤ 0
   (`masks.py` in Phase 1; the audit already uses it).
5. **Season-outlier quarters** (robust z > 3.5): Mississippi 2015Q4, 2023Q4 (A) and 2014Q1 (B); Everglades 2021Q1 (B).
   Mississippi 2023Q4 is low in both tracks, so it is probably a real landscape signal (2023 drought) rather than an artefact.
   Not removed; noted for model diagnostics.
6. **Irma POST composite is cloudy** (A 88 % valid, B 62 %, 1 clear observation); Ida POST is good (A 100 %, 3 obs).
7. **Mississippi "tree" 17 %** in WorldCover is likely ridge/levee forest and some misclassified marsh; the strict
   wetland mask (herbaceous wetland + mangrove only) excludes it.
8. **First visible signal**: Ida POST shows VV +2 dB and Track A NDVI 0.44 → 0.33; Irma POST shows Track A NDVI 0.28 → 0.21.
   Not analysed further until the counterfactual models exist (no peeking at post-event data for tuning).

## Gate

All Phase 0 conditions hold (UTM, square pixels, one grid, all periods present, SAR valid in the large majority of
quarters, no NDVI = −1). The first audit run reported "NDVI out of range" on early Track B files; the cause was
negative HLS reflectance in the audit's NDVI computation, not the data. Audit rule fixed (`audit_exports.py`, test
added); re-run on all 320 files: **Gate PASS**, every check green.

## Compute used

Earth Engine: **96.6 EECU-hours of 150** (Community tier, noncommercial). 320 successful tasks carry all of it;
55 failed and 65 cancelled attempts used none. Colab Pro: CPU runtime only (≈0.08 CCU/h), **≈1.0 CCU used** (200 → 198.98). No GPU used.
