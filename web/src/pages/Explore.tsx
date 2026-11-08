import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import Stage, { Layer, UV, View, VIEW0, ZoomButtons } from "../components/Stage";
import { Icon, Seg, Verdict } from "../components/ui";
import { TimeChart, ValueBars } from "../components/charts";
import { fmt, quarterLabel, SITES, TRACKS, useMaps, useResults } from "../lib/data";
import { attrOf, cutoffLabel, isPlacebo, leadKey, verdictOf } from "../lib/derive";
import { cfPath, imageKeys, layerURL, modelsFor, nearestKey, nearestSample, pixelSeries, placeboCuts, sampleDeficits, skillAny,
  usePixels, useDebounced } from "../lib/explore";
import { FAM_LABEL, FAM_ORDER, famOf, meta, sortModels } from "../lib/models";
import { ensemble, EnsStat, gradientCSS, Kind as RKind, loadPixels, valueAt } from "../lib/raster";

type Mode = "gallery" | "compare" | "ensemble" | "timelapse";
type K = "cf" | "deficit" | "width";
const KIND_FILE: Record<K, "cf_ndvi" | "deficit" | "width"> = { cf: "cf_ndvi", deficit: "deficit", width: "width" };
const KIND_R: Record<K, RKind> = { cf: "ndvi", deficit: "deficit", width: "width" };
const KIND_LABEL: Record<K, string> = { cf: "Counterfactual NDVI", deficit: "Damage (deficit)", width: "Uncertainty (90 % width)" };
const UNDER = { dark: "url(#tc) saturate(.7) brightness(.62)", rgb: "url(#tc)" };

