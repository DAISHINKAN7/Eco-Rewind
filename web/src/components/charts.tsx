import { ReactNode, useState } from "react";
import { colorOf, fmt } from "../lib/data";

type Pt = { label: string; v: number; lo?: number | null; hi?: number | null; color?: string; faded?: boolean; tag?: ReactNode };

const scale = (d0: number, d1: number, r0: number, r1: number) => (v: number) => r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0);
const ticks = (a: number, b: number, n = 5) => {
  const step = Math.pow(10, Math.floor(Math.log10((b - a) / n || 1)));
  const s = [1, 2, 2.5, 5, 10].map((m) => m * step).find((m) => (b - a) / m <= n) ?? step;
  const out = [];
  for (let v = Math.ceil(a / s) * s; v <= b + 1e-9; v += s) out.push(+v.toFixed(6));
  return out;
};

/** Forest plot: one row per model, point + interval, zero line. */
export function Forest({ rows, unit = "NDVI", width = 560 }: { rows: Pt[]; unit?: string; width?: number }) {
  const all = rows.flatMap((r) => [r.v, r.lo ?? r.v, r.hi ?? r.v]);
  const lo = Math.min(0, ...all), hi = Math.max(0, ...all);
  const pad = (hi - lo) * 0.08 || 0.01;
  const L = 150, R = width - 70, rowH = 26, H = rows.length * rowH + 30;
  const x = scale(lo - pad, hi + pad, L, R);
  return (
    <div className="chart-wrap"><svg width="100%" viewBox={`0 0 ${width} ${H}`} role="img" aria-label="forest plot">
      {ticks(lo - pad, hi + pad).map((t) => <g key={t}><line x1={x(t)} x2={x(t)} y1={4} y2={H - 22} stroke="var(--line)" />
        <text x={x(t)} y={H - 6} textAnchor="middle">{t}</text></g>)}
      <line x1={x(0)} x2={x(0)} y1={0} y2={H - 22} stroke="var(--muted)" strokeDasharray="3 3" />
      {rows.map((r, i) => {
        const y = 14 + i * rowH;
        return <g key={r.label} opacity={r.faded ? 0.35 : 1}>
          <text x={L - 12} y={y + 4} textAnchor="end" style={{ fill: "var(--text)" }}>{r.label}</text>
          {r.lo != null && r.hi != null && <line x1={x(r.lo)} x2={x(r.hi)} y1={y} y2={y} stroke={r.color} strokeWidth={2} opacity={0.55} />}
          <circle cx={x(r.v)} cy={y} r={5.5} fill={r.color} />
          <text x={R + 8} y={y + 4} className="mono" style={{ fill: "var(--text)" }}>{fmt(r.v, 3, true)}</text>
        </g>;
      })}
      <text x={R + 8} y={H - 6}>{unit}</text>
    </svg></div>
  );
}

/** Placebo-in-time: placebo range band, 95th percentile line, event median marker, per model. */
export function PlaceboStrip({ rows, width = 640 }: { rows: { label: string; pmin: number; pmax: number; p95: number;
  ev: number; evmin: number; pass: boolean; faded?: boolean }[]; width?: number }) {
  const all = rows.flatMap((r) => [r.pmin, r.pmax, r.ev, r.evmin]);
  const lo = Math.min(...all), hi = Math.max(...all), pad = (hi - lo) * 0.06 || 0.01;
  const L = 150, R = width - 30, rowH = 30, H = rows.length * rowH + 30;
  const x = scale(lo - pad, hi + pad, L, R);
  return (
    <div className="chart-wrap"><svg width="100%" viewBox={`0 0 ${width} ${H}`} role="img" aria-label="placebo test per model">
      {ticks(lo - pad, hi + pad).map((t) => <g key={t}><line x1={x(t)} x2={x(t)} y1={4} y2={H - 22} stroke="var(--line)" />
        <text x={x(t)} y={H - 6} textAnchor="middle">{t}</text></g>)}
      <line x1={x(0)} x2={x(0)} y1={0} y2={H - 22} stroke="var(--muted)" strokeDasharray="3 3" />
      {rows.map((r, i) => {
        const y = 16 + i * rowH;
        return <g key={r.label} opacity={r.faded ? 0.4 : 1}>
          <text x={L - 12} y={y + 4} textAnchor="end" style={{ fill: "var(--text)" }}>{r.label}</text>
          <rect x={x(r.pmin)} y={y - 7} width={Math.max(2, x(r.pmax) - x(r.pmin))} height={14} rx={7} fill="var(--placebo)" opacity={0.22} />
          <line x1={x(r.p95)} x2={x(r.p95)} y1={y - 10} y2={y + 10} stroke="var(--placebo)" strokeWidth={2} />
          <line x1={x(r.evmin)} x2={x(r.ev)} y1={y} y2={y} stroke="var(--observed)" strokeWidth={1.5} opacity={0.6} />
          <circle cx={x(r.ev)} cy={y} r={6} fill="var(--observed)" stroke={r.pass ? "var(--pass)" : "var(--fail)"} strokeWidth={2} />
        </g>;
      })}
    </svg></div>
  );
}

