import { useEffect, useRef, useState } from "react";
import { readNpy, writeNpy } from "../lib/npy";
import SceneUpload from "../components/SceneUpload";
import ForecastEngine from "../components/ForecastEngine";
import { Empty, Icon } from "../components/ui";
import { Lines, legendItem } from "../components/charts";
import { BASE, fmt, quarterLabel, useJSON } from "../lib/data";
import { deficitColor, f16, ndviColor } from "../lib/derive";

type Meta = { model: string; site: string; track: string; cutoff: string; size: number; T_in: number; D: number;
  channels: string[]; stats: [number, number][]; n_in: number; layout: { values: number[]; masks: number[]; static: number[]; sar: number[] };
  s_in: number[]; s_out: number[]; in_keys: string[]; out_keys: (string | null)[]; leads: number[]; val_r2: number;
  patches: { id: string; label: string; thumbs: string[] }[]; note: string;
  models?: { id: string; file: string; val_r2: number | null; params: number }[]; tiles?: { id: string; row: number; col: number; cover: number }[];
  grid?: { H: number; W: number }; static_stats?: ([number, number] | null)[] };

const LAB = BASE + "lab/";
const get = (p: string) => fetch(LAB + p).then((r) => { if (!r.ok) throw new Error(p); return r.arrayBuffer(); }).then(f16);

function Canvas({ data, S, color, size = 120 }: { data: Float32Array | null; S: number; color: (v: number) => number[]; size?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext("2d")!;
    if (!data) { ctx.clearRect(0, 0, c.width, c.height); return; }      // e.g. user input has no observed future
    const img = ctx.createImageData(S, S);
    for (let i = 0; i < S * S; i++) {
      const v = data[i];
      if (!isFinite(v)) { img.data[i * 4 + 3] = 0; continue; }
      const [r, g, b] = color(v);
      img.data.set([r, g, b, 255], i * 4);
    }
    ctx.putImageData(img, 0, 0);
  }, [data, S, color]);
  return <canvas ref={ref} width={S} height={S} style={{ width: size, height: size, imageRendering: "pixelated", borderRadius: 8, background: "var(--surface2)" }} />;
}

