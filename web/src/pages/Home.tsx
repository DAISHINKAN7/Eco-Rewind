import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import HeroRewind, { HeroData } from "../components/HeroRewind";
import { Icon } from "../components/ui";
import { fmt, MapSite, quarterLabel, Results, useMaps, useResults } from "../lib/data";
import { attrOf, cutoffLabel, isPlacebo, verdictOf } from "../lib/derive";
import { cfPath, imageKeys, layerURL, modelsFor, skillAny } from "../lib/explore";
import { meta, sortModels } from "../lib/models";
import { CountUp, Glow, Marquee, Reveal, SectionHead, useInView } from "../lib/fx";
import { ensemble } from "../lib/raster";

const HERO_ST = "mississippi_A", HERO_CUT = "ida";
const DIM = "url(#tc) saturate(.6) brightness(.55)";
const mean = (x: number[]) => (x.length ? x.reduce((a, b) => a + b, 0) / x.length : NaN);

export default function Home() {
  const { data: r } = useResults();
  const { data: maps } = useMaps();
  const m = maps?.[HERO_ST];
  const heroModel = m && modelsFor(m, HERO_CUT).includes("simvp") ? "simvp" : m ? modelsFor(m, HERO_CUT)[0] : null;
  const keys = m ? imageKeys(m) : [];
  const preKey = keys.filter((k) => k < "2021Q3").slice(-1)[0];
  const allModels = useMemo(() => new Set(Object.values(maps ?? {}).flatMap((s) => s.models)), [maps]);
  const nModels = allModels.size || 19;
  const hv = verdictOf(r, "mississippi", "A", heroModel ?? "simvp", "lead0");
  const hero: HeroData | null = m && heroModel && preKey ? {
    rgb: layerURL(HERO_ST, `obs_rgb_${preKey}.png`), damage: layerURL(HERO_ST, cfPath(heroModel, HERO_CUT, "deficit", 0)),
    cf: layerURL(HERO_ST, cfPath(heroModel, HERO_CUT, "cf_ndvi", 0)), obs: layerURL(HERO_ST, `observed/${HERO_CUT}/ndvi_L0.png`),
    corners: m.coordinates, deficit: attrOf(r, "mississippi", "A", HERO_CUT, heroModel, "lead 0")?.deficit ?? null, model: meta(heroModel).name,
    passes: hv ? (hv.pass ? "It passes the placebo test: the same model finds no such damage on fake landfall dates." : "It fails the placebo test.") : "",
    nModels, nTests: r?.verdict.length ?? 0 } : null;

  const ida = r?.verdict.filter((v) => v.event === "ida" && v.stat === "lead0") ?? [];
  const idaPass = ida.filter((v) => v.pass).length;
  const lead0 = r?.attribution.filter((a) => a.event === "ida" && a.stat === "lead 0") ?? [];
  const range = lead0.length ? [Math.min(...lead0.map((a) => a.deficit)), Math.max(...lead0.map((a) => a.deficit))] : null;
  const rho = (ev: string, tr: string, cov: string) => mean((r?.external ?? []).filter((e) => e.event === ev && e.track === tr && e.map === "lead 0" && e.covariate === cov).map((e) => e.rho));
  const best = [...(r?.leaderboard ?? [])].filter((l) => l.site === "everglades" && l.track === "B").sort((a, b) => b.NDVI - a.NDVI)[0];

  const ticker = r ? [
    <><b>IDA</b> landfall deficit <em>{range ? `${fmt(range[0], 3, true)} … ${fmt(range[1], 3, true)}` : "…"}</em> NDVI</>,
    <><b>{idaPass}/{ida.length}</b> Ida tests pass the placebo</>,
    <>damage vs storm-track distance <em>ρ {fmt(rho("ida", "A", "track_km"), 2)}</em></>,
    <><b>IRMA</b> fails the inland placebo</>,
    <><b>{nModels}</b> trained models</>, <><b>{r.verdict.length}</b> pre-registered placebo tests</>,
    best ? <>best skill <b>{meta(best.model).short}</b> R² <em>{best.NDVI.toFixed(2)}</em></> : null,
    <>no deep model beats the best baseline</>,
    ...lead0.filter((a) => a.track === "A").sort((a, b) => b.deficit - a.deficit).map((a) => <>{meta(a.model).short} <em>{fmt(a.deficit, 3, true)}</em></>),
  ].filter(Boolean) : [];

  return (
    <div className="home">
      <HeroRewind data={hero} />
      {ticker.length > 0 && <Marquee items={ticker} />}

      <section className="wrap home-sec">
        <SectionHead n="01" kicker="The result, in numbers" title={<>Every number here is <span className="grad">live</span> from the pre-registered runs.</>} />
        {r && <Bento r={r} maps={maps} nModels={nModels} range={range} rhoIda={rho("ida", "A", "track_km")} rhoIrma={rho("irma", "B", "track_km")} keys={keys} />}
      </section>

      {maps?.["mississippi_B"] && r && <section className="wrap home-sec">
        <SectionHead n="02" kicker="The placebo theatre" title={<>Same model, same marsh. <span className="grad">Three years without a hurricane.</span></>}>
          A model that sees damage everywhere will also see it when nothing happened. So every model is re-run with fake landfall dates in calm
          years. Real damage must beat all of them.
        </SectionHead>
        <PlaceboTheatre r={r} m={maps["mississippi_B"]} st="mississippi_B" />
      </section>}

      {maps && <section className="wrap home-sec">
        <SectionHead n="03" kicker="The model wall" title={<>{nModels} models. One storm. <span className="grad">Hover to rewind.</span></>}>
          Each tile is a model's real damage map for Hurricane Irma. Hover to see its storm-free world instead. ✓ / ✗ is the pre-registered placebo verdict.
        </SectionHead>
        <Wall r={r} maps={maps} />
      </section>}

      {r && <section className="wrap home-sec">
        <SectionHead n="04" kicker="Two storms, two verdicts" title={<>One signal survived every test. <span className="grad">The other didn't.</span></>} />
        <Scorecards r={r} />
      </section>}

      <section className="home-cta">
        <Reveal className="wrap">
          <div className="cta-big">Rewind it <span className="grad">yourself.</span></div>
          <p className="muted" style={{ maxWidth: 560, margin: "18px auto 30px", fontSize: 17 }}>Every model, every pixel, every placebo year. Pick any pixel in the marsh and watch {nModels} models disagree about its future.</p>
          <div className="hero2-cta" style={{ justifyContent: "center" }}>
            <Link className="btn primary big" to="/explore">Open the studio <Icon name="arrow" size={16} /></Link>
            <Link className="btn big" to="/lab"><Icon name="cpu" size={16} /> Run SimVP on your GPU</Link>
            <Link className="btn big" to="/evidence"><Icon name="chart" size={16} /> All evidence</Link>
          </div>
        </Reveal>
      </section>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ spec sheet
function Bento({ r, maps, nModels, range, rhoIda, rhoIrma, keys }: { r: Results; maps: Record<string, MapSite> | null; nModels: number;
  range: number[] | null; rhoIda: number; rhoIrma: number; keys: string[] }) {
  const [ref, inv] = useInView<HTMLDivElement>();
  // placebo matrix: rows = models, columns = site/resolution/window
  const cols = [...new Set(r.verdict.map((v) => `${v.site}|${v.track}|${v.stat}`))].sort((a, b) => a.localeCompare(b));
  const colLabel = (c: string) => { const [s, t, st] = c.split("|"); return [`${s === "mississippi" ? "LA" : "FL"} ${t === "A" ? "10m" : "30m"}`, st === "lead0" ? "landfall" : "q1–3"]; };
  const rowsM = sortModels([...new Set(r.verdict.map((v) => v.model))]);
  const cell = (m: string, c: string) => { const [s, t, st] = c.split("|"); return r.verdict.find((v) => v.model === m && v.site === s && v.track === t && v.stat === st); };
  const npass = r.verdict.filter((v) => v.pass).length;
  const lead0 = r.attribution.filter((a) => a.event === "ida" && a.stat === "lead 0" && a.track === "A").sort((a, b) => a.deficit - b.deficit);
  const lo = -0.02, hi = 0.12, X = (v: number) => ((v - lo) / (hi - lo)) * 100;
  const top = [...r.leaderboard].filter((l) => l.site === "mississippi" && l.track === "A").sort((a, b) => b.NDVI - a.NDVI);
  const covs = [...new Set(r.external.map((e) => e.covariate))].slice(0, 3);
  const covName: Record<string, string> = { track_km: "Distance to storm track", coast_m: "Distance to coast", wind_kt: "Maximum wind" };
  const rhoOf = (ev: string, cov: string) => mean(r.external.filter((e) => e.event === ev && e.map === "lead 0" && e.covariate === cov).map((e) => e.rho));
  const [fi, setFi] = useState(0);
  useEffect(() => { if (!keys.length) return; const t = setInterval(() => setFi((i) => (i + 1) % keys.length), 650); return () => clearInterval(t); }, [keys.length]);
  const famCount = maps ? sortModels([...new Set(Object.values(maps).flatMap((s) => s.models))]).reduce<Record<string, number>>((acc, id) => { acc[meta(id).fam] = (acc[meta(id).fam] ?? 0) + 1; return acc; }, {}) : {};
  const deep = new Set(["convlstm", "simvp", "ecotransformer"]);
  return (
    <div className={`sheet ${inv ? "in" : ""}`} ref={ref}>
      <div className="sh-cell sh-matrix">
        <div className="sh-k">Fig. 1 · Placebo-in-time test</div>
        <div className="sh-num"><CountUp to={npass} /><span>/{r.verdict.length}</span></div>
        <p className="sh-cap">Each cell: does the model's storm deficit beat the 95th percentile of its own deficits on fake landfall dates in calm years?</p>
        <table className="mx"><thead><tr><th />{cols.map((c) => { const [a, b] = colLabel(c); return <th key={c}><span>{a}</span><span>{b}</span></th>; })}<th className="mx-n" /></tr></thead>
          <tbody>{rowsM.map((m, ri) => <tr key={m}><td className="mx-l">{meta(m).short}</td>
            {cols.map((c, ci) => { const v = cell(m, c); return <td key={c}>{v ? <span className={`mk ${v.pass ? "p" : "f"}`} style={{ transitionDelay: `${(ri * cols.length + ci) * 14}ms` }}
              title={`${meta(m).name} · ${colLabel(c).join(" ")} · ${v.pass ? "pass" : "fail"} · event ${fmt(v.event_median, 3, true)} vs p95 ${fmt(v.placebo_p95, 3, true)}`} /> : <span className="mk na" />}</td>; })}
            <td className="mx-n mono">{r.verdict.filter((v) => v.model === m && v.pass).length}/{r.verdict.filter((v) => v.model === m).length}</td></tr>)}</tbody></table>
        <div className="sh-legend"><span className="mk p" /> pass <span className="mk f" /> fail <span className="mk na" /> not run</div>
      </div>

      <div className="sh-cell sh-def">
        <div className="sh-k">Fig. 2 · Ida, just after landfall</div>
        <div className="sh-num">{range ? <><CountUp to={range[0]} decimals={3} sign /><span> to </span><CountUp to={range[1]} decimals={3} sign /></> : "…"}</div>
        <p className="sh-cap">NDVI deficit (counterfactual − observed), one tick per model, Louisiana 10 m. All positive.</p>
        <div className="axis">
          <div className="axis-line" /><div className="axis-zero" style={{ left: `${X(0)}%` }}><span>0</span></div>
          {lead0.map((a, i) => <div key={a.model} className="tick" style={{ left: `${X(a.deficit)}%`, transitionDelay: `${i * 60}ms` }} title={`${meta(a.model).name} ${fmt(a.deficit, 3, true)}`}>
            <span className="tick-l">{meta(a.model).short}</span></div>)}
          {[0.05, 0.1].map((v) => <div key={v} className="axis-t" style={{ left: `${X(v)}%` }}>{v.toFixed(2)}</div>)}
        </div>
      </div>

      <div className="sh-cell sh-rho">
        <div className="sh-k">Fig. 3 · Independent evidence (NOAA HURDAT2)</div>
        <div className="sh-num"><span className="sh-sym">ρ</span><CountUp to={rhoIda} decimals={2} /></div>
        <p className="sh-cap">Spearman correlation between damage and each covariate across spatial blocks. Ida behaves like a storm; Irma ({fmt(rhoIrma, 2, true)} with track distance) does not.</p>
        <table className="rho2"><thead><tr><th /><th>Ida</th><th>Irma</th></tr></thead><tbody>{covs.map((c) => <tr key={c}><td>{covName[c] ?? c}</td>
          {(["ida", "irma"] as const).map((ev) => { const v = rhoOf(ev, c); return <td key={ev}><span className="db"><span className="db-z" />
            {isFinite(v) && <span className={`db-f ${ev}`} style={{ left: v < 0 ? `${50 + v * 50}%` : "50%", width: `${Math.abs(v) * 50}%` }} />}</span><span className="mono">{fmt(v, 2, true)}</span></td>; })}</tr>)}</tbody></table>
      </div>

      <div className="sh-cell sh-film">
        <div className="film-mini">{maps?.[HERO_ST] && keys.map((k, i) => <img key={k} src={layerURL(HERO_ST, `obs_rgb_${k}.png`)} alt="" loading="lazy" style={{ opacity: i === fi ? 1 : 0, filter: "url(#tc)" }} />)}</div>
        <div className="film-cap"><span className="sh-k">Fig. 4 · The record, {keys.length} quarterly composites</span><span className="mono">{keys[fi] ? quarterLabel(keys[fi]) : ""}</span></div>
      </div>

      <div className="sh-cell sh-race">
        <div className="sh-k">Fig. 5 · Forecast skill, Louisiana 10 m</div>
        <div className="sh-num">{top[0] ? top[0].NDVI.toFixed(2) : "—"}<span> R² · {top[0] ? meta(top[0].model).short : ""}</span></div>
        <p className="sh-cap">NDVI R² on held-out blocks in calm windows. Deep networks shaded; none beats the best baseline.</p>
        <div className="race2">{top.map((l, i) => <div key={l.model} className={`r2row ${deep.has(l.model) ? "deep" : ""}`}><span>{meta(l.model).short}</span>
          <span className="r2bar"><span style={{ width: `${(Math.max(0, l.NDVI) / 0.8) * 100}%`, transitionDelay: `${i * 70}ms` }} /></span><span className="mono">{l.NDVI.toFixed(3)}</span></div>)}</div>
      </div>

      <div className="sh-cell sh-models">
        <div className="sh-k">Fig. 6 · The benchmark</div>
        <div className="sh-num"><CountUp to={nModels} /><span> models</span></div>
        <div className="seg-bar">{(["baseline", "deep", "ablation", "transfer", "experimental"] as const).map((f) => famCount[f] ? <span key={f} className={`sb ${f}`} style={{ ["--n" as string]: famCount[f] }}><b>{famCount[f]}</b><span style={{ width: 92 }}>{f}</span></span> : null)}</div>
        <p className="sh-cap">Same pixels, same held-out blocks, same placebo windows for every model.</p>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ placebo theatre
function PlaceboTheatre({ r, m, st }: { r: Results; m: MapSite; st: string }) {
  const cuts = ["ida", ...Object.keys(m.cutoffs).filter(isPlacebo).sort()];
  const models = sortModels(modelsFor(m, "ida")).filter((id) => verdictOf(r, "mississippi", "B", id, "lead0"));
  const [mi, setMi] = useState(0);
  const [auto, setAuto] = useState(true);
  const [ref, inv] = useInView<HTMLDivElement>();
  useEffect(() => { if (!auto || !inv || !models.length) return; const t = setInterval(() => setMi((i) => (i + 1) % models.length), 4200); return () => clearInterval(t); }, [auto, inv, models.length]);
  const id = models[mi] ?? models[0];
  const v = id ? verdictOf(r, "mississippi", "B", id, "lead0") : undefined;
  const [means, setMeans] = useState<Record<string, number | null>>({});
  useEffect(() => {
    if (!id) return;
    let live = true;
    cuts.forEach((c) => ensemble([layerURL(st, cfPath(id, c, "deficit", 0))], "mean").then((e) => live && setMeans((s) => ({ ...s, [id + c]: e?.meanAll ?? null }))));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  const under = imageKeys(m).filter((k) => k < "2015Q3").slice(-1)[0];
  if (!id) return null;
  return (
    <div className="theatre" ref={ref}>
      <div className="theatre-models">{models.map((x, i) => <button key={x} className={i === mi ? "on" : ""} onClick={() => { setAuto(false); setMi(i); }}>
        {meta(x).short}{i === mi && auto && <span className="tm-prog" />}</button>)}</div>
      <div className="theatre-stage">
        {cuts.map((c, i) => {
          const val = means[id + c];
          return <div key={c} className={`theatre-panel ${isPlacebo(c) ? "pl" : "ev"}`}>
            <div className="tp-img">
              {under && <img src={layerURL(st, `obs_rgb_${under}.png`)} alt="" style={{ filter: DIM }} />}
              <img key={id + c} className="tp-ov" style={{ animationDelay: `${i * 90}ms` }} src={layerURL(st, cfPath(id, c, "deficit", 0))} alt={`${meta(id).name} · ${cutoffLabel(c)}`} />
              <span className={`tp-tag ${isPlacebo(c) ? "pl" : "ev"}`}>{isPlacebo(c) ? "no storm" : "hurricane"}</span>
            </div>
            <div className="tp-cap"><span>{isPlacebo(c) ? `Placebo ${c.match(/\d{4}/)?.[0]}` : "Ida · 2021"}</span>
              <b className="mono" style={{ color: isPlacebo(c) ? "var(--placebo)" : "var(--dmg1)" }}>{val == null ? "…" : fmt(val, 3, true)}</b></div>
          </div>;
        })}
        {v && <div key={id} className={`stamp ${v.pass ? "pass" : "fail"}`}>{v.pass ? "PASS" : "FAIL"}<small>{v.pass ? "the storm beats every calm year" : "calm years look as damaged"}</small></div>}
      </div>
      <div className="theatre-foot muted">Mean NDVI deficit of each map, computed in your browser from the published layer · Louisiana 30 m HLS.
        Pre-registered rule: event median {v ? fmt(v.event_median, 3, true) : "…"} vs placebo 95th percentile {v ? fmt(v.placebo_p95, 3, true) : "…"}.</div>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ model wall
function Wall({ r, maps }: { r: Results | null; maps: Record<string, MapSite> }) {
  const st = maps["everglades_B"] ? "everglades_B" : HERO_ST, cut = st.startsWith("ever") ? "irma" : "ida", [s, t] = st.split("_");
  const ids = sortModels(modelsFor(maps[st], cut));
  const under = imageKeys(maps[st]).filter((k) => k < (cut === "irma" ? "2017Q3" : "2021Q3")).slice(-1)[0];
  return <div className="wall wall2">{ids.map((id, i) => {
    const mm = meta(id), a = attrOf(r, s, t, cut, id, "lead 0"), v = verdictOf(r, s, t, id, "lead0"), sk = skillAny(r, id, s, t);
    return <Reveal key={id} delay={(i % 7) * 60}><Glow as={Link} tilt className="wall-tile" to={`/explore?mode=gallery&site=${s}&track=${t}&model=${id}`} style={{ ["--c" as string]: mm.color }}>
      <div className="wall-img">
        <img src={layerURL(st, `obs_rgb_${under}.png`)} alt="" loading="lazy" style={{ filter: DIM }} />
        <img className="w-def" src={layerURL(st, cfPath(id, cut, "deficit", 0))} alt={`${mm.name} damage map`} loading="lazy" />
        <img className="w-cf" src={layerURL(st, cfPath(id, cut, "cf_ndvi", 0))} alt="" loading="lazy" />
        <span className="w-hint mono">◀◀ no-storm world</span>
      </div>
      <div className="wall-cap"><span className="dot" style={{ background: mm.color }} /><span className="wall-name">{mm.short}</span>
        {v && <span className={`mini ${v.pass ? "pass" : "fail"}`}>{v.pass ? "✓" : "✗"}</span>}</div>
      <div className="wall-sub mono">{a ? fmt(a.deficit, 3, true) : mm.fam}{sk ? <span className="dim"> · R² {sk.v.toFixed(2)}</span> : null}</div>
    </Glow></Reveal>;
  })}</div>;
}

// ------------------------------------------------------------------------------------------------ scorecards
function Scorecards({ r }: { r: Results }) {
  const card = (ev: string, site: string, tr: string) => {
    const time = r.verdict.filter((v) => v.event === ev && v.stat === "lead0"), tp = time.filter((v) => v.pass).length;
    const sp = r.space.filter((x) => x.event === ev && x.map === "lead 0"), spOk = sp.filter((x) => x.inland < x.all / 2).length;
    const rho = mean(r.external.filter((e) => e.event === ev && e.map === "lead 0" && e.covariate === "track_km").map((e) => e.rho));
    const l0 = r.attribution.filter((a) => a.event === ev && a.stat === "lead 0");
    const checks = [
      { ok: tp / (time.length || 1) > 0.75, k: "Beats fake storms", v: `${tp}/${time.length} tests`, d: "event deficit above the placebo 95th percentile" },
      { ok: spOk / (sp.length || 1) > 0.5, k: "Quiet inland", v: `${spOk}/${sp.length} maps`, d: "inland control blocks below half the deficit" },
      { ok: rho < -0.2, k: "Follows the track", v: `ρ ${fmt(rho, 2, true)}`, d: "worse closer to the storm's path (NOAA HURDAT2)" },
      { ok: l0.length > 0 && l0.every((a) => a.deficit > 0), k: "Models agree on sign", v: `${l0.filter((a) => a.deficit > 0).length}/${l0.length} positive`, d: "every model sees a loss" },
    ];
    const credible = checks.filter((c) => c.ok).length >= 3;
    return <Glow key={ev} className={`score ${credible ? "ok" : "bad"}`}>
      <div className="score-head"><div><div className="eyebrow">{site}</div><h3>Hurricane {ev === "ida" ? "Ida · 2021" : "Irma · 2017"}</h3></div>
        <div className={`score-stamp ${credible ? "ok" : "bad"}`}>{credible ? "CREDIBLE" : "NOT CREDIBLE"}</div></div>
      {checks.map((c, i) => <Reveal key={c.k} delay={i * 110} className="score-row">
        <span className={`score-ic ${c.ok ? "ok" : "bad"}`}>{c.ok ? "✓" : "✗"}</span>
        <span className="score-t"><b>{c.k}</b><span className="dim">{c.d}</span></span><span className="mono score-v">{c.v}</span></Reveal>)}
      <Link className="chip" to={`/explore?site=${ev === "ida" ? "mississippi" : "everglades"}&track=${tr}&mode=ensemble`} style={{ marginTop: 14 }}>see the ensemble map <Icon name="arrow" size={12} /></Link>
    </Glow>;
  };
  return <div className="grid g2 scores">{card("ida", "Barataria Bay, Louisiana", "A")}{card("irma", "Everglades, Florida", "B")}</div>;
}
