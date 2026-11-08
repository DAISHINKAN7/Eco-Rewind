# EcoRewind — Frontend Specification (v1, for mock-ups)

> Purpose of this document: a complete brief for generating visual mock-ups (ChatGPT image generation or a designer),
> and later the build spec. Every screen, component, state, colour and data contract is described. Mock-ups should
> show **real-looking** satellite imagery of coastal wetlands (Louisiana marsh, Florida Everglades mangroves), not
> generic dashboards.

---

## 0. One-paragraph pitch (put this in the hero)

**EcoRewind asks: what would these wetlands look like today if the hurricane had never happened?** Machine-learning
models "rewind" the satellite record and generate a storm-free counterfactual for every pixel. The difference between
what happened and what would have happened is the damage the storm caused. Then comes the twist: *we tried to break
our own result*. Fake hurricanes in calm years, inland areas the storm never reached, nine competing models. Some
findings survived. Most did not. This site shows both.

Tone: a scientific instrument that's also beautiful. Think NASA Earth Observatory × Bloomberg graphics × a
high-end data-viz studio (Pudding, Reuters Graphics). Calm, confident, honest. Never "AI magic" hype.

---

## 1. Audience & goals

| Audience | What they must get in 60 seconds |
|---|---|
| Recruiters / hiring managers (ML, DL, geospatial) | End-to-end ML system: data engineering → 9 models → rigorous evaluation → deployed live inference |
| Researchers / reviewers (Climate Change AI) | The method, the placebo falsification, honest negative results, reproducibility |
| General public | Scrub time, see the storm hit, see the counterfactual, understand uncertainty |

Success: a visitor can (1) watch the storm hit and the counterfactual diverge, (2) switch models and *see* the
attribution change, (3) run a placebo and see a fake signal fail, (4) run a model live in their browser, (5) find
every number in the paper traced to a run.

---

## 2. Information architecture (routes)

```
/                     Landing: hero "rewind" animation + 4 entry cards
/explore              THE MAP: swipe / time / model / placebo (the centrepiece)
/explore/:site        Deep link: everglades | mississippi (+ query: track, model, quarter, view, placebo)
/lab                  Live counterfactual lab (in-browser model inference)
/models               Model zoo + leaderboard + model cards (extensible registry)
/models/:id           Model card (architecture diagram, training curves, skill, placebo verdict)
/evidence             Placebo tests: in time, in space; verdict matrix; attribution spread (C3)
/pipeline             How it was built: data → cube → folds → models → conformal → placebo (animated diagram)
/story                Scrollytelling narrative incl. the v1 → v2 story (bugs found & fixed)
/data                 Data sources, coverage heatmaps, downloads, licences
/paper                Paper, figures, numbers, citation, reproducibility, compute log
/about                Author, contact, credits
```

Global nav (top bar, translucent over the map): logo "EcoRewind" (wordmark + rewind-arrow-over-leaf icon) ·
Explore · Lab · Models · Evidence · Pipeline · Story · Paper · theme toggle (light/dark) · GitHub icon.
Mobile: bottom tab bar (Explore, Lab, Evidence, Story, More).

---

## 3. Visual language

### 3.1 Colour tokens (dark default; light variant)

| Token | Dark | Light | Use |
|---|---|---|---|
| `--bg` | `#0B1210` (deep marsh black-green) | `#F6F4EE` (paper) | page |
| `--surface` | `#121C19` | `#FFFFFF` | panels/cards |
| `--surface-glass` | `rgba(18,28,25,0.72)` + 12 px blur | `rgba(255,255,255,0.78)` | floating map panels |
| `--text` | `#E8EFEA` | `#14201C` | body |
| `--muted` | `#8FA39A` | `#5E6F68` | secondary |
| `--observed` | `#E9C46A` (sand gold) | `#B8860B` | "what happened" lines/layers |
| `--counterfactual` | `#5EEAD4` (teal glow) | `#0F766E` | "no-storm" lines/layers |
| `--damage` | sequential `#FFF3B0 → #F4A261 → #E76F51 → #9B2226` | same | deficit heatmap (positive = loss) |
| `--recovery` | `#2A9D8F → #264653` | same | negative deficit (greener than expected) |
| `--placebo` | `#A78BFA` (violet) | `#6D28D9` | anything placebo |
| `--pass` / `--fail` | `#4ADE80` / `#F87171` | `#15803D` / `#B91C1C` | verdict badges |
| `--interval` | counterfactual at 18 % opacity | same | 90 % bands |
| `--storm` | `#F8FAFC` thin line + glow | `#0F172A` | landfall markers |

