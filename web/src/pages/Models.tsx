import { ReactNode, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Empty, Icon, Seg, Verdict } from "../components/ui";
import { Bars, Scatter, TimeChart, ValueBars, legendItem } from "../components/charts";
import { colorOf, fmt, modelName, Registry, Results, TRACKS, useJSON, useMaps, useResults } from "../lib/data";
import { attrOf, cutoffLabel, isPlacebo, leadKey, skillOf, verdictOf } from "../lib/derive";
import { imageKeys, layerURL, sampleDeficits, skillAny, usePixels } from "../lib/explore";
import { FAM_LABEL, FAM_ORDER, famOf, meta, MODEL_META } from "../lib/models";

export const ABOUT: Record<string, { idea: string; how: string; arch?: string[] }> = {
  persistence: { idea: "The last observed value carries forward.", how: "Forecast = most recent valid pre-cutoff value per pixel. The floor every model must beat." },
  climatology: { idea: "Each pixel's seasonal average.", how: "Mean of all pre-cutoff observations of the same calendar quarter. Strong because wetlands are highly seasonal." },
  harmonic: { idea: "CCDC-style harmonic regression with a trend.", how: "Huber-robust fit of mean + linear trend + annual and semi-annual cosines; the trend extrapolates poorly from short records." },
  harmonic_notrend: { idea: "Harmonic regression without the trend (amendment A1).", how: "Same robust harmonic fit, trend term dropped. Added before Phase 3 because the trended version under-performed climatology." },
  synth_control: { idea: "Difference-in-differences against unaffected neighbours.", how: "Each pixel's pre-storm offset from matched, least-exposed donor blocks of the same land cover, applied to the donors' observed post-cutoff values. Sees post-storm neighbour data, which is why it is hard to beat." },
  lgbm: { idea: "Gradient-boosted trees on lags.", how: "LightGBM quantile regression (q10/q50/q90) on 4 lags of every channel, season, horizon, static context and 3×3/7×7 neighbourhood means." },
  convlstm: { idea: "Convolutional LSTM over the 8-quarter input.", how: "2-layer ConvLSTM (hidden 32) → conv head emitting all horizons × channels × 3 quantiles. v1 continuity baseline.",
    arch: ["8 quarters × 22 ch", "ConvLSTM ×2", "conv head", "D × 5 × 3 quantiles"] },
  simvp: { idea: "SimVP: simple, strong spatiotemporal predictor.", how: "Per-frame conv encoder (↓4), gated spatiotemporal translator (gSTA ×4) over stacked time, conv decoder with a skip, quantile heads per horizon.",
    arch: ["8 quarters", "conv encoder ↓4", "gSTA translator ×4", "decoder ↑4 + skip", "q10 / q50 / q90"] },
  ecotransformer: { idea: "EcoTransformer v2: SAR-gated factorised attention.", how: "Optical and radar patch embeddings fused by a learned SAR gate, static context added, factorised time/space attention ×4, learned horizon queries with quarter-of-year embedding, quantile heads.",
    arch: ["optical + SAR patches", "SAR gate", "time ⟂ space attention ×4", "horizon queries", "quantile heads"] },
};

function Status({ m }: { m: Registry }) {
  if (m.family === "experimental") return <span className="badge exp">{m.status === "done" ? "experimental · post hoc" : "experimental · planned"}</span>;
  return m.status === "done" ? <span className="badge pass">done</span> : m.status === "running" ? <span className="badge exp">running</span> : <span className="badge plan">planned</span>;
}

type Cell = { v: number; src: "leaderboard" | "phase5" } | null;
const SITES3: [string, string, string][] = [["mississippi", "A", "Louisiana · 10 m"], ["mississippi", "B", "Louisiana · 30 m"], ["everglades", "B", "Everglades · 30 m"]];

function SkillCell({ c }: { c: Cell }) {
  if (!c) return <td className="n dim">—</td>;
  const w = Math.max(0, Math.min(1, c.v / 0.85));
  return <td className="n skill">
    <span className="skill-bar"><span style={{ width: `${w * 100}%`, background: c.v < 0 ? "var(--fail)" : c.src === "phase5" ? "rgba(var(--accent-rgb),.45)" : "var(--cf)" }} /></span>
    <span className={c.src === "phase5" ? "p5" : ""}>{c.v.toFixed(3)}{c.src === "phase5" ? "†" : ""}</span>
  </td>;
}

