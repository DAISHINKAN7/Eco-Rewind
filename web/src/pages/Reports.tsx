import { useState } from "react";
import { fmt, useResults } from "../lib/data";
import { CountUp, Reveal } from "../lib/fx";

const GH = "https://github.com/DAISHINKAN7/EcoRewind2/blob/main/";
const DOCS: [string, string, string, string][] = [
  ["Phase 0", "Re-export and audit", "Rebuilt every Earth Engine export; the audit caught v1's leaky split, broken radar and wrong study area.", "reports/phase_0_report.md"],
  ["Phase 1", "Cubes, masks, blocks, folds", "Zarr cubes with per-channel validity, 3.84 km blocks with buffers, five stratified folds.", "reports/phase_1_report.md"],
  ["Phase 2", "Evaluation harness and baselines", "One harness for every model; six baselines; split-conformal intervals calibrated on placebo windows.", "reports/phase_2_report.md"],
  ["Phase 3", "Deep models", "ConvLSTM, SimVP and EcoTransformer v2 on Colab T4s, 5 folds × 2 seeds, resumable per fold.", "reports/phase_3_report.md"],
  ["Phase 4", "Placebo verdict", "Placebo tests in time and space under the amendment-A4 rules.", "reports/phase_4_report.md"],
  ["Phase 5", "Attribution, external evidence, ablations", "Attribution spread, HURDAT2 correlations, ablations, transfer, resolution and the post-hoc neighbour model.", "reports/phase_5_report.md"],
  ["Log", "Results changelog", "Every amendment and decision, dated, with what had been seen at the time.", "RESULTS_CHANGELOG.md"],
  ["Config", "Pre-registration", "Events, placebo windows, horizons and pass criteria, fixed before any model ran.", "configs/preregistration.yaml"],
  ["Data", "Sources, grids, products", "Sensors, cloud masks, grids and every derived product.", "docs/DATA.md"],
];
const AMEND: [string, string, string, string][] = [
  ["A1", "27 Oct", "Harmonic without trend", "The trended harmonic baseline was worse than climatology everywhere; a trend-free rung was added, with no tuned parameter."],
  ["A2", "27 Oct", "Lead 0 as a secondary analysis", "The event-quarter post-landfall composite is evaluated too. Primary claims stay on quarters 1–3."],
  ["A3", "27 Oct", "Matched placebo lead 0", "Placebo lead-0 composites are exported over the same days as the ~1-month event composite. It can only remove spurious signal."],
  ["A4", "2 Nov", "Placebo test operationalised", "Statistic and pooling fixed before computing: per-fold deficit, placebo distribution over windows × folds × seeds, space test by coast distance."],
  ["A5", "2 Nov", "Phase 5 experiments declared", "Ablations, transfer, resolution and the exploratory neighbour-informed SimVP, each with its comparison, before any Phase 5 GPU run."],
];
const CMDS: [string, string][] = [
  ["Earth Engine export + audit", "notebooks/01_gee_export_colab.ipynb · 02_audit_exports_colab.ipynb"],
  ["Cubes and folds", "notebooks/10_phase1_colab.ipynb"],
  ["Baselines", "notebooks/20_phase2_colab.ipynb · 21_placebo_post_colab.ipynb"],
  ["Deep models (T4)", "notebooks/30_phase3_colab.ipynb"],
  ["Phase 5 GPU runs", "notebooks/50_phase5_gpu_colab.ipynb"],
  ["Analyses + demo export", "notebooks/51_phase5_analysis_colab.ipynb"],
  ["Website data + build", "notebooks/60_web_build_colab.ipynb"],
  ["Tests", "python -m pytest -q"],
  ["Run the site locally", "cd web && npm ci && npm run dev"],
];