Diverging damage scale is centred at 0, symmetric, clipped at ±0.15 NDVI; legend always visible.
Colour-blind safe: verify the damage/recovery and observed/counterfactual pairs with a CVD simulator.

### 3.2 Typography
- Display: **Fraunces** (or Newsreader), large, editorial, for hero and section titles.
- UI/body: **Inter**. Numbers: **JetBrains Mono** / tabular figures for every metric.
- Scale: 64 / 40 / 28 / 20 / 16 / 13 px.

### 3.3 Motion
- Time scrubbing is buttery: cross-fade between quarterly rasters (200 ms), damage layer "breathes in" when the
  storm passes (400 ms ease-out), storm track draws on with a glowing head.
- Number tickers animate on change (300 ms). Respect `prefers-reduced-motion` (instant swaps).
- Map is full-bleed; panels float on glass.

### 3.4 Iconography & imagery
- Line icons (Lucide). Sensor badges: S2 (Sentinel-2), HLS (Landsat+S2), S1 (SAR radar).
- Base imagery: true-colour satellite composites of each quarter; optional hillshade/terrain.
- Illustrations: thin-line technical diagrams (architecture, pipeline), same palette.

---

## 4. Global components

| Component | Description |
|---|---|
| `TimeScrubber` | Horizontal timeline 2013Q2 → 2023Q4, one tick per quarter; event quarter marked with storm icon and split PRE/POST notch; placebo dates violet; drag handle shows quarter label + sensor badge + clear-pixel %; play/pause, speed 0.5×/1×/2×, loop; keyboard ←/→ |
| `SwipeCompare` | Vertical divider over the map, draggable; left = Observed, right = Counterfactual (label chips at top); alternative mode "Split 3" (Observed | Counterfactual | Deficit) |
| `ModelSwitcher` | Pill carousel of models grouped *Baselines / Deep / Experimental*; each pill: name, family icon, placebo badge (pass/fail/untested), NDVI R²; "Compare 2" mode |
| `PlaceboToggle` | Switch "Real event ↔ Placebo (fake landfall)"; when on, UI tints violet, scrubber jumps to the placebo date, banner: "No hurricane happened here. Any 'damage' is model error." |
| `LayerPanel` | Layers: true colour, NDVI, NDMI, NDWI, SAR VV/VH, deficit, interval width, wetland mask, folds/blocks, buffers, coast-distance exposure, storm track, landfall point; opacity sliders |
| `PixelInspector` | Click → side sheet: lat/lon, land cover, fold, block; chart of observed vs counterfactual (median + 90 % band) over time for the selected channel; deficit at each lead; "this pixel's placebo" mini-chart |
| `MetricCard` | Big number + label + interval + tiny sparkline + provenance link ("from run phase3_core_v1, fold mean") |
| `VerdictBadge` | PASS / FAIL / UNTESTED / EXPERIMENTAL, colour + icon + tooltip with rule |
| `Provenance` | Small "ⓘ source" chip on every number → popover: run id, git commit, data hash, script |
| `HonestyBanner` | Contextual notes (e.g., "Irma passes the time test but fails the space test — treat with caution") |

---

## 5. Page specs

### 5.1 Landing `/`
- **Hero (full viewport):** satellite view of the Barataria marsh. Autoplay loop (8 s): quarter by quarter →
  Hurricane Ida's track sweeps in (white glow) → the observed imagery browns → a teal "rewind" wipe sweeps right-to-left
  revealing the green counterfactual → the damage heatmap ignites along the coast. Headline (Fraunces 64):
  **"What would the marsh look like if the hurricane never came?"** Sub: "Counterfactual satellite forecasting,
  stress-tested with placebos." CTAs: **Explore the rewind** (primary), **Run a model live** (secondary).