/** Pixel buffers for a set of layer URLs (loaded lazily, cached in raster.ts). */
function useBuffers(urls: string[]) {
  const [bufs, set] = useState<Record<string, Awaited<ReturnType<typeof loadPixels>>>>({});
  const key = urls.join("|");
  useEffect(() => {
    let live = true;
    urls.forEach((u) => { if (!(u in bufs)) loadPixels(u).then((p) => live && set((b) => ({ ...b, [u]: p }))); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return bufs;
}

export default function Explore() {
  const [q, setQ] = useSearchParams();
  const set = (kv: Record<string, string | null>) => {
    const n = new URLSearchParams(q);
    for (const [k, v] of Object.entries(kv)) v == null ? n.delete(k) : n.set(k, v);
    setQ(n, { replace: true });
  };
  const site = q.get("site") === "everglades" ? "everglades" : "mississippi";
  const track = q.get("track") === "A" || q.get("track") === "B" ? q.get("track")! : site === "mississippi" ? "A" : "B";
  const event = site === "mississippi" ? "ida" : "irma";
  const mode = (["gallery", "compare", "ensemble", "timelapse"].includes(q.get("mode") ?? "") ? q.get("mode") : "gallery") as Mode;
  const kind = (["cf", "deficit", "width"].includes(q.get("kind") ?? "") ? q.get("kind") : "deficit") as K;
  const { data: r } = useResults();
  const { data: maps } = useMaps();
  const st = `${site}_${track}`;
  const m = maps?.[st];
  const cuts = m ? [event, ...placeboCuts(m)].filter((c) => m.cutoffs[c]) : [event];
  const cut = cuts.includes(q.get("cut") ?? "") ? q.get("cut")! : event;
  const placebo = isPlacebo(cut);
  const models = useMemo(() => (m ? sortModels(modelsFor(m, cut)) : []), [m, cut]);
  const focus = models.includes(q.get("model") ?? "") ? q.get("model")! : models.includes("simvp") ? "simvp" : models[0] ?? "";
  const hidden = new Set((q.get("hide") ?? "").split(",").filter(Boolean));
  const shown = models.filter((id) => !hidden.has(id));
  const leads = m?.cutoffs[cut]?.leads ?? [0];
  const [li, setLi] = useState(0);
  const lead = leads[Math.min(li, leads.length - 1)] ?? 0;
  const [view, setView] = useState<View>(VIEW0);
  const [cursor, setCursor] = useState<UV | null>(null);
  const [pin, setPin] = useState<UV | null>(null);
  const [split, setSplit] = useState(0.5);
  const [playing, setPlaying] = useState(false);
  const [rgb, setRgb] = useState(q.get("rgb") !== "0");
  const { data: px, loading: pxLoading } = usePixels(m ? st : null);

  useEffect(() => { setLi(0); setPin(null); setView(VIEW0); }, [st, cut]);
  useEffect(() => {
    if (!playing || mode === "timelapse") return;
    const t = setInterval(() => setLi((i) => (i + 1) % leads.length), 1500);
    return () => clearInterval(t);
  }, [playing, leads.length, mode]);

  const aspect = m ? m.shape[1] / m.shape[0] : 1;
  const qkey = leadKey(cut, lead);
  const underKey = m ? nearestKey(m, qkey) : null;
  const underlay: Layer = rgb && m && underKey ? { src: layerURL(st, `obs_rgb_${underKey}.png`), filter: UNDER.dark, key: "under" } : null;
  const lay = (id: string, k: K = kind, op = 1): Layer => {
    if (!m) return null;
    const p = id === "obs" ? `observed/${cut}/ndvi_L${lead}.png` : id === "sd" ? `disagreement/${cut}/sd_L${lead}.png` : cfPath(id, cut, KIND_FILE[k], lead);
    return m.layers[p] ? { src: layerURL(st, p), opacity: op, key: "ov" } : null;
  };
  const kindOfTile = (id: string): RKind => (id === "obs" ? "ndvi" : id === "sd" ? "width" : KIND_R[kind]);
  const urlOf = (id: string) => { const l = lay(id); return l ? l.src : null; };

  // ---- stats per model
  const sdef = useMemo(() => sampleDeficits(px, cut), [px, cut]);
  const leadPos = (id: string) => sdef[id]?.leads.indexOf(lead) ?? -1;
  const sampleDef = (id: string) => { const s = sdef[id]; const j = leadPos(id); return s && j >= 0 ? s.mean[j] : null; };
  const stat = lead === 0 ? "lead 0" : "leads 1-3";
  const vstat = lead === 0 ? "lead0" : "primary";
  const verdict = (id: string) => verdictOf(r, site, track, id, vstat as "lead0" | "primary");
  const passes = (id: string) => verdict(id)?.pass;

  // ---- read-out under the cursor / at the pin, for every visible tile
  const [sortBy, setSortBy] = useState<"fam" | "def" | "skill">("fam");
  const shownSorted = sortBy === "fam" ? shown : [...shown].sort((a, b) => sortBy === "def" ? (sampleDef(b) ?? -9) - (sampleDef(a) ?? -9)
    : (skillAny(r, b, site, track)?.v ?? -9) - (skillAny(r, a, site, track)?.v ?? -9));
  const tileIds = mode === "gallery" ? [kind === "cf" ? "obs" : "sd", ...shownSorted] : [];
  const probeIds = [...new Set([...tileIds, ...models])];
  const probeUrls = probeIds.map(urlOf).filter((u): u is string => !!u);
  const bufs = useBuffers(cursor || pin ? probeUrls : []);
  const valAt = (id: string, uv: UV | null) => { const u = urlOf(id); return uv && u ? valueAt(bufs[u] ?? null, kindOfTile(id), uv[0], uv[1]) : null; };

  const tl = mode === "timelapse";
  const lib = <Library {...{ models, focus, hidden, r, site, track, lead, sampleDef, passes, mode, placebo }}
    onFocus={(id) => set({ model: id })}
    onToggle={(id) => { const h = new Set(hidden); h.has(id) ? h.delete(id) : h.add(id); set({ hide: [...h].join(",") || null }); }}
    onPreset={(p) => {
      const keep = p === "all" ? models : p === "pass" ? models.filter((id) => passes(id) === true) : p === "none" ? [] : models.filter((id) => famOf(id) === p);
      set({ hide: models.filter((id) => !keep.includes(id)).join(",") || null });
    }} />;

  return (
    <div className="studio">
      <header className="studio-top">
        <Seg value={site} options={[["mississippi", "Louisiana · Ida"], ["everglades", "Everglades · Irma"]]}
          onChange={(s) => set({ site: s, track: null, cut: null, model: null, hide: null })} />
        <select value={track} onChange={(e) => set({ track: e.target.value, cut: null })} aria-label="resolution">
          {["A", "B"].map((t) => <option key={t} value={t}>{t === "A" ? "10 m · Sentinel-2" : "30 m · HLS"}</option>)}</select>
        <select value={cut} onChange={(e) => set({ cut: e.target.value })} aria-label="scenario" className={placebo ? "violet" : ""}>
          {cuts.map((c) => <option key={c} value={c}>{cutoffLabel(c)}</option>)}</select>
        <div className="studio-modes">
          <Seg value={mode} onChange={(v) => set({ mode: v })} options={[["gallery", "All models"], ["compare", "Compare"], ["ensemble", "Ensemble"], ["timelapse", "Time-lapse"]]} />
        </div>
        {(mode === "gallery" || mode === "compare") && <Seg value={kind} onChange={(v) => set({ kind: v })}
          options={[["cf", "No-storm NDVI"], ["deficit", "Damage"], ["width", "Uncertainty"]]} />}
        <label className="toggle" title="show the real satellite image under the model layers"><input type="checkbox" checked={rgb} onChange={(e) => setRgb(e.target.checked)} /> imagery</label>
      </header>

      {!m && <div className="studio-empty">{maps === null ? <>Map layers aren't in this deployment. Run <span className="mono">notebooks/60_web_build_colab.ipynb</span>.</> : <div className="skeleton" style={{ height: 400 }} />}</div>}

      {m && <div className={`studio-body ${tl ? "no-lib" : ""}`}>
        {!tl && <aside className="studio-lib">{lib}</aside>}

        <section className="studio-main">
          {placebo && <div className="placebo-banner"><b>Placebo:</b> no hurricane happened in {cut.match(/\d{4}/)?.[0]}. Any "damage" shown is model error — this is how we test the models.</div>}
          {mode === "gallery" && <div className="gallery-sort stage-ui"><span className="dim">sort</span>
            <Seg value={sortBy} onChange={setSortBy} options={[["fam", "Family"], ["def", "Damage"], ["skill", "Skill"]]} /></div>}
          {mode === "gallery" && <div className="gallery" style={{ ["--n" as string]: tileIds.length }}>
            {tileIds.map((id) => {
              const ov = lay(id), v = valAt(id, cursor ?? pin), isObs = id === "obs" || id === "sd", mm = meta(id);
              const sd = isObs ? null : sampleDef(id), pv = isObs ? undefined : passes(id);
              return <div key={id} className={`tile ${id === focus ? "on" : ""}`} style={{ ["--c" as string]: isObs ? "#fb9db0" : mm.color }}>
                <div className="tile-head" onClick={() => !isObs && set({ model: id })}>
                  <span className="dot" style={{ background: isObs ? "var(--observed)" : mm.color }} />
                  <span className="tile-name" title={isObs ? undefined : mm.name}>{id === "obs" ? "Observed" : id === "sd" ? "Model disagreement σ" : mm.short}</span>
                  {!isObs && pv != null && <span className={`mini ${pv ? "pass" : "fail"}`}>{pv ? "✓" : "✗"}</span>}
                  <span className="tile-val mono">{v != null ? fmt(v, 3, kind === "deficit" && !isObs) : sd != null && kind === "deficit" ? <span className="dim">{fmt(sd, 3, true)}</span> : ""}</span>
                </div>
                <Stage layers={[underlay, ov]} aspect={aspect} view={view} onView={setView} cursor={cursor} onCursor={setCursor} pin={pin}
                  onPick={setPin} className="tile-stage">
                  {!ov && <div className="tile-na">no layer for lead {lead}</div>}
                </Stage>
                {!isObs && <div className="tile-foot">
                  <button className="link" onClick={() => set({ mode: "compare", model: id, a: "obs" })}>compare ⇄</button>
                </div>}
              </div>;
            })}
            {!tileIds.length && <div className="note">No models selected. Use the library on the left.</div>}
          </div>}

          {mode === "compare" && <CompareStage {...{ m, st, cut, lead, models, focus, kind, aspect, view, setView, cursor, setCursor, pin, setPin, split, setSplit, underlay, q, set, lay }} />}
          {mode === "ensemble" && <EnsembleStage {...{ st, cut, lead, shown, models, aspect, view, setView, cursor, setCursor, pin, setPin, underlay, m, passes }} />}
          {mode === "timelapse" && <TimeLapse {...{ m, st, cut, focus, aspect, view, setView, pin, setPin, rgb, models }} onFocus={(id: string) => set({ model: id })} />}
          {!tl && <ZoomButtons view={view} onView={setView} />}
        </section>

        <aside className="studio-insp">
          <Inspector {...{ r, site, track, event, cut, lead, stat, focus, models, shown, sdef, passes, verdict, px, pxLoading, pin, m, valAt }}
            onFocus={(id: string) => set({ model: id })} onClear={() => setPin(null)} kind={kind} />
        </aside>
      </div>}

      {m && !tl && <footer className="studio-time">
        <button className="play" onClick={() => setPlaying((p) => !p)} aria-label={playing ? "pause" : "play"}><Icon name={playing ? "pause" : "play"} size={16} /></button>
        <div className="leads">
          {leads.map((l, i) => <button key={l} className={`leadbtn ${i === li ? "on" : ""} ${l >= 1 && l <= 3 ? "primary" : ""}`} onClick={() => { setPlaying(false); setLi(i); }}>
            <b>{l === 0 ? "Landfall" : `+${l} quarter${l > 1 ? "s" : ""}`}</b><span>{quarterLabel(leadKey(cut, l))}</span></button>)}
        </div>
        <Legend kind={mode === "ensemble" ? "deficit" : KIND_R[kind]} />
      </footer>}
    </div>
  );
}

// ------------------------------------------------------------------------------------------- library
function Library({ models, focus, hidden, r, site, track, lead, sampleDef, passes, onFocus, onToggle, onPreset, mode, placebo }: {
  models: string[]; focus: string; hidden: Set<string>; r: any; site: string; track: string; lead: number; mode: Mode; placebo: boolean;
  sampleDef: (id: string) => number | null; passes: (id: string) => boolean | undefined;
  onFocus: (id: string) => void; onToggle: (id: string) => void; onPreset: (p: string) => void;
}) {
  const multi = mode === "gallery" || mode === "ensemble";
  return <>
    <div className="lib-head">
      <h3>{models.length} models</h3>
      <span className="muted" style={{ fontSize: 12 }}>{multi ? "tick to show · click to focus" : "click to focus"}</span>
    </div>
    {multi && <div className="presets">
      {[["all", "All"], ["pass", "Placebo-passing"], ["baseline", "Baselines"], ["deep", "Deep"], ["none", "None"]].map(([k, l]) =>
        <button key={k} className="chip" onClick={() => onPreset(k)}>{l}</button>)}
    </div>}
    {FAM_ORDER.map((f) => {
      const ids = models.filter((id) => famOf(id) === f);
      if (!ids.length) return null;
      return <div key={f}>
        <div className="group-label">{FAM_LABEL[f]}</div>
        {ids.map((id) => {
          const mm = meta(id), sk = skillAny(r, id, site, track), d = sampleDef(id), p = passes(id);
          return <div key={id} className={`lib-row ${id === focus ? "on" : ""} ${hidden.has(id) && multi ? "off" : ""}`}>
            {multi && <input type="checkbox" checked={!hidden.has(id)} onChange={() => onToggle(id)} aria-label={`show ${mm.name}`} />}
            <button className="lib-name" onClick={() => onFocus(id)} title={mm.blurb}>
              <span className="dot" style={{ background: mm.color }} />{mm.short}</button>
            <span className="lib-num mono" title={sk?.src === "phase5" ? "Phase 5 test R²" : "NDVI R² on placebo windows"}>{sk ? sk.v.toFixed(2) : "—"}</span>
            <span className={`lib-num mono ${d != null && d > 0.02 ? (placebo ? "violet" : "warm") : ""}`} title={`sample mean deficit at lead ${lead}`}>{d == null ? "·" : fmt(d, 3, true)}</span>
            {p == null ? <span className="mini none">·</span> : <span className={`mini ${p ? "pass" : "fail"}`} title="pre-registered placebo-in-time test">{p ? "✓" : "✗"}</span>}
          </div>;
        })}
      </div>;
    })}
    <div className="lib-key dim">R² · deficit at this lead (3000-pixel sample) · placebo test</div>
  </>;
}

// ------------------------------------------------------------------------------------------- compare
function CompareStage({ m, st, cut, lead, models, focus, kind, aspect, view, setView, cursor, setCursor, pin, setPin, split, setSplit, underlay, q, set, lay }: any) {
  const a = q.get("a") === "obs" || models.includes(q.get("a")) ? q.get("a") : "obs";
  const b = models.includes(q.get("b")) ? q.get("b") : focus;
  const opts = [["obs", "Observed (what happened)"], ...models.map((id: string) => [id, meta(id).name])];
  const nameOf = (id: string) => (id === "obs" ? "Observed" : meta(id).short);
  const L = lay(a, kind, 1), R = lay(b, kind, 1);
  const [cine, setCine] = useState(false);
  useEffect(() => {
    if (!cine) return;
    let raf = 0; const t0 = performance.now();
    const f = (t: number) => { setSplit(0.5 + 0.42 * Math.sin((t - t0) / 1400)); raf = requestAnimationFrame(f); };
    raf = requestAnimationFrame(f);
    return () => cancelAnimationFrame(raf);
  }, [cine]);
  return <>
    <Stage layers={[underlay, L]} right={[underlay, R]} split={split} onSplit={setSplit} aspect={aspect} view={view} onView={setView}
      cursor={cursor} onCursor={setCursor} pin={pin} onPick={setPin} className="big-stage"
      labels={[<><span className="dot" style={{ background: a === "obs" ? "var(--observed)" : meta(a).color }} />{nameOf(a)}</>,
        <><span className="dot" style={{ background: meta(b).color }} />{nameOf(b)}</>]} />
    <div className="compare-pick stage-ui">
      <select value={a} onChange={(e) => set({ a: e.target.value })} aria-label="left side">{opts.map(([v, l]: string[]) => <option key={v} value={v}>{l}</option>)}</select>
      <button className="icon-btn" onClick={() => set({ a: b, b: a === "obs" ? focus : a })} aria-label="swap" title="swap sides">⇄</button>
      <select value={b} onChange={(e) => set({ b: e.target.value, model: e.target.value })} aria-label="right side">{opts.slice(1).map(([v, l]: string[]) => <option key={v} value={v}>{l}</option>)}</select>
      <button className={`icon-btn ${cine ? "on" : ""}`} onClick={() => setCine((c) => !c)} title="auto-sweep the divider" aria-label="auto sweep">{cine ? "❚❚" : "↔"}</button>
    </div>
    {a === "obs" && kind !== "cf" && <div className="compare-note stage-ui">Left: observed NDVI (the observation has no deficit). Right: {KIND_LABEL[kind as K].toLowerCase()}.</div>}
  </>;
}

// ------------------------------------------------------------------------------------------- ensemble
function EnsembleStage({ st, cut, lead, shown, models, aspect, view, setView, cursor, setCursor, pin, setPin, underlay, m, passes }: any) {
  const [stat, setStat] = useState<EnsStat>("mean");
  const [res, setRes] = useState<Awaited<ReturnType<typeof ensemble>>>(null);
  const [busy, setBusy] = useState(false);
  const ids: string[] = useDebounced(shown.filter((id: string) => m.layers[cfPath(id, cut, "deficit", lead)]), 200);
  useEffect(() => {
    let live = true;
    setBusy(true);
    ensemble(ids.map((id) => layerURL(st, cfPath(id, cut, "deficit", lead))), stat).then((e) => { if (live) { setRes(e); setBusy(false); } });
    return () => { live = false; };
  }, [ids.join(","), stat, st, cut, lead]);
  const npass = ids.filter((id) => passes(id) === true).length;
  return <>
    <Stage layers={[underlay, res && { src: res.url, key: "ens" }]} aspect={aspect} view={view} onView={setView} cursor={cursor} onCursor={setCursor}
      pin={pin} onPick={setPin} className="big-stage" />
    <div className="ens-card glass stage-ui">
      <div className="eyebrow">Ensemble of {ids.length} model{ids.length === 1 ? "" : "s"} {busy && <span className="spin" />}</div>
      <Seg value={stat} onChange={setStat} options={[["mean", "Mean damage"], ["agree", "Agreement"], ["sd", "Spread σ"]]} />
      <p className="muted" style={{ fontSize: 12.5, margin: "10px 0 0" }}>
        {stat === "mean" ? "Per-pixel mean of the selected models' deficits." : stat === "agree" ? "Share of selected models that see a deficit above 0.05 NDVI at each pixel." : "How much the selected models disagree at each pixel."}
        {" "}Computed live in your browser from the published layers.</p>
      {res && <div className="ens-nums">
        <div><b className="mono">{fmt(res.meanAll, 3, true)}</b><span>area-mean deficit</span></div>
        <div><b className="mono">{res.agreeAll == null ? "—" : Math.round(res.agreeAll * 100) + "%"}</b><span>mean agreement</span></div>
        <div><b className="mono">{npass}/{ids.length}</b><span>placebo-passing</span></div>
      </div>}
      <div className="legend-bar" style={{ background: gradientCSS(stat === "mean" ? "deficit" : "width"), marginTop: 10 }} />
      <div className="mono dim legend-ticks">{stat === "mean" ? <><span>−0.3 gain</span><span>0</span><span>+0.3 loss</span></> : stat === "agree" ? <><span>0 %</span><span>100 % agree</span></> : <><span>0</span><span>0.6</span></>}</div>
      {ids.length < models.length && <div className="dim" style={{ fontSize: 11.5, marginTop: 6 }}>Change the set in the model library.</div>}
    </div>
  </>;
}

// ------------------------------------------------------------------------------------------- time-lapse
function TimeLapse({ m, st, cut, focus, aspect, view, setView, pin, setPin, rgb, models, onFocus }: any) {
  const keys: string[] = imageKeys(m);
  const lead0 = leadKey(cut, 0), landfall = keys.findIndex((k) => k > lead0.slice(0, 6));
  const [i, setI] = useState(Math.max(0, landfall - 4));
  const [play, setPlay] = useState(false);
  const [band, setBand] = useState<"rgb" | "ndvi">("rgb");
  const [split, setSplit] = useState(0.5);
  useEffect(() => { if (!play) return; const t = setInterval(() => setI((x) => (x + 1) % keys.length), 650); return () => clearInterval(t); }, [play, keys.length]);
  const k = keys[Math.min(i, keys.length - 1)];
  const leadAt = (m.cutoffs[cut]?.leads ?? []).find((l: number) => leadKey(cut, l) === k);
  const cf = leadAt != null ? cfPath(focus, cut, "cf_ndvi", leadAt) : null;
  const base: Layer = { src: layerURL(st, `${band === "rgb" ? "obs_rgb" : "obs_ndvi"}_${k}.png`), filter: band === "rgb" ? UNDER.rgb : undefined, key: "tl" };
  const showCf = cf && m.layers[cf];
  const after = landfall >= 0 && i >= landfall;
  return <>
    <Stage layers={[base]} right={showCf ? [{ src: layerURL(st, `obs_ndvi_${k}.png`), key: "nd" }, { src: layerURL(st, cf!), key: "cf" }] : undefined}
      split={showCf ? split : undefined} onSplit={setSplit} aspect={aspect} view={view} onView={setView} pin={pin} onPick={setPin} className="big-stage"
      labels={showCf ? [<>Observed · {quarterLabel(k)}</>, <><span className="dot" style={{ background: meta(focus).color }} />{meta(focus).short} · no-storm world</>] : undefined} />
    <ZoomButtons view={view} onView={setView} />
    <div className="tl-card glass stage-ui">
      <div className="tl-date"><span className="mono">{quarterLabel(k)}</span>
        {after ? <span className="badge fail">after {isPlacebo(cut) ? "placebo date" : "landfall"}</span> : <span className="badge none">before</span>}</div>
      <Seg value={band} onChange={setBand} options={[["rgb", "True colour"], ["ndvi", "NDVI"]]} />
      {showCf ? <p className="muted" style={{ fontSize: 12.5, margin: "10px 0 0" }}>Forecast quarter: drag the divider to see {meta(focus).short}'s storm-free version.
        <select value={focus} onChange={(e) => onFocus(e.target.value)} style={{ marginTop: 8, width: "100%" }}>{models.map((id: string) => <option key={id} value={id}>{meta(id).name}</option>)}</select></p>
        : <p className="muted" style={{ fontSize: 12.5, margin: "10px 0 0" }}>Every quarterly cloud-masked composite in the record. Counterfactuals appear on forecast quarters.</p>}
    </div>
    <footer className="studio-time tl">
      <button className="play" onClick={() => setPlay((p) => !p)} aria-label={play ? "pause" : "play"}><Icon name={play ? "pause" : "play"} size={16} /></button>
      <div className="tl-track">
        <input type="range" min={0} max={keys.length - 1} value={i} onChange={(e) => { setPlay(false); setI(+e.target.value); }} aria-label="quarter" />
        <div className="tl-ticks">{keys.map((kk, j) => <span key={kk} style={{ left: `${(j / (keys.length - 1)) * 100}%` }}
          className={`${j === landfall ? "lf" : ""} ${(m.cutoffs[cut]?.leads ?? []).some((l: number) => leadKey(cut, l) === kk) ? "fc" : ""}`}>{kk.endsWith("Q1") ? kk.slice(0, 4) : ""}</span>)}</div>
      </div>
      <span className="mono" style={{ minWidth: 120, textAlign: "right" }}>{k}</span>
    </footer>
  </>;
}

// ------------------------------------------------------------------------------------------- inspector
function Inspector({ r, site, track, event, cut, lead, stat, focus, models, shown, sdef, passes, verdict, px, pxLoading, pin, m, valAt, onFocus, onClear, kind }: any) {
  const mm = meta(focus);
  const a = attrOf(r, site, track, event, focus, stat);
  const v = verdict(focus);
  const sk = skillAny(r, focus, site, track);
  const sd = sdef[focus];
  const placebo = isPlacebo(cut);
  // deficit-over-leads chart (sample means), all models
  const leadsAll: number[] = m.cutoffs[cut]?.leads ?? [];
  const defSeries = shown.filter((id: string) => sdef[id]).map((id: string) => ({ id, name: meta(id).short, color: meta(id).color,
    values: leadsAll.map((l) => { const j = sdef[id].leads.indexOf(l); return j >= 0 ? sdef[id].mean[j] : null; }), dash: passes(id) === false, dots: true }));
  const near = pin && px ? nearestSample(px, m.shape, pin) : null;
  const ps = near ? pixelSeries(px, near.i, cut) : null;
  const pinVals = pin ? models.map((id: string) => ({ id, label: meta(id).short, v: valAt(id, pin), color: meta(id).color, faded: passes(id) === false }))
    .filter((x: any) => x.v != null).sort((x: any, y: any) => y.v - x.v) : [];
  const obsVal = pin ? valAt("obs", pin) : null;
  return <>
    <div className="insp-focus">
      <div className="eyebrow">{placebo ? cutoffLabel(cut) : `${SITES[site].storm} · ${SITES[site].landfall}`} · {TRACKS[track]}</div>
      <div className="insp-title"><span className="dot" style={{ background: mm.color, width: 12, height: 12 }} /><h3>{mm.name}</h3></div>
      <div className="muted" style={{ fontSize: 12.5 }}>{mm.blurb}{famOf(focus) !== "baseline" && famOf(focus) !== "deep" ? ` · ${FAM_LABEL[famOf(focus) as keyof typeof FAM_LABEL].toLowerCase()}` : ""}</div>
      <div className="insp-kpis">
        <div><b className="mono" style={{ color: (a?.deficit ?? sd?.mean[sd.leads.indexOf(lead)] ?? 0) > 0.02 ? "var(--dmg1)" : "var(--cf)" }}>
          {fmt(a?.deficit ?? (sd ? sd.mean[sd.leads.indexOf(lead)] : null), 3, true)}</b>
          <span>{a ? (lead === 0 ? "deficit just after landfall" : "deficit, quarters 1–3") : `sample deficit at lead ${lead}`}</span></div>
        <div><b className="mono">{sk ? sk.v.toFixed(3) : "—"}</b><span>{sk?.src === "phase5" ? "test R² (Phase 5)" : "skill · NDVI R²"}</span></div>
        <div>{v ? <Verdict pass={v.pass} /> : <span className="badge none">not tested</span>}<span>placebo test</span></div>
      </div>
      {v && <div className="dim mono" style={{ fontSize: 11 }}>event {fmt(v.event_median, 3, true)} vs placebo p95 {fmt(v.placebo_p95, 3, true)}</div>}
      <Link className="chip" to={`/models/${focus}`} style={{ marginTop: 10 }}>model card <Icon name="arrow" size={12} /></Link>
    </div>

    {pin ? <div className="insp-sec">
      <div className="sec-head"><h4><Icon name="pin" size={14} /> This pixel · {lead === 0 ? "landfall" : `lead ${lead}`}</h4><button className="link" onClick={onClear}>clear</button></div>
      {obsVal != null && <div className="muted" style={{ fontSize: 12.5, marginBottom: 6 }}>Observed NDVI <b className="mono" style={{ color: "var(--observed)" }}>{fmt(obsVal, 3)}</b></div>}
      {pinVals.length ? <ValueBars rows={pinVals} span={kind === "deficit" ? 0.3 : undefined} /> : <div className="dim" style={{ fontSize: 12.5 }}>No model output here (not an evaluated wetland pixel). Try a coloured area.</div>}
      {pxLoading && <div className="dim" style={{ fontSize: 12, marginTop: 10 }}><span className="spin" /> loading pixel histories…</div>}
      {ps && near && <>
        <div className="group-label" style={{ marginTop: 16 }}>Full history · nearest sampled pixel {near.dist > 3 ? `(${Math.round(near.dist * (m.shape[0] > 1000 ? 10 : 30))} m away)` : ""}</div>
        <TimeChart x={ps.label} marker={ps.landfall} markerLabel={placebo ? "placebo date" : "landfall"} focus={focus} onFocus={onFocus} height={230} width={380}
          series={[{ id: "obs", name: "Observed", color: "var(--observed)", values: ps.obs, width: 2.4, dots: true },
            ...shown.filter((id: string) => ps.models[id]).map((id: string) => ({ id, name: meta(id).short, color: meta(id).color, values: ps.models[id].q50, dash: true,
              band: id === focus ? [ps.models[id].q10, ps.models[id].q90] as [(number | null)[], (number | null)[]] : undefined }))]} />
        <div className="dim" style={{ fontSize: 11.5 }}>Solid: observed NDVI. Dashed: each model's storm-free forecast (band = {mm.short} 80 % interval). Click a line to focus.</div>
      </>}
    </div> : <div className="insp-sec">
      <div className="muted" style={{ fontSize: 12.5 }}><Icon name="pin" size={13} /> Click any map to read every model at that pixel and see its 10-year history.</div>
    </div>}

    {defSeries.length > 0 && <div className="insp-sec">
      <h4>Damage over time · every model</h4>
      <TimeChart x={leadsAll.map((l: number) => (l === 0 ? "landfall" : `+${l}q`))} focus={focus} onFocus={onFocus} height={190} width={380} series={defSeries} shade={leadsAll.length > 3 ? [leadsAll.indexOf(1), leadsAll.indexOf(Math.min(3, Math.max(...leadsAll)))] : undefined} />
      <div className="dim" style={{ fontSize: 11.5 }}>Mean counterfactual − observed NDVI over 3000 sampled wetland pixels. Dashed = fails the placebo test. Shaded = the pre-registered window (quarters 1–3).
        {placebo ? " On a placebo date every line should sit at 0." : ""}</div>
    </div>}
  </>;
}

function Legend({ kind }: { kind: RKind }) {
  return <div className="legend">
    <div className="legend-bar" style={{ background: gradientCSS(kind) }} />
    <div className="mono dim legend-ticks">{kind === "deficit" ? <><span>−0.3 gain</span><span>0</span><span>+0.3 loss</span></> : kind === "ndvi" ? <><span>NDVI −0.2</span><span>bare</span><span>1.0 green</span></> : <><span>0</span><span>0.3</span><span>0.6</span></>}</div>
  </div>;
}