export default function Models() {
  const { data: r } = useResults();
  const [sort, setSort] = useState<number>(0);
  const [group, setGroup] = useState(true);
  if (!r) return <div className="page wrap"><div className="skeleton" style={{ height: 500 }} /></div>;
  const done = r.registry.filter((m) => m.status === "done").map((m) => m.id);
  const ids = Array.from(new Set([...done, ...r.leaderboard.map((l) => l.model)])).filter((id) => MODEL_META[id]);
  const rows = ids.map((id) => {
    const cells = SITES3.map(([s, t]) => skillAny(r, id, s, t));
    const tests = r.verdict.filter((v) => v.model === id);
    const p5 = r.phase5.filter((x) => String(x.model).replace(/_s\d+$/, "") === id);
    const mins = p5.length ? p5.reduce((a, b) => a + (+b.minutes || 0), 0) : null;
    const val = p5.filter((x) => x.site === "everglades").map((x) => +x.val_r2);
    return { id, cells, tests, mins, val: val.length ? val.reduce((a, b) => a + b, 0) / val.length : null };
  });
  const key = (x: typeof rows[0]) => (sort < 3 ? x.cells[sort]?.v : sort === 3 ? (x.tests.length ? x.tests.filter((t) => t.pass).length / x.tests.length : null) : x.val) ?? -9;
  const sorted = [...rows].sort((a, b) => key(b) - key(a));
  const fams = group ? FAM_ORDER : (["all"] as const);
  // scatter: the pre-registered models (they have placebo verdicts)
  const sc = rows.filter((x) => x.tests.length && x.cells[0] && x.cells[2]).map((x) => ({
    id: x.id, label: meta(x.id).short, x: Math.max(0, (x.cells[0]!.v + x.cells[2]!.v) / 2), y: x.tests.filter((t) => t.pass).length / x.tests.length,
    color: meta(x.id).color, r: famOf(x.id) === "baseline" ? 7 : 9, ring: famOf(x.id) === "experimental" }));
  // ablations: validation R² vs parent (Everglades 30 m, the ablation site)
  const valOf = (id: string) => rows.find((x) => x.id === id)?.val ?? null;
  const abl = rows.filter((x) => meta(x.id).parent && x.val != null && valOf(meta(x.id).parent!) != null)
    .map((x) => ({ id: x.id, d: x.val! - valOf(meta(x.id).parent!)! })).sort((a, b) => b.d - a.d);
  const th = (i: number, label: string) => <th className={`sort n ${sort === i ? "on" : ""}`} onClick={() => setSort(i)}>{label}{sort === i ? " ↓" : ""}</th>;
  return (
    <div className="page wrap">
      <div className="page-head">
        <div><div className="eyebrow">Model zoo</div><h1 style={{ marginTop: 10 }}>{ids.length} trained models, one benchmark</h1>
          <p>Every model forecasts the same pixels on held-out spatial blocks. Skill is NDVI R² on undisturbed placebo windows; the placebo
            column shows each pre-registered test (does the model invent damage in a calm year?).</p></div>
        <div style={{ display: "flex", gap: 8 }}>
          <Seg value={group ? "g" : "r"} options={[["g", "By family"], ["r", "Ranked"]]} onChange={(v) => setGroup(v === "g")} />
          <Link className="btn" to="/explore?mode=gallery&site=everglades&track=B">See their maps <Icon name="arrow" size={14} /></Link>
        </div>
      </div>

      <div className="card pad0 zoo">
        <table className="t zoo-t">
          <thead><tr><th>Model</th>{SITES3.map(([, , l], i) => <th key={l} className="sort n" onClick={() => setSort(i)}>{l}{sort === i ? " ↓" : ""}</th>)}
            {th(3, "Placebo tests")}{th(4, "Val. R² (EG)")}<th className="n">GPU time</th></tr></thead>
          <tbody>{fams.map((f) => {
            const rs = sorted.filter((x) => f === "all" || famOf(x.id) === f);
            if (!rs.length) return null;
            return [group && <tr key={f} className="fam-row"><td colSpan={7}>{FAM_LABEL[f as keyof typeof FAM_LABEL]}<span className="dim"> · {rs.length}</span></td></tr>,
              ...rs.map((x) => <tr key={x.id}>
                <td><Link to={`/models/${x.id}`} className="zoo-name"><span className="dot" style={{ background: meta(x.id).color }} />
                  <span><b>{meta(x.id).name}</b><span className="zoo-sub">{meta(x.id).blurb}</span></span></Link></td>
                {x.cells.map((c, i) => <SkillCell key={i} c={c} />)}
                <td className="n"><span className="tests">{x.tests.length ? x.tests.map((t, i) => <span key={i} className={`tdot ${t.pass ? "pass" : "fail"}`}
                  title={`${t.site} ${t.track} · ${t.stat === "lead0" ? "landfall" : "quarters 1–3"} · ${t.pass ? "pass" : "fail"}`} />) : <span className="dim" title="variants are not part of the pre-registered placebo test">n/a</span>}</span></td>
                <td className="n mono">{x.val == null ? <span className="dim">—</span> : x.val.toFixed(3)}</td>
                <td className="n mono dim">{x.mins == null ? "CPU" : `${(x.mins / 60).toFixed(1)} h`}</td>
              </tr>)];
          })}</tbody>
        </table>
        <p className="dim zoo-foot">† Phase 5 test R² (variants are not on the pre-registered leaderboard). Synthetic control uses neighbours' post-storm observations;
          every other model forecasts from pre-storm history only. GPU time summed over seeds and folds on a T4.</p>
      </div>

      <div className="grid g2" style={{ marginTop: 18, alignItems: "start" }}>
        <div className="card">
          <h3>Skill vs honesty</h3>
          <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>Right = forecasts better. Up = passes more placebo tests. The deep models (large dots) sit among the baselines, not above them.</p>
          <Scatter xLabel="NDVI R² · mean of Louisiana 10 m and Everglades 30 m" yLabel="placebo tests passed" xr={[0, 0.8]} yr={[0, 1.05]} pts={sc}
            yfmt={(v) => (v > 1 ? "" : `${Math.round(v * 100)}%`)} />
        </div>
        <div className="card">
          <h3>What each component is worth</h3>
          <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>Validation R² of each variant minus its parent (Everglades 30 m). Right of zero helps; left hurts.</p>
          <ValueBars rows={abl.map((a) => ({ id: a.id, label: meta(a.id).short, v: a.d, color: a.d >= 0 ? "var(--pass)" : "var(--fail)" }))} />
          <p className="dim" style={{ fontSize: 12, marginTop: 10 }}>Pre-registered: no ablation could change the published models. Transfer = trained on the other site, never seeing this one.</p>
        </div>
      </div>

      {FAM_ORDER.map((f) => {
        const ms = r.registry.filter((m) => MODEL_META[m.id] && famOf(m.id) === f);
        if (!ms.length) return null;
        return <section key={f} style={{ marginTop: 44 }}>
          <h2 style={{ fontSize: 28 }}>{FAM_LABEL[f]}</h2>
          {f === "experimental" && <p className="note" style={{ maxWidth: 820 }}>Developed after seeing the Phase 3/4 results (amendment A5). Shown separately and never part of the headline verdict.</p>}
          {f === "ablation" && <p className="muted" style={{ maxWidth: 820 }}>Judged on validation NDVI R² only, as pre-registered.</p>}
          <div className="grid g3" style={{ marginTop: 14 }}>{ms.map((m) => <ModelCard key={m.id} m={m} r={r} />)}</div>
        </section>;
      })}
      {r.registry.some((m) => m.status !== "done") && <section style={{ marginTop: 44 }}>
        <h2 style={{ fontSize: 28 }}>Reserved slots</h2>
        <div className="grid g3" style={{ marginTop: 14 }}>{r.registry.filter((m) => m.status !== "done").map((m) => <ModelCard key={m.id} m={m} r={r} />)}</div>
      </section>}
    </div>
  );
}