- **Stats strip:** 2 hurricanes · 2 sites · 10 years of imagery · 9 models · 150 deep-model trainings · 24 placebo tests ·
  1 robust finding. Each animates in.
- **Four cards:** Explore (map thumbnail) · Lab (glowing neural grid) · Evidence (verdict matrix thumbnail) ·
  Story (v1→v2 thumbnail).
- **"The honest result" teaser:** three one-liners with badges: ✅ Ida's immediate post-landfall damage is real
  (survives every test) · ⚠️ Lasting damage depends on which model you ask · ❌ Irma's signal fails the inland test.

### 5.2 Explore `/explore` (centrepiece)
Layout (desktop): full-bleed MapLibre map; top: site tabs (Everglades / Barataria-Mississippi) + track toggle
(10 m Sentinel-2 / 30 m HLS); bottom: `TimeScrubber`; left floating glass panel: `ModelSwitcher` + `LayerPanel`;
right floating panel: **Attribution card** (site-mean deficit for the selected model & quarter, 90 % interval,
area-integrated NDVI·ha, placebo verdict badge, compare-to-other-models mini dot plot); bottom-right: legend.
- **Swipe mode** (default): Observed | Counterfactual.
- **Deficit mode:** heatmap over true colour; hover tooltip shows value + interval.
- **Uncertainty mode:** interval width map ("where the model is unsure").
- **Model-disagreement mode:** per-pixel standard deviation across models (C3 as a map).
- **Compare models:** two synced maps side by side (e.g., SimVP vs synth-control), linked cursors.
- **Placebo toggle:** same UI, fake landfall (2018 for Ida; 2015/2016 for Irma).
- **Exposure overlay:** coast-distance bands; the 20 % least-exposed blocks outlined (space-placebo region), with
  their mean deficit shown in a callout ("inland: +0.00 vs all: +0.07 → damage follows the coast ✅").
- **Folds overlay:** 3.84 km blocks coloured by fold, buffers hatched (shows the leakage-proof split).
- Mobile: map full screen; panels become bottom sheets; swipe divider is horizontal.
- Empty/loading states: skeleton shimmer over map; "tiles for this quarter are thin (2 clear Landsat scenes)" warning
  when clear-pixel % < 30.

### 5.3 Live Lab `/lab`
"Run a hurricane-free forecast yourself, in your browser."
- Left: mini-map to pick a 128 × 128 (10 m) or 64 × 64 (30 m) patch; or choose from 6 curated patches
  (coastal marsh, inland marsh, mangrove fringe, open water edge, farmland control, urban control).
- Center: **input strip** — the 8 input quarters as thumbnails (NDVI false-colour), each with a toggle to drop
  it (simulate clouds) and a SAR on/off switch; **cutoff picker** (any quarter; real landfall and placebo dates
  highlighted).
- Button **Generate counterfactual** → animated inference: a neural "pulse" visual, per-step progress, timing chip
  ("SimVP · 0.85 M params · 420 ms · WebGPU"). Output: next 1–9 quarters as a film strip: counterfactual median,
  q10/q90, observed (if the future exists), deficit.
- Right: **chart** for the patch mean with band; **what-if controls**: drop SAR, drop quarters, shorter history (T_in 4/8);
  model selector (only browser-exportable models, labelled).
- Footer note: "Illustrative live run of the published model weights. Paper numbers come from the full 5-fold
  evaluation, not from this widget."
- Fallback when WebGPU/WASM unsupported: precomputed outputs for the curated patches.

### 5.4 Models `/models` and `/models/:id` (extensible registry — see §7)
- **Leaderboard table:** model, family (Baseline / Deep / Experimental / Ablation), params, NDVI R² (Irma B, Ida A)
  with ± fold std, coverage, placebo verdicts (lead 0 / leads 1–3 per event), compute (GPU-h, CCU), status.
  Sort/filter; a "skill vs uses-post-cutoff-information" toggle explaining synth-control's advantage.