/** Grouped bars, e.g. skill per model per site. */
export function Bars({ groups, series, height = 240, max = 1, min = 0, fmtv = (v: number) => v.toFixed(2) }: {
  groups: string[]; series: { name: string; color: string; values: (number | null)[]; hatch?: boolean }[];
  height?: number; max?: number; min?: number; fmtv?: (v: number) => string }) {
  const W = 720, L = 36, B = height - 26, T = 10;
  const gw = (W - L - 10) / groups.length, bw = Math.min(26, (gw - 14) / series.length);
  const y = scale(min, max, B, T);
  const [hov, setHov] = useState<string | null>(null);
  return (
    <div className="chart-wrap"><svg width="100%" viewBox={`0 0 ${W} ${height}`} role="img" aria-label="bar chart">
      {ticks(min, max, 5).map((t) => <g key={t}><line x1={L} x2={W} y1={y(t)} y2={y(t)} stroke="var(--line)" />
        <text x={L - 6} y={y(t) + 4} textAnchor="end">{t}</text></g>)}
      {groups.map((g, gi) => {
        const x0 = L + gi * gw + (gw - bw * series.length) / 2;
        return <g key={g}>
          {series.map((s, si) => {
            const v = s.values[gi];
            if (v == null) return null;
            const yy = y(Math.max(min, v));
            const k = `${g}-${s.name}`;
            return <g key={s.name} onMouseEnter={() => setHov(k)} onMouseLeave={() => setHov(null)}>
              <rect x={x0 + si * bw + 1} y={yy} width={bw - 2} height={Math.max(1, B - yy)} rx={3} fill={s.color} opacity={hov && hov !== k ? 0.45 : 0.92} />
              {hov === k && <text x={x0 + si * bw + bw / 2} y={yy - 5} textAnchor="middle" style={{ fill: "var(--text)" }}>{fmtv(v)}</text>}
            </g>;
          })}
          <text x={L + gi * gw + gw / 2} y={height - 8} textAnchor="middle">{g}</text>
        </g>;
      })}
    </svg></div>
  );
}

/** Line chart with optional bands (time series, training curves). */
export function Lines({ x, series, height = 220, yLabel, marker, ymin, ymax }: {
  x: string[]; series: { name: string; color: string; values: (number | null)[]; band?: [(number | null)[], (number | null)[]]; dash?: boolean }[];
  height?: number; yLabel?: string; marker?: number; ymin?: number; ymax?: number }) {
  const W = 720, L = 40, R = W - 10, T = 10, B = height - 30;
  const vals = series.flatMap((s) => [...s.values, ...(s.band ? [...s.band[0], ...s.band[1]] : [])]).filter((v): v is number => v != null && isFinite(v));
  const lo = ymin ?? Math.min(...vals), hi = ymax ?? Math.max(...vals), pad = ymin != null ? 0 : (hi - lo) * 0.08 || 0.05;
  const xs = scale(0, Math.max(1, x.length - 1), L, R), ys = scale(lo - pad, hi + pad, B, T);
  const path = (v: (number | null)[]) => v.map((p, i) => (p == null ? null : `${xs(i)},${ys(p)}`)).reduce((acc, p, i) =>
    p == null ? acc : acc + (i === 0 || v[i - 1] == null ? "M" : "L") + p, "");
  const every = Math.max(1, Math.ceil(x.length / 9));
  return (
    <div className="chart-wrap"><svg width="100%" viewBox={`0 0 ${W} ${height}`} role="img" aria-label={yLabel ?? "line chart"}>
      {ticks(lo - pad, hi + pad, 4).map((t) => <g key={t}><line x1={L} x2={R} y1={ys(t)} y2={ys(t)} stroke="var(--line)" />
        <text x={L - 6} y={ys(t) + 4} textAnchor="end">{t}</text></g>)}
      {x.map((k, i) => i % every === 0 && <text key={k} x={xs(i)} y={height - 10} textAnchor="middle">{k}</text>)}
      {marker != null && <g><line x1={xs(marker)} x2={xs(marker)} y1={T} y2={B} stroke="var(--text)" strokeDasharray="4 4" opacity={0.7} />
        <text x={xs(marker) + 5} y={T + 10} style={{ fill: "var(--text)" }}>landfall</text></g>}
      {series.map((s) => s.band && (() => {
        const [a, b] = s.band!;
        const top = a.map((v, i) => (v == null || b[i] == null ? null : `${xs(i)},${ys(b[i]!)}`)).filter(Boolean);
        const bot = a.map((v, i) => (v == null || b[i] == null ? null : `${xs(i)},${ys(v)}`)).filter(Boolean).reverse();
        return top.length ? <polygon key={s.name + "b"} points={[...top, ...bot].join(" ")} fill={s.color} opacity={0.16} /> : null;
      })())}
      {series.map((s) => <path key={s.name} d={path(s.values) || undefined} fill="none" stroke={s.color} strokeWidth={2.2} strokeDasharray={s.dash ? "5 4" : undefined} />)}
      {series.map((s) => s.values.map((v, i) => v != null && <circle key={s.name + i} cx={xs(i)} cy={ys(v)} r={2.4} fill={s.color} />))}
    </svg></div>
  );
}

