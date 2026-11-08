// Live forecasting engine: exact ports of the Python baselines in src/ecorewind/models/baselines/
// (simple.py: Persistence, Climatology; harmonic.py: Harmonic with Huber IRLS). Runs on any quarterly series.

export type Pt = { key: string; v: number | null };              // key "YYYYQn" (a "_POST" suffix is treated as its quarter)
export const qt = (k: string) => { const m = k.match(/^(\d{4})Q(\d)/); return m ? +m[1] * 4 + (+m[2] - 1) : NaN; };
export const season = (k: string) => (qt(k) % 4 + 4) % 4;
export const keyOf = (t: number) => `${Math.floor(t / 4)}Q${(t % 4) + 1}`;

export function persistence(hist: Pt[], tgt: string[]) {
  let last: number | null = null;
  for (const p of hist) if (p.v != null && isFinite(p.v)) last = p.v;
  return tgt.map(() => last);
}

export function climatology(hist: Pt[], tgt: string[]) {
  const s = [0, 0, 0, 0], n = [0, 0, 0, 0];
  let all = 0, na = 0;
  for (const p of hist) if (p.v != null && isFinite(p.v)) { s[season(p.key)] += p.v; n[season(p.key)]++; all += p.v; na++; }
  return tgt.map((k) => (n[season(k)] ? s[season(k)] / n[season(k)] : na ? all / na : null));
}

