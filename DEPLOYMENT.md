# Deploying EcoRewind for free

This guide puts the EcoRewind website online at zero cost, end to end, with every command spelled out.

**Recommended setup:**

| Piece | Where | Why |
|---|---|---|
| Source code | GitHub (this repository, `main`) | Already there; Vercel deploys from it automatically |
| The website (app, ~15 MB) | **Vercel**, free Hobby plan | Builds the Vite app on every push to `main`, global CDN, HTTPS, preview URLs |
| The site data (~1 GB: maps, pixel samples, networks, tiles) | **Cloudflare Pages**, free plan | Holds many static files (20,000 per site, 25 MiB each), CDN, lets you set the CORS header the app needs |

The app and its data are deliberately separate: the app is small and changes often; the data is large and changes only when
you rerun the analysis. The app is told where the data lives through one build setting, `VITE_DATA_BASE`.

```
 ┌──────────────┐  push   ┌──────────────────────────┐        ┌───────────────────────────────┐
 │ GitHub main  │ ──────► │ Vercel: builds web/       │  GET   │ Cloudflare Pages: data/       │
 │ (code)       │         │ ecorewind.vercel.app      │ ─────► │ ecorewind-data.pages.dev      │
 └──────────────┘         │ VITE_DATA_BASE=…pages.dev │ (CORS) │ results.json, maps.json,      │
                          └──────────────────────────┘        │ layers/, pixels/, lab/, …     │
 ┌──────────────┐  wrangler pages deploy                       └───────────────────────────────┘
 │ Colab / Drive│ ──────────────────────────────────────────────────────▲
 │ (makes data) │
 └──────────────┘
```

> Why not GitHub Pages any more? Its published sites are limited to **1 GB**, and the data alone is ~930 MB before the
> Lab tiles. It still works without the tiles, but there is no headroom left. Sources are at the end.

---

## 0. What you need

- A GitHub account with this repository (it can stay public or become private; Vercel works with either).
- A free **Vercel** account (sign in with GitHub): https://vercel.com/signup
- A free **Cloudflare** account: https://dash.cloudflare.com/sign-up
- One of these, to hold the ~1 GB data folder while uploading it:
  - **Google Colab** (recommended: the data is already on your Drive, nothing is downloaded), or
  - your own computer with Node.js 20+, ~2 GB free disk and a decent connection.

Everything below uses only free tiers. No credit card is needed for the steps shown.

## 1. What actually gets deployed

| Folder / file | Size | Needed by | Comes from |
|---|---|---|---|
| `results.json` | ~0.1 MB | every page | `scripts/build_web_data.py` |
| `maps.json` | ~0.1 MB | Explore, Home, model pages | `build_web_data.py` |
| `layers/<site>_<track>/` | ~810 MB, ~2 000 PNGs | maps everywhere | `export_demo.py` → `build_web_data.py` |
| `pixels/<site>_<track>.json` | ~35 MB (4 files, largest ~15 MB) | Explore inspector, Lab, model pages | `export_demo.py` (rounded by `build_web_data.py`) |
| `training/curves.json` | ~0.4 MB | model pages | `export_demo.py` |
| `lab/` | ~110–230 MB | Lab neural engine | `export_lab_model.py` |
| ↳ `lab/simvp.onnx`, `convlstm.onnx`, `ecotransformer.onnx` | 3.5 / 2.8 / 9.3 MB | the networks the browser runs | |
| ↳ `lab/patches/`, `lab/tiles/`, `lab/meta.json` | | sample inputs, click-anywhere tiles, input spec | |

**Not deployed, and not needed by the site:**
- `*.pt` PyTorch weights (saved next to the ONNX files on Drive since the latest export script; see §8);
- the Zarr cubes, Earth Engine exports and run folders (`MyDrive/EcoRewind2/…`): these are the research archive;
- `lab/_cache/`: training caches (excluded automatically by `build_web_data.py`).

Every file is far below Cloudflare's 25 MiB per-file limit and the total (~2 300 files) is far below its 20 000-file limit.

