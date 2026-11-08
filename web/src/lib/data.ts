import { MODEL_META } from "./models";
import { useEffect, useState } from "react";

// Everything shown on the site comes from these files (built by scripts/build_web_data.py from the run outputs).
// Where the data lives: same site by default; set VITE_DATA_BASE (e.g. a Hugging Face dataset or a CDN, with a trailing
// slash and CORS enabled) to host the ~1 GB of map layers separately from the app.
const envBase = (import.meta.env.VITE_DATA_BASE as string | undefined)?.trim();
export const BASE = envBase ? (envBase.endsWith("/") ? envBase : envBase + "/") : import.meta.env.BASE_URL + "data/";

export type Registry = {
  id: string; name: string; family: "baseline" | "deep" | "ablation" | "experimental" | "expanded";
  status: "planned" | "running" | "done" | "withdrawn"; parent: string | null; variant: Record<string, string> | null;
  preregistered: boolean; uses_post_cutoff_info: boolean; params: number | null; run_prefix: string | null;
  lab_exportable: boolean; tags: string[];
};
export type Leader = { site: string; track: string; model: string; NDVI: number; NDMI: number; NDWI: number;
  rmse: number; coverage: number; width?: number; seeds?: number[] };
export type Verdict = { stat: "primary" | "lead0"; site: string; track: string; event: string; model: string;
  event_median: number; event_min: number; placebo_p95: number; placebo_min: number; placebo_max: number;
  frac_above: number; coverage: number; pass: boolean; n_event: number; n_placebo: number };
export type Space = { site: string; track: string; event: string; model: string; map: string; inland: number; all: number };
export type Attr = { event: string; site: string; track: string; stat: string; model: string; deficit: number;
  lo: number | null; hi: number | null; total: number; placebo: "pass" | "fail" | null };
export type Ext = { event: string; site: string; track: string; map: string; model: string; covariate: string;
  rho: number; lo: number; hi: number; blocks?: number };
export type Results = {
  generated: string; registry: Registry[]; leaderboard: Leader[]; verdict: Verdict[]; space: Space[];
  attribution: Attr[]; external: Ext[]; phase5: Record<string, any>[];
  carbon: { verified: boolean; rows: Record<string, any>[] }; compute: Record<string, string>[];
};
export type MapSite = { coordinates: number[][]; shape: [number, number]; keys: string[]; models: string[];
  cutoffs: Record<string, { leads: number[] }>; layers: Record<string, boolean> };
export type Maps = Record<string, MapSite>;

const cache: Record<string, Promise<any>> = {};
export function fetchJSON<T>(path: string): Promise<T | null> {
  if (!cache[path]) cache[path] = fetch(BASE + path).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  return cache[path];
}
export function useJSON<T>(path: string | null): { data: T | null; loading: boolean } {
  const [s, set] = useState<{ data: T | null; loading: boolean }>({ data: null, loading: !!path });
  useEffect(() => {
    if (!path) return;
    let live = true;
    set({ data: null, loading: true });
    fetchJSON<T>(path).then((d) => live && set({ data: d, loading: false }));
    return () => { live = false; };
  }, [path]);
  return s;
}
export const useResults = () => useJSON<Results>("results.json");
export const useMaps = () => useJSON<Maps>("maps.json");

// ---------------------------------------------------------------- display metadata
export const SITES: Record<string, { name: string; storm: string; landfall: string; center: [number, number];
  zoom: number; cat: string }> = {
  mississippi: { name: "Barataria Bay, Louisiana", storm: "Ida", landfall: "29 Aug 2021", center: [-90.0, 29.4], zoom: 9.4, cat: "Category 4" },
  everglades: { name: "Everglades, Florida", storm: "Irma", landfall: "10 Sep 2017", center: [-81.0, 25.35], zoom: 9.4, cat: "Category 4" },
};
export const EVENT_SITE: Record<string, string> = { ida: "mississippi", irma: "everglades" };
export const TRACKS: Record<string, string> = { A: "10 m Sentinel-2", B: "30 m HLS (Landsat + S2)" };

const NAMES: Record<string, string> = {
  persistence: "Persistence", climatology: "Climatology", harmonic: "Harmonic (trend)",
  harmonic_notrend: "Harmonic (no trend)", synth_control: "Synthetic control", lgbm: "LightGBM",
  convlstm: "ConvLSTM", simvp: "SimVP", ecotransformer: "EcoTransformer v2",
};
export const modelName = (id: string, reg?: Registry[]) =>
  MODEL_META[id]?.name ?? NAMES[id] ?? reg?.find((r) => r.id === id)?.name ?? id.replace(/_/g, " ");
export const COLORS: Record<string, string> = {
  persistence: "#94a3b8", climatology: "#e9c46a", harmonic: "#f4a261", harmonic_notrend: "#fbbf24",
  synth_control: "#5eead4", lgbm: "#60a5fa", convlstm: "#f472b6", simvp: "#a78bfa", ecotransformer: "#34d399",
};
export const colorOf = (m: string) => MODEL_META[m]?.color ?? COLORS[m.replace(/__.*$/, "")] ?? "#8fa39a";

export const fmt = (v: number | null | undefined, d = 3, sign = false) =>
  v == null || Number.isNaN(v) ? "—" : (sign && v > 0 ? "+" : "") + v.toFixed(d);
export const pct = (v: number | null | undefined, d = 0) => (v == null ? "—" : (v * 100).toFixed(d) + "%");
export const quarterLabel = (k: string) => {
  const m = k.match(/^(\d{4})Q(\d)(_P?POST)?$/);
  if (!m) return k;
  const months = ["Jan–Mar", "Apr–Jun", "Jul–Sep", "Oct–Dec"];
  return m[3] ? `${m[1]} post-landfall` : `${months[+m[2] - 1]} ${m[1]}`;
};
