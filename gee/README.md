# Earth Engine export (Phase 0)

Run from Colab with `notebooks/01_gee_export_colab.ipynb` (CPU). Order:

1. `python gee/preflight.py --project ID` → `gee_preflight.md`, `exports/s2_product.json`. Stop if the verdict is STOP.
2. `python gee/<script>.py --dry-run` → lists files, grids and date windows; submits nothing.
3. `--limit 1` → one test task; then no flag → all. Already-submitted tasks are skipped (`--force` to resubmit).
4. `python gee/monitor.py --project ID [--watch 300]`.

Scripts: `export_trackA_s2.py` (S2 10 m), `export_trackB_hls.py` (HLS 30 m), `export_s1.py` (S1 on both grids),
`export_static.py` (DEM, coast distance, WorldCover). Shared code and task planning in `common.py`.
Set `ECOREWIND_REPORTS` to a Drive folder so the preflight output and manifests persist. Details: `docs/DATA.md`.
