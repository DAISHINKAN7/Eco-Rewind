import { useEffect, useMemo, useRef, useState } from "react";
import { ENGINES, keyOf, Pt, qt } from "../lib/forecast";
import { blockMean, indices, nextQuarters, PRESETS, Raster, readRaster } from "../lib/imagery";
import { colorFor } from "../lib/raster";

export type Series = { hist: Pt[]; tgt: string[]; truth: (number | null)[]; label: string };
type Stack = { w: number; h: number; ndvi: Float32Array[]; names: string[] };
const MAXPX = 160;

function ArrCanvas({ a, w, h, kind, pin, onPick, label }: { a: Float32Array | null; w: number; h: number; kind: "ndvi" | "deficit"; pin?: [number, number] | null;
  onPick?: (x: number, y: number) => void; label: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current; if (!c || !a) return;
    const x = c.getContext("2d")!, im = x.createImageData(w, h);
    for (let i = 0; i < w * h; i++) { const v = a[i]; if (!isFinite(v)) continue; const col = colorFor(kind, v); im.data.set([col[0], col[1], col[2], 255], i * 4); }
    x.putImageData(im, 0, 0);
  }, [a, w, h, kind]);
  return <figure className="is-map">
    <div className="is-canvas" onClick={(e) => { if (!onPick) return; const r = e.currentTarget.getBoundingClientRect(); onPick(Math.floor(((e.clientX - r.left) / r.width) * w), Math.floor(((e.clientY - r.top) / r.height) * h)); }}
      style={{ aspectRatio: `${w} / ${h}`, cursor: onPick ? "crosshair" : "default" }}>
      <canvas ref={ref} width={w} height={h} />
      {pin && <span className="stage-pin" style={{ left: `${((pin[0] + 0.5) / w) * 100}%`, top: `${((pin[1] + 0.5) / h) * 100}%` }} />}
      {!a && <span className="is-na">no data</span>}
    </div><figcaption>{label}</figcaption></figure>;
}

