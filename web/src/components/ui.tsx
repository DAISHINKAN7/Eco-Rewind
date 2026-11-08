import { ReactNode, useEffect, useState } from "react";
import { NavLink, Link } from "react-router-dom";

/** Mark: a hurricane's two spiral arms (logarithmic spiral, counter-clockwise like a northern storm), the outer arm
 *  ending in a backward arrowhead (rewind), around the eye. */
export const Leaf = ({ size = 30 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-label="EcoRewind" role="img" className="logo-mark">
    <g fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18.10,16.00 L18.14,15.78 L18.16,15.55 L18.15,15.31 L18.12,15.07 L18.06,14.83 L17.97,14.59 L17.86,14.36 L17.72,14.13 L17.56,13.92 L17.37,13.71 L17.15,13.53 L16.91,13.36 L16.65,13.22 L16.37,13.10 L16.07,13.00 L15.75,12.94 L15.42,12.91 L15.09,12.91 L14.75,12.95 L14.40,13.03 L14.06,13.14 L13.72,13.29 L13.39,13.48 L13.08,13.71 L12.78,13.98 L12.51,14.28 L12.26,14.62 L12.05,14.98 L11.87,15.38 L11.72,15.81 L11.62,16.26 L11.57,16.72 L11.56,17.20 L11.61,17.69 L11.70,18.19 L11.86,18.68 L12.06,19.17 L12.32,19.64 L12.64,20.10 L13.01,20.53 L13.43,20.93 L13.90,21.29 L14.42,21.61 L14.99,21.88 L15.59,22.10 L16.22,22.26 L16.89,22.35 L17.58,22.37 L18.28,22.32 L18.99,22.20 L19.70,22.00 L20.40,21.72 L21.08,21.36 L21.74,20.93 L22.37,20.41 L22.95,19.82 L23.49,19.16 L23.96,18.43 L24.36,17.63 L24.69,16.78 L24.94,15.88 L25.09,14.93 L25.15,13.96 L25.10,12.95 L24.95,11.94 L24.68,10.92 L24.31,9.91 L23.82,8.92 L23.22,7.96 L22.50,7.05" strokeWidth={2.3} />
      <path d="M13.90,16.00 L13.86,16.22 L13.84,16.45 L13.85,16.69 L13.88,16.93 L13.94,17.17 L14.03,17.41 L14.14,17.64 L14.28,17.87 L14.44,18.08 L14.63,18.29 L14.85,18.47 L15.09,18.64 L15.35,18.78 L15.63,18.90 L15.93,19.00 L16.25,19.06 L16.58,19.09 L16.91,19.09 L17.25,19.05 L17.60,18.97 L17.94,18.86 L18.28,18.71 L18.61,18.52 L18.92,18.29 L19.22,18.02 L19.49,17.72 L19.74,17.38 L19.95,17.02 L20.13,16.62 L20.28,16.19 L20.38,15.74 L20.43,15.28 L20.44,14.80 L20.39,14.31 L20.30,13.81 L20.14,13.32 L19.94,12.83 L19.68,12.36 L19.36,11.90 L18.99,11.47 L18.57,11.07 L18.10,10.71 L17.58,10.39 L17.01,10.12 L16.41,9.90 L15.78,9.74 L15.11,9.65 L14.42,9.63 L13.72,9.68 L13.01,9.80 L12.30,10.00 L11.60,10.28 L10.92,10.64 L10.26,11.07 L9.63,11.59 L9.05,12.18 L8.51,12.84 L8.04,13.57 L7.64,14.37 L7.31,15.22 L7.06,16.12 L6.91,17.07 L6.85,18.04 L6.90,19.05 L7.05,20.06 L7.32,21.08 L7.69,22.09 L8.18,23.08 L8.78,24.04 L9.50,24.95" strokeWidth={2.3} opacity={0.55} />
      <path d="M26.35,8.74 L22.50,7.05 L22.39,11.25" strokeWidth={2.3} />
    </g>
    <circle cx={16} cy={16} r={1.9} fill="var(--signal)" />
  </svg>
);

const P = (d: string) => <path d={d} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />;
export const Icon = ({ name, size = 18 }: { name: string; size?: number }) => {
  const paths: Record<string, ReactNode> = {
    map: <>{P("M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z")}{P("M9 4v14M15 6v14")}</>,
    cube: <>{P("M12 2l9 5v10l-9 5-9-5V7z")}{P("M3 7l9 5 9-5M12 12v10")}</>,
    flask: <>{P("M9 3h6M10 3v6L4 20h16L14 9V3")}{P("M7 15h10")}</>,
    chart: <>{P("M4 20V10M10 20V4M16 20v-7M21 20H3")}</>,
    play: <path d="M8 5l11 7-11 7z" fill="currentColor" />,
    pause: <><rect x="6" y="5" width="4" height="14" fill="currentColor" /><rect x="14" y="5" width="4" height="14" fill="currentColor" /></>,
    sun: <>{P("M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6L4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4")}<circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" strokeWidth="1.7" /></>,
    moon: P("M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"),
    github: <path fill="currentColor" d="M12 2a10 10 0 0 0-3.2 19.5c.5.1.7-.2.7-.5v-1.8c-2.8.6-3.4-1.2-3.4-1.2-.5-1.2-1.1-1.5-1.1-1.5-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .9 1.5 2.3 1.1 2.9.8.1-.6.3-1.1.6-1.3-2.2-.3-4.6-1.1-4.6-5a3.9 3.9 0 0 1 1-2.7 3.6 3.6 0 0 1 .1-2.7s.8-.3 2.7 1a9.4 9.4 0 0 1 5 0c1.9-1.3 2.7-1 2.7-1 .5 1.4.2 2.4.1 2.7a3.9 3.9 0 0 1 1 2.7c0 3.9-2.4 4.7-4.6 5 .4.3.7.9.7 1.9V21c0 .3.2.6.7.5A10 10 0 0 0 12 2z" />,
    arrow: P("M5 12h14M13 6l6 6-6 6"),
    check: P("M5 12l5 5L20 7"),
    x: P("M6 6l12 12M18 6L6 18"),
    pin: <>{P("M12 21s-7-6.2-7-12a7 7 0 0 1 14 0c0 5.8-7 12-7 12z")}<circle cx="12" cy="9" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.7" /></>,
    layers: <>{P("M12 3l9 5-9 5-9-5z")}{P("M3 13l9 5 9-5")}</>,
    storm: <>{P("M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0")}{P("M12 3c-5 0-8 4-8 7M12 21c5 0 8-4 8-7M3 12c0 3 2 6 6 7M21 12c0-3-2-6-6-7")}</>,
    book: <>{P("M4 4h11a3 3 0 0 1 3 3v13H7a3 3 0 0 1-3-3z")}{P("M4 17a3 3 0 0 1 3-3h11")}</>,
    flow: <>{P("M4 6h6v4H4zM14 14h6v4h-6zM10 8h4a2 2 0 0 1 2 2v4")}</>,
    info: <>{P("M12 8v.01M11 12h1v5h1")}<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.7" /></>,
    cpu: <>{P("M7 7h10v10H7zM10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4")}</>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>{paths[name]}</svg>;
};

export function useTheme() {
  const [t, setT] = useState<string>(() => { try { return localStorage.getItem("theme") || "light"; } catch { return "dark"; } });
  useEffect(() => {
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem("theme", t); } catch { /* private mode */ }
  }, [t]);
  return [t, () => setT(t === "dark" ? "light" : "dark")] as const;
}

const LINKS = [["/explore", "Explore", "map"], ["/lab", "Lab", "flask"], ["/models", "Models", "cube"],
  ["/evidence", "Evidence", "chart"], ["/pipeline", "Pipeline", "flow"], ["/story", "Story", "book"],
  ["/reports", "Reports", "info"]] as const;

export function Nav() {
  const [theme, toggle] = useTheme();
  return (
    <>
      <nav className="nav">
        <div className="wrap">
          <Link to="/" className="logo"><Leaf />EcoRewind</Link>
          <div className="nav-links">{LINKS.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}</div>
          <div className="nav-tools">
            <button className="icon-btn" onClick={toggle} aria-label="Toggle theme"><Icon name={theme === "dark" ? "sun" : "moon"} /></button>
            <a className="icon-btn" href="https://github.com/DAISHINKAN7/EcoRewind2" aria-label="GitHub" target="_blank" rel="noreferrer"><Icon name="github" /></a>
          </div>
        </div>
      </nav>
      <div className="tabbar">{LINKS.slice(0, 5).map(([to, label, ic]) => <NavLink key={to} to={to}><Icon name={ic} />{label}</NavLink>)}</div>
    </>
  );
}

export const Footer = ({ generated }: { generated?: string }) => (
  <footer className="footer">
    <div className="wrap">
      <div className="foot-word">EcoRewind</div>
      <div className="foot-grid">
        <div><h5>About</h5><p className="muted" style={{ margin: 0, maxWidth: 440 }}>Counterfactual satellite forecasting for coastal wetlands after hurricanes: a benchmark
          and a cautionary study, pre-registered and tested against itself. Data build {generated || "—"}.</p></div>
        <div><h5>Explore</h5>{LINKS.map(([to, label]) => <Link key={to} to={to}>{label}</Link>)}</div>
        <div><h5>Data</h5><span className="dim" style={{ fontSize: 12.5, lineHeight: 1.7 }}>Contains modified Copernicus Sentinel-1/2 data · NASA HLS · ESA WorldCover ·
          Copernicus DEM · NOAA HURDAT2 · processed with Google Earth Engine</span>
          <a href="https://github.com/DAISHINKAN7/EcoRewind2" target="_blank" rel="noreferrer" style={{ marginTop: 10 }}>Source on GitHub →</a></div>
      </div>
    </div>
  </footer>
);

export const Verdict = ({ pass, label }: { pass: boolean | null | undefined; label?: string }) =>
  pass == null ? <span className="badge none">{label ?? "untested"}</span>
    : <span className={`badge ${pass ? "pass" : "fail"}`}><Icon name={pass ? "check" : "x"} size={11} />{label ?? (pass ? "PASS" : "FAIL")}</span>;

export const Seg = <T extends string>({ value, options, onChange, violet }: {
  value: T; options: [T, string][]; onChange: (v: T) => void; violet?: boolean }) => (
  <div className={`seg${violet ? " violet" : ""}`} role="tablist">
    {options.map(([v, l]) => <button key={v} className={v === value ? "on" : ""} onClick={() => onChange(v)} role="tab" aria-selected={v === value}>{l}</button>)}
  </div>
);

export const Source = ({ text }: { text: string }) => (
  <span className="chip" title={text} style={{ fontSize: 11 }}><Icon name="info" size={12} />source</span>
);

export const Empty = ({ title, children }: { title: string; children: ReactNode }) => (
  <div className="card" style={{ textAlign: "center", padding: 40 }}>
    <h3>{title}</h3><div className="muted" style={{ maxWidth: 560, margin: "8px auto 0" }}>{children}</div>
  </div>
);