- **Scatter:** skill (x) vs placebo pass-rate (y), bubble = params, colour = family. Insight callout: "bigger ≠ better".
- **Model card page:** hero name + one-line idea; animated **architecture diagram** (e.g., EcoTransformer: optical &
  SAR patch embeddings → SAR gate → factorised time/space attention → horizon queries → quantile heads); inputs/outputs;
  training curves (val NDVI R² per epoch per fold, from logs); skill table per band/horizon; attribution maps
  small multiples; placebo verdict; limitations; code link; "used in the live lab" badge.
- **Slots reserved now (status: Planned / Running / Done):**
  - *Ablations:* EcoTransformer SAR off · SAR concat · smoothness loss · static off · T_in 4 / 12.
  - *Experimental:* **Neighbour-informed deep model** (uses least-exposed neighbours' contemporaneous signal;
    declared post-Phase-3 follow-up — always shown with an "Experimental, developed after seeing results" ribbon).
  - *Expanded:* Presto head, Prithvi-EO-2.0 head, Earthformer, third seed.
  Planned models show a ghost card with the hypothesis and pre-registration link; no fake numbers.

### 5.5 Evidence `/evidence`
- **Verdict matrix (hero):** rows = 9+ models, columns = (Irma B, Ida A, Ida B) × (lead 0, leads 1–3); cells = PASS/FAIL
  with the event-vs-p95 margin as a mini bar. Hover → distribution plot.
- **Placebo-in-time explainer:** animated: draw 10–20 placebo dots (violet beeswarm), mark the 95th percentile line,
  drop the real-event dots (gold) — they land above (pass) or within (fail). One panel per event × model, small multiples.
- **Placebo-in-space explainer:** coast→inland gradient chart (deficit by coast-distance decile) for Ida B (clean
  gradient) vs Irma B (inverted) with a map inset of the inland blocks.
- **Attribution spread (C3):** forest plot — one row per model, point + 90 % interval, placebo-failing models faded;
  range/ratio callout; comparison with v1's "~20×".
- **Lead-time decay:** deficit vs lead (0…8) per model; shows "immediate and transient".
- **Coverage check:** calibration plot (nominal 90 % vs achieved 0.88–0.90).

### 5.6 Pipeline `/pipeline`
Horizontal scroll-driven animated diagram, each stage clickable with a detail drawer + real artefact preview:
1. **Earth Engine export** — 320 files, Sentinel-2 / HLS / Sentinel-1 SAR, cloud masking, quarterly composites
   (show a quarter assembling from scenes).
2. **Audit** — the checks (grid nesting, SAR sanity, coverage heatmap).
3. **Data cube** — Zarr (T, C, H, W), 12 channels, validity masks (rotating 3-D cube visual).
4. **Spatial folds** — 3.84 km blocks, buffers, stratified folds (map animation).
5. **Pre-registration** — the locked YAML with amendments A1–A4 (git timeline).
6. **Models** — 6 baselines + 3 deep (+ reserved slots) fan out.
7. **Conformal intervals** — calibration on placebo windows.
8. **Placebo tests** — time + space.
9. **Outputs** — maps, tables, paper, this site.
Side rail: compute meter (Earth Engine EECU-h, Colab CCU by phase), tests count (52 passing), git commits.

### 5.7 Story `/story` (scrollytelling)
Chapters (sticky map/visual on the right, text on the left):
1. *The question* — wetlands, carbon, hurricanes.
2. *The idea* — counterfactual = "rewind" (swipe demo).
3. *Version 1* — R² 0.901 looked amazing… the leaky split (animated: test pixels next to training pixels); the SAR
   export bug; the wrong Mississippi AOI. "We threw it away."
4. *Version 2* — rebuilt with locks: pre-registration, spatial blocks, placebo tests.
5. *The models* — simple beats fancy (leaderboard animation).
6. *The test* — fake hurricanes (placebo beeswarm).
7. *What survived* — Ida's immediate damage (map + gradient).
8. *What didn't* — lasting damage depends on the model; Irma fails inland.
9. *Why it matters* — attribution claims need placebos and many models.
10. *Try it* — CTA to Explore and Lab.