function design(t: number, t0: number, trend: boolean, semi = true) {
  const r = [1];
  if (trend) r.push((t - t0) / 4);
  r.push(Math.cos((2 * Math.PI * t) / 4), Math.sin((2 * Math.PI * t) / 4));
  if (semi) r.push(Math.cos(Math.PI * t));
  return r;
}
function solve(A: number[][], b: number[]) {                    // Gaussian elimination with partial pivoting
  const n = b.length, M = A.map((row, i) => [...row, b[i]]);
  for (let c = 0; c < n; c++) {
    let p = c; for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
    [M[c], M[p]] = [M[p], M[c]];
    for (let r = c + 1; r < n; r++) { const f = M[r][c] / (M[c][c] || 1e-12); for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k]; }
  }
  const x = Array(n).fill(0);
  for (let r = n - 1; r >= 0; r--) { let s = M[r][n]; for (let k = r + 1; k < n; k++) s -= M[r][k] * x[k]; x[r] = s / (M[r][r] || 1e-12); }
  return x;
}
const median = (a: number[]) => { const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

/** Huber-robust harmonic regression; falls back to climatology with too few points (as in Python). */
export function harmonic(hist: Pt[], tgt: string[], trend: boolean, iters = 5, k = 1.345, minObs = 7) {
  const obs = hist.filter((p) => p.v != null && isFinite(p.v)) as { key: string; v: number }[];
  const t0 = hist.length ? qt(hist[hist.length - 1].key) : 0;
  const P = design(0, 0, trend).length;
  if (obs.length < Math.max(minObs, P + 2)) return { pred: climatology(hist, tgt), beta: null as number[] | null, fallback: true };
  const X = obs.map((p) => design(qt(p.key), t0, trend)), y = obs.map((p) => p.v);
  let w = y.map(() => 1), beta = Array(P).fill(0);
  for (let it = 0; it < iters; it++) {
    const A = Array.from({ length: P }, (_, i) => Array.from({ length: P }, (_, j) => (i === j ? 1e-6 : 0))), b = Array(P).fill(0);
    X.forEach((x, n) => { for (let i = 0; i < P; i++) { b[i] += x[i] * w[n] * y[n]; for (let j = 0; j < P; j++) A[i][j] += x[i] * w[n] * x[j]; } });
    beta = solve(A, b);
    const res = X.map((x, n) => y[n] - x.reduce((s, v, i) => s + v * beta[i], 0));
    const scale = Math.max(1e-9, 1.4826 * median(res.map(Math.abs)));
    w = res.map((r) => { const u = Math.abs(r) / (k * scale); return u <= 1 ? 1 : 1 / Math.max(u, 1e-12); });
  }
  return { pred: tgt.map((kk) => design(qt(kk), t0, trend).reduce((s, v, i) => s + v * beta[i], 0)), beta, fallback: false };
}

/** In-sample residual band (labelled as such in the UI; the published intervals are conformal). */
export function residualBand(hist: Pt[], fit: (h: Pt[], k: string[]) => (number | null)[], q = 0.9) {
  const keys = hist.filter((p) => p.v != null).map((p) => p.key);
  const pred = fit(hist, keys), obs = hist.filter((p) => p.v != null).map((p) => p.v as number);
  const r = pred.map((p, i) => (p == null ? null : Math.abs(obs[i] - p))).filter((v): v is number => v != null).sort((a, b) => a - b);
  return r.length ? r[Math.min(r.length - 1, Math.floor(q * r.length))] : null;
}

export const ENGINES = [
  { id: "persistence", name: "Persistence", fit: (h: Pt[], t: string[]) => persistence(h, t) },
  { id: "climatology", name: "Seasonal climatology", fit: (h: Pt[], t: string[]) => climatology(h, t) },
  { id: "harmonic", name: "Harmonic (trend)", fit: (h: Pt[], t: string[]) => harmonic(h, t, true).pred },
  { id: "harmonic_notrend", name: "Harmonic (no trend)", fit: (h: Pt[], t: string[]) => harmonic(h, t, false).pred },
] as const;

/** Parse "2019Q3, 0.61" lines (also tab/semicolon separated; a header line is ignored). */
export function parseSeries(text: string): Pt[] {
  const out: Pt[] = [];
  for (const line of text.split(/\r?\n/)) {
    const m = line.trim().match(/^(\d{4})\s*[-_ ]?\s*Q([1-4])\s*[,;\t ]\s*(-?\d*\.?\d+|nan|NaN|)$/i);
    if (m) out.push({ key: `${m[1]}Q${m[2]}`, v: m[3] === "" || /nan/i.test(m[3]) ? null : +m[3] });
  }
  return out.sort((a, b) => qt(a.key) - qt(b.key));
}

/** Parse a user series with a report: errors stop the forecast, warnings explain fallbacks. */
export function parseReport(text: string) {
  const pts: Pt[] = [], errors: string[] = [], warnings: string[] = [];
  const seen = new Set<string>();
  text.split(/\r?\n/).forEach((raw, i) => {
    const line = raw.trim();
    if (!line || /^#/.test(line) || (i === 0 && /quarter|date|key/i.test(line))) return;
    const m = line.match(/^(\d{4})\s*[-_ ]?\s*Q([1-4])\s*[,;\t ]\s*(\S*)$/i);
    if (!m) { errors.push(`line ${i + 1}: "${line.slice(0, 40)}" is not "YYYYQn, value"`); return; }
    const key = `${m[1]}Q${m[2]}`, s = m[3];
    if (seen.has(key)) { errors.push(`line ${i + 1}: ${key} appears twice`); return; }
    seen.add(key);
    if (s === "" || /^(nan|na|null|-)$/i.test(s)) { pts.push({ key, v: null }); return; }
    const v = Number(s);
    if (!isFinite(v)) { errors.push(`line ${i + 1}: "${s}" is not a number`); return; }
    if (v < -1 || v > 1) { errors.push(`line ${i + 1}: ${v} is outside the NDVI range [−1, 1]`); return; }
    pts.push({ key, v });
  });
  pts.sort((a, b) => qt(a.key) - qt(b.key));
  return { pts, errors, warnings };
}

export const TEMPLATE = `quarter,ndvi
# Quarterly NDVI for one location. Lines starting with # are ignored. Leave a value empty or write nan for cloudy quarters.
2016Q1,0.41
2016Q2,0.58
2016Q3,0.66
2016Q4,0.49
2017Q1,0.43
2017Q2,0.60
2017Q3,0.69
2017Q4,0.51
2018Q1,0.40
2018Q2,
2018Q3,0.67
2018Q4,0.50
2019Q1,0.44
2019Q2,0.61
2019Q3,0.70
2019Q4,0.48
# values at or after the event quarter are optional: if present they are the "observed" truth and give a deficit
2020Q3,0.52
2020Q4,0.40
2021Q1,0.38
`;
