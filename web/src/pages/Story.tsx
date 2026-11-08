import { ReactNode, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Forest } from "../components/charts";
import { fmt, MapSite, Results, useMaps, useResults } from "../lib/data";
import { cfPath, imageKeys, layerURL } from "../lib/explore";
import { meta } from "../lib/models";

type Ch = { k: string; title: string; body: ReactNode; vis: ReactNode };
const avg = (x: number[]) => (x.length ? x.reduce((a, b) => a + b, 0) / x.length : NaN);

export default function Story() {
  const { data: r } = useResults();
  const { data: maps } = useMaps();
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLElement | null)[]>([]);
  useEffect(() => {
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) setActive(+(e.target as HTMLElement).dataset.i!); }), { rootMargin: "-45% 0px -50% 0px" });
    refs.current.forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, [r, maps]);
  if (!r) return <div className="page wrap"><div className="skeleton" style={{ height: 500 }} /></div>;
  const chapters = build(r, maps);
  return (
    <div className="page wrap story">
      <header className="ev-head"><div className="eyebrow">The story</div>
        <h1>How we rewound two hurricanes, and why we tried to prove ourselves wrong.</h1></header>
      <div className="sx">
        <div className="sx-text">{chapters.map((c, i) => <section key={c.k} ref={(el) => (refs.current[i] = el)} data-i={i} className={`sx-ch ${i === active ? "on" : ""}`}>
          <div className="sx-k mono">{c.k}</div><h2>{c.title}</h2><div className="sx-body">{c.body}</div>
          <div className="sx-inline">{c.vis}</div></section>)}</div>
        <div className="sx-stick"><div className="sx-frame">{chapters.map((c, i) => <div key={c.k} className={`sx-vis ${i === active ? "on" : ""}`}>{c.vis}</div>)}
          <div className="sx-dots">{chapters.map((c, i) => <button key={c.k} className={i === active ? "on" : ""} aria-label={c.k}
            onClick={() => refs.current[i]?.scrollIntoView({ behavior: "smooth", block: "center" })} />)}</div></div></div>
      </div>
    </div>
  );
}

