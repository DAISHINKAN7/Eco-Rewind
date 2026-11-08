import { useEffect, useState } from "react";
import { BASE, fetchJSON, MapSite, Results } from "./data";
import { isPlacebo, leadKey } from "./derive";

export type Pixels = {
  keys: string[]; r: number[]; c: number[]; fold: number[]; observed: (number | null)[][];
  cf: Record<string, Record<string, { keys: string[]; leads: number[]; q10: (number | null)[][]; q50: (number | null)[][]; q90: (number | null)[][] }>>;
};

export const layerURL = (st: string, p: string) => `${BASE}layers/${st}/${p}`;
export const cfPath = (model: string, cut: string, kind: "cf_ndvi" | "deficit" | "width", lead: number) => `${model}/${cut}/${kind}_L${lead}.png`;

/** Fetch the per-pixel samples lazily, with progress. */
export function usePixels(st: string | null) {
  const [s, set] = useState<{ data: Pixels | null; loading: boolean }>({ data: null, loading: false });
  useEffect(() => {
    if (!st) return;
    let live = true;
    set({ data: null, loading: true });
    fetchJSON<Pixels>(`pixels/${st}.json`).then((d) => live && set({ data: d, loading: false }));
    return () => { live = false; };
  }, [st]);
  return s;
}

const qnum = (k: string) => { const m = k.match(/^(\d{4})Q(\d)/); return m ? +m[1] * 4 + +m[2] - 1 : 0; };
export const sortKeys = (keys: string[]) => [...keys].sort((a, b) => qnum(a) - qnum(b) || (a.length - b.length));

/** Nearest quarter (by time) that has an image of `kind`; ties go to the earlier quarter. */
export function nearestKey(m: MapSite, key: string, kind: "obs_rgb" | "obs_ndvi" = "obs_rgb") {
  const t = qnum(key) + (key.includes("POST") ? 0.4 : 0);
  let best: string | null = null, bd = 1e9;
  for (const k of sortKeys(m.keys)) {
    if (!m.layers[`${kind}_${k}.png`]) continue;
    const d = Math.abs(qnum(k) - t);
    if (d < bd) { bd = d; best = k; }
  }
  return best;
}

/** Quarters with imagery, ordered. */
export const imageKeys = (m: MapSite) => sortKeys(m.keys.filter((k) => m.layers[`obs_rgb_${k}.png`]));

/** Models with counterfactual layers for this cutoff. */
export const modelsFor = (m: MapSite, cut: string) =>
  m.cutoffs[cut] ? m.models.filter((id) => m.cutoffs[cut].leads.some((l) => m.layers[cfPath(id, cut, "cf_ndvi", l)])) : [];

/** Mean (cf − observed) over the sampled pixels, per lead -> rough attribution for every model incl. variants. */
export function sampleDeficits(px: Pixels | null, cut: string) {
  const out: Record<string, { leads: number[]; mean: (number | null)[]; n: number[] }> = {};
  if (!px) return out;
  for (const [model, byCut] of Object.entries(px.cf)) {
    const c = byCut[cut];
    if (!c) continue;
    const idx = c.keys.map((k) => px.keys.indexOf(k));
    const mean: (number | null)[] = [], n: number[] = [];
    c.keys.forEach((_, j) => {
      let s = 0, k = 0;
      if (idx[j] >= 0) for (let p = 0; p < px.r.length; p++) {
        const q = c.q50[p]?.[j], o = px.observed[p]?.[idx[j]];
        if (q != null && o != null) { s += q - o; k++; }
      }
      mean.push(k ? s / k : null); n.push(k);
    });
    out[model] = { leads: c.leads, mean, n };
  }
  return out;
}

/** Nearest sampled pixel to an image fraction (u, v). */
export function nearestSample(px: Pixels | null, shape: [number, number], uv: [number, number]) {
  if (!px) return null;
  const r0 = uv[1] * shape[0], c0 = uv[0] * shape[1];
  let best = -1, bd = 1e18;
  for (let i = 0; i < px.r.length; i++) { const d = (px.r[i] - r0) ** 2 + (px.c[i] - c0) ** 2; if (d < bd) { bd = d; best = i; } }
  return best < 0 ? null : { i: best, dist: Math.sqrt(bd), uv: [(px.c[best] + 0.5) / shape[1], (px.r[best] + 0.5) / shape[0]] as [number, number] };
}

/** Time axis + series for one sampled pixel: observed record, each model's counterfactual median (+ band). */
export function pixelSeries(px: Pixels, i: number, cut: string) {
  const lead0 = leadKey(cut, 0);
  const keys = sortKeys(px.keys.filter((k) => !k.includes("POST") || k === lead0));
  const at = (k: string) => px.keys.indexOf(k);
  const obs = keys.map((k) => px.observed[i]?.[at(k)] ?? null);
  const models: Record<string, { q50: (number | null)[]; q10: (number | null)[]; q90: (number | null)[] }> = {};
  for (const [m, byCut] of Object.entries(px.cf)) {
    const c = byCut[cut];
    if (!c) continue;
    const q50 = keys.map(() => null as number | null), q10 = [...q50], q90 = [...q50];
    c.keys.forEach((k, j) => { const t = keys.indexOf(k); if (t >= 0) { q50[t] = c.q50[i]?.[j] ?? null; q10[t] = c.q10[i]?.[j] ?? null; q90[t] = c.q90[i]?.[j] ?? null; } });
    // connect the forecast to the last observation before the cutoff so lines read as a branch
    const first = q50.findIndex((v) => v != null);
    if (first > 0) { const prev = [...obs.slice(0, first)].reverse().findIndex((v) => v != null); if (prev >= 0) { const t = first - 1 - prev; q50[t] = obs[t]; } }
    models[m] = { q50, q10, q90 };
  }
  const landfall = keys.indexOf(lead0);
  return { keys, label: keys.map((k) => k.replace(/_P?POST$/, "★")), obs, models, landfall };
}

/** Skill (NDVI R²) for any model: pre-registered leaderboard for the main models, Phase 5 test R² for variants. */
export function skillAny(r: Results | null, id: string, site: string, track: string): { v: number; src: "leaderboard" | "phase5" } | null {
  const l = r?.leaderboard.find((x) => x.model === id && x.site === site && x.track === track);
  if (l) return { v: l.NDVI, src: "leaderboard" };
  const p = (r?.phase5 ?? []).filter((x) => String(x.model).replace(/_s\d+$/, "") === id && x.site === site && x.track === track && x.test_r2 != null);
  return p.length ? { v: p.reduce((a, b) => a + +b.test_r2, 0) / p.length, src: "phase5" } : null;
}

export const placeboCuts = (m: MapSite | undefined) => (m ? Object.keys(m.cutoffs).filter(isPlacebo).sort() : []);

/** Debounced value (for heavy recomputation like ensemble maps). */
export function useDebounced<T>(v: T, ms = 250) {
  const [d, set] = useState(v);
  useEffect(() => { const t = setTimeout(() => set(v), ms); return () => clearTimeout(t); }, [JSON.stringify(v), ms]);
  return d;
}