function ModelCard({ m, r }: { m: Registry; r: Results }) {
  const base = m.id.replace(/__.*$/, "").replace(/_(off|concat)$/, "");
  const sk = skillOf(r, m.id, "mississippi", "A") ?? skillOf(r, m.id, "everglades", "B");
  const p5 = r.phase5.filter((x) => (x.model ?? "").replace(/_s\d+$/, "") === m.id || x.label?.startsWith(m.name));
  const planned = m.status !== "done";
  return (
    <Link to={`/models/${m.id}`} className="card" style={{ color: "var(--text)", borderStyle: planned ? "dashed" : "solid", opacity: planned ? 0.75 : 1 }}>
      <div className="card-head"><span><span className="dot" style={{ background: meta(m.id).color }} /><b>{m.name}</b></span><Status m={m} /></div>
      <div className="muted" style={{ fontSize: 13, minHeight: 40 }}>{ABOUT[m.id]?.idea ?? (MODEL_META[m.id] ? `${MODEL_META[m.id].blurb}${m.parent ? ` · variant of ${modelName(m.parent)}` : ""}.` : "Reserved slot.")}</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
        {m.params && <span className="chip">{(m.params / 1e6).toFixed(2)} M params</span>}
        {m.uses_post_cutoff_info && <span className="chip" style={{ color: "var(--warn)" }}>sees post-storm neighbours</span>}
        {!m.preregistered && <span className="chip" style={{ color: "var(--warn)" }}>post hoc</span>}
        {sk && <span className="chip mono">R² {sk.NDVI.toFixed(3)}</span>}
        {p5.length > 0 && p5[0].val_r2 != null && <span className="chip mono">val R² {(+p5[0].val_r2).toFixed(3)}</span>}
        {m.lab_exportable && <span className="chip" style={{ color: "var(--cf)" }}>in the live lab</span>}
      </div>
    </Link>
  );
}