/** Scatter with label collision avoidance (labels move to free slots, with a leader line when displaced). */
export function Scatter({ pts, xLabel, yLabel, xr = [0, 1], yr = [0, 1], height = 380, yfmt }: {
  pts: { id: string; label: string; x: number; y: number; r?: number; color: string; ring?: boolean }[]; xLabel: string; yLabel: string;
  xr?: [number, number]; yr?: [number, number]; height?: number; yfmt?: (v: number) => string }) {
  const W = 600, H = height, L = 52, R = W - 16, T = 18, B = H - 44;
  const x = scale(xr[0], xr[1], L, R), y = scale(yr[0], yr[1], B, T);
  const [hov, setHov] = useState<string | null>(null);
  // greedy label placement
  type Box = [number, number, number, number];
  const hit = (a: Box, b: Box) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
  const placed: Box[] = pts.map((p) => { const r = (p.r ?? 8) + 1; return [x(p.x) - r, y(p.y) - r, x(p.x) + r, y(p.y) + r]; });
  const labels = [...pts].sort((a, b) => b.y - a.y || a.x - b.x).map((p) => {
    const px = x(p.x), py = y(p.y), r = p.r ?? 8, w = p.label.length * 6.3 + 4, h = 13;
    const cands: [number, number][] = [[r + 6, -h / 2], [-r - 6 - w, -h / 2], [r + 4, -r - h], [r + 4, r], [-w / 2, -r - h - 3], [-w / 2, r + 3]];
    for (let k = 1; k < 9; k++) cands.push([r + 10, -h / 2 + k * 15], [r + 10, -h / 2 - k * 15], [-r - 10 - w, -h / 2 + k * 15]);
    let best = cands[cands.length - 1];
    for (const c of cands) {
      const bx: Box = [px + c[0], py + c[1], px + c[0] + w, py + c[1] + h];
      if (bx[0] < L || bx[2] > W - 2 || bx[1] < 2 || bx[3] > B) continue;
      if (!placed.some((q) => hit(q, bx))) { best = c; break; }
    }
    const bx: Box = [px + best[0], py + best[1], px + best[0] + w, py + best[1] + h];
    placed.push(bx);
    const far = Math.abs(best[1] + h / 2) > r + 8 || best[0] > r + 8;
    return { p, bx, far };
  });
  return (
    <div className="chart-wrap"><svg width="100%" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="scatter">
      {ticks(xr[0], xr[1], 5).map((t) => <g key={"x" + t}><line x1={x(t)} x2={x(t)} y1={T} y2={B} stroke="var(--line)" /><text x={x(t)} y={B + 16} textAnchor="middle">{t}</text></g>)}
      {ticks(yr[0], yr[1], 5).map((t) => <g key={"y" + t}><line x1={L} x2={R} y1={y(t)} y2={y(t)} stroke="var(--line)" /><text x={L - 8} y={y(t) + 4} textAnchor="end">{yfmt ? yfmt(t) : t}</text></g>)}
      <text x={(L + R) / 2} y={H - 6} textAnchor="middle">{xLabel}</text>
      <text x={12} y={(T + B) / 2} transform={`rotate(-90 12 ${(T + B) / 2})`} textAnchor="middle">{yLabel}</text>
      {labels.map(({ p, bx, far }) => far && <line key={p.id + "l"} x1={x(p.x)} y1={y(p.y)} x2={bx[0] < x(p.x) ? bx[2] : bx[0]} y2={(bx[1] + bx[3]) / 2} stroke="var(--muted)" strokeWidth={0.7} opacity={0.6} />)}
      {pts.map((p) => <circle key={p.id} cx={x(p.x)} cy={y(p.y)} r={p.r ?? 8} fill={p.ring ? "var(--bg)" : p.color} stroke={p.ring ? p.color : "var(--bg)"} strokeWidth={p.ring ? 2.5 : 2}
        opacity={hov && hov !== p.id ? 0.3 : 0.95} onMouseEnter={() => setHov(p.id)} onMouseLeave={() => setHov(null)} />)}
      {labels.map(({ p, bx }) => <text key={p.id + "t"} x={bx[0] + 2} y={bx[3] - 3} style={{ fill: hov === p.id ? "var(--cf)" : "var(--text)", fontSize: 11 }}
        opacity={hov && hov !== p.id ? 0.35 : 1}>{p.label}</text>)}
    </svg></div>
  );
}