export default function ImageSeries({ onSeries, focus }: { onSeries: (s: Series | null) => void; focus: string }) {
  const [rasters, setRasters] = useState<Raster[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preset, setPreset] = useState("ndvi");
  const [range, setRange] = useState<[number, number]>([-1, 1]);
  const [startQ, setStartQ] = useState("2016Q1");
  const [evIdx, setEvIdx] = useState(0);
  const [horizon, setHorizon] = useState(4);
  const [pin, setPin] = useState<[number, number] | null>(null);
  const [lead, setLead] = useState(0);

  async function load(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true); setErr(null);
    try {
      const rs = await Promise.all([...files].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true })).map(readRaster));
      setRasters(rs); setPin(null);
      if (rs[0].bands.length >= 12) setPreset("s2_12"); else if (rs[0].bands.length === 6) setPreset("hls"); else if (rs[0].bands.length === 4) setPreset("four"); else setPreset("ndvi");
      setEvIdx(rs.length === 12 && rs[0].name === "ndvi_01.tif" ? 8 : Math.max(1, Math.min(rs.length - 1, Math.round(rs.length * 0.7))));
    } catch (e: any) { setErr(e.message ?? String(e)); }
    setBusy(false);
  }
  const keys = useMemo(() => nextQuarters(startQ, rasters.length), [startQ, rasters.length]);
  const stack: Stack | null = useMemo(() => {
    if (!rasters.length) return null;
    try {
      const ws = new Set(rasters.map((r) => `${r.width}x${r.height}`));
      if (ws.size > 1) throw new Error(`all images must have the same size (got ${[...ws].join(", ")})`);
      const f = Math.max(1, Math.ceil(Math.max(rasters[0].width, rasters[0].height) / MAXPX));
      const ndvi = rasters.map((r) => blockMean(indices(r, PRESETS[preset].map, range).NDVI, r.width, r.height, f));
      setErr(null);
      return { w: ndvi[0].w, h: ndvi[0].h, ndvi: ndvi.map((x) => x.data), names: rasters.map((r) => r.name) };
    } catch (e: any) { setErr(e.message ?? String(e)); return null; }
  }, [rasters, preset, range]);
  useEffect(() => { if (stack && !pin) setPin([stack.w >> 1, stack.h >> 1]); }, [stack]);

  const evKey = keys[evIdx], tgt = evKey ? Array.from({ length: horizon }, (_, j) => keyOf(qt(evKey) + j)) : [];
  const seriesAt = (i: number) => {
    const hist: Pt[] = keys.slice(0, evIdx).map((k, t) => ({ key: k, v: isFinite(stack!.ndvi[t][i]) ? +stack!.ndvi[t][i].toFixed(4) : null }));
    const truth = tgt.map((k) => { const t = keys.indexOf(k); return t >= 0 && isFinite(stack!.ndvi[t][i]) ? +stack!.ndvi[t][i].toFixed(4) : null; });
    return { hist, truth };
  };
  useEffect(() => {
    if (!stack || !pin || !evKey) { onSeries(null); return; }
    const { hist, truth } = seriesAt(pin[1] * stack.w + pin[0]);
    onSeries({ hist, tgt, truth, label: `your image · pixel (${pin[0]}, ${pin[1]})` });
  }, [stack, pin, evIdx, horizon, startQ]);

  // whole-image forecast for the focus model at one lead
  const maps = useMemo(() => {
    if (!stack || !evKey || evIdx < 1) return null;
    const eng = ENGINES.find((e) => e.id === focus) ?? ENGINES[1], n = stack.w * stack.h, L = Math.min(lead, tgt.length - 1);
    const fc = new Float32Array(n).fill(NaN), def = new Float32Array(n).fill(NaN), t0 = performance.now();
    const tObs = keys.indexOf(tgt[L]);
    for (let i = 0; i < n; i++) {
      const { hist } = seriesAt(i);
      if (!hist.some((p) => p.v != null)) continue;
      const v = eng.fit(hist, [tgt[L]])[0];
      if (v == null) continue;
      fc[i] = v;
      if (tObs >= 0 && isFinite(stack.ndvi[tObs][i])) def[i] = v - stack.ndvi[tObs][i];
    }
    let s = 0, k = 0; for (const v of def) if (isFinite(v)) { s += v; k++; }
    return { fc, def: k ? def : null, ms: performance.now() - t0, meanDef: k ? s / k : null, name: eng.name };
  }, [stack, evIdx, horizon, startQ, lead, focus]);

  const quarters = Array.from({ length: 64 }, (_, i) => keyOf(2010 * 4 + i));
  const p = PRESETS[preset];
  return <div className="is">
    <label className="btn" style={{ justifyContent: "center" }}>{busy ? "reading…" : rasters.length ? `${rasters.length} images loaded · replace` : "Upload images (one per quarter)"}
      <input type="file" multiple accept=".tif,.tiff,.png,.jpg,.jpeg" hidden onChange={(e) => { load(e.target.files); e.target.value = ""; }} /></label>
    <a className="dim is-ex" href="#" onClick={(e) => { e.preventDefault(); setStartQ("2019Q1"); loadExample(load); }}>or load the example series (12 quarterly NDVI GeoTIFFs)</a>
    {rasters.length > 0 && <>
      <label className="is-f">Band layout<select value={preset} onChange={(e) => setPreset(e.target.value)}>{Object.entries(PRESETS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
      {!p.map && rasters[0].kind === "image" && <div className="fe-ctrl"><label>Black = NDVI<input type="number" step="0.1" value={range[0]} onChange={(e) => setRange([+e.target.value, range[1]])} /></label>
        <label>White = NDVI<input type="number" step="0.1" value={range[1]} onChange={(e) => setRange([range[0], +e.target.value])} /></label></div>}
      <div className="fe-ctrl">
        <label>First image is<select value={startQ} onChange={(e) => setStartQ(e.target.value)}>{quarters.map((k) => <option key={k}>{k}</option>)}</select></label>
        <label>Event at image<select value={evIdx} onChange={(e) => setEvIdx(+e.target.value)}>{keys.map((k, i) => i > 0 && <option key={k} value={i}>{i + 1} · {k}</option>)}</select></label>
      </div>
      <label className="is-f">Horizon<select value={horizon} onChange={(e) => setHorizon(+e.target.value)}>{[1, 2, 3, 4, 6, 8].map((n) => <option key={n} value={n}>{n} quarter{n > 1 ? "s" : ""}</option>)}</select></label>
      <div className="is-files mono">{rasters.map((r, i) => <span key={r.name} className={i >= evIdx ? "post" : ""}>{keys[i]} · {r.name} · {r.width}×{r.height}{r.bands.length > 1 ? ` · ${r.bands.length} bands` : ""}</span>)}</div>
    </>}
    {err && <div className="fe-msg bad">{err}</div>}
    {stack && maps && <div className="is-maps">
      <div className="is-maps-h"><span className="sh-k">Whole image · {maps.name}</span>
        <select value={lead} onChange={(e) => setLead(+e.target.value)}>{tgt.map((k, j) => <option key={k} value={j}>{j === 0 ? `event (${k})` : `+${j}q (${k})`}</option>)}</select></div>
      <div className="is-grid">
        <ArrCanvas a={stack.ndvi[evIdx - 1]} w={stack.w} h={stack.h} kind="ndvi" pin={pin} onPick={(x, y) => setPin([x, y])} label={`Last image before the event (${keys[evIdx - 1]})`} />
        <ArrCanvas a={maps.fc} w={stack.w} h={stack.h} kind="ndvi" pin={pin} onPick={(x, y) => setPin([x, y])} label={`Storm-free forecast · ${tgt[Math.min(lead, tgt.length - 1)]}`} />
        <ArrCanvas a={maps.def} w={stack.w} h={stack.h} kind="deficit" pin={pin} onPick={(x, y) => setPin([x, y])} label={maps.def ? `Deficit · mean ${maps.meanDef! > 0 ? "+" : ""}${maps.meanDef!.toFixed(3)}` : "Deficit: needs an image at this quarter"} />
      </div>
      <div className="dim mono" style={{ fontSize: 10.5 }}>{stack.w}×{stack.h} px · {(stack.w * stack.h).toLocaleString()} pixel forecasts in {maps.ms.toFixed(0)} ms · click a map to inspect a pixel below</div>
    </div>}
  </div>;
}

/** The bundled example: 12 quarterly NDVI GeoTIFFs with a storm in quarter 9 (examples/ndvi_series/). */
async function loadExample(load: (f: FileList) => void) {
  const names = Array.from({ length: 12 }, (_, i) => `ndvi_${String(i + 1).padStart(2, "0")}.tif`);
  const files = await Promise.all(names.map(async (n) => new File([await (await fetch(`${import.meta.env.BASE_URL}examples/ndvi_series/${n}`)).blob()], n)));
  const dt = new DataTransfer(); files.forEach((f) => dt.items.add(f));
  load(dt.files);
}