### 5.8 Data `/data`
Coverage heatmap (quarters × channels × site/track, clear-pixel %), v1 vs v2 SAR comparison, sensor timeline,
AOI maps, downloads (cubes via Zenodo, predictions, tiles), licences and credits (Copernicus, NASA HLS, ESA WorldCover,
NOAA HURDAT2).

### 5.9 Paper `/paper`
Abstract, PDF embed, figure gallery (each figure links to its script + run), tables, BibTeX/CITATION.cff, reproducibility
steps, compute log chart, changelog of amendments (A1–A4) rendered as a timeline.

---

## 6. Data contracts (what the build consumes; all precomputed, static hosting)

```
/data/manifest.json            sites, tracks, quarters, models (registry), runs, version, git commit
/data/models/registry.json     see §7
/tiles/{site}_{track}.pmtiles  raster layers per quarter: rgb, ndvi, ndmi, ndwi, sar_vv
/tiles/{site}_{track}_{model}_{cutoff}.pmtiles   counterfactual q50, q10, q90, deficit per lead
/tiles/{site}_{track}_disagreement_{cutoff}.pmtiles   per-pixel SD across models
/pixels/{site}_{track}/{z}/{x}/{y}.json   downsampled per-pixel time series (observed + cf median/band per model)
/evidence/verdict.json         Phase 4 primary + lead-0 rows
/evidence/placebo_dist.json    per model × event: placebo values, event values, p95
/evidence/space.json           deficit by coast-distance decile
/evidence/spread.json          attribution per model with intervals
/metrics/leaderboard.json      skill per model/site/band/horizon, coverage, compute
/training/{model}_{site}_{track}_{cutoff}_k{fold}.json   epoch curves (val R², loss)
/lab/{model}.onnx + lab/patches/*.npz   browser-inference models and curated patches
```
Every JSON carries `run_id`, `git_commit`, `data_hash` for the Provenance chip.

---

## 7. Extensible model registry (so new models drop in without redesign)

```json
{
  "id": "ecotransformer_v2",
  "name": "EcoTransformer v2",
  "family": "deep",                       // baseline | deep | ablation | experimental | expanded
  "status": "done",                       // planned | running | done | withdrawn
  "parent": null,                         // ablations point to their parent, e.g. "ecotransformer_v2"
  "variant": null,                        // e.g. {"sar": "off"} or {"loss": "pinball+smooth"}
  "preregistered": true,                  // false => "developed after seeing results" ribbon
  "uses_post_cutoff_info": false,         // true for synth_control and the neighbour-informed model
  "params": 2290000,
  "runs": ["phase3_core_v1"],
  "seeds": [0, 1],
  "lab_exportable": false,
  "card": {"idea": "...", "diagram": "ecotransformer.svg", "limitations": ["..."]},
  "tags": ["attention", "SAR gate", "quantile"]
}
```
UI rules: pages render whatever the registry lists; `planned` → ghost card; `experimental` → amber ribbon and excluded
from the headline verdict unless toggled; `ablation` → shown nested under its parent with Δ vs parent; models with
`uses_post_cutoff_info` get a "sees post-storm neighbours" chip and are compared in their own group.

Reserved entries at launch:
`ecotransformer_v2__sar_off`, `__sar_concat`, `__smooth`, `__static_off`, `__tin4`, `__tin12` (ablation, planned);
`neighbour_informed` (experimental, planned); `presto_head`, `prithvi_head`, `earthformer` (expanded, planned).

---

## 8. Accessibility, performance, deployment
- WCAG AA contrast; keyboard for scrubber, swipe and switchers; screen-reader text for every chart (data table toggle).
- Performance budget: first paint < 2 s on 4G; PMTiles range requests; lazy-load model ONNX (< 5 MB, quantised int8).
- Stack: SvelteKit or Next.js (static export) · MapLibre GL + PMTiles · deck.gl for animated layers · Observable Plot /
  D3 for charts · onnxruntime-web (WebGPU → WASM fallback). Hosting: Cloudflare Pages / GitHub Pages; tiles on
  Cloudflare R2 (free tier) or GitHub Releases.
