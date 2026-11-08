import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Seg } from "../components/ui";
import { Forest, PlaceboStrip } from "../components/charts";
import { fmt, pct, Results, useResults } from "../lib/data";
import { CountUp } from "../lib/fx";
import { meta, sortModels } from "../lib/models";

const COMBOS: [string, string, string][] = [["mississippi", "A", "ida"], ["mississippi", "B", "ida"], ["everglades", "B", "irma"], ["everglades", "A", "irma"]];
const NAME = (s: string, t: string) => `${s === "mississippi" ? "Ida · Louisiana" : "Irma · Everglades"} · ${t === "A" ? "10 m" : "30 m"}`;
const SECTIONS: [string, string][] = [["time", "Placebo in time"], ["space", "Placebo in space"], ["track", "Storm-track evidence"], ["spread", "Model spread"], ["calib", "Calibration"], ["carbon", "Carbon (illustrative)"]];
const mean = (x: number[]) => (x.length ? x.reduce((a, b) => a + b, 0) / x.length : NaN);

export default function Evidence() {
  const { data: r } = useResults();
  const [active, setActive] = useState("time");
  useEffect(() => {
    const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && setActive(e.target.id)), { rootMargin: "-40% 0px -55% 0px" });
    SECTIONS.forEach(([id]) => { const el = document.getElementById(id); if (el) io.observe(el); });
    return () => io.disconnect();
  }, [r]);
  if (!r) return <div className="page wrap"><div className="skeleton" style={{ height: 500 }} /></div>;
  const tot = (s: string) => r.verdict.filter((v) => v.stat === s);
  const cov = r.verdict.map((v) => v.coverage);
  return (
    <div className="page wrap ev">
      <header className="ev-head">
        <div className="eyebrow">Evidence</div>
        <h1>We tried to break our own result.</h1>
        <p className="md-lead">A deficit only counts if it survives three independent attacks: fake hurricanes in calm years, inland areas the storm barely
          touched, and NOAA's record of where the storm actually went. Every rule below was fixed in the pre-registration before any model ran.</p>
        <div className="md-kpis">
          <div><b><CountUp to={tot("lead0").filter((v) => v.pass).length} /><span className="of">/{tot("lead0").length}</span></b><span>tests pass just after landfall</span></div>
          <div><b><CountUp to={tot("primary").filter((v) => v.pass).length} /><span className="of">/{tot("primary").length}</span></b><span>pass over quarters 1–3</span></div>
          <div><b>{fmt(Math.min(...cov), 2)}–{fmt(Math.max(...cov), 2)}</b><span>coverage of the 90 % intervals</span></div>
          <div><b>Ida</b><span>credible just after landfall</span></div>
          <div><b className="sig">Irma</b><span>fails space and track checks</span></div>
        </div>
      </header>

      <div className="ev-body">
        <nav className="ev-toc">{SECTIONS.map(([id, l], i) => <a key={id} href={`#/evidence`} className={active === id ? "on" : ""}
          onClick={(e) => { e.preventDefault(); document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" }); }}><span className="mono">{String(i + 1).padStart(2, "0")}</span>{l}</a>)}</nav>
        <div className="ev-main">
          <TimeSection r={r} />
          <SpaceSection r={r} />
          <TrackSection r={r} />
          <SpreadSection r={r} />
          <CalibSection r={r} />
          <CarbonSection r={r} />
        </div>
      </div>
    </div>
  );
}

const Sec = ({ id, n, title, lead, children }: { id: string; n: number; title: string; lead: React.ReactNode; children: React.ReactNode }) => (
  <section id={id} className="ev-sec"><div className="ev-sec-h"><span className="sh-k">§ {n}</span><h2>{title}</h2><p className="muted">{lead}</p></div>{children}</section>
);

function TimeSection({ r }: { r: Results }) {
  const [stat, setStat] = useState<"lead0" | "primary">("lead0");
  const models = sortModels([...new Set(r.verdict.map((v) => v.model))]);
  const combos = COMBOS.filter(([s, t]) => r.verdict.some((v) => v.site === s && v.track === t));
  return <Sec id="time" n={1} title="Placebo in time: fake hurricanes" lead={<>Each model is re-run with landfall moved to calm years with no storm within 200 km (checked against HURDAT2).
    It passes only if its real-storm deficit beats the 95th percentile of its own placebo deficits.</>}>
    <Seg value={stat} onChange={setStat} options={[["lead0", "Just after landfall"], ["primary", "Quarters 1–3 (pre-registered primary)"]]} />
    <div className="figs" style={{ marginTop: 16 }}>
      <figure className="fig wide"><figcaption><span className="sh-k">Fig. 1</span><h3>Verdict matrix</h3><p>Cell = verdict and the share of folds whose event deficit exceeds the placebo 95th percentile.</p></figcaption>
        <div style={{ overflowX: "auto" }}><table className="t vm">
          <thead><tr><th>Model</th>{combos.map(([s, t]) => <th key={s + t} className="c">{NAME(s, t)}</th>)}</tr></thead>
          <tbody>{models.map((m) => <tr key={m}><td><span className="dot" style={{ background: meta(m).color }} />{meta(m).name}</td>
            {combos.map(([s, t]) => { const v = r.verdict.find((x) => x.model === m && x.site === s && x.track === t && x.stat === stat);
              return <td key={s + t} className="c">{v ? <span className={`vcell ${v.pass ? "p" : "f"}`}><b>{v.pass ? "PASS" : "FAIL"}</b><i className="mono">{pct(v.frac_above)}</i></span> : <span className="dim">—</span>}</td>; })}</tr>)}</tbody></table></div>
      </figure>
      {combos.slice(0, 3).map(([s, t], i) => {
        const rows = r.verdict.filter((v) => v.site === s && v.track === t && v.stat === stat);
        return <figure className="fig" key={s + t}><figcaption><span className="sh-k">Fig. {2 + i}</span><h3>{NAME(s, t)}</h3>
          <p>Shaded: range of placebo deficits; tick: their 95th percentile; dot: event median (outline = verdict).</p></figcaption>
          <PlaceboStrip width={520} rows={rows.map((v) => ({ label: meta(v.model).short, pmin: v.placebo_min, pmax: v.placebo_max, p95: v.placebo_p95, ev: v.event_median, evmin: v.event_min, pass: v.pass }))} />
        </figure>;
      })}
      <figure className="fig"><figcaption><span className="sh-k">Reading it</span><h3>What passes, and why</h3></figcaption>
        <p className="muted" style={{ fontSize: 13.5, lineHeight: 1.65, margin: 0 }}>{stat === "lead0"
          ? "Just after landfall, Ida's deficit clears every calm-year placebo for every model on both resolutions. That is the robust finding."
          : "Over quarters 1–3, most passes come with an event deficit near zero: they pass because calm-year placebos are biased negative, and with only 1–3 placebo years the 95th percentile is essentially the placebo maximum. Read them with caution."}</p>
      </figure>
    </div>
  </Sec>;
}

function SpaceSection({ r }: { r: Results }) {
  const combos = COMBOS.filter(([s, t, e]) => r.space.some((x) => x.site === s && x.track === t && x.event === e));
  return <Sec id="space" n={2} title="Placebo in space: the inland control" lead={<>Real storm damage should fade away from the coast. Each line joins a model's deficit over all blocks (left) to its deficit
    in the 20 % of blocks farthest inland (right). Falling lines are what a storm looks like.</>}>
    <div className="figs">{combos.map(([s, t, e], i) => {
      const rows = r.space.filter((x) => x.site === s && x.track === t && x.event === e && x.map === "lead 0");
      const vals = rows.flatMap((x) => [x.all, x.inland]), lo = Math.min(0, ...vals), hi = Math.max(...vals);
      const Y = (v: number) => 14 + (1 - (v - lo) / (hi - lo || 1)) * 200;
      const falling = rows.filter((x) => x.inland < x.all / 2).length;
      return <figure className="fig" key={s + t}><figcaption><span className="sh-k">Fig. {5 + i}</span><h3>{NAME(s, t)}</h3>
        <p>{falling}/{rows.length} models: inland below half of the all-block deficit.</p></figcaption>
        <svg viewBox="0 0 420 240" className="slope">
          <line x1={110} x2={110} y1={10} y2={218} stroke="var(--line)" /><line x1={310} x2={310} y1={10} y2={218} stroke="var(--line)" />
          {lo < 0 && <line x1={110} x2={310} y1={Y(0)} y2={Y(0)} stroke="var(--dim)" strokeDasharray="3 4" />}
          {rows.map((x) => { const down = x.inland < x.all / 2; return <g key={x.model} opacity={0.95}>
            <line x1={110} x2={310} y1={Y(x.all)} y2={Y(x.inland)} stroke={down ? "var(--mark)" : "var(--signal)"} strokeWidth={1.5} />
            <circle cx={110} cy={Y(x.all)} r={3} fill="var(--mark)" /><circle cx={310} cy={Y(x.inland)} r={3} fill={down ? "var(--mark)" : "var(--signal)"} /></g>; })}
          {(() => {                                                 // right-hand labels, pushed apart so they never overlap
            const ls = rows.map((x) => ({ m: x.model, y: Y(x.inland), down: x.inland < x.all / 2 })).sort((a, b) => a.y - b.y);
            for (let k = 1; k < ls.length; k++) ls[k].y = Math.max(ls[k].y, ls[k - 1].y + 11);
            const over = ls.length ? ls[ls.length - 1].y - 222 : 0;
            if (over > 0) ls.forEach((l) => (l.y -= over));
            return ls.map((l) => <text key={l.m} x={322} y={l.y + 3.5} style={{ fontSize: 9.5, fill: l.down ? "var(--muted)" : "var(--signal)" }}>{meta(l.m).short}</text>);
          })()}
          <text x={110} y={236} textAnchor="middle">all blocks</text><text x={310} y={236} textAnchor="middle">inland blocks</text>
          <text x={102} y={Y(hi) + 4} textAnchor="end">{fmt(hi, 2, true)}</text><text x={102} y={Y(lo) + 4} textAnchor="end">{fmt(lo, 2, true)}</text>
        </svg>
      </figure>;
    })}</div>
  </Sec>;
}

function TrackSection({ r }: { r: Results }) {
  const cols: [string, string, string, number][] = [];
  for (const [s, t, e] of COMBOS) for (const [cv, l, want] of [["track_km", "track", -1], ["coast_m", "coast", -1], ["wind_kt", "wind", 1]] as const)
    if (r.external.some((x) => x.site === s && x.track === t && x.event === e && x.covariate === cv)) cols.push([`${s}|${t}|${e}`, cv, l, want]);
  const models = sortModels([...new Set(r.external.map((x) => x.model))]);
  const groups = [...new Set(cols.map((c) => c[0]))];
  const cell = (g: string, cv: string, m: string) => { const [s, t, e] = g.split("|"); return r.external.find((x) => x.site === s && x.track === t && x.event === e && x.covariate === cv && x.model === m && x.map === "lead 0"); };
  return <Sec id="track" n={3} title="Independent evidence: NOAA HURDAT2" lead={<>Spearman ρ across spatial blocks between the attributed deficit and three independent measures of exposure: distance to the storm's best track
    and to the coast (damage should fall with distance, ρ &lt; 0), and peak wind (ρ &gt; 0). Bracketed: 90 % block-bootstrap interval.</>}>
    <figure className="fig wide" style={{ border: "1px solid var(--line)" }}><figcaption><span className="sh-k">Fig. 9</span><h3>Correlation matrix, just after landfall</h3>
      <p>Filled cell: expected sign with an interval excluding zero. Red outline: the opposite sign. Shade ∝ |ρ|.</p></figcaption>
      <div style={{ overflowX: "auto" }}><table className="t hm">
        <thead><tr><th rowSpan={2}>Model</th>{groups.map((g) => { const [s, t] = g.split("|"); return <th key={g} colSpan={cols.filter((c) => c[0] === g).length} className="c grp">{NAME(s, t)}</th>; })}</tr>
          <tr>{cols.map(([g, , l, want]) => <th key={g + l} className="c">{l} {want < 0 ? "(−)" : "(+)"}</th>)}</tr></thead>
        <tbody>{models.map((m) => <tr key={m}><td><span className="dot" style={{ background: meta(m).color }} />{meta(m).short}</td>
          {cols.map(([g, cv, , want]) => { const x = cell(g, cv, m); if (!x) return <td key={g + cv} className="c dim">·</td>;
            const good = Math.sign(x.rho) === want && Math.sign(x.lo) === Math.sign(x.hi), bad = Math.sign(x.rho) === -want && Math.sign(x.lo) === Math.sign(x.hi);
            return <td key={g + cv} className={`c hmc ${good ? "good" : bad ? "bad" : ""}`} style={{ ["--a" as string]: Math.abs(x.rho) }} title={`ρ ${fmt(x.rho, 2, true)} [${fmt(x.lo, 2, true)}, ${fmt(x.hi, 2, true)}] · ${x.blocks} blocks`}>
              <span className="mono">{fmt(x.rho, 2, true)}</span></td>; })}</tr>)}</tbody></table></div>
    </figure>
  </Sec>;
}

function SpreadSection({ r }: { r: Results }) {
  return <Sec id="spread" n={4} title="Model spread: how much does the answer depend on the model?" lead={<>Each panel ranks every model's attributed deficit. Faded rows fail the placebo test. Dropping them collapses the disagreement:
    this is the cautionary half of the study.</>}>
    <div className="figs">{[["ida", "mississippi", "A"], ["ida", "mississippi", "B"], ["irma", "everglades", "B"]].flatMap(([e, s, t]) => ["lead 0", "leads 1-3"].map((st, j) => {
      const rows = r.attribution.filter((a) => a.event === e && a.site === s && a.track === t && a.stat === st).sort((a, b) => a.deficit - b.deficit);
      if (!rows.length) return null;
      const all = rows.map((a) => a.deficit), pass = rows.filter((a) => a.placebo === "pass").map((a) => a.deficit);
      const span = (x: number[]) => (x.length ? Math.max(...x) - Math.min(...x) : null);
      return <figure className="fig" key={e + t + st}><figcaption><span className="sh-k">{NAME(s, t)}</span><h3>{st === "lead 0" ? "Just after landfall" : "Quarters 1–3"}</h3>
        <p>Spread: all models <b className="mono">{fmt(span(all), 3)}</b> → placebo-passing <b className="mono">{fmt(span(pass), 3)}</b> NDVI.</p></figcaption>
        <Forest width={520} rows={rows.map((a) => ({ label: meta(a.model).short, v: a.deficit, color: a.placebo === "fail" ? "var(--mark3)" : "var(--mark)", faded: a.placebo === "fail" }))} />
      </figure>;
    })).filter(Boolean)}</div>
  </Sec>;
}

function CalibSection({ r }: { r: Results }) {
  const rows = sortModels([...new Set(r.verdict.map((v) => v.model))]).map((m) => ({ m, c: r.verdict.filter((v) => v.model === m).map((v) => v.coverage) }));
  const X = (v: number) => ((v - 0.8) / 0.15) * 100;
  return <Sec id="calib" n={5} title="Calibration: are the 90 % intervals honest?" lead={<>Split-conformal intervals calibrated on placebo windows of the calibration fold only. Each mark is the achieved coverage of one
    model × site × window; the line is the nominal 90 %.</>}>
    <figure className="fig" style={{ border: "1px solid var(--line)" }}>
      <div className="calib">{rows.map(({ m, c }) => <div key={m} className="calib-row"><span className="cmp-l">{meta(m).short}</span>
        <span className="calib-track"><span className="calib-nom" style={{ left: `${X(0.9)}%` }} />{c.map((v, i) => <span key={i} className="calib-dot" style={{ left: `${X(v)}%` }} title={v.toFixed(3)} />)}</span>
        <span className="mono cmp-v">{mean(c).toFixed(3)}</span></div>)}
        <div className="seed-axis"><span>0.80</span><span>achieved coverage · nominal 0.90</span><span>0.95</span></div></div>
    </figure>
  </Sec>;
}

function CarbonSection({ r }: { r: Results }) {
  return <Sec id="carbon" n={6} title="Carbon: an illustration, not a result" lead={<>Relative NDVI loss × wetland area is computed from the runs. The tonnes-of-carbon column multiplies by literature carbon densities that are
    still placeholders ({r.carbon.verified ? "verified" : "unverified"}, configs/carbon.yaml). Irma rows are shown for completeness but are not credible.</>}>
    <div className="card pad0"><table className="t">
      <thead><tr><th>Site · resolution</th><th>Event</th><th>Model</th><th className="n">Deficit</th><th className="n">Relative loss</th><th className="n">Area (ha)</th><th className="n">t C (low – high)</th></tr></thead>
      <tbody>{r.carbon.rows.map((c, i) => <tr key={i} style={{ opacity: c.event === "irma" ? 0.45 : 1 }}><td>{c.site === "mississippi" ? "Louisiana" : "Everglades"} · {c.track === "A" ? "10 m" : "30 m"}</td>
        <td>{c.event === "ida" ? "Ida" : "Irma"}</td><td>{meta(c.model).short}</td>
        <td className="n mono">{fmt(c.deficit, 3, true)}</td><td className="n mono">{pct(c.relative_loss, 1)}</td><td className="n mono">{c.area_ha?.toLocaleString()}</td>
        <td className="n mono" style={{ color: r.carbon.verified ? "var(--text)" : "var(--dim)" }}>{c.tC_low?.toLocaleString()} – {c.tC_high?.toLocaleString()}</td></tr>)}</tbody></table></div>
    <p className="dim" style={{ fontSize: 12.5, marginTop: 14 }}>Explore the maps behind every number in the <Link to="/explore">studio</Link>.</p>
  </Sec>;
}