function NeuralEngine() {
  const { data: meta, loading } = useJSON<Meta>("lab/meta.json");
  const [pi, setPi] = useState(0);
  const [drop, setDrop] = useState<boolean[]>([]);
  const [sarOff, setSarOff] = useState(false);
  const [x, setX] = useState<Float32Array | null>(null);
  const [obs, setObs] = useState<Float32Array | null>(null);
  const [ref, setRef] = useState<Float32Array | null>(null);
  const [out, setOut] = useState<Float32Array | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [ms, setMs] = useState<number | null>(null);
  const [backend, setBackend] = useState("");
  const [lead, setLead] = useState(0);
  const [custom, setCustom] = useState<string | null>(null);
  const [seas, setSeas] = useState<{ s_in: number[]; s_out: number[] } | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [arch, setArch] = useState<string | null>(null);
  const [tile, setTile] = useState<string | null>(null);
  const sessions = useRef<Record<string, any>>({});
  const [rawIn, setRawIn] = useState(true);
  const [upErr, setUpErr] = useState<string | null>(null);
  const sess = useRef<any>(null);

  const models = meta?.models?.length ? meta.models : meta ? [{ id: "simvp", file: "simvp.onnx", val_r2: meta.val_r2, params: 0 }] : [];
  const A = arch && models.some((x) => x.id === arch) ? arch : models[0]?.id ?? "simvp";
  useEffect(() => {
    if (!meta || tile) return;
    const p = meta.patches[pi].id;
    setOut(null); setMs(null); setDrop(Array(meta.T_in).fill(false)); setCustom(null); setUpErr(null); setSeas(null); setNotes([]);
    const refFile = meta.models?.length ? `patches/${p}_ref_${A}.f16` : `patches/${p}_ref.f16`;
    Promise.all([get(`patches/${p}_x.f16`), get(`patches/${p}_obs.f16`), get(refFile).catch(() => null)]).then(([a, b, c]) => { setX(a); setObs(b); setRef(c); });
  }, [meta, pi, A, tile]);
  useEffect(() => {
    if (!meta || !tile) return;
    setOut(null); setMs(null); setDrop(Array(meta.T_in).fill(false)); setCustom(null); setUpErr(null); setSeas(null); setNotes([]);
    Promise.all([get(`tiles/${tile}_x.f16`), get(`tiles/${tile}_obs.f16`)]).then(([a, b]) => { setX(a); setObs(b); setRef(null); });
  }, [meta, tile]);

  if (loading) return <div className="skeleton" style={{ height: 420 }} />;
  if (!meta) return (
    <div>
      <Empty title="The neural model hasn't been exported into this deployment yet">
        The lab runs a real SimVP checkpoint exported to ONNX by <span className="mono">scripts/export_lab_model.py</span> (one ~25-minute T4 run), then built into
        the site by <span className="mono">notebooks/60_web_build_colab.ipynb</span>. Nothing on this page is simulated.
      </Empty>
    </div>);

  const S = meta.size, T = meta.T_in, CIN = meta.n_in, C = meta.channels.length, D = meta.D;
  const ndviIdx = meta.channels.indexOf("NDVI");
  const [mN, sN] = meta.stats[ndviIdx];
  const plane = (arr: Float32Array | null, d: number, ch: number, q: number) => {
    if (!arr) return null;
    const o = new Float32Array(S * S), base = (((d * C + ch) * 3) + q) * S * S;
    for (let i = 0; i < S * S; i++) o[i] = arr[base + i] * sN + mN;
    return o;
  };
  const obsPlane = (d: number) => (obs ? obs.subarray(d * S * S, (d + 1) * S * S) : null);
  const defPlane = (d: number) => {
    const p = plane(out ?? ref, d, ndviIdx, 1), o = obsPlane(d);
    if (!p || !o) return null;
    const r = new Float32Array(S * S);
    for (let i = 0; i < S * S; i++) r[i] = p[i] - o[i];
    return r;
  };
  const mean = (a: Float32Array | null) => { if (!a) return null; let s = 0, n = 0; for (const v of a) if (isFinite(v)) { s += v; n++; } return n ? s / n : null; };

  async function run() {
    if (!x) return;
    setBusy(`loading ${A}…`);
    const ort = await import("onnxruntime-web");
    const file = models.find((x) => x.id === A)?.file ?? "simvp.onnx";
    if (!sessions.current[A]) {
      const providers = ("gpu" in navigator) ? ["webgpu", "wasm"] : ["wasm"];
      try { sessions.current[A] = await ort.InferenceSession.create(LAB + file, { executionProviders: providers }); setBackend(providers[0]); }
      catch { sessions.current[A] = await ort.InferenceSession.create(LAB + file, { executionProviders: ["wasm"] }); setBackend("wasm"); }
    }
    sess.current = sessions.current[A];
    setBusy("running…");
    const inp = new Float32Array(x);
    const per = CIN * S * S;
    for (let t = 0; t < T; t++) {
      for (const ch of [...(drop[t] ? meta!.layout.values : []), ...(sarOff ? meta!.layout.sar : [])]) {
        inp.fill(0, t * per + ch * S * S, t * per + (ch + 1) * S * S);
        const mch = meta!.layout.masks[meta!.layout.values.indexOf(ch)];
        inp.fill(0, t * per + mch * S * S, t * per + (mch + 1) * S * S);
      }
    }
    const t0 = performance.now();
    const all: Record<string, any> = {
      x: new ort.Tensor("float32", inp, [1, T, CIN, S, S]),
      s_in: new ort.Tensor("int64", BigInt64Array.from((seas?.s_in ?? meta!.s_in).map(BigInt)), [1, T]),
      s_out: new ort.Tensor("int64", BigInt64Array.from((seas?.s_out ?? meta!.s_out).map(BigInt)), [1, D]),
    };
    const feeds = Object.fromEntries((sess.current.inputNames as string[]).map((k) => [k, all[k]]));   // exporters drop unused inputs
    const res = await sess.current.run(feeds);
    const y = (res.y ?? Object.values(res)[0]).data as Float32Array;
    const sorted = new Float32Array(y.length);
    for (let d = 0; d < D; d++) for (let c = 0; c < C; c++) for (let i = 0; i < S * S; i++) {
      const b = ((d * C + c) * 3) * S * S + i, v = [y[b], y[b + S * S], y[b + 2 * S * S]].sort((p, q) => p - q);
      sorted[b] = v[0]; sorted[b + S * S] = v[1]; sorted[b + 2 * S * S] = v[2];
    }
    setMs(performance.now() - t0); setOut(sorted); setBusy(null);
  }

  const VALS = meta.layout.values, MASKS = meta.layout.masks, STAT = meta.layout.static;
  const ss: [number, number][] | undefined = (meta as any).static_stats;
  /** model units -> physical units (NaN where the validity mask is 0) */
  const toRaw = (a: Float32Array) => {
    const r = new Float32Array(a), per = CIN * S * S;
    for (let t = 0; t < T; t++) VALS.forEach((ch, ci) => {
      const [m0, s0] = meta.stats[ci];
      for (let i = 0; i < S * S; i++) { const o = t * per + ch * S * S + i, mk = a[t * per + MASKS[ci] * S * S + i]; r[o] = mk > 0.5 ? a[o] * s0 + m0 : NaN; }
    });
    if (ss) for (let t = 0; t < T; t++) STAT.forEach((ch, k) => { if (!ss[k]) return; for (let i = 0; i < S * S; i++) { const o = t * per + ch * S * S + i; r[o] = r[o] * ss[k][1] + ss[k][0]; } });
    return r;
  };
  /** physical units -> model units, building masks from NaN and filling gaps with 0 (the per-season mean in model units is ~0) */
  const fromRaw = (a: Float32Array) => {
    const r = new Float32Array(a), per = CIN * S * S;
    for (let t = 0; t < T; t++) VALS.forEach((ch, ci) => {
      const [m0, s0] = meta.stats[ci];
      for (let i = 0; i < S * S; i++) { const o = t * per + ch * S * S + i, v = a[o], ok = isFinite(v); r[o] = ok ? (v - m0) / s0 : 0; r[t * per + MASKS[ci] * S * S + i] = ok ? 1 : 0; }
    });
    for (let t = 0; t < T; t++) STAT.forEach((ch, k) => { for (let i = 0; i < S * S; i++) { const o = t * per + ch * S * S + i; let v = a[o];
      if (ss?.[k]) v = (v - ss[k][0]) / ss[k][1]; r[o] = isFinite(v) ? Math.max(-10, Math.min(10, v)) : 0; } });
    return r;
  };
  const save = (name: string, blob: Blob) => { const u = URL.createObjectURL(blob), el = document.createElement("a"); el.href = u; el.download = name; el.click(); setTimeout(() => URL.revokeObjectURL(u), 1000); };
  async function upload(f: File) {
    try {
      const { data, shape } = readNpy(await f.arrayBuffer());
      const sh = shape.length === 5 && shape[0] === 1 ? shape.slice(1) : shape;
      if (sh.join() !== [T, CIN, S, S].join()) throw new Error(`shape (${shape.join(", ")}) does not match (${T}, ${CIN}, ${S}, ${S})`);
      if (!rawIn && Array.from(data.subarray(0, 4096)).some((v) => !isFinite(v))) throw new Error("model-unit input must not contain NaN; tick 'physical units' to let the page build the masks");
      setX(rawIn ? fromRaw(data) : data); setObs(null); setRef(null); setOut(null); setMs(null); setCustom(f.name); setUpErr(null); setDrop(Array(T).fill(false)); setSeas(null); setNotes([]);
    } catch (e: any) { setUpErr(e.message ?? String(e)); }
  }

  const modified = drop.some(Boolean) || sarOff;
  const maxDiff = out && ref && !modified ? out.reduce((m, v, i) => Math.max(m, Math.abs(v - ref[i])), 0) * sN : null;
  const chart = {
    x: meta.out_keys.map((k, d) => (k ? k.replace("_POST", "*") : `L${d}`)),
    cf: meta.leads.map((_, d) => mean(plane(out ?? ref, d, ndviIdx, 1))),
    lo: meta.leads.map((_, d) => mean(plane(out ?? ref, d, ndviIdx, 0))),
    hi: meta.leads.map((_, d) => mean(plane(out ?? ref, d, ndviIdx, 2))),
    ob: meta.leads.map((_, d) => mean(obsPlane(d))),
  };
  const patch = meta.patches[pi];
  return (
    <div>
      <div className="lab-sub">
        <p className="muted">Trained networks ({models.map((x) => x.id).join(", ")}) exported to ONNX, running on your GPU (WebGPU) or CPU (WebAssembly). Input: the last {meta.T_in} quarters of a {meta.size} × {meta.size} patch,
          {meta.n_in} channels (optical, radar, validity masks, terrain). Drop quarters to fake clouds, switch the radar off, and the network re-forecasts.</p>
        <span className="chip"><Icon name="cpu" size={13} /> {A} · val NDVI R² {fmt(models.find((x) => x.id === A)?.val_r2 ?? meta.val_r2, 2)} · {meta.site === "mississippi" ? "Louisiana" : "Everglades"} {meta.track === "A" ? "10 m" : "30 m"}</span>
      </div>
      <div className="grid" style={{ gridTemplateColumns: "260px 1fr", alignItems: "start" }}>
        <div className="card">
          {models.length > 1 && <><div className="group-label" style={{ marginTop: 0 }}>Network</div>
            <div className="arch-pick">{models.map((x) => <button key={x.id} className={x.id === A ? "on" : ""} onClick={() => { setArch(x.id); setOut(null); setMs(null); }}>
              <b>{x.id === "ecotransformer" ? "EcoTransformer" : x.id === "convlstm" ? "ConvLSTM" : "SimVP"}</b>
              <span className="mono">{x.params ? `${(x.params / 1e6).toFixed(2)} M params` : ""}{x.val_r2 != null ? ` · val R² ${x.val_r2.toFixed(2)}` : ""}</span></button>)}</div></>}
          {meta.tiles && meta.tiles.length > 0 && meta.grid && <><div className="group-label">Anywhere in the study area</div>
            <div className="tile-map" style={{ aspectRatio: `${meta.grid.W} / ${meta.grid.H}` }}>
              <img src={`${BASE}layers/${meta.site}_${meta.track}/obs_rgb_${meta.in_keys[meta.in_keys.length - 1]}.png`} alt="" style={{ filter: "url(#tc)" }} onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} />
              {meta.tiles.map((t) => <button key={t.id} className={t.id === tile ? "on" : ""} title={`tile ${t.row},${t.col} · ${Math.round(t.cover * 100)} % wetland`}
                style={{ left: `${(t.col / meta.grid!.W) * 100}%`, top: `${(t.row / meta.grid!.H) * 100}%`, width: `${(S / meta.grid!.W) * 100}%`, height: `${(S / meta.grid!.H) * 100}%` }}
                onClick={() => setTile(t.id)} />)}
            </div>
            <div className="dim" style={{ fontSize: 11.5, margin: "6px 0 4px" }}>{meta.tiles.length} tiles · click one to run the network there{tile ? <> · <button className="link" onClick={() => setTile(null)}>back to samples</button></> : ""}</div></>}
          <div className="group-label">Sample region</div>
          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {meta.patches.map((p, i) => <button key={p.id} onClick={() => { setTile(null); setPi(i); }} className={`pill${i === pi && !tile && !custom ? " on" : ""}`} style={{ flexDirection: "column", alignItems: "stretch", padding: 6 }}>
              <img src={LAB + "patches/" + p.thumbs[p.thumbs.length - 1]} alt="" style={{ width: "100%", borderRadius: 6 }} />
              <span style={{ fontSize: 11.5 }}>{p.label}</span></button>)}
          </div>
          <div className="group-label">What-if</div>
          <label style={{ display: "flex", gap: 8, fontSize: 13, alignItems: "center" }}><input type="checkbox" checked={sarOff} onChange={(e) => setSarOff(e.target.checked)} /> Radar (Sentinel-1) off</label>
          <p className="dim" style={{ fontSize: 12 }}>Dropped quarters and radar are zeroed with validity 0, exactly how the model sees clouds in training.</p>
          <div className="group-label">Your own satellite scenes</div>
          <SceneUpload meta={meta} onBuild={(b) => { setX(fromRaw(b.x)); setObs(null); setRef(null); setOut(null); setMs(null); setCustom(b.label); setSeas({ s_in: b.s_in, s_out: b.s_out }); setNotes(b.notes); setUpErr(null); setDrop(Array(T).fill(false)); }} />
          <div className="group-label">Your own tensor (.npy)</div>
          <label className="btn" style={{ width: "100%", justifyContent: "center" }}>Upload .npy<input type="file" accept=".npy" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} /></label>
          <label style={{ display: "flex", gap: 8, fontSize: 12.5, alignItems: "center", marginTop: 8 }}><input type="checkbox" checked={rawIn} onChange={(e) => setRawIn(e.target.checked)} /> physical units (NaN = cloud)</label>
          {custom && <div className="fe-msg ok" style={{ marginTop: 8 }}>Running on <b>{custom}</b></div>}
          {upErr && <div className="fe-msg bad" style={{ marginTop: 8 }}>{upErr}</div>}
          <div className="group-label">Templates (this patch)</div>
          <button className="btn" style={{ width: "100%", justifyContent: "center", marginBottom: 6 }} disabled={!x} onClick={() => x && save(`ecorewind_${patch.id}_physical.npy`, writeNpy(toRaw(x), [T, CIN, S, S]))}>Physical units .npy</button>
          <button className="btn" style={{ width: "100%", justifyContent: "center" }} disabled={!x} onClick={() => x && save(`ecorewind_${patch.id}_model.npy`, writeNpy(x, [T, CIN, S, S]))}>Model units .npy</button>
        </div>
        <div className="grid">
          <div className="card">
            <div className="card-head"><h3>Input · last {T} quarters before landfall</h3><span className="muted" style={{ fontSize: 12.5 }}>{custom ? `your input: ${custom}` : tile ? `tile ${tile.slice(1).replace("_", ", ")} · click a quarter to drop it` : `${patch.label} · click a quarter to drop it`}</span></div>
            <div style={{ display: "flex", gap: 8, overflowX: "auto" }}>
              {(tile || custom ? meta.in_keys.map((k) => "") : patch.thumbs).map((t, i) => tile || custom ? <button key={i} onClick={() => setDrop((d) => d.map((v, j) => (j === i ? !v : v)))} className="q-chip" style={{ opacity: drop[i] ? 0.3 : 1 }}>
                <Canvas data={x ? (() => { const o = new Float32Array(S * S), b = (i * CIN + VALS[0]) * S * S; for (let k = 0; k < S * S; k++) o[k] = x[b + k] * meta.stats[0][1] + meta.stats[0][0]; return o; })() : null} S={S} color={ndviColor} size={92} />
                <div className="mono dim" style={{ fontSize: 10.5 }}>{meta.in_keys[i]}{drop[i] ? " · dropped" : ""}</div></button> : ( <button key={t} onClick={() => setDrop((d) => d.map((v, j) => (j === i ? !v : v)))} style={{ border: 0, background: "none", padding: 0, cursor: "pointer", textAlign: "center" }}>
                <img src={LAB + "patches/" + t} alt={meta.in_keys[i]} style={{ width: 92, height: 92, borderRadius: 8, opacity: drop[i] ? 0.18 : 1, outline: drop[i] ? "2px dashed var(--fail)" : "none" }} />
                <div className="mono dim" style={{ fontSize: 10.5 }}>{meta.in_keys[i]}{drop[i] ? " · dropped" : ""}</div></button>))}
            </div>
            <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 16, flexWrap: "wrap" }}>
              <button className="btn primary" onClick={run} disabled={!!busy || !x}>{busy ?? `Run ${A === "ecotransformer" ? "EcoTransformer" : A === "convlstm" ? "ConvLSTM" : "SimVP"}`} <Icon name="arrow" size={15} /></button>
              {ms != null && <span className="chip">{A} · {backend.toUpperCase()} · {ms.toFixed(0)} ms</span>}
              {notes.length > 0 && <div className="fe-msg" style={{ width: "100%" }}>{notes.map((n) => <div key={n}>{n}</div>)}</div>}
              {maxDiff != null && <span className={`badge ${maxDiff < 0.02 ? "pass" : "fail"}`}>matches PyTorch reference · max |Δ| {maxDiff.toFixed(4)} NDVI</span>}
              {!out && ref && <span className="dim" style={{ fontSize: 12.5 }}>Showing the PyTorch reference output until you run the model.</span>}
            </div>
          </div>
          <div className="card">
            <div className="card-head"><h3>Output · storm-free forecast</h3>
              <div className="seg">{meta.leads.map((l, d) => <button key={d} className={lead === d ? "on" : ""} onClick={() => setLead(d)}>{l === 0 ? "lead 0" : `+${l}`}</button>)}</div></div>
            <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
              {[["Counterfactual (median)", plane(out ?? ref, lead, ndviIdx, 1), ndviColor],
                ["Observed (with storm)", obsPlane(lead), ndviColor],
                ["Deficit = cf − observed", defPlane(lead), deficitColor],
                ["Uncertainty q10", plane(out ?? ref, lead, ndviIdx, 0), ndviColor],
                ["Uncertainty q90", plane(out ?? ref, lead, ndviIdx, 2), ndviColor]].map(([label, d, col]) => (
                <div key={label as string}><Canvas data={d as Float32Array | null} S={S} color={col as (v: number) => number[]} size={150} />
                  <div className="muted" style={{ fontSize: 12 }}>{label as string}</div></div>))}
            </div>
            <div className="mono dim" style={{ fontSize: 11.5, marginTop: 8 }}>{quarterLabel(meta.out_keys[lead] ?? "")} · patch mean deficit {fmt(mean(defPlane(lead)), 3, true)} NDVI</div>
          </div>
          <div className="card">
            <h3>Patch mean over the forecast horizon</h3>
            <Lines x={chart.x} series={[{ name: "obs", color: "var(--observed)", values: chart.ob },
              { name: "cf", color: "var(--cf)", values: chart.cf, band: [chart.lo, chart.hi], dash: true }]} height={220} />
            <div>{legendItem("Observed", "var(--observed)")}{legendItem("Counterfactual median + q10–q90", "var(--cf)")}</div>
            <p className="note" style={{ marginTop: 12 }}>{`Illustrative live model: ${meta.site === "mississippi" ? "Louisiana" : "Everglades"} ${meta.track === "A" ? "10 m" : "30 m"}, ${meta.cutoff} cutoff, fold ${(meta as any).fold ?? 0}, seed 0.`} Published numbers come from the 5-fold, 2-seed evaluation, not from this single model.</p>
          </div>
          <details className="guide card">
            <summary>Input specification · bring your own patch</summary>
            <div className="guide-grid">
              <div><h5>Array</h5><ul>
                <li><b>.npy</b>, float16/32/64, C order, shape <span className="mono">({T}, {CIN}, {S}, {S})</span> = (quarters, channels, rows, cols); a leading batch axis of 1 is accepted.</li>
                <li>{T} <b>consecutive</b> quarterly composites, oldest first, ending the quarter <b>before</b> the event. The network forecasts the next {D} quarters.</li>
                <li>{S} × {S} pixels at the model's resolution ({meta.track === "A" ? "10 m" : "30 m"}, so {S * (meta.track === "A" ? 10 : 30) / 1000} km across).</li>
                <li>Season order is taken from the model's training cutoff: the inputs are treated as {meta.in_keys[0]} … {meta.in_keys[T - 1]} (quarter-of-year matters, the year does not).</li></ul></div>
              <div><h5>Physical units (recommended)</h5><ul>
                <li>Channels 0–2: NDVI, NDMI, NDWI as plain indices in [−1, 1]. Channels 3–4: Sentinel-1 VV and VH backscatter in <b>dB</b>.</li>
                <li>Use <span className="mono">NaN</span> for clouds or missing radar: the page writes the validity masks (channels 5–9) for you.</li>
                <li>Channels 10–17: elevation (m), distance to coast (m), and fractions 0–1 of tree, grass, water, herbaceous wetland, mangrove, other land cover.</li>
                <li>Easiest start: download the physical-units template for a sample patch, edit it in NumPy, upload it back.</li></ul></div>
            </div>
            <table className="t spec-t"><thead><tr><th className="n">Ch</th><th>Name</th><th>Physical unit</th><th>Model unit</th></tr></thead><tbody>
              {meta.channels.map((c, i) => <tr key={c}><td className="n mono">{VALS[i]}</td><td>{c}</td><td>{i < 3 ? "index, −1 … 1" : "dB"}</td><td className="mono">(x − {meta.stats[i][0].toFixed(3)}) / {meta.stats[i][1].toFixed(3)}, gaps 0</td></tr>)}
              {meta.channels.map((c, i) => <tr key={c + "m"}><td className="n mono">{MASKS[i]}</td><td>{c} valid</td><td>1 = observed, 0 = cloud / missing</td><td className="mono">same</td></tr>)}
              {["elevation_m", "coast_dist_m", "lc_tree", "lc_grass", "lc_water", "lc_herb_wetland", "lc_mangrove", "lc_other"].map((c, k) => <tr key={c}><td className="n mono">{STAT[k]}</td><td>{c}</td>
                <td>{c.startsWith("lc_") ? "fraction 0 … 1" : c.endsWith("_m") ? "metres" : ""}</td>
                <td className="mono">{c.startsWith("lc_") ? "same, clipped ±10" : ss?.[k] ? `(x − ${ss[k][0].toFixed(1)}) / ${ss[k][1].toFixed(1)}` : "robust z-score (constants in newer exports)"}</td></tr>)}
            </tbody></table>
          </details>
        </div>
      </div>
    </div>
  );
}

export default function Lab() {
  return (
    <div className="page wrap">
      <div className="page-head"><div><div className="eyebrow">Lab</div><h1>Run the models yourself</h1>
        <p>Two engines run entirely in your browser. Nothing on this page is pre-rendered: change the input and the forecast is recomputed.</p></div></div>
      <section className="lab-sec">
        <div className="lab-h"><span className="sec-n mono">A</span><div><h2>Forecast engine · any pixel, any series</h2>
          <p className="muted">Exact ports of the four statistical baselines. Pick a pixel, drag its history, or paste your own series: each model refits in under a millisecond.</p></div></div>
        <ForecastEngine />
      </section>
      <section className="lab-sec">
        <div className="lab-h"><span className="sec-n mono">B</span><div><h2>Neural engine · the trained network</h2></div></div>
        <NeuralEngine />
      </section>
    </div>
  );
}
