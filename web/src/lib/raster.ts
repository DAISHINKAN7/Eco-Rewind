// Decode the colourised PNG layers back to physical values (the colour maps and scales are those of
// scripts/build_web_data.py CMAPS and scripts/export_demo.py SCALES), and compute ensemble maps in the browser.

export type Kind = "ndvi" | "deficit" | "width";
export const SCALES: Record<Kind, [number, number]> = { ndvi: [-0.2, 1.0], deficit: [-0.3, 0.3], width: [0, 0.6] };
const CMAPS: Record<Kind, [number, number[]][]> = {
  ndvi: [[0, [120, 72, 36]], [0.35, [200, 170, 90]], [0.6, [110, 170, 80]], [1, [20, 95, 50]]],
  deficit: [[0, [38, 70, 83]], [0.35, [42, 157, 143]], [0.5, [240, 240, 230]], [0.65, [244, 162, 97]], [0.85, [231, 111, 81]], [1, [155, 34, 38]]],
  width: [[0, [13, 8, 135]], [0.5, [204, 71, 120]], [1, [240, 249, 33]]],
};
export const kindOf = (path: string): Kind => (/ndvi/.test(path) ? "ndvi" : /deficit/.test(path) ? "deficit" : "width");

const interp = (stops: [number, number[]][], t: number) => {
  t = Math.max(0, Math.min(1, t));
  for (let i = 1; i < stops.length; i++) if (t <= stops[i][0]) {
    const [t0, c0] = stops[i - 1], [t1, c1] = stops[i], f = (t - t0) / (t1 - t0 || 1);
    return c0.map((c, k) => Math.floor(c + (c1[k] - c) * f));
  }
  return stops[stops.length - 1][1];
};
export const colorFor = (kind: Kind, v: number) => {
  const [lo, hi] = SCALES[kind];
  return interp(CMAPS[kind], (v - lo) / (hi - lo));
};
export const gradientCSS = (kind: Kind) => `linear-gradient(90deg, ${CMAPS[kind].map(([t, c]) => `rgb(${c.join(",")}) ${t * 100}%`).join(", ")})`;

// 255-entry lookup: colour -> u8 code -> value. A 32^3 cache keeps decoding of whole images fast.
const LUT: Partial<Record<Kind, { rgb: Int16Array; memo: Map<number, number> }>> = {};
function lut(kind: Kind) {
  if (!LUT[kind]) {
    const rgb = new Int16Array(255 * 3);
    for (let i = 0; i < 255; i++) { const c = interp(CMAPS[kind], i / 254); rgb.set(c, i * 3); }
    LUT[kind] = { rgb, memo: new Map() };
  }
  return LUT[kind]!;
}
export function decodeRGB(kind: Kind, r: number, g: number, b: number): number {
  const L = lut(kind), key = (r << 16) | (g << 8) | b;
  let code = L.memo.get(key);
  if (code === undefined) {
    let best = 0, bd = 1e9;
    for (let i = 0; i < 255; i++) {
      const dr = L.rgb[i * 3] - r, dg = L.rgb[i * 3 + 1] - g, db = L.rgb[i * 3 + 2] - b, d = dr * dr + dg * dg + db * db;
      if (d < bd) { bd = d; best = i; }
    }
    code = best; L.memo.set(key, code);
  }
  const [lo, hi] = SCALES[kind];
  return lo + (code / 254) * (hi - lo);
}

// ------------------------------------------------------------------ pixel access
type Px = { w: number; h: number; data: Uint8ClampedArray };
const pxCache = new Map<string, Promise<Px | null>>();
export function loadPixels(url: string): Promise<Px | null> {
  if (!pxCache.has(url)) {
    pxCache.set(url, new Promise((res) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        try {
          const c = document.createElement("canvas");
          c.width = img.naturalWidth; c.height = img.naturalHeight;
          const ctx = c.getContext("2d", { willReadFrequently: true })!;
          ctx.drawImage(img, 0, 0);
          res({ w: c.width, h: c.height, data: ctx.getImageData(0, 0, c.width, c.height).data });
        } catch { res(null); }
      };
      img.onerror = () => res(null);
      img.src = url;
    }));
    if (pxCache.size > 120) pxCache.delete(pxCache.keys().next().value!);  // bounded
  }
  return pxCache.get(url)!;
}
/** value at image fraction (u, v); null = no data */
export function valueAt(p: Px | null, kind: Kind, u: number, v: number): number | null {
  if (!p || u < 0 || v < 0 || u >= 1 || v >= 1) return null;
  const x = Math.floor(u * p.w), y = Math.floor(v * p.h), i = (y * p.w + x) * 4;
  if (p.data[i + 3] === 0) return null;
  return decodeRGB(kind, p.data[i], p.data[i + 1], p.data[i + 2]);
}

// ------------------------------------------------------------------ ensemble maps
export type EnsStat = "mean" | "agree" | "sd";
export type Ens = { url: string; n: number; meanAll: number | null; agreeAll: number | null; cells: number };
/** Per-pixel ensemble of deficit layers -> colourised PNG data URL + summary numbers. */
export async function ensemble(urls: string[], stat: EnsStat, thr = 0.05): Promise<Ens | null> {
  const ims = (await Promise.all(urls.map(loadPixels))).filter((p): p is Px => !!p);
  if (!ims.length) return null;
  const { w, h } = ims[0], n = w * h;
  const sum = new Float32Array(n), sq = new Float32Array(n), cnt = new Uint8Array(n), pos = new Uint8Array(n);
  for (const p of ims) {
    if (p.w !== w || p.h !== h) continue;
    const d = p.data;
    for (let i = 0; i < n; i++) {
      if (d[i * 4 + 3] === 0) continue;
      const v = decodeRGB("deficit", d[i * 4], d[i * 4 + 1], d[i * 4 + 2]);
      sum[i] += v; sq[i] += v * v; cnt[i]++; if (v > thr) pos[i]++;
    }
  }
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  const ctx = c.getContext("2d")!, out = ctx.createImageData(w, h);
  let mAll = 0, aAll = 0, k = 0;
  const need = Math.max(1, Math.ceil(ims.length / 2));
  for (let i = 0; i < n; i++) {
    if (cnt[i] < need) continue;
    const m = sum[i] / cnt[i], sd = Math.sqrt(Math.max(0, sq[i] / cnt[i] - m * m)), ag = pos[i] / cnt[i];
    mAll += m; aAll += ag; k++;
    let col: number[], a = 235;
    if (stat === "mean") { col = colorFor("deficit", m); a = Math.min(235, Math.max(40, Math.abs(m) / 0.3 * 255 * 2.2)); }
    else if (stat === "sd") col = colorFor("width", sd);
    else { col = colorFor("width", ag * 0.6); a = 60 + ag * 175; }
    out.data.set([col[0], col[1], col[2], a], i * 4);
  }
  ctx.putImageData(out, 0, 0);
  return { url: c.toDataURL(), n: ims.length, meanAll: k ? mAll / k : null, agreeAll: k ? aAll / k : null, cells: k };
}
