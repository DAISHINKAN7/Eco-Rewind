import { useEffect, useMemo, useRef, useState } from "react";
import Stage, { UV, View, VIEW0 } from "./Stage";
import { Seg } from "./ui";
import { fmt, quarterLabel, useMaps } from "../lib/data";
import { cutoffLabel, isPlacebo } from "../lib/derive";
import { imageKeys, layerURL, nearestSample, placeboCuts, usePixels } from "../lib/explore";
import { ENGINES, keyOf, parseReport, Pt, qt, residualBand, TEMPLATE } from "../lib/forecast";
import { meta } from "../lib/models";
import ImageSeries, { Series } from "./ImageSeries";

const SITES: [string, string][] = [["mississippi_A", "Louisiana · 10 m"], ["mississippi_B", "Louisiana · 30 m"], ["everglades_B", "Everglades · 30 m"], ["everglades_A", "Everglades · 10 m"]];
const Y0 = -0.2, Y1 = 1.0;

function download(name: string, text: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/csv" })); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

export default function ForecastEngine() {
  const { data: maps } = useMaps();
  const [mode, setMode] = useState<"pixel" | "own" | "images">("pixel");
  const [imgSeries, setImgSeries] = useState<Series | null>(null);
  const [st, setSt] = useState("mississippi_A");
  const m = maps?.[st];
  const event = st.startsWith("miss") ? "ida" : "irma";
  const cuts = m ? [event, ...placeboCuts(m)] : [event];
  const [cut, setCut] = useState(event);
  useEffect(() => setCut(event), [st]);
  const { data: px, loading } = usePixels(mode === "pixel" && m ? st : null);
  const [pin, setPin] = useState<UV | null>(null);
  const [view, setView] = useState<View>(VIEW0);
  const [hist, setHist] = useState<Pt[] | null>(null);
  const [base, setBase] = useState<Pt[] | null>(null);
  const [focus, setFocus] = useState("harmonic_notrend");
  // own-data mode
  const [text, setText] = useState(TEMPLATE);
  const rep = useMemo(() => parseReport(text), [text]);
  const lastKey = rep.pts.length ? rep.pts[rep.pts.length - 1].key : "2021Q1";
  const [evq, setEvq] = useState("2020Q3");
  const [horizon, setHorizon] = useState(4);

  const near = mode === "pixel" && px && m && pin ? nearestSample(px, m.shape, pin) : null;
  const tgt = useMemo(() => mode === "images" ? imgSeries?.tgt ?? [] : mode === "own" ? Array.from({ length: horizon }, (_, j) => keyOf(qt(evq) + j))
    : px?.cf.climatology?.[cut]?.keys ?? [], [mode, horizon, evq, px, cut, imgSeries]);
  const c0 = tgt.length ? qt(tgt[0]) : Infinity;

  useEffect(() => { if (mode === "pixel" && px && m && !pin) setPin([(px.c[1234 % px.c.length] + 0.5) / m.shape[1], (px.r[1234 % px.r.length] + 0.5) / m.shape[0]]); }, [px, m, mode]);
  useEffect(() => {
    if (mode === "images") { setHist(imgSeries?.hist ?? null); setBase(imgSeries?.hist ?? null); return; }
    if (mode === "own") {                                    // continuous quarters, gaps = missing (as the models see them)
      const pre = rep.pts.filter((p) => qt(p.key) < c0);
      const h: Pt[] = pre.length ? Array.from({ length: c0 - qt(pre[0].key) }, (_, j) => { const k = keyOf(qt(pre[0].key) + j); return { key: k, v: pre.find((p) => p.key === k)?.v ?? null }; }) : [];
      setHist(h); setBase(h); return;
    }
    if (!px || !near) return;
    const h = px.keys.filter((k) => !k.includes("POST") && qt(k) < c0).sort((a, b) => qt(a) - qt(b)).map((k) => ({ key: k, v: px.observed[near.i][px.keys.indexOf(k)] }));
    setHist(h); setBase(h);
  }, [px, near?.i, cut, mode, rep, c0, imgSeries]);
  const truth = useMemo(() => mode === "images" ? imgSeries?.truth ?? [] : mode === "own" ? tgt.map((k) => rep.pts.find((p) => p.key === k)?.v ?? null)
    : px && near ? tgt.map((k) => px.observed[near.i][px.keys.indexOf(k)] ?? null) : [], [mode, rep, px, near?.i, tgt.join(), imgSeries]);

  const valid = (hist ?? []).filter((p) => p.v != null).length;
  const seasons = new Set((hist ?? []).filter((p) => p.v != null).map((p) => qt(p.key) % 4)).size;
  const warnings = [
    ...(mode === "own" && valid < 7 ? [`Only ${valid} valid points before ${evq}: both harmonic models fall back to climatology (they need ≥ 7).`] : []),
    ...(mode === "own" && valid > 0 && seasons < 4 ? [`History covers ${seasons}/4 seasons: climatology uses the overall mean for the missing seasons.`] : []),
    ...(mode === "own" && rep.pts.some((p) => qt(p.key) >= c0 && !tgt.includes(p.key)) ? ["Rows after the forecast horizon are ignored."] : []),
  ];
  const blocked = (mode === "own" && (rep.errors.length > 0 || valid === 0)) || (mode === "images" && (!imgSeries || valid === 0));

  const t0 = performance.now();
  const fits = useMemo(() => hist && !blocked ? ENGINES.map((e) => {
    const s = performance.now(), pred = e.fit(hist, tgt), ms = performance.now() - s;
    const band = residualBand(hist, e.fit as any);
    const pub = mode === "pixel" && px && near ? px.cf[e.id]?.[cut]?.q50[near.i] ?? null : null;
    const edited = JSON.stringify(hist) !== JSON.stringify(base);
    const dPub = pub && !edited ? Math.max(...pred.map((v, j) => (v == null || pub[j] == null ? 0 : Math.abs(v - pub[j]!)))) : null;
    const def = pred.map((v, j) => (v == null || truth[j] == null ? null : v - truth[j]!));
    return { ...e, pred, ms, band, dPub, def };
  }) : [], [hist, tgt.join(), truth, cut, blocked]);
  const total = performance.now() - t0;

  const keys = [...(hist ?? []).map((p) => p.key), ...tgt];
  const W = 900, H = 330, L = 44, R = W - 16, T = 16, B = H - 30;
  const X = (i: number) => L + (i / Math.max(1, keys.length - 1)) * (R - L), Y = (v: number) => T + ((Y1 - v) / (Y1 - Y0)) * (B - T);
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<number | null>(null);
  const setV = (i: number, clientY: number) => {
    const r = svg.current!.getBoundingClientRect(), y = ((clientY - r.top) / r.height) * H;
    const v = Math.max(Y0, Math.min(Y1, Y1 - ((y - T) / (B - T)) * (Y1 - Y0)));
    setHist((h) => h && h.map((p, j) => (j === i ? { ...p, v: +v.toFixed(3) } : p)));
  };
  const nh = hist?.length ?? 0;
  const path = (vals: (number | null)[], off: number) => vals.reduce((a, v, j) => (v == null ? a : a + (a && vals[j - 1] != null ? "L" : "M") + `${X(off + j).toFixed(1)},${Y(v).toFixed(1)}`), "");
  const f = fits.find((x) => x.id === focus);
  const edit = (fn: (h: Pt[]) => Pt[]) => setHist((h) => (h ? fn(h) : h));
  const under = m ? imageKeys(m).filter((k) => qt(k) < c0).slice(-1)[0] : null;
  const quarters = Array.from({ length: 16 * 4 }, (_, i) => keyOf(2010 * 4 + i));
  const exportCsv = () => download("ecorewind_series.csv", "quarter,ndvi\n" + [...(hist ?? []), ...tgt.map((k, j) => ({ key: k, v: truth[j] }))].map((p) => `${p.key},${p.v ?? ""}`).join("\n"));
  const label = mode !== "pixel" ? "your event" : isPlacebo(cut) ? "fake landfall" : "landfall";

  return (
    <div className="fe">
      <div className="fe-side">
        <Seg value={mode} onChange={setMode} options={[["pixel", "Study pixel"], ["own", "Your series"], ["images", "Your images"]]} />
        {mode === "pixel" ? <>
          <div className="fe-ctrl">
            <select value={st} onChange={(e) => { setSt(e.target.value); setPin(null); }}>{SITES.filter(([k]) => maps?.[k]).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            <select value={cut} onChange={(e) => setCut(e.target.value)}>{cuts.map((x) => <option key={x} value={x}>{cutoffLabel(x)}</option>)}</select>
          </div>
          {m && <Stage className="fe-map" aspect={m.shape[1] / m.shape[0]} view={view} onView={setView} pin={near?.uv ?? pin} onPick={setPin}
            layers={[under ? { src: layerURL(st, `obs_rgb_${under}.png`), filter: "url(#tc)" } : null]} />}
          <div className="fe-meta mono">{loading ? "loading 3000 pixel histories…" : near ? `pixel r${px!.r[near.i]} c${px!.c[near.i]} · fold ${px!.fold[near.i]} · click the image to move` : ""}</div>
        </> : mode === "images" ? <div className="fe-own">
          <div className="fe-msg ok">Upload one image per quarter, oldest first (file names are sorted). Each model forecasts every pixel; click the maps to pick the pixel shown in the chart.</div>
          <ul className="is-rules"><li>GeoTIFF: Sentinel-2 / HLS multi-band (NDVI is computed) or a single NDVI band</li><li>PNG / JPG: greyscale NDVI, with the value range you set</li>
            <li>All images the same size and area; large images are averaged down to ≤ {160} px</li><li>Pick the quarter of the first image and which image is the event</li></ul>
        </div> : <div className="fe-own">
          <div className="fe-ctrl">
            <label>Event quarter<select value={evq} onChange={(e) => setEvq(e.target.value)}>{quarters.map((k) => <option key={k} value={k}>{k}</option>)}</select></label>
            <label>Horizon<select value={horizon} onChange={(e) => setHorizon(+e.target.value)}>{[1, 2, 3, 4, 5, 6, 8].map((n) => <option key={n} value={n}>{n} quarter{n > 1 ? "s" : ""}</option>)}</select></label>
          </div>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={12} spellCheck={false} aria-label="your series" />
          <div className="fe-row">
            <label className="btn">Upload CSV<input type="file" accept=".csv,.txt,.tsv" hidden onChange={(e) => { const f0 = e.target.files?.[0]; if (f0) f0.text().then(setText); }} /></label>
            <button className="btn" onClick={() => download("ecorewind_template.csv", TEMPLATE)}>Template</button>
            <button className="btn" onClick={() => setText(TEMPLATE)}>Example</button>
          </div>
          {rep.errors.length > 0 && <div className="fe-msg bad">{rep.errors.slice(0, 5).map((e) => <div key={e}>{e}</div>)}{rep.errors.length > 5 && <div>+{rep.errors.length - 5} more</div>}</div>}
          {warnings.length > 0 && <div className="fe-msg">{warnings.map((w) => <div key={w}>{w}</div>)}</div>}
          {!rep.errors.length && <div className="fe-msg ok">{rep.pts.length} quarters read · {valid} valid before {evq} · last row {lastKey}</div>}
        </div>}
        <div className="fe-tools">
          <div className="sh-k">Edit the input</div>
          <button className="btn" onClick={() => setHist(base)}>Reset</button>
          <button className="btn" onClick={() => edit((h) => h.map((p, i) => (i >= h.length - 4 && p.v != null ? { ...p, v: +(p.v - 0.15).toFixed(3) } : p)))}>Drought: last year −0.15</button>
          <button className="btn" onClick={() => edit((h) => h.map((p, i) => (p.v == null ? p : { ...p, v: +(p.v + 0.02 * (i - h.length) / 4).toFixed(3) })))}>Add a +0.02 / yr trend</button>
          <button className="btn" onClick={() => edit((h) => h.map((p, i) => ((i * 7919) % 10 < 3 ? { ...p, v: null } : p)))}>Clouds: drop 30 %</button>
          <button className="btn" onClick={exportCsv}>Download as CSV</button>
          <div className="dim" style={{ fontSize: 11.5, marginTop: 4 }}>Drag any point before the cutoff. Double-click a point to mark it cloudy.</div>
        </div>
      </div>

      <div className="fe-main">
        {mode === "images" && <ImageSeries onSeries={setImgSeries} focus={focus} />}
        <div className="fe-chart">
          {blocked ? <div className="fe-blocked">{mode === "images" ? "Upload a quarterly image series above, or load the example." : "Fix the input on the left to run the models."}</div> :
          <svg ref={svg} viewBox={`0 0 ${W} ${H}`} width="100%" onPointerMove={(e) => drag.current != null && setV(drag.current, e.clientY)}
            onPointerUp={() => (drag.current = null)} onPointerLeave={() => (drag.current = null)}>
            {[0, 0.25, 0.5, 0.75, 1].map((v) => <g key={v}><line x1={L} x2={R} y1={Y(v)} y2={Y(v)} stroke="var(--line)" /><text x={L - 8} y={Y(v) + 4} textAnchor="end">{v.toFixed(2)}</text></g>)}
            {keys.map((k, i) => k.endsWith("Q1") && <text key={k + i} x={X(i)} y={H - 8} textAnchor="middle">{k.slice(0, 4)}</text>)}
            {nh > 0 && <><rect x={X(nh) - 6} y={T} width={R - X(nh) + 6} height={B - T} fill="rgba(255,255,255,.025)" />
              <line x1={X(nh) - 6} x2={X(nh) - 6} y1={T} y2={B} stroke={mode === "pixel" && isPlacebo(cut) ? "var(--placebo)" : "var(--signal)"} strokeDasharray="4 4" />
              <text x={X(nh)} y={T + 12} style={{ fill: mode === "pixel" && isPlacebo(cut) ? "var(--placebo)" : "var(--signal)" }}>{label}</text></>}
            {f?.band != null && <polygon fill="rgba(255,255,255,.07)" points={[...f.pred.map((v, j) => v == null ? "" : `${X(nh + j)},${Y(v + f.band!)}`), ...f.pred.map((v, j) => v == null ? "" : `${X(nh + j)},${Y(v - f.band!)}`).reverse()].filter(Boolean).join(" ")} />}
            {hist && <path d={path(hist.map((p) => p.v), 0)} fill="none" stroke="var(--observed)" strokeWidth={1.4} opacity={0.6} />}
            {base && hist && JSON.stringify(base) !== JSON.stringify(hist) && <path d={path(base.map((p) => p.v), 0)} fill="none" stroke="var(--dim)" strokeWidth={1} strokeDasharray="3 4" />}
            {truth.length > 0 && <path d={path(truth, nh)} fill="none" stroke="var(--observed)" strokeWidth={1.4} opacity={0.6} />}
            {truth.map((v, j) => v != null && <rect key={j} x={X(nh + j) - 3.5} y={Y(v) - 3.5} width={7} height={7} fill="var(--observed)" />)}
            {fits.map((x) => <path key={x.id} d={path([hist?.filter((p) => p.v != null).slice(-1)[0]?.v ?? null, ...x.pred], nh - 1)} fill="none"
              stroke={meta(x.id).color} strokeWidth={x.id === focus ? 2.6 : 1.3} opacity={x.id === focus ? 1 : 0.55} strokeDasharray={x.id === focus ? undefined : "5 4"} />)}
            {hist?.map((p, i) => <g key={p.key} style={{ cursor: "ns-resize" }} onPointerDown={(e) => { (e.target as Element).setPointerCapture?.(e.pointerId); drag.current = i; }}
              onDoubleClick={() => edit((h) => h.map((q, j) => (j === i ? { ...q, v: q.v == null ? base?.[i]?.v ?? 0.5 : null } : q)))}>
              <circle cx={X(i)} cy={p.v == null ? B - 4 : Y(p.v)} r={9} fill="transparent" />
              {p.v == null ? <text x={X(i)} y={B - 1} textAnchor="middle" style={{ fill: "var(--dim)" }}>×</text>
                : <circle cx={X(i)} cy={Y(p.v)} r={4.2} fill="var(--bg)" stroke="var(--observed)" strokeWidth={1.6} />}
            </g>)}
          </svg>}
          <div className="fe-legend"><span><i className="sq" /> observed (drag before the cutoff)</span><span><i className="ln" /> live forecast · focus model solid · 90 % in-sample residual band</span>
            <span className="mono dim">{fits.length} models refit in {total.toFixed(2)} ms</span></div>
        </div>

        <table className="t fe-t">
          <thead><tr><th>Model</th>{tgt.map((k, j) => <th key={k} className="n">{j === 0 ? (mode !== "pixel" ? k : "landfall") : `+${j}q`}</th>)}<th className="n">Mean deficit</th>{mode === "pixel" && <th className="n">vs published</th>}<th className="n">Fit</th></tr></thead>
          <tbody>{fits.map((x) => {
            const d = x.def.filter((v): v is number => v != null), md = d.length ? d.reduce((a, b) => a + b, 0) / d.length : null;
            return <tr key={x.id} className={x.id === focus ? "on" : ""} onClick={() => setFocus(x.id)}>
              <td><span className="dot" style={{ background: meta(x.id).color }} />{meta(x.id).short}</td>
              {x.pred.map((v, j) => <td key={j} className="n mono">{fmt(v, 3)}</td>)}
              <td className="n mono" style={{ color: md != null && md > 0.02 ? "var(--dmg1)" : undefined }}>{fmt(md, 3, true)}</td>
              {mode === "pixel" && <td className="n mono">{x.dPub == null ? <span className="dim">edited</span> : <span title="max |live − published Python| over leads">|Δ| {x.dPub.toFixed(3)}</span>}</td>}
              <td className="n mono dim">{x.ms < 0.01 ? "<0.01" : x.ms.toFixed(2)} ms</td></tr>;
          })}</tbody>
        </table>

        <details className="guide" open={mode === "own"}>
          <summary>Input guidelines · what these models accept</summary>
          <div className="guide-grid">
            <div><h5>Format</h5><ul>
              <li>CSV or plain text, one row per quarter: <span className="mono">YYYYQn, value</span> (e.g. <span className="mono">2019Q3, 0.64</span>). <span className="mono">2019-Q3</span> and tabs/semicolons also work.</li>
              <li>An optional header row (<span className="mono">quarter,ndvi</span>) and <span className="mono">#</span> comment lines are ignored.</li>
              <li>Missing or cloudy quarters: leave the value empty or write <span className="mono">nan</span>. Gaps are fine.</li>
              <li>Each quarter at most once; order does not matter.</li></ul></div>
            <div><h5>Values</h5><ul>
              <li>One vegetation index per row; the models were built for <b>NDVI</b> in [−1, 1] from cloud-masked quarterly composites (healthy marsh ≈ 0.4–0.8, open water &lt; 0).</li>
              <li>Other indices (NDMI, NDWI, EVI) work mechanically, but the published skill numbers apply to NDVI only.</li>
              <li>Values outside [−1, 1] are rejected.</li></ul></div>
            <div><h5>History needed</h5><ul>
              <li>Rows <b>before</b> the event quarter are the model input; rows at or after it are optional observed values used only to compute the deficit.</li>
              <li>Persistence needs 1 valid value; climatology at least 1 per season (else the overall mean); both harmonic models need <b>≥ 7</b> valid values, else they fall back to climatology, exactly as the published pipeline does.</li>
              <li>Two or more years of history give stable seasonal fits; the study sites use 6–8 years.</li></ul></div>
            <div><h5>What you get</h5><ul>
              <li>Each model's storm-free forecast for the chosen horizon, the deficit (forecast − observed) where you supplied observations, and a 90 % in-sample residual band.</li>
              <li>Everything runs locally; nothing is uploaded anywhere.</li>
              <li>The deep networks need full image patches (22 channels × 64 × 64 pixels); see the neural engine's input spec below.</li></ul></div>
          </div>
        </details>
      </div>
    </div>
  );
}