---

## 2. Get the data folder

### Option A: build it in Colab (recommended)

In `notebooks/60_web_build_colab.ipynb` (CPU runtime, High-RAM):

1. Run **cell 1** (Setup): pulls the latest code, copies cubes and placebo composites.
2. **Cell 2** (lab networks): skip it if the check cell already shows the three networks. To add the tiles without
   retraining:
   ```python
   !python -u scripts/export_lab_model.py --cubes /content/cubes --phase1 {D}/phase1 --table-cache /content/tables \
       --ppost-exports /content/ppost --out {D}/web_data/lab --tiles-only > /content/tiles.log 2>&1; echo exit=$?
   !tail -3 /content/tiles.log
   ```
3. Run **cell 3** (web data). The data folder is now at `/content/ecorewind2/web/public/data`.
4. Skip cells 4–5 (they publish to GitHub Pages, which you are replacing).

Continue with §3, option A, in the same runtime.

### Option B: on your computer

```bash
cd ecorewind-web                       # the unzipped frontend, or <repo>/web
bash scripts/fetch-data.sh             # copies data/ from the gh-pages branch (≈1 GB)
# add the Lab tiles exported on Drive (gh-pages was published before they existed):
#   download MyDrive/EcoRewind2/lab_update.zip (made with the cell below), then
unzip -o lab_update.zip -d public/data/lab
```
Colab cell that makes `lab_update.zip`:
```python
!cd {D}/web_data/lab && zip -qr {D}/lab_update.zip tiles meta.json && ls -lh {D}/lab_update.zip
```

---

## 3. Put the data on Cloudflare Pages

### 3.1 One-time Cloudflare setup

1. Sign in at https://dash.cloudflare.com.
2. Find your **Account ID**: dashboard home → right-hand column ("Account ID"), or *Workers & Pages → Overview*.
   Copy it.
3. Create an **API token** that can deploy Pages projects:
   *My Profile → API Tokens → Create Token → Create Custom Token*
   - Permissions: **Account → Cloudflare Pages → Edit**
   - Account resources: your account
   - Create, then copy the token (it is shown once). Treat it like a password.

### 3.2 The CORS header file

The app reads image pixels into a canvas and downloads the networks from another domain, so the data host must send
`Access-Control-Allow-Origin`. Cloudflare Pages reads response headers from a `_headers` file at the root of the
uploaded folder. Create `data/_headers` (i.e. `web/public/data/_headers`) containing:

```
/*
  Access-Control-Allow-Origin: *
  Cache-Control: public, max-age=3600
/lab/*
  Cache-Control: public, max-age=86400
```

### 3.3 Upload: option A, from Colab (no download to your laptop)

Add your token and account ID to **Colab Secrets** (key icon in the left bar) as `CLOUDFLARE_API_TOKEN` and
`CLOUDFLARE_ACCOUNT_ID`, with notebook access on. Then, in the runtime from §2A:

```python
import os
from google.colab import userdata
os.environ["CLOUDFLARE_API_TOKEN"] = userdata.get("CLOUDFLARE_API_TOKEN")
os.environ["CLOUDFLARE_ACCOUNT_ID"] = userdata.get("CLOUDFLARE_ACCOUNT_ID")
DATA = "/content/ecorewind2/web/public/data"
open(f"{DATA}/_headers", "w").write("/*\n  Access-Control-Allow-Origin: *\n  Cache-Control: public, max-age=3600\n/lab/*\n  Cache-Control: public, max-age=86400\n")
!node -v 2>/dev/null || (curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null && apt-get install -y nodejs >/dev/null)
!npx --yes wrangler@4 pages project create ecorewind-data --production-branch main || true   # first time only
!npx --yes wrangler@4 pages deploy {DATA} --project-name ecorewind-data --branch main --commit-dirty=true
```

The first `project create` makes `ecorewind-data`; later runs print "already exists", which is fine (`|| true`).
The upload takes a few minutes for ~1 GB; re-deploys only upload changed files. The last line prints the URL,
e.g. `https://ecorewind-data.pages.dev`. If the name is taken, choose another and use it everywhere below.

