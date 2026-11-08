# Drive inventory (metadata only, 2026-10-25)

Built from the Google Drive file listing and the export metadata JSONs already on Drive.
No raster was opened for this page; pixel-level checks are in `data_audit.md` once the
Colab notebook has run.

## Folders

| Source | Drive folder | Files | Quarters (2016Q1–2023Q4) | Notes |
|---|---|---|---|---|
| `everglades_v1` | `EcoRewind/Everglades` | 32 `.tif` + 5 `_mask.tif` | 32/32 | **2017Q2 is `_INTERPOLATED`** (linear gap-fill, not an observation) |
| `mississippi_v1` | `EcoRewind/Mississippi` | 32 `.tif` | 32/32 | Wrong AOI (see below) |
| `mississippi_v2` | `EcoRewind/Mississippi_v2` (root-level folder) | 31 `.tif` | 31/32 | **2016Q2 missing**: export skipped, 0 S2 and 0 S1 scenes |

Other files in `EcoRewind/`: `pipeline_metadata_v2.json`, `mississippi_v2_metadata.json`,
and `validation_report/` (`qc_report.json`, `qc_summary.csv`, `data_readiness.json`, QC PNGs).

## What the v1/v2 metadata already tells us

1. **Your memory is right: v2 is the correct Mississippi.** `mississippi_v2_metadata.json` says
   v1 was centred at (29.5, −90.0), the open Mississippi delta mouth with NDVI ≈ −0.02; v2 is
   centred at (29.45, −90.7), Barataria Bay *Spartina alterniflora* marsh, NDVI ≈ 0.25–0.45,
   20 km × 20 km. v1 `data_readiness.json` even notes "NDVI near 0 is correct for open-water
   delta AOI", so v1 Mississippi was water, not wetland. **Drop `mississippi_v1`.**
2. **CRS differs between versions.** v1 files are EPSG:4326 (degrees, "~10 m equivalent");
   v2 is UTM 15N (EPSG:32615) at 10 m. Everglades exists only as v1, so it is in degrees
   and needs reprojecting to UTM 17N (or re-exporting) before 256 × 256 px spatial blocks
   mean 2.56 km.
3. **Bands (both versions):** Blue, Green, Red, NIR, NDVI, NDWI, SAR_VV, 7 bands.
   **No SWIR (B11/B12) and no SAR VH.** The plan says re-export.
4. **SAR is mostly absent in v2 Mississippi.** Per-quarter S1 scene counts in the export log
   are 0 for 27 of 31 exported quarters (non-zero only in 2016Q1 = 7, 2016Q3 = 1, 2020Q3 = 5,
   2020Q4 = 2). That is very likely the cause of v1's "SAR valid on ~13% of pixels": the
   export filter (probably orbit or instrument-mode settings on `COPERNICUS/S1_GRD`) excluded
   most acquisitions, since Sentinel-1 covered this area every 6–12 days until S1B failed in Dec 2021.
5. **Thin optical composites.** S2 scene counts per quarter range from 1 to 10 (cloud filter ≤20%).
   Quarters built from one scene (2016Q1, 2021Q3 *Ida*, 2022Q2, 2023Q2) are the least
   trustworthy; 2021Q3, the event quarter, is one of them.
6. **Everglades summer quarters:** v1 QC notes 40–51% NaN (cloud) in five Q3 files, which is
   why the `_mask.tif` files exist for 2016Q2/Q3, 2018Q3, 2019Q3 and 2020Q3.
7. **Event timing:** Irma 2017-09-10 → 2017Q3 (6 pre-event quarters, the 2017Q2 one synthetic);
   Ida 2021-08-29 → 2021Q3 (21 pre-event quarters in v2, 2016Q2 missing).

## Duplicates elsewhere in Drive

Search also finds copies of these files (created 2026-04-21 and 2026-04-29) in six other
folders (IDs `16PDp33…`, `149Mtwc…`, `10VcAkaQ…`, `1N9jP5uk…`, `1RYMPZAx…`, `1TDLhYUu…`), probably
from Kaggle or Colab copies. Byte sizes match the originals. The audit reads only the three
folders above; keep the copies or delete them as you like, but don't point code at them.

## Recommended re-export (gate for weeks 1–2)

One committed Earth Engine script (`gee/export_composites.js`), same AOI and grid for both
sites, UTM per site at 10 m, bands:
`B2,B3,B4,B8,B11,B12,NDVI,NDWI,VV,VH,n_clear_obs,n_s1_obs`, with S1 filtered on
`instrumentMode == 'IW'` only (both orbits), plus a per-quarter clear-observation count.
Everglades: replace the interpolated 2017Q2 with a real (even if cloudy) composite plus its mask.
