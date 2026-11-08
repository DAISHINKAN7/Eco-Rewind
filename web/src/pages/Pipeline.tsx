import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { fmt, MapSite, Results, useMaps, useResults } from "../lib/data";
import { cfPath, imageKeys, layerURL } from "../lib/explore";
import { CountUp, Reveal } from "../lib/fx";
import { FAM_LABEL, FAM_ORDER, meta } from "../lib/models";

const GH = "https://github.com/DAISHINKAN7/EcoRewind2/blob/main/";
const ST = "mississippi_A";
type Stage = { t: string; n: string; d: string; code: string; vis?: (r: Results, m: MapSite | undefined) => ReactNode };

const STAGES: Stage[] = [
  { t: "Earth Engine export", n: "320 files · 96.6 EECU-h", code: "gee/",
    d: "Quarterly, cloud-masked composites 2013–2023: Sentinel-2 at 10 m (Cloud Score+ ≥ 0.6), Landsat + Sentinel-2 HLS at 30 m (Fmask), Sentinel-1 radar VV/VH (both orbits, linear-power mean). UTM grids snapped so 30 m pixels nest 3 × 3 in the 10 m grid. The hurricane quarter is split into pre- and post-landfall composites.",
    vis: (_, m) => m && <div className="pl-film">{imageKeys(m).filter((_, i) => i % 3 === 0).slice(0, 10).map((k) => <figure key={k}><img src={layerURL(ST, `obs_rgb_${k}.png`)} alt="" loading="lazy" style={{ filter: "url(#tc)" }} /><figcaption className="mono">{k}</figcaption></figure>)}</div> },
  { t: "Audit gate", n: "0 open issues", code: "scripts/audit_exports.py",
    d: "Every file checked for grid identity, square pixels, all periods present, valid radar and no NDVI = −1 artefacts. The audit caught v1's wrong Mississippi area, its broken SAR export and a synthetic Everglades quarter." },
  { t: "Data cube", n: "(T, C, H, W) Zarr", code: "src/ecorewind/data/cube.py",
    d: "Zarr cubes with 12 channels (6 bands, NDVI, NDWI, NDMI, VV, VH, VH/VV) and a validity mask per channel. An index is valid only where its own inputs are. Louisiana 10 m: 33 quarters × 2238 × 2235 pixels.",
    vis: (_, m) => m && <div className="pl-cube">{imageKeys(m).filter((_, i) => i % 4 === 1).slice(0, 7).map((k, i) => <img key={k} src={layerURL(ST, `obs_rgb_${k}.png`)} alt="" loading="lazy" style={{ filter: "url(#tc)", ["--i" as string]: i }} />)}<span className="mono">T × C × H × W</span></div> },
  { t: "Spatial folds", n: "3.84 km blocks · 640 m buffers", code: "scripts/make_folds.py",
    d: "Blocks nest exactly at 10 m and 30 m. Five folds stratified by wetland share and a damage proxy. Test, calibration and training blocks are separated by buffers, so no test pixel sits next to a training pixel. v1's R² 0.901 came from exactly that leak.",
    vis: () => <div className="pl-folds">{Array.from({ length: 80 }, (_, i) => { const f = (Math.floor(i / 10) * 3 + (i % 10) * 7) % 5; return <span key={i} className={`f${f}`} />; })}</div> },
  { t: "Pre-registration", n: "amendments A1–A5", code: "configs/preregistration.yaml",
    d: "Events, placebo windows (checked against NOAA HURDAT2 within 200 km), horizons and pass criteria were fixed in YAML before any model ran. Every later change is an amendment logged with its reason before the result it affects." },
  { t: "Models", n: "19 trained", code: "src/ecorewind/models/",
    d: "Six statistical baselines, three deep networks (ConvLSTM, SimVP, EcoTransformer v2), seven ablations, two cross-site transfers and one post-hoc experiment, all through one harness on identical pixels. Deep models trained on Colab T4s, 5 folds × 2 seeds, resumable per fold.",
    vis: (r) => { const ids = [...new Set(r.registry.filter((x) => x.status === "done").map((x) => x.id))];
      return <div className="pl-fams">{FAM_ORDER.map((f) => { const n = ids.filter((id) => meta(id).fam === f).length; return n ? <div key={f}><span>{FAM_LABEL[f]}</span><i>{Array.from({ length: n }, (_, k) => <b key={k} />)}</i><span className="mono">{n}</span></div> : null; })}</div>; } },
  { t: "Conformal intervals", n: "90 % nominal", code: "src/ecorewind/eval/conformal.py",
    d: "Split-conformal / CQR intervals calibrated on placebo windows of the calibration fold only. Achieved coverage stays at 0.88–0.90 for every model.",
    vis: (r) => <div className="pl-cov">{r.verdict.map((v, i) => <span key={i} style={{ left: `${((v.coverage - 0.8) / 0.15) * 100}%` }} title={`${meta(v.model).short} ${v.coverage.toFixed(3)}`} />)}<i style={{ left: `${(0.1 / 0.15) * 100}%` }} /><em className="mono">0.80</em><em className="mono r">0.95</em></div> },
  { t: "Placebo tests", n: "time · space · track", code: "scripts/placebo_verdict.py",
    d: "Fake landfalls in calm years (time), inland least-exposed blocks (space), and rank agreement with independent NOAA track distance and wind. Rules from amendment A4.",
    vis: (r) => <div className="pl-tests">{r.verdict.map((v, i) => <span key={i} className={v.pass ? "p" : "f"} />)}</div> },
  { t: "Outputs", n: "maps · samples · site", code: "scripts/export_demo.py",
    d: "Counterfactual, deficit, uncertainty and disagreement layers for every model, cutoff and lead; 3000-pixel time series; ONNX networks for the browser; this website, built by scripts/build_web_data.py.",
    vis: (_, m) => m && <div className="pl-out">{[cfPath("simvp", "ida", "cf_ndvi", 0), cfPath("simvp", "ida", "deficit", 0), cfPath("simvp", "ida", "width", 0), "disagreement/ida/sd_L0.png"].filter((p) => m.layers[p]).map((p) => <img key={p} src={layerURL(ST, p)} alt="" loading="lazy" />)}</div> },
];