### 3.3 Upload: option B, from your computer

```bash
cd ecorewind-web
printf '/*\n  Access-Control-Allow-Origin: *\n  Cache-Control: public, max-age=3600\n/lab/*\n  Cache-Control: public, max-age=86400\n' > public/data/_headers
npx wrangler@4 login                                   # opens a browser to authorise
npx wrangler@4 pages project create ecorewind-data --production-branch main   # first time only
npx wrangler@4 pages deploy public/data --project-name ecorewind-data --branch main
```

### 3.4 Check the data host

```bash
D=https://ecorewind-data.pages.dev
curl -sI $D/results.json  | grep -iE "^HTTP|access-control|content-type"
curl -sI $D/lab/meta.json | grep -iE "^HTTP|access-control"
curl -s  $D/maps.json | head -c 200; echo
```
Expected: `HTTP/2 200`, `access-control-allow-origin: *`, `content-type: application/json`, and JSON text.
If the CORS line is missing, the `_headers` file was not in the uploaded folder's root.

---

## 4. Put the app on Vercel

### 4.1 Import the repository

1. https://vercel.com/new → **Import Git Repository** → pick `EcoRewind2` (grant Vercel access to it if asked).
2. **Root Directory**: click *Edit* → choose **`web`**. This matters: the app lives in `web/`.
3. Framework preset: **Vite** (auto-detected; `web/vercel.json` sets the same: `npm ci`, `npm run build`, output `dist`).
4. **Environment Variables** → add:
   - Key: `VITE_DATA_BASE`
   - Value: `https://ecorewind-data.pages.dev/` (your data URL **with the trailing slash**)
   - Environments: Production and Preview.
5. **Deploy**. The build takes ~1 minute. You get `https://<project>.vercel.app`.

`VITE_DATA_BASE` is baked in at build time. If you change it, trigger a new deployment
(*Deployments → … → Redeploy*), otherwise the old value stays in the build.

### 4.2 From then on

- Every push to `main` that touches `web/` redeploys automatically; pull requests get preview URLs.
- The research code (`src/`, `scripts/`, `notebooks/`) is not part of the build. Pushes there still trigger a build,
  which is harmless. To skip them: *Settings → Git → Ignored Build Step* → command `git diff --quiet HEAD^ HEAD -- .`
  (Vercel runs it from the Root Directory, so `.` is `web/`; exit code 0 means "skip").
- Custom domain (optional, free with a domain you own): *Settings → Domains → Add*.

### 4.3 Without the Vercel website (CLI)

```bash
cd web
npm i -g vercel
vercel link                                   # once: choose/create the project
vercel env add VITE_DATA_BASE production      # paste https://ecorewind-data.pages.dev/
vercel deploy --prod
```

---

## 5. Verify the live site

Open `https://<project>.vercel.app` and check, in order:

| Page | What you should see | If not |
|---|---|---|
| Home | Hero imagery, the storm sequence, figures with numbers | Blank figures: data URL wrong (see §7) |
| Explore | 10 model tiles for Louisiana 10 m; hovering shows values | Tiles show but no values: CORS (see §7) |
| Lab → A | Chart of a real pixel, 4 models, "vs published |Δ|" ≈ 0.000 | |
| Lab → B | Three network buttons; "Run SimVP" shows `WEBGPU` or `WASM` and "matches PyTorch reference" | Missing networks: lab/ not uploaded |
| Lab → B | "Anywhere in the study area" tile map | Missing: tiles not exported (see §2A step 2) |
| Models / Evidence / Reports | Tables and charts filled | |

Browser check (DevTools → Console on the live site):
```js
const base = "https://ecorewind-data.pages.dev/";          // your VITE_DATA_BASE
for (const p of ["results.json", "maps.json", "lab/meta.json", "pixels/mississippi_A.json", "lab/simvp.onnx"]) {
  const r = await fetch(base + p).catch((e) => e);
  console.log(p, r.status ?? r.message, r.headers?.get?.("access-control-allow-origin"));
}
```
(Each line should print `200 *`.)

