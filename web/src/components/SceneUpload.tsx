import { useEffect, useMemo, useRef, useState } from "react";
import { blockMean, crop, indices, nextQuarters, PRESETS, Raster, readRaster } from "../lib/imagery";
import { colorFor } from "../lib/raster";

type LabMeta = { size: number; T_in: number; D: number; n_in: number; track: string; in_keys: string[];
  layout: { values: number[]; masks: number[]; static: number[]; sar: number[] } };
export type Built = { x: Float32Array; s_in: number[]; s_out: number[]; label: string; notes: string[] };
const LC = [["lc_herb_wetland", "Herbaceous wetland / marsh"], ["lc_mangrove", "Mangrove"], ["lc_water", "Open water"], ["lc_grass", "Grassland"], ["lc_tree", "Tree cover"], ["lc_other", "Other"]];
const STATIC = ["elevation_m", "coast_dist_m", "lc_tree", "lc_grass", "lc_water", "lc_herb_wetland", "lc_mangrove", "lc_other"];
const season = (k: string) => +k.slice(-1) - 1;

/** Turn T quarterly multi-band scenes into the network's input (physical units, NaN = missing; the Lab normalises it). */
export default function SceneUpload({ meta, onBuild }: { meta: LabMeta; onBuild: (b: Built) => void }) {
  const T = meta.T_in, S = meta.size, target = meta.track === "A" ? 10 : 30;
  const [rs, setRs] = useState<Raster[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [preset, setPreset] = useState("s2_12");
  const [factor, setFactor] = useState(3);
  const [startQ, setStartQ] = useState(meta.in_keys[0] ?? "2019Q3");
  const [lc, setLc] = useState("lc_herb_wetland");
  const [box, setBox] = useState<[number, number] | null>(null);
  const cv = useRef<HTMLCanvasElement>(null);

  async function load(files: FileList | null) {
    if (!files?.length) return;
    setErr(null);
    try {
      let list = [...files].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
      if (list.length < T) throw new Error(`the network needs ${T} consecutive quarterly scenes; got ${list.length}`);
      list = list.slice(-T);
      const r = await Promise.all(list.map(readRaster));
      const sizes = new Set(r.map((x) => `${x.width}x${x.height}`));
      if (sizes.size > 1) throw new Error(`all scenes must cover the same grid (got ${[...sizes].join(", ")})`);
      setRs(r); setBox(null);
      const nb = r[0].bands.length;
      setPreset(nb === 13 ? "s2_13" : nb >= 12 ? "s2_12" : nb === 6 ? "hls" : nb === 4 ? "four" : "s2_12");
      const res = r[0].resM; if (res) setFactor(Math.max(1, Math.round(target / res)));
    } catch (e: any) { setErr(e.message ?? String(e)); setRs([]); }
  }
  const prep = useMemo(() => {
    if (!rs.length) return null;
    try {
      const map = PRESETS[preset].map;
      if (!map) throw new Error("the networks need multi-band scenes (green, red, NIR, SWIR1), not NDVI only");
      const per = rs.map((r) => { const ix = indices(r, map); return (["NDVI", "NDMI", "NDWI"] as const).map((k) => blockMean(ix[k]!, r.width, r.height, factor)); });
      const { w, h } = per[0][0];
      if (w < S || h < S) throw new Error(`after resampling to ${target} m the scenes are ${w}×${h} px; the network needs at least ${S}×${S} (≈ ${(S * target / 1000).toFixed(1)} km)`);
      return { per, w, h };
    } catch (e: any) { setErr(e.message ?? String(e)); return null; }
  }, [rs, preset, factor]);
  useEffect(() => { if (prep) { setErr(null); if (!box) setBox([Math.floor((prep.w - S) / 2), Math.floor((prep.h - S) / 2)]); } }, [prep]);
  useEffect(() => {                                            // preview: NDVI of the last scene, with the input window
    const c = cv.current; if (!c || !prep) return;
    c.width = prep.w; c.height = prep.h;
    const x = c.getContext("2d")!, im = x.createImageData(prep.w, prep.h), a = prep.per[T - 1][0].data;
    for (let i = 0; i < a.length; i++) { if (!isFinite(a[i])) continue; const col = colorFor("ndvi", a[i]); im.data.set([col[0], col[1], col[2], 255], i * 4); }
    x.putImageData(im, 0, 0);
  }, [prep]);

  const keys = nextQuarters(startQ, T), outKeys = nextQuarters(nextQuarters(startQ, T + 1)[T], meta.D);
  function build() {
    if (!prep || !box) return;
    const CIN = meta.n_in, per = CIN * S * S, x = new Float32Array(T * per).fill(NaN);
    const [x0, y0] = box; let miss = 0;
    for (let t = 0; t < T; t++) {
      for (let k = 0; k < 3; k++) {
        const pl = crop(prep.per[t][k].data, prep.w, x0, y0, S);
        x.set(pl, t * per + meta.layout.values[k] * S * S);
        if (k === 0) miss += pl.filter((v) => !isFinite(v)).length;
      }
      // radar (channels 3, 4) stays NaN = missing; static layers: unknown terrain (→ training median), chosen land cover
      meta.layout.static.forEach((ch, j) => {
        const name = STATIC[j], v = name.startsWith("lc_") ? (name === lc ? 1 : 0) : NaN;
        x.fill(v, t * per + ch * S * S, t * per + (ch + 1) * S * S);
      });
    }
    const notes = ["Radar (Sentinel-1) not supplied: treated as missing, as for clouds in training.",
      "Terrain unknown: elevation and coast distance set to the training-area median.", `Land cover set to: ${LC.find((l) => l[0] === lc)?.[1]}.`];
    if (miss) notes.push(`${((100 * miss) / (T * S * S)).toFixed(0)} % of optical pixels are missing (clouds / nodata).`);
    onBuild({ x, s_in: keys.map(season), s_out: outKeys.map(season), label: `${rs.length} scenes · ${keys[0]}–${keys[T - 1]} · window (${x0}, ${y0})`, notes });
  }
  const quarters = Array.from({ length: 64 }, (_, i) => nextQuarters("2010Q1", 64)[i]);
  return <div className="su">
    <label className="btn" style={{ width: "100%", justifyContent: "center" }}>{rs.length ? `${rs.length} scenes · replace` : `Upload ${T} quarterly scenes (.tif)`}
      <input type="file" multiple accept=".tif,.tiff" hidden onChange={(e) => { load(e.target.files); e.target.value = ""; }} /></label>
    <a className="dim is-ex" href="#" onClick={async (e) => { e.preventDefault(); setStartQ("2019Q3");
      const names = Array.from({ length: 8 }, (_, i) => `s2_${String(i + 1).padStart(2, "0")}.tif`);
      const files = await Promise.all(names.map(async (n) => new File([await (await fetch(`${import.meta.env.BASE_URL}examples/s2_scenes/${n}`)).blob()], n)));
      const dt = new DataTransfer(); files.forEach((f) => dt.items.add(f)); load(dt.files); }}>or load the example (8 Sentinel-2 L2A scenes)</a>
    {rs.length > 0 && <>
      <label className="is-f">Band layout<select value={preset} onChange={(e) => setPreset(e.target.value)}>{Object.entries(PRESETS).filter(([, v]) => v.map).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></label>
      <div className="fe-ctrl">
        <label>Pixel size<select value={factor} onChange={(e) => setFactor(+e.target.value)}>{[1, 2, 3, 6].map((f) => <option key={f} value={f}>{Math.round(target / f)} m → {target} m (×{f})</option>)}</select></label>
        <label>First scene<select value={startQ} onChange={(e) => setStartQ(e.target.value)}>{quarters.map((k) => <option key={k}>{k}</option>)}</select></label>
      </div>
      <label className="is-f">Dominant land cover<select value={lc} onChange={(e) => setLc(e.target.value)}>{LC.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
      {prep && box && <div className="su-prev" style={{ aspectRatio: `${prep.w} / ${prep.h}` }}
        onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(), cx = ((e.clientX - r.left) / r.width) * prep.w, cy = ((e.clientY - r.top) / r.height) * prep.h;
          setBox([Math.max(0, Math.min(prep.w - S, Math.round(cx - S / 2))), Math.max(0, Math.min(prep.h - S, Math.round(cy - S / 2)))]); }}>
        <canvas ref={cv} />
        <span className="su-box" style={{ left: `${(box[0] / prep.w) * 100}%`, top: `${(box[1] / prep.h) * 100}%`, width: `${(S / prep.w) * 100}%`, height: `${(S / prep.h) * 100}%` }} />
      </div>}
      {prep && <div className="dim" style={{ fontSize: 11.5 }}>NDVI of the last scene at {target} m ({prep.w}×{prep.h} px). Click to place the {S}×{S} input window. Forecasts {outKeys[0]} → {outKeys[outKeys.length - 1]}.</div>}
      <button className="btn primary" style={{ justifyContent: "center" }} disabled={!prep} onClick={build}>Use these scenes</button>
    </>}
    {err && <div className="fe-msg bad">{err}</div>}
  </div>;
}