const SITE4: [string, string, string][] = [["mississippi", "A", "Louisiana · 10 m"], ["mississippi", "B", "Louisiana · 30 m"], ["everglades", "B", "Everglades · 30 m"], ["everglades", "A", "Everglades · 10 m"]];
const comparatorOf = (id: string) => meta(id).parent ?? (famOf(id) === "deep" ? "synth_control" : id === "climatology" ? "harmonic_notrend" : "climatology");
type Curve = { site: string; track: string; model: string; cutoff: string; fold: number; val_r2: (number | null)[]; best: number };

const Fig = ({ n, title, cap, children, wide }: { n: number; title: string; cap?: ReactNode; children: ReactNode; wide?: boolean }) => (
  <figure className={`fig ${wide ? "wide" : ""}`}><figcaption><span className="sh-k">Fig. {n}</span><h3>{title}</h3>{cap && <p>{cap}</p>}</figcaption>{children}</figure>
);

function SkillCompare({ r, id, other }: { r: Results; id: string; other: string }) {
  const rows = SITE4.map(([s, t, l]) => ({ l, a: skillAny(r, id, s, t), b: skillAny(r, other, s, t) })).filter((x) => x.a || x.b);
  const lo = Math.min(-0.1, ...rows.flatMap((x) => [x.a?.v ?? 0, x.b?.v ?? 0])), hi = Math.max(0.9, ...rows.flatMap((x) => [x.a?.v ?? 0, x.b?.v ?? 0]));
  const X = (v: number) => ((v - lo) / (hi - lo)) * 100;
  return <div className="cmp">{rows.map((x) => <div key={x.l} className="cmp-row"><span className="cmp-l">{x.l}</span>
    <span className="cmp-track"><span className="cmp-zero" style={{ left: `${X(0)}%` }} />
      {x.b && <span className="cmp-bar b" style={{ left: `${Math.min(X(0), X(x.b.v))}%`, width: `${Math.abs(X(x.b.v) - X(0))}%` }} />}
      {x.a && <span className="cmp-bar a" style={{ left: `${Math.min(X(0), X(x.a.v))}%`, width: `${Math.abs(X(x.a.v) - X(0))}%`, background: meta(id).color }} />}</span>
    <span className="mono cmp-v">{x.a ? x.a.v.toFixed(3) : "—"}<span className="dim"> / {x.b ? x.b.v.toFixed(3) : "—"}</span></span></div>)}
    <div className="cmp-key"><span><i style={{ background: meta(id).color }} />{meta(id).short}</span><span><i className="b" />{meta(other).short}</span>
      <span className="dim">NDVI R², held-out blocks{rows.some((x) => x.a?.src === "phase5" || x.b?.src === "phase5") ? " · variants: Phase 5 test R²" : ""}</span></div></div>;
}

