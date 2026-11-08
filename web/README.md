# EcoRewind website

Static single-page app: Vite + React 18 + TypeScript, onnxruntime-web for the in-browser networks, hand-built SVG/canvas
charts. No server code: it reads JSON, PNG and ONNX files from a `data/` folder and works on any static host.

## Requirements

- Node.js 20 or newer (`node -v`), npm 10+
- The data folder (~1 GB): results, map layers, pixel samples, lab models. See "Data" below.

## Run locally

```bash
cd web
npm ci                       # install exact dependency versions from package-lock.json
bash scripts/fetch-data.sh   # copy the published data from the gh-pages branch into public/data (once, ~1 GB)
npm run dev                  # http://localhost:5173
```

Without the data the site still runs, but most pages show "not in this deployment" placeholders.

Other commands:

| Command | What it does |
|---|---|
| `npm run build` | Type-checks, then writes the production site to `dist/` (copies `public/data` into it) |
| `npm run preview` | Serves `dist/` at http://localhost:4173 to check the production build |
| `npx tsc --noEmit -p .` | Type-check only |

## Data

Everything on the site comes from one folder with this layout:

```
data/
  results.json            leaderboard, verdicts, attribution, evidence, Phase 5, compute log
  maps.json               per site/track: footprint, quarters, models, cutoffs, available layers
  layers/<site_track>/    colourised PNG layers (observed, counterfactual, deficit, uncertainty, disagreement, true colour)
  pixels/<site_track>.json 3000 sampled pixel histories with every model's forecast
  training/curves.json    validation curves for every deep-model training
  lab/                    ONNX networks (simvp/convlstm/ecotransformer.onnx), patches, tiles, meta.json
```

It is produced by `scripts/build_web_data.py` (run by `notebooks/60_web_build_colab.ipynb`). To get it:

- **From the published site:** `bash scripts/fetch-data.sh` (sparse clone of the repository's `gh-pages` branch).
- **From Google Drive:** after notebook 60 has run, copy the built `web/public/data` folder.

### Hosting the data somewhere else

The app looks for `./data/` next to `index.html`. To keep the ~1 GB of data on a separate host (a Hugging Face dataset,
a bucket, a CDN, GitHub Pages), build with:

```bash
VITE_DATA_BASE=https://your-data-host.example/ecorewind/data/ npm run build
```

The data host must send `Access-Control-Allow-Origin: *` (the explorer reads image pixels into a canvas, which needs CORS).
Check with `curl -sI <VITE_DATA_BASE>results.json | grep -i access-control` before switching; buckets usually need CORS
switched on explicitly.

## Deploy

The site uses hash routing (`/#/explore`), so no server rewrites are needed anywhere.

### GitHub Pages
`notebooks/60_web_build_colab.ipynb` builds the site and pushes `dist/` to the `gh-pages` branch. Or by hand:

```bash
npm run build
cd dist && touch .nojekyll && git init -q && git checkout -q -b gh-pages && git add -A && git commit -qm "site build"
git push -f https://github.com/<you>/<repo>.git gh-pages
```
Then repository Settings → Pages → Deploy from branch → `gh-pages` / root.

### Vercel
`vercel.json` is included (Vite preset, `dist` output, caching and CORS headers).

1. Import the repository in Vercel and set **Root Directory** to `web`.
2. The ~1 GB data folder is likely too large for a Vercel deployment, so host the data elsewhere and add an
   environment variable `VITE_DATA_BASE` (see above) before building. Vercel's limits change; check the current
   limits page before relying on any number.
3. Or deploy a local build: `npm i -g vercel && vercel deploy --prod` from `web/`.

### Hugging Face Spaces (static)
A static Space serves `index.html` directly. `deploy/huggingface/README.md` holds the Space metadata (`sdk: static`).

```bash
pip install -U huggingface_hub
hf auth login                                  # write token from huggingface.co/settings/tokens
bash scripts/deploy-hf.sh <your-username>/ecorewind
```
The script builds, adds the Space README, creates the Space if needed and uploads `dist/` (large folders are split
into several commits; re-running resumes). With the data included this is ~1 GB, which counts against your Hub storage.

### Any other static host
Upload the contents of `dist/` (Netlify, Cloudflare Pages, S3 + CloudFront, nginx…). Same data options as above.

## Bring your own data (Lab)

Everything runs in the browser; nothing is uploaded anywhere.

| Input | Engine | Format |
|---|---|---|
| A quarterly series | Forecast engine (4 statistical models) | CSV / text, one `YYYYQn, value` per line, NDVI in [−1, 1], `nan` for clouds |
| A quarterly image series | Forecast engine, every pixel | One image per quarter, same size: Sentinel-2 / HLS multi-band GeoTIFF (NDVI computed), single-band NDVI GeoTIFF, or greyscale PNG/JPG with a stated NDVI range. Large images are averaged to ≤ 160 px |
| 8 quarterly satellite scenes | Neural engine (SimVP / ConvLSTM / EcoTransformer) | Multi-band GeoTIFFs (Sentinel-2 L1C/L2A 12–13 bands, HLS 6 bands, or 4 bands G/R/NIR/SWIR1), same grid, ≥ 64 × 64 px after resampling to the model's resolution. NDVI, NDMI, NDWI are computed with the cube's formulas; radar is treated as missing; terrain set to the training median; land cover chosen by you |
| A model-ready tensor | Neural engine | `.npy`, shape (8, 18, 64, 64), physical or model units (channel spec on the page; templates downloadable) |

Synthetic examples ship in `public/examples/` (12 NDVI GeoTIFFs; 8 Sentinel-2 L2A-style scenes) and load with one click.

## Code map

```
src/
  App.tsx                 routes, scroll reveal, true-colour SVG filter
  pages/                  Home · Explore (studio) · Lab · Models (+ model detail) · Evidence · Pipeline · Story · Reports
  components/
    HeroRewind.tsx        scroll-driven canvas hero (real imagery, HURDAT2 track, rewind)
    Stage.tsx             pan/zoom image stage with swipe, crosshair and pin (used by the explorer)
    ForecastEngine.tsx    live forecasting UI: study pixel, your series, your image series
    ImageSeries.tsx       quarterly image uploads → per-pixel forecasts and damage maps
    SceneUpload.tsx       Sentinel-2/HLS scenes → network input (indices, resampling, window, seasons)
    charts.tsx            SVG charts (time series, forest, placebo strip, scatter with label repel, bars)
    ui.tsx                nav, footer, small UI parts
  lib/
    data.ts               data loading, BASE / VITE_DATA_BASE, shared types
    models.ts             names, colours and families of all models
    explore.ts            map/layer/pixel helpers
    raster.ts             decode colourised PNGs back to values; in-browser ensembles
    forecast.ts           JS ports of persistence, climatology and robust harmonic regression
    npy.ts                .npy reader/writer for the neural engine
    imagery.ts            GeoTIFF/PNG reading (geotiff.js), spectral indices, resampling
    fx.tsx                reveal, count-up, cursor highlight, marquee
```

The forecasting engine (`lib/forecast.ts`) reproduces the Python baselines in `src/ecorewind/models/baselines/`
to within 0.0004 NDVI on the published pixel samples; the ONNX networks reproduce PyTorch to within 0.001.