export default function Pipeline() {
  const { data: r } = useResults();
  const { data: maps } = useMaps();
  const m = maps?.[ST];
  const comp = (r?.compute ?? []).filter((c) => c.platform === "colab" && c.units && !isNaN(+String(c.units).replace("~", "")));
  const total = comp.reduce((a, c) => a + +String(c.units).replace("~", ""), 0);
  const maxU = Math.max(1, ...comp.map((c) => +String(c.units).replace("~", "")));
  return (
    <div className="page wrap pl">
      <header className="ev-head">
        <div className="eyebrow">Pipeline</div>
        <h1>From raw orbits to a falsification test.</h1>
        <p className="md-lead">Nine stages, each a script in the repository, each reproducible on free or cheap cloud compute. Nothing in between is done by hand.</p>
        <div className="md-kpis">
          <div><b><CountUp to={320} /></b><span>exported rasters</span></div>
          <div><b>2</b><span>resolutions, nested grids</span></div>
          <div><b><CountUp to={19} /></b><span>trained models</span></div>
          <div><b><CountUp to={55} /></b><span>automated tests</span></div>
          <div><b>{total ? <CountUp to={total} decimals={0} /> : "—"}</b><span>Colab compute units, total</span></div>
        </div>
      </header>

      <ol className="pl-log">{STAGES.map((s, i) => <Reveal as="li" key={s.t} className="pl-step">
        <div className="pl-n mono">{String(i + 1).padStart(2, "0")}</div>
        <div className="pl-txt"><h2>{s.t}</h2><div className="pl-stat mono">{s.n}</div><p>{s.d}</p>
          <a className="chip" href={GH + s.code} target="_blank" rel="noreferrer">{s.code} ↗</a></div>
        <div className="pl-vis">{r && s.vis?.(r, m)}</div>
      </Reveal>)}</ol>

      {comp.length > 0 && <section className="md-sec">
        <div className="md-sec-h"><h2>Compute budget</h2><p className="muted">Colab compute units per task. {r?.compute.find((c) => c.platform === "earth-engine")?.note ?? ""} on Earth Engine.
          Full log in <Link to="/reports">Reports</Link>.</p></div>
        <div className="pl-comp">{comp.map((c, i) => { const u = +String(c.units).replace("~", ""); return <div key={i} className="cmp-row">
          <span className="cmp-l mono" style={{ fontSize: 11.5 }}>{c.task}</span>
          <span className="cmp-track"><span className="cmp-bar a" style={{ left: 0, width: `${(u / maxU) * 100}%`, background: c.hardware && /t4|gpu|a100/i.test(c.hardware) ? "var(--mark)" : "var(--mark3)", top: 7 }} /></span>
          <span className="mono cmp-v">{fmt(u, 2)} <span className="dim">{c.hardware}</span></span></div>; })}</div>
        <div className="cmp-key"><span><i style={{ background: "var(--mark)" }} />GPU (T4)</span><span><i style={{ background: "var(--mark3)" }} />CPU</span></div>
      </section>}
    </div>
  );
}