function SeedPlot({ r, id, other }: { r: Results; id: string; other: string }) {
  const rows = (mid: string) => r.phase5.filter((x) => String(x.model).replace(/_s\d+$/, "") === mid);
  const A = rows(id), B = rows(other);
  const sites = [...new Set([...A, ...B].map((x) => `${x.site}|${x.track}`))];
  if (!A.length) return <p className="dim">No GPU runs for this model.</p>;
  const all = [...A, ...B].map((x) => +x.val_r2), lo = Math.min(...all) - 0.03, hi = Math.max(...all) + 0.03, X = (v: number) => ((v - lo) / (hi - lo)) * 100;
  return <div className="seeds">{sites.map((k) => { const [s, t] = k.split("|"), a = A.filter((x) => x.site === s && x.track === t), b = B.filter((x) => x.site === s && x.track === t);
    return <div key={k} className="seed-row"><span className="cmp-l">{s === "mississippi" ? "Louisiana" : "Everglades"} · {t === "A" ? "10 m" : "30 m"}</span>
      <span className="seed-track">{b.map((x, i) => <span key={"b" + i} className="seed b" style={{ left: `${X(+x.val_r2)}%` }} title={`${meta(other).short} seed ${x.seed}: ${(+x.val_r2).toFixed(3)}`} />)}
        {a.map((x, i) => <span key={"a" + i} className="seed a" style={{ left: `${X(+x.val_r2)}%`, background: meta(id).color }} title={`${meta(id).short} seed ${x.seed}: ${(+x.val_r2).toFixed(3)}`} />)}</span>
      <span className="mono cmp-v">{a.length ? (a.reduce((q, x) => q + +x.val_r2, 0) / a.length).toFixed(3) : "—"}<span className="dim"> / {b.length ? (b.reduce((q, x) => q + +x.val_r2, 0) / b.length).toFixed(3) : "—"}</span></span></div>; })}
    <div className="seed-axis"><span>{lo.toFixed(2)}</span><span>validation NDVI R² · one mark per seed</span><span>{hi.toFixed(2)}</span></div></div>;
}

function CurveCompare({ curves, id, other }: { curves: Curve[]; id: string; other: string }) {
  const sites = [...new Set(curves.filter((c) => c.model.replace(/_s\d+$/, "") === id).map((c) => `${c.site}|${c.track}`))];
  const [k, setK] = useState(sites[0] ?? "");
  const [s, t] = (k || sites[0] || "|").split("|");
  const mine = curves.filter((c) => c.model.replace(/_s\d+$/, "") === id && c.site === s && c.track === t);
  const theirs = curves.filter((c) => c.model.replace(/_s\d+$/, "") === other && c.site === s && c.track === t);
  if (!mine.length) return <p className="dim">No training curves for this model.</p>;
  const n = Math.max(...[...mine, ...theirs].map((c) => c.val_r2.length));
  const med = (cs: Curve[]) => Array.from({ length: n }, (_, e) => { const v = cs.map((c) => c.val_r2[e]).filter((x): x is number => x != null).sort((a, b) => a - b); return v.length ? v[v.length >> 1] : null; });
  const clip = (v: number | null) => (v == null ? null : Math.max(-0.2, v));
  return <>
    {sites.length > 1 && <div style={{ marginBottom: 10 }}><Seg value={k || sites[0]} onChange={setK} options={sites.map((x) => [x, x.replace("mississippi|", "Louisiana · ").replace("everglades|", "Everglades · ").replace("· A", "· 10 m").replace("· B", "· 30 m")] as [string, string])} /></div>}
    <TimeChart x={Array.from({ length: n }, (_, i) => String(i + 1))} height={260} ymin={-0.2} ymax={1} width={760} focus={id}
      series={[...theirs.map((c, i) => ({ id: "t" + i, name: meta(other).short, color: "var(--mark3)", values: c.val_r2.map(clip), width: 0.8, opacity: 0.5 })),
        ...mine.map((c, i) => ({ id: "m" + i, name: `${meta(id).short} · ${c.cutoff} k${c.fold}`, color: meta(id).color, values: c.val_r2.map(clip), width: 0.8, opacity: 0.45 })),
        ...(theirs.length ? [{ id: "tm", name: `${meta(other).short} median`, color: "var(--mark2)", values: med(theirs).map(clip), width: 2.2, dash: true }] : []),
        { id, name: `${meta(id).short} median`, color: meta(id).color, values: med(mine).map(clip), width: 2.6 }]} />
    <div className="cmp-key"><span><i style={{ background: meta(id).color }} />{meta(id).short} · {mine.length} trainings</span>{theirs.length > 0 && <span><i className="b" />{meta(other).short} · {theirs.length}</span>}<span className="dim">epoch → validation NDVI R²; thick = median</span></div>
  </>;
}