function build(r: Results, maps: Record<string, MapSite> | null): Ch[] {
  const ida0 = r.attribution.filter((a) => a.event === "ida" && a.track === "A" && a.stat === "lead 0").sort((a, b) => a.deficit - b.deficit);
  const ida13 = r.attribution.filter((a) => a.event === "ida" && a.track === "A" && a.stat === "leads 1-3").sort((a, b) => a.deficit - b.deficit);
  const sp = (e: string) => r.space.filter((s) => s.event === e && s.track === "B" && s.map === "lead 0");
  const top = [...r.leaderboard].filter((l) => l.site === "mississippi" && l.track === "A").sort((a, b) => b.NDVI - a.NDVI);
  const img = (st: string, before: string) => { const m = maps?.[st]; const k = m ? imageKeys(m).filter((x) => x < before).slice(-1)[0] : null; return k ? layerURL(st, `obs_rgb_${k}.png`) : null; };
  const la = img("mississippi_A", "2021Q3"), fl = img("everglades_B", "2017Q3");
  const ida = maps?.mississippi_A, simDef = ida?.layers[cfPath("simvp", "ida", "deficit", 0)] ? layerURL("mississippi_A", cfPath("simvp", "ida", "deficit", 0)) : null;
  const simCf = ida?.layers[cfPath("simvp", "ida", "cf_ndvi", 0)] ? layerURL("mississippi_A", cfPath("simvp", "ida", "cf_ndvi", 0)) : null;
  const grid = (fn: (i: number) => string, cap: string) => <figure className="sx-grid"><div>{Array.from({ length: 144 }, (_, i) => <span key={i} style={{ background: fn(i) }} />)}</div><figcaption>{cap}</figcaption></figure>;
  return [
    { k: "01 · The question", title: "Coastal wetlands store carbon and blunt storm surge. Hurricanes damage them, but by how much?",
      body: <p>To know what a storm did, you need to know what would have happened without it. That world doesn't exist, so we predict it: a
        <b> counterfactual</b> forecast of every pixel, learned only from the years before the storm.</p>,
      vis: <div className="sx-pair">{[[la, "Barataria Bay, Louisiana", "Hurricane Ida · 29 Aug 2021 · Cat 4"], [fl, "Everglades, Florida", "Hurricane Irma · 10 Sep 2017 · Cat 4"]].map(([s, a, b]) =>
        <figure key={a as string}>{s && <img src={s as string} alt="" style={{ filter: "url(#tc)" }} />}<figcaption><b>{a}</b><span>{b}</span></figcaption></figure>)}</div> },
    { k: "02 · Version 1", title: "R² 0.901 looked amazing. It was a leak.",
      body: <p>The first EcoRewind split pixels at random, so every test pixel had training pixels next door and the model simply copied its neighbours.
        The radar export was broken and the Mississippi study area was in the wrong place. We threw it away.</p>,
      vis: grid((i) => ((i * 7919) % 5 === 0 ? "var(--signal)" : "var(--mark4)"), "Random split: test pixels (red) surrounded by training pixels.") },
    { k: "03 · Version 2", title: "Rebuilt with locks.",
      body: <p>Spatial blocks 3.84 km wide with 640 m buffers, so test areas are isolated. A pre-registration written before any model ran. Placebo windows
        checked against the NOAA hurricane record. Every later change logged before its result (amendments A1–A5).</p>,
      vis: grid((i) => { const b = Math.floor((i % 12) / 4) + 3 * Math.floor(i / 48); return b === 1 || b === 5 ? "var(--signal)" : b === 3 ? "#8e8e94" : "var(--mark4)"; },
        "Block split: whole blocks held out (red = test, grey = calibration, dark = training).") },
    { k: "04 · The models", title: "Nineteen models. Simple beat fancy.",
      body: <p>Six statistical baselines, three deep networks and ten variants, all on identical pixels and folds. The best placebo-window skill comes from
        {" "}{top.slice(0, 2).map((t) => meta(t.model).name).join(" and ")}. The deep networks learn real structure but never beat the best baseline: a useful
        answer for anyone about to spend GPU money on this.</p>,
      vis: <div className="race2 sx-race">{top.map((l) => <div key={l.model} className={`r2row ${["convlstm", "simvp", "ecotransformer"].includes(l.model) ? "deep" : ""}`}>
        <span>{meta(l.model).short}</span><span className="r2bar"><span style={{ width: `${(Math.max(0, l.NDVI) / 0.8) * 100}%` }} /></span><span className="mono">{l.NDVI.toFixed(3)}</span></div>)}
        <p className="dim" style={{ fontSize: 12 }}>NDVI R², Louisiana 10 m. Deep networks shaded.</p></div> },
    { k: "05 · What survived", title: "Ida's damage, right after landfall, is real.",
      body: <p>Every model sees it, from {fmt(ida0[0]?.deficit, 3, true)} to {fmt(ida0[ida0.length - 1]?.deficit, 3, true)} NDVI. It beats the calm-year placebos for every model,
        fades inland, and is strongest along the storm's track.</p>,
      vis: <div className="sx-map">{la && <img src={la} alt="" style={{ filter: "url(#tc) saturate(.6) brightness(.55)" }} />}{simDef && <img src={simDef} alt="SimVP damage map" />}
        <span className="mono">SimVP damage map · Louisiana 10 m · landfall</span></div> },
    { k: "06 · What didn't", title: "Lasting damage depends on whom you ask. Irma fails.",
      body: <p>A quarter later the models disagree in sign; those that pass the placebo test agree on ≈ 0. Irma passes the fake-storm test, but its "damage" is larger
        inland ({fmt(avg(sp("irma").map((s) => s.inland)), 3, true)} vs {fmt(avg(sp("irma").map((s) => s.all)), 3, true)} overall) and farther from the track, so it isn't storm damage.</p>,
      vis: <div><Forest width={520} rows={ida13.map((a) => ({ label: meta(a.model).short, v: a.deficit, color: a.placebo === "fail" ? "var(--mark3)" : "var(--mark)", faded: a.placebo === "fail" }))} />
        <p className="dim" style={{ fontSize: 12 }}>Ida, quarters 1–3. Faded = fails the placebo test.</p></div> },
    { k: "07 · Why it matters", title: "Attribution claims need placebos and many models.",
      body: <><p>A single model with no placebo test would have reported Irma damage with confidence, and over-stated Ida's lasting loss. The same protocol (block folds,
        pre-registration, placebos in time and space, many models) applies to any satellite damage claim.</p>
        <div className="hero2-cta" style={{ marginTop: 18 }}><Link className="btn primary" to="/explore">Explore the maps</Link><Link className="btn" to="/evidence">See every test</Link><Link className="btn" to="/lab">Run a model</Link></div></>,
      vis: <div className="sx-map">{la && <img src={la} alt="" style={{ filter: "url(#tc) saturate(.6) brightness(.55)" }} />}{simCf && <img src={simCf} alt="counterfactual" />}
        <span className="mono">The marsh without Ida · SimVP counterfactual</span></div> },
  ];
}