---

## 6. Updating later

| You changed… | Do this |
|---|---|
| Frontend code (`web/`) | `git push` → Vercel redeploys by itself |
| Results / maps (reran notebooks 51 or 60) | Rebuild the data (§2A cells 1 and 3) and redeploy it (§3.3); the app needs nothing |
| The lab networks | Rerun cell 2 (delete `MyDrive/EcoRewind2/web_data/lab` first to retrain), then §2A cell 3 and §3.3 |
| The data URL | Change `VITE_DATA_BASE` in Vercel, then *Redeploy* |

Cloudflare keeps every data deployment; roll back under *Workers & Pages → ecorewind-data → Deployments*.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Pages say "not in this deployment" | `VITE_DATA_BASE` missing at build time | Set it in Vercel, then *Redeploy* |
| Console: `blocked by CORS policy` | No `Access-Control-Allow-Origin` on the data | `_headers` must be at the root of the uploaded folder; re-deploy; check with §3.4 |
| 404s for `…pages.devresults.json` | Missing trailing slash | Use `https://…pages.dev/` (the app also adds one, but check the value) |
| Maps load, hover values never appear | CORS missing on PNGs | Same as the CORS row; `_headers` uses `/*` so it covers every path |
| Lab B: "loading simvp…" forever | ONNX blocked or 404 | Open `https://…pages.dev/lab/simvp.onnx` directly; check CORS on `/lab/*` |
| Lab B is slow | No WebGPU in this browser; runs on WebAssembly | Expected (seconds instead of milliseconds); Chrome/Edge have WebGPU |
| wrangler: file too large | A file > 25 MiB | Should not happen (largest ~15 MB); re-run `build_web_data.py`, which rounds the pixel files |
| wrangler: too many files | > 20 000 files | Should not happen (~2 300); remove stray folders (e.g. `lab/_cache`) from the upload |
| Vercel build fails at `tsc` | Type error in your change | Run `npm run build` locally first; the log names the file |
| Vercel builds the wrong folder | Root Directory not set | *Settings → General → Root Directory* = `web` |

---

## 8. The trained models (where they are, how to use them)

**What exists:**
- **Published results** (all 19 models, every site, fold and seed) were produced by `scripts/run_baselines.py`. It keeps the
  best weights in memory while training and stores **predictions and metrics** (`MyDrive/EcoRewind2/runs/…/deep_cache`,
  `metrics.csv`, `attribution.csv`), not weight files. Those predictions are what the maps and numbers on the site are made of.
- **Deployable networks**: `scripts/export_lab_model.py` trains SimVP, ConvLSTM and EcoTransformer v2 on Louisiana 30 m
  (Ida cutoff, fold 0, seed 0, the published configuration) and writes, in `MyDrive/EcoRewind2/web_data/lab/`:
  - `simvp.onnx`, `convlstm.onnx`, `ecotransformer.onnx`: what the website runs (via onnxruntime-web);
  - `simvp.pt`, `convlstm.pt`, `ecotransformer.pt`: PyTorch weights with everything needed to rebuild the network
    (written by exports made with the current script; earlier exports have the ONNX files only).

The website needs **only the ONNX files**, and they are already inside the data folder you deploy (§1). Nothing else
about the models has to be deployed.