function DeficitLeads({ id, other }: { id: string; other: string }) {
  const { data: maps } = useMaps();
  const sts = maps ? Object.keys(maps).filter((st) => maps[st].models.includes(id)) : [];
  const [st, setSt] = useState<string | null>(null);
  const S = st && sts.includes(st) ? st : sts.find((x) => x === "everglades_B") ?? sts[0] ?? null;
  const { data: px, loading } = usePixels(S);
  if (!sts.length) return <p className="dim">No pixel samples for this model.</p>;
  const m = maps![S!], cuts = Object.keys(m.cutoffs).sort((a, b) => +isPlacebo(a) - +isPlacebo(b));
  const series = cuts.flatMap((c) => {
    const d = sampleDeficits(px, c), leads = m.cutoffs[c].leads;
    const row = (mid: string, col: string, w: number) => d[mid] ? [{ id: mid + c, name: `${meta(mid).short} · ${isPlacebo(c) ? "placebo " + c.match(/\d{4}/)?.[0] : "storm"}`, color: col,
      values: leads.map((l) => { const j = d[mid].leads.indexOf(l); return j >= 0 ? d[mid].mean[j] : null; }), width: w, dash: isPlacebo(c), dots: !isPlacebo(c) }] : [];
    return [...row(other, "var(--mark3)", 1.4), ...row(id, isPlacebo(c) ? "var(--placebo)" : meta(id).color, isPlacebo(c) ? 1.4 : 2.6)];
  });
  const L = Math.max(...cuts.map((c) => m.cutoffs[c].leads.length));
  return <>
    {sts.length > 1 && <div style={{ marginBottom: 10 }}><Seg value={S!} onChange={setSt} options={sts.map((x) => [x, x.replace("mississippi_", "Louisiana · ").replace("everglades_", "Everglades · ").replace("· A", "· 10 m").replace("· B", "· 30 m")] as [string, string])} /></div>}
    {loading ? <div className="skeleton" style={{ height: 240 }} /> : <TimeChart x={Array.from({ length: L }, (_, i) => (i === 0 ? "landfall" : `+${i}q`))} height={250} width={760} series={series} focus={id + cuts[0]} />}
    <div className="cmp-key"><span><i style={{ background: meta(id).color }} />{meta(id).short} · storm (solid) · placebo years (dashed)</span><span><i className="b" />{meta(other).short}</span>
      <span className="dim">mean counterfactual − observed NDVI over 3000 sampled pixels; placebo lines should sit at 0</span></div>
  </>;
}