export default function Reports() {
  const { data: r } = useResults();
  const [copied, setCopied] = useState<number | null>(null);
  const comp = (r?.compute ?? []).filter((c) => c.date !== "date");
  const ccu = comp.filter((c) => c.platform === "colab").reduce((a, c) => a + (+String(c.units).replace("~", "") || 0), 0);
  const copy = (t: string, i: number) => { navigator.clipboard?.writeText(t).then(() => { setCopied(i); setTimeout(() => setCopied(null), 1400); }); };
  return (
    <div className="page wrap">
      <header className="ev-head"><div className="eyebrow">Reports & reproducibility</div>
        <h1>Every number has a paper trail.</h1>
        <p className="md-lead">Each figure on this site is generated from the runs below by scripts in the repository. Every phase reproduces on Google Colab and Earth Engine
          from the notebooks, and every change of plan was logged before the result it could affect.</p>
        <div className="md-kpis">
          <div><b><CountUp to={9} /></b><span>reports and specs</span></div>
          <div><b><CountUp to={5} /></b><span>logged amendments</span></div>
          <div><b><CountUp to={55} /></b><span>automated tests</span></div>
          <div><b>{ccu ? <CountUp to={ccu} decimals={0} /> : "—"}</b><span>Colab compute units</span></div>
          <div><b>96.6</b><span>Earth Engine EECU-hours</span></div>
        </div>
      </header>

      <section className="md-sec"><div className="md-sec-h"><h2>Documents</h2></div>
        <div className="rp-docs">{DOCS.map(([k, t, d, p]) => <Reveal key={p}><a className="rp-doc" href={GH + p} target="_blank" rel="noreferrer">
          <span className="k">{k}</span><span><h3>{t}</h3><p>{d}</p></span><span className="mono">{p} ↗</span></a></Reveal>)}</div></section>

      <section className="md-sec"><div className="md-sec-h"><h2>Amendment log</h2><p className="muted">Changes to the pre-registered plan, each dated and logged before the result it could affect.</p></div>
        <div className="rp-amend">{AMEND.map(([k, d, t, x]) => <div key={k}><b>{k}</b><span className="sh-k">{d} 2026</span><h4>{t}</h4><p>{x}</p></div>)}</div></section>

      <section className="md-sec"><div className="md-sec-h"><h2>Reproduce it</h2><p className="muted">Colab + Google Drive; nothing is downloaded locally. Needs an Earth Engine project and a GitHub token in Colab Secrets.</p></div>
        <div className="rp-cmds">{CMDS.map(([t, c], i) => <div key={t} className="rp-cmd"><span className="n">{String(i + 1).padStart(2, "0")}</span><span>{t}</span><code>{c}</code>
          <button className="btn" style={{ padding: "6px 12px", fontSize: 12 }} onClick={() => copy(c, i)}>{copied === i ? "copied" : "copy"}</button></div>)}</div></section>

      {comp.length > 0 && <section className="md-sec"><div className="md-sec-h"><h2>Compute log</h2></div>
        <div className="card pad0" style={{ overflowX: "auto" }}><table className="t">
          <thead><tr><th>Date</th><th>Platform</th><th>Hardware</th><th>Task</th><th className="n">Units</th><th>Note</th></tr></thead>
          <tbody>{comp.map((c, i) => <tr key={i}><td className="mono">{c.date}</td><td>{c.platform}</td><td>{c.hardware}</td><td className="mono" style={{ fontSize: 12 }}>{c.task}</td>
            <td className="n mono">{c.units === "" ? "—" : fmt(+String(c.units).replace("~", ""), 2)}</td><td className="dim" style={{ fontSize: 12 }}>{c.note}</td></tr>)}</tbody></table></div></section>}
      <p className="dim" style={{ fontSize: 12.5, marginTop: 30 }}>Data build {r?.generated}. Credits: Copernicus Sentinel-1/2 (ESA), NASA HLS, ESA WorldCover, Copernicus DEM, NOAA HURDAT2, processed with Google Earth Engine.</p>
    </div>
  );
}