- Analytics-free by default; no cookies.

---

## 9. Honesty rules for every visual
1. A damage number never appears without its interval and placebo verdict.
2. Placebo-failing models are visible but faded, never hidden.
3. Live-lab outputs are labelled illustrative.
4. Experimental / post-hoc models are ribboned and separated.
5. Thin-data quarters are flagged on the scrubber.
6. Every number has a provenance chip.

---

## 10. Mock-up prompts (one image per prompt; 16:9 desktop unless stated)

1. **Landing hero** — "Dark, cinematic web page hero for a scientific project called EcoRewind. Full-bleed satellite
   image of Louisiana coastal marsh with a glowing white hurricane track curving across it; the right half of the
   image is rendered greener with a teal glow (a 'rewound' storm-free version) separated by a vertical light divider;
   an orange-red heat map glows along the coastline. Large serif headline 'What would the marsh look like if the
   hurricane never came?', two buttons 'Explore the rewind' and 'Run a model live'. Translucent top nav. Palette deep
   green-black, sand gold, teal, coral. Editorial, NASA Earth Observatory style."
2. **Explore map** — "Full-screen interactive map UI of a coastal wetland from satellite, split by a draggable vertical
   divider: left 'Observed' (browner, storm-damaged), right 'Counterfactual' (greener). Bottom: a quarterly timeline
   2015–2023 with a storm icon at 2021Q3 and play button. Left glass panel with model pills (Climatology, Synth-control,
   SimVP, EcoTransformer…) each with a green PASS or red FAIL badge; layer toggles. Right glass panel: 'Attribution'
   card with big number '+0.089 NDVI', interval bar, 'Placebo: PASS', and a small dot plot comparing 9 models.
   Dark theme."
3. **Placebo mode** — same map but tinted violet, banner 'No hurricane happened here — any damage is model error',
   damage heat map nearly empty.
4. **Model disagreement map** — map showing per-pixel disagreement across models as a magma-coloured layer, with a
   side-by-side compare of two models and linked cursors.
5. **Pixel inspector** — side sheet with a line chart: gold observed line, teal counterfactual line with shaded 90 %
   band, vertical storm marker, deficit bars per quarter.
6. **Live Lab** — browser-ML playground: left mini-map with a selected square patch; centre a film strip of 8 input
   satellite thumbnails with toggles, a 'Generate counterfactual' button with a glowing neural pulse animation and a
   chip 'SimVP · 0.85M params · 420 ms · WebGPU'; output film strip of predicted quarters with uncertainty; right a chart.
7. **Models leaderboard** — data table + bubble scatter (skill vs placebo pass rate), family colours, ghost cards for
   'Planned: Neighbour-informed model', 'Planned: SAR-off ablation' with dashed outlines.
8. **Model card** — EcoTransformer architecture diagram (thin technical line art, optical and radar streams merging
   through a gate, attention blocks, quantile heads), training-curve chart, skill table, verdict badges.
9. **Evidence page** — verdict matrix heat-grid (models × events × lead), a violet beeswarm of placebo dots with a
   95th-percentile line and gold real-event dots above it, a forest plot of attribution per model.
10. **Space-placebo panel** — chart of deficit vs distance from coast: one clean declining curve (Ida) and one
    inverted curve (Irma) with map insets highlighting inland blocks.
11. **Pipeline page** — horizontal animated flow: satellites → quarterly composites → 3-D data cube → spatial fold
    grid → model fan-out → calibration → placebo tests → maps & paper; compute meter on the side.
12. **Story chapter 'Version 1'** — scrollytelling layout: left text 'R² 0.901 looked amazing…', right map showing
    red test pixels adjacent to blue training pixels with a 'LEAK' label.
13. **Mobile Explore** — phone screen, full-screen map, horizontal swipe divider, bottom sheet with timeline and model pills.
14. **Light theme Explore** — same as 2 in light paper palette.