export function ModelDetail() {
  const { id = "" } = useParams();
  const { data: r } = useResults();
  const { data: curves } = useJSON<Curve[]>("training/curves.json");
  const m = r?.registry.find((x) => x.id === id);
  const about = ABOUT[id];
  if (!r) return <div className="page wrap"><div className="skeleton" style={{ height: 500 }} /></div>;
  if (!m && !about && !MODEL_META[id]) return <div className="page wrap"><Empty title="Unknown model">No model called “{id}”. <Link to="/models">Back to the zoo</Link>.</Empty></div>;
  const mm = meta(id), other = comparatorOf(id), isVariant = !!mm.parent;
  const kids = r.registry.filter((x) => x.parent === id);
  const p5 = r.phase5.filter((x) => String(x.model).replace(/_s\d+$/, "") === id);
  const gpuH = p5.reduce((a, x) => a + (+x.minutes || 0), 0) / 60;
  const tests = r.verdict.filter((v) => v.model === id);
  const params = m?.params ?? null;
  const best = SITE4.map(([s, t]) => skillAny(r, id, s, t)).filter(Boolean)[0];
  let fig = 0;
  return (
    <div className="page wrap md">
      <Link to="/models" className="chip">← Model zoo</Link>
      <header className="md-head">
        <div className="eyebrow">{FAM_LABEL[mm.fam]}{mm.parent ? ` · variant of ${meta(mm.parent).name}` : ""}</div>
        <h1><span className="md-dot" style={{ background: mm.color }} />{mm.name}</h1>
        <p className="md-lead">{isVariant ? VARIANT_NOTE[id] ?? mm.blurb : about?.idea ?? mm.blurb}</p>
        <div className="md-kpis">
          <div><b>{best ? best.v.toFixed(3) : "—"}</b><span>{best?.src === "phase5" ? "test NDVI R² (Phase 5)" : "NDVI R², held-out blocks"}</span></div>
          <div><b>{tests.length ? `${tests.filter((t) => t.pass).length}/${tests.length}` : "—"}</b><span>{tests.length ? "placebo tests passed" : "not in the pre-registered test"}</span></div>
          <div><b>{p5.length ? (p5.reduce((a, x) => a + +x.val_r2, 0) / p5.length).toFixed(3) : "—"}</b><span>validation R², mean of {p5.length || 0} runs</span></div>
          <div><b>{gpuH ? `${gpuH.toFixed(1)} h` : "CPU"}</b><span>{gpuH ? "T4 GPU time" : "no GPU needed"}</span></div>
          <div><b>{params ? `${(params / 1e6).toFixed(2)} M` : mm.fam === "baseline" ? "—" : "≈ parent"}</b><span>parameters</span></div>
        </div>
      </header>

      {about && <section className="md-sec"><div className="md-how"><div><span className="sh-k">How it works</span><p>{about.how}</p></div>
        {about.arch && <div className="arch-flow">{about.arch.map((x, i) => <span key={x} className="arch-step"><i>{String(i + 1).padStart(2, "0")}</i>{x}</span>)}</div>}</div></section>}

      <section className="md-sec">
        <div className="md-sec-h"><h2>{isVariant ? `Against its parent, ${meta(other).name}` : `Against ${meta(other).name}`}</h2>
          <p className="muted">{isVariant ? "Every chart overlays the variant on the model it was derived from, same data, same folds." : `Compared with ${famOf(id) === "deep" ? "the strongest baseline" : "a reference baseline"} on the same pixels and folds.`}</p></div>
        <div className="figs">
          <Fig n={++fig} title="Skill by site and resolution" cap="Bars from zero; negative R² means worse than predicting the mean."><SkillCompare r={r} id={id} other={other} /></Fig>
          {p5.length > 0 && <Fig n={++fig} title="Validation R², seed by seed" cap="Each mark is one training run (all folds pooled)."><SeedPlot r={r} id={id} other={other} /></Fig>}
          {curves && famOf(id) !== "baseline" && <Fig n={++fig} title="Training curves" cap="Validation NDVI R² per epoch for every cutoff × fold × seed. Early stopping keeps the best epoch." wide><CurveCompare curves={curves} id={id} other={other} /></Fig>}
          <Fig n={++fig} title="Damage over time, storm vs calm years" cap="A trustworthy model shows a deficit after the storm and flat lines in the placebo years." wide><DeficitLeads id={id} other={other} /></Fig>
        </div>
      </section>

      {tests.length > 0 && <section className="md-sec">
        <div className="md-sec-h"><h2>Attribution and placebo verdicts</h2></div>
        <div className="card pad0"><table className="t md-t">
          <thead><tr><th>Site · resolution</th><th>Event</th><th className="n">Deficit at landfall</th><th className="c">Verdict</th><th className="n">Deficit, quarters 1–3</th><th className="c">Verdict</th></tr></thead>
          <tbody>{SITE4.map(([s, t, l]) => {
            const e = s === "mississippi" ? "ida" : "irma", a0 = attrOf(r, s, t, e, id, "lead 0"), a1 = attrOf(r, s, t, e, id, "leads 1-3");
            if (!a0 && !a1) return null;
            return <tr key={s + t}><td>{l}</td><td>{e === "ida" ? "Ida 2021" : "Irma 2017"}</td>
              <td className="n mono">{fmt(a0?.deficit, 3, true)}</td><td className="c"><Verdict pass={verdictOf(r, s, t, id, "lead0")?.pass} /></td>
              <td className="n mono">{fmt(a1?.deficit, 3, true)}</td><td className="c"><Verdict pass={verdictOf(r, s, t, id, "primary")?.pass} /></td></tr>;
          })}</tbody></table></div>
      </section>}

      {!isVariant && famOf(id) !== "experimental" && SITE4.some(([s, t]) => skillOf(r, id, s, t)) && <section className="md-sec">
        <div className="md-sec-h"><h2>Skill per channel</h2><p className="muted">NDVI, moisture (NDMI) and water (NDWI) indices on undisturbed placebo windows.</p></div>
        <div className="card"><Bars groups={["NDVI", "NDMI", "NDWI"]} max={1} min={0}
          series={SITE4.slice(0, 3).map(([s, t], i) => { const k = skillOf(r, id, s, t); return { name: `${s} ${t}`, color: ["var(--mark)", "var(--mark2)", "var(--mark3)"][i], values: [k?.NDVI ?? null, k?.NDMI ?? null, k?.NDWI ?? null] }; })} />
          <div>{SITE4.slice(0, 3).map(([, , l], i) => legendItem(l, ["var(--mark)", "var(--mark2)", "var(--mark3)"][i]))}</div></div>
      </section>}

      <section className="md-sec"><ModelMaps id={id} other={other} /></section>

      {kids.length > 0 && <section className="md-sec"><div className="md-sec-h"><h2>Variants</h2></div>
        <div className="grid g3">{kids.map((k) => <ModelCard key={k.id} m={k} r={r} />)}</div></section>}
      <p className="dim" style={{ marginTop: 28, fontSize: 12 }}><Icon name="info" size={12} /> Source: runs {m?.run_prefix ?? "—"}, data build {r.generated}.</p>
    </div>
  );
}

