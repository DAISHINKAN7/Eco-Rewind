import { Attr, Results, Verdict } from "./data";

// cutoff name -> its cutoff quarter (event or fake landfall); all pre-registered dates fall in Q3
export const cutoffQuarter = (cut: string) => {
  const y = cut.match(/(\d{4})$/)?.[1] ?? (cut.startsWith("ida") ? "2021" : "2017");
  return { y: +y, q: 3 };
};
export const leadKey = (cut: string, lead: number) => {
  const { y, q } = cutoffQuarter(cut);
  if (lead === 0) return `${y}Q${q}_POST`;
  const t = (y * 4 + q - 1) + lead;
  return `${Math.floor(t / 4)}Q${(t % 4) + 1}`;
};
export const isPlacebo = (cut: string) => cut.includes("placebo");
export const cutoffLabel = (cut: string) =>
  isPlacebo(cut) ? `Placebo ${cut.match(/\d{4}/)?.[0]} (fake landfall)` : cut === "ida" ? "Hurricane Ida (2021)" : "Hurricane Irma (2017)";

export function verdictOf(r: Results | null, site: string, track: string, model: string, stat: "primary" | "lead0"): Verdict | undefined {
  return r?.verdict.find((v) => v.site === site && v.track === track && v.model === model && v.stat === stat);
}
export function attrOf(r: Results | null, site: string, track: string, event: string, model: string, stat: string): Attr | undefined {
  return r?.attribution.find((a) => a.site === site && a.track === track && a.event === event && a.model === model && a.stat === stat);
}
export const skillOf = (r: Results | null, model: string, site: string, track: string) =>
  r?.leaderboard.find((l) => l.model === model && l.site === site && l.track === track);

// float16 -> float32 (lab patches are stored as raw little-endian f16)
export function f16(buf: ArrayBuffer): Float32Array {
  const u = new Uint16Array(buf), out = new Float32Array(u.length);
  for (let i = 0; i < u.length; i++) {
    const h = u[i], s = h & 0x8000 ? -1 : 1, e = (h >> 10) & 0x1f, f = h & 0x3ff;
    out[i] = e === 0 ? s * Math.pow(2, -14) * (f / 1024) : e === 31 ? (f ? NaN : s * Infinity) : s * Math.pow(2, e - 15) * (1 + f / 1024);
  }
  return out;
}
const NDVI_STOPS: [number, number[]][] = [[0, [120, 72, 36]], [0.35, [200, 170, 90]], [0.6, [110, 170, 80]], [1, [20, 95, 50]]];
const DEF_STOPS: [number, number[]][] = [[0, [38, 70, 83]], [0.35, [42, 157, 143]], [0.5, [240, 240, 230]], [0.65, [244, 162, 97]], [0.85, [231, 111, 81]], [1, [155, 34, 38]]];
const interp = (stops: [number, number[]][], t: number) => {
  t = Math.max(0, Math.min(1, t));
  for (let i = 1; i < stops.length; i++) if (t <= stops[i][0]) {
    const [t0, c0] = stops[i - 1], [t1, c1] = stops[i], f = (t - t0) / (t1 - t0 || 1);
    return c0.map((c, k) => c + (c1[k] - c) * f);
  }
  return stops[stops.length - 1][1];
};
export const ndviColor = (v: number) => interp(NDVI_STOPS, (v + 0.2) / 1.2);
export const deficitColor = (v: number) => interp(DEF_STOPS, (v + 0.3) / 0.6);