export const legendItem = (label: string, color: string) => (
  <span key={label} style={{ display: "inline-flex", alignItems: "center", marginRight: 14, fontSize: 12.5, color: "var(--muted)" }}>
    <span className="dot" style={{ background: color }} />{label}
  </span>
);
export { colorOf };

export type TSeries = { id: string; name: string; color: string; values: (number | null)[]; band?: [(number | null)[], (number | null)[]];
  width?: number; dash?: boolean; opacity?: number; dots?: boolean };
/** Multi-series time chart with hover read-out, highlighted series, shaded window and an event marker. */
export function TimeChart({ x, series, height = 230, marker, markerLabel = "landfall", shade, ymin, ymax, focus, onFocus, unit = "", width = 720 }: {
  x: string[]; series: TSeries[]; height?: number; marker?: number; markerLabel?: string; shade?: [number, number];
  ymin?: number; ymax?: number; focus?: string; onFocus?: (id: string) => void; unit?: string; width?: number }) {
  const W = width, L = 40, R = W - 10, T = 12, B = height - 26;
  const vals = series.flatMap((s) => [...s.values, ...(s.band ? [...s.band[0], ...s.band[1]] : [])]).filter((v): v is number => v != null && isFinite(v));
  const lo0 = ymin ?? (vals.length ? Math.min(...vals) : 0), hi0 = ymax ?? (vals.length ? Math.max(...vals) : 1);
  const pad = (hi0 - lo0) * 0.08 || 0.05, lo = ymin ?? lo0 - pad, hi = ymax ?? hi0 + pad;
  const xs = scale(0, Math.max(1, x.length - 1), L, R), ys = scale(lo, hi, B, T);
  const [hov, setHov] = useState<number | null>(null);
  const path = (v: (number | null)[]) => v.reduce((acc, p, i) => (p == null || !isFinite(p) ? acc : acc + (i === 0 || v[i - 1] == null ? "M" : "L") + `${xs(i).toFixed(1)},${ys(p).toFixed(1)}`), "");
  const every = Math.max(1, Math.ceil(x.length / Math.max(3, Math.floor(W / 80))));
  const ordered = [...series].sort((a, b) => (a.id === focus ? 1 : 0) - (b.id === focus ? 1 : 0));
  const move = (e: React.MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect(), px = ((e.clientX - r.left) / r.width) * W;
    setHov(Math.max(0, Math.min(x.length - 1, Math.round(((px - L) / (R - L)) * (x.length - 1)))));
  };
  const hv = hov != null ? series.map((s) => ({ s, v: s.values[hov] })).filter((o) => o.v != null).sort((a, b) => (b.v as number) - (a.v as number)) : [];
  return (
    <div className="chart-wrap" style={{ position: "relative" }}>
      <svg width="100%" viewBox={`0 0 ${W} ${height}`} role="img" aria-label="time series" onMouseMove={move} onMouseLeave={() => setHov(null)}>
        {shade && <rect x={xs(shade[0]) - 4} width={xs(shade[1]) - xs(shade[0]) + 8} y={T} height={B - T} fill="var(--cf)" opacity={0.06} rx={4} />}
        {ticks(lo, hi, 4).map((t) => <g key={t}><line x1={L} x2={R} y1={ys(t)} y2={ys(t)} stroke="var(--line)" />
          <text x={L - 6} y={ys(t) + 4} textAnchor="end">{t}</text></g>)}
        {x.map((k, i) => i % every === 0 && <text key={k + i} x={xs(i)} y={height - 8} textAnchor="middle">{k}</text>)}
        {marker != null && marker >= 0 && <g><line x1={xs(marker)} x2={xs(marker)} y1={T} y2={B} stroke="var(--fail)" strokeDasharray="4 4" opacity={0.8} />
          <text x={xs(marker) + 5} y={T + 10} style={{ fill: "var(--fail)" }}>{markerLabel}</text></g>}
        {ordered.map((s) => s.band && (() => {
          const [a, b] = s.band!;
          const top: string[] = [], bot: string[] = [];
          a.forEach((v, i) => { if (v != null && b[i] != null) { top.push(`${xs(i)},${ys(b[i]!)}`); bot.unshift(`${xs(i)},${ys(v)}`); } });
          return top.length ? <polygon key={s.id + "b"} points={[...top, ...bot].join(" ")} fill={s.color} opacity={0.16} /> : null;
        })())}
        {ordered.map((s) => {
          const f = focus == null || s.id === focus;
          return <path key={s.id} d={path(s.values) || undefined} fill="none" stroke={s.color} strokeWidth={s.width ?? (s.id === focus ? 2.6 : 1.4)}
            strokeDasharray={s.dash ? "5 4" : undefined} opacity={s.opacity ?? (f ? 1 : 0.38)} strokeLinejoin="round"
            style={{ cursor: onFocus ? "pointer" : undefined }} onClick={() => onFocus?.(s.id)} />;
        })}
        {ordered.filter((s) => s.dots).map((s) => s.values.map((v, i) => v != null && <circle key={s.id + i} cx={xs(i)} cy={ys(v)} r={2.3} fill={s.color} />))}
        {hov != null && <line x1={xs(hov)} x2={xs(hov)} y1={T} y2={B} stroke="var(--text)" opacity={0.25} />}
      </svg>
      {hov != null && hv.length > 0 && <div className="chart-tip" style={{ left: `${(xs(hov) / W) * 100}%`, transform: xs(hov) > W * 0.6 ? "translateX(calc(-100% - 10px))" : "translateX(10px)" }}>
        <div className="mono" style={{ marginBottom: 4 }}>{x[hov]}</div>
        {hv.slice(0, 10).map(({ s, v }) => <div key={s.id} style={{ display: "flex", gap: 8, justifyContent: "space-between", fontWeight: s.id === focus ? 600 : 400 }}>
          <span><span className="dot" style={{ background: s.color, width: 7, height: 7 }} />{s.name}</span><span className="mono">{fmt(v, 3)}{unit}</span></div>)}
        {hv.length > 10 && <div className="dim">+{hv.length - 10} more</div>}
      </div>}
    </div>
  );
}

/** Horizontal value bars around zero (per-model read-out at one pixel / one statistic). */
export function ValueBars({ rows, unit = "", span }: { rows: { id: string; label: string; v: number | null; color: string; faded?: boolean; tag?: ReactNode }[];
  unit?: string; span?: number }) {
  const m = span ?? Math.max(0.02, ...rows.map((r) => Math.abs(r.v ?? 0)));
  return (
    <div className="vbars">
      {rows.map((r) => <div key={r.id} className="vbar" style={{ opacity: r.faded ? 0.42 : 1 }}>
        <span className="vbar-l"><span className="dot" style={{ background: r.color }} />{r.label}</span>
        <span className="vbar-track">
          <span className="vbar-zero" />
          {r.v != null && <span className="vbar-fill" style={{ background: r.color, left: r.v >= 0 ? "50%" : `${50 - (Math.abs(r.v) / m) * 50}%`, width: `${(Math.min(Math.abs(r.v), m) / m) * 50}%` }} />}
        </span>
        <span className="vbar-v mono">{r.v == null ? "—" : fmt(r.v, 3, true)}{r.v == null ? "" : unit}</span>
        {r.tag}
      </div>)}
    </div>
  );
}