const VARIANT_NOTE: Record<string, string> = {
  ecotransformer_off: "Same network with the Sentinel-1 radar branch removed: does radar help see through clouds?",
  ecotransformer_concat: "Radar and optical stacked into one input instead of the learned gate.",
  ecotransformer__smooth: "Adds a penalty on quarter-to-quarter jumps in the forecast.",
  ecotransformer__nostatic: "Terrain and land-cover layers zeroed: how much does geography help?",
  ecotransformer__nomask: "Validity masks zeroed: the network can no longer tell clouds from data.",
  ecotransformer__tin4: "Sees one year of history instead of two.",
  ecotransformer__tin12: "Sees three years of history instead of two.",
  simvp__xfer: "Trained only on the other site, then applied here unchanged.",
  ecotransformer__xfer: "Trained only on the other site, then applied here unchanged.",
  simvp__nbr: "Also sees post-storm observations of unaffected inland neighbours (amendment A5, post hoc).",
};

/** This model's real damage maps: every site/resolution and every cutoff (event + placebo years), just after landfall. */
function ModelMaps({ id, other }: { id: string; other?: string }) {
  const { data: maps } = useMaps();
  if (!maps) return null;
  const sets = Object.entries(maps).flatMap(([st, m]) => Object.keys(m.cutoffs).sort((a, b) => +isPlacebo(a) - +isPlacebo(b) || a.localeCompare(b))
    .filter((c) => m.layers[`${id}/${c}/deficit_L0.png`]).map((c) => ({ st, m, c })));
  if (!sets.length) return null;
  return <div className="card" style={{ marginTop: 18 }}>
    <div className="card-head"><h3>Damage maps · just after landfall{other ? ` · ${meta(id).short} above, ${meta(other).short} below` : ""}</h3><span className="muted" style={{ fontSize: 12.5 }}>Placebo maps should be blank: no storm happened.</span></div>
    <div className="wall" style={{ marginTop: 0 }}>
      {sets.map(({ st, m, c }) => {
        const [site, track] = st.split("_"), under = imageKeys(m).filter((k) => k < leadKey(c, 0)).slice(-1)[0];
        return <Link key={st + c} className="wall-tile" to={`/explore?site=${site}&track=${track}&cut=${c}&mode=compare&kind=deficit&model=${id}&b=${id}`}>
          <div className="wall-img">
            {under && <img src={layerURL(st, `obs_rgb_${under}.png`)} alt="" loading="lazy" style={{ filter: "url(#tc) saturate(.6) brightness(.55)" }} />}
            <img src={layerURL(st, `${id}/${c}/deficit_L0.png`)} alt="" loading="lazy" />
          </div>
          {other && m.layers[`${other}/${c}/deficit_L0.png`] && <div className="wall-img pair">
            {under && <img src={layerURL(st, `obs_rgb_${under}.png`)} alt="" loading="lazy" style={{ filter: "url(#tc) saturate(.6) brightness(.55)" }} />}
            <img src={layerURL(st, `${other}/${c}/deficit_L0.png`)} alt="" loading="lazy" /></div>}
          <div className="wall-cap"><span className="wall-name">{site === "mississippi" ? "Louisiana" : "Everglades"} · {track === "A" ? "10 m" : "30 m"}</span></div>
          <div className="wall-sub" style={{ color: isPlacebo(c) ? "var(--placebo)" : "var(--dmg1)" }}>{cutoffLabel(c)}</div>
        </Link>;
      })}
    </div>
  </div>;
}