**Run an ONNX network in Python** (e.g. on a server or in a notebook):
```python
import json, numpy as np, onnxruntime as ort
L = "web_data/lab"                                   # or the downloaded data/lab folder
m = json.load(open(f"{L}/meta.json"))
S, T, C = m["size"], m["T_in"], m["n_in"]
x = np.fromfile(f"{L}/patches/p0_x.f16", dtype=np.float16).astype("float32").reshape(1, T, C, S, S)
sess = ort.InferenceSession(f"{L}/ecotransformer.onnx")
feeds = {"x": x, "s_in": np.array([m["s_in"]]), "s_out": np.array([m["s_out"]])}
y = sess.run(None, {i.name: feeds[i.name] for i in sess.get_inputs()})[0]   # (1, D, 5 channels, 3 quantiles, S, S)
```
**Rebuild a network from its `.pt` weights** (inside this repository):
```python
import sys, torch; sys.path.insert(0, "src")
from ecorewind.models.deep.trainer import DeepModel
from ecorewind.models.deep.nets import build
ck = torch.load("web_data/lab/simvp.pt", weights_only=False)
net = build(ck["arch"], DeepModel._layout(None, ck["channels"]), ck["D"], ck["T_in"], **ck["arch_kwargs"])
net.load_state_dict(ck["state_dict"]); net.eval()
```
Both snippets were checked against each other: the reloaded PyTorch network and its ONNX export agree to ~1e-6.

**Keep a copy** of `web_data/lab/` outside Drive, e.g. as a GitHub Release asset (*Releases → Draft a new release →
attach a zip*; files up to 2 GiB each) or a Hugging Face model repository.

---

## 9. Alternatives (also free)

**A. Everything on Cloudflare Pages (one host, no Vercel).** Build the app with the data inside and upload once:
```bash
cd web && npm ci && npm run build          # with public/data present (§2B), it is copied into dist/data
printf '/*\n  Access-Control-Allow-Origin: *\n' > dist/_headers
npx wrangler@4 pages project create ecorewind --production-branch main
npx wrangler@4 pages deploy dist --project-name ecorewind --branch main
```
No `VITE_DATA_BASE` needed (the data sits next to the app). You lose Vercel's automatic deploys from GitHub unless you connect
the repository in the Cloudflare dashboard instead (*Workers & Pages → Create → Pages → Connect to Git*; root `web`,
build `npm run build`, output `dist`; the data must then come from elsewhere, because it is not in the repository).

**B. Hugging Face.** The app as a static Space (`bash web/scripts/deploy-hf.sh <user>/ecorewind`, see `web/README.md`),
with the data inside it or in a dataset repository. Hugging Face storage is generous, but browser access to dataset files
goes through redirects that are not documented to send CORS headers for every request type, so **test before relying on
it**: upload, then run the §3.4 `curl` checks against
`https://huggingface.co/datasets/<user>/<repo>/resolve/main/results.json` and a PNG under `layers/`. If the CORS header is
there, set `VITE_DATA_BASE=https://huggingface.co/datasets/<user>/<repo>/resolve/main/`.

**C. GitHub Pages (what you have now).** Works without the Lab tiles while the site stays under 1 GB
(`notebooks/60_web_build_colab.ipynb` cells 3–5). Not recommended going forward.

---

## 10. Limits and costs to keep in mind

- **Vercel Hobby** is intended for personal, non-commercial projects; check the current terms and usage limits at
  https://vercel.com/docs/plans/hobby. The app itself is small (~15 MB) because the data is elsewhere.
- **Cloudflare Pages Free**: 20 000 files per site and 25 MiB per file (sources below). Check
  https://developers.cloudflare.com/pages/platform/limits/ for the current list.
- **Tokens**: the Cloudflare token lives only in Colab Secrets or your shell, never in the repository. To revoke it:
  *My Profile → API Tokens → Roll / Delete*.

## Sources

- GitHub Pages limits (1 GB site size, 100 GB/month soft bandwidth): https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
- Cloudflare Pages limits (20 000 files, 25 MiB per file): https://developers.cloudflare.com/pages/platform/limits/
- Cloudflare changelog, file limit for paid plans (free stays at 20 000): https://developers.cloudflare.com/changelog/post/2026-01-23-pages-file-limit-increase/
- Vercel limits: https://vercel.com/docs/limits
- Hugging Face CORS behaviour on dataset files (community reports): https://github.com/huggingface/datasets/issues/7931 ·
  https://discuss.huggingface.co/t/http-headers-and-cache-for-model-files/80110
