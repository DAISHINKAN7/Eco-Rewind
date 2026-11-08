// Read user imagery (GeoTIFF via geotiff.js, or PNG/JPG via canvas) and derive the model's spectral indices with the
// same definitions as src/ecorewind/data/indices.py: NDVI = (NIR−Red)/(NIR+Red); NDWI (McFeeters) = (Green−NIR)/(Green+NIR);
// NDMI = (NIR−SWIR1)/(NIR+SWIR1); invalid where an input is missing or the denominator is ~0.

export type Raster = { name: string; width: number; height: number; bands: Float32Array[]; resM: number | null; kind: "tiff" | "image" };

export async function readRaster(file: File): Promise<Raster> {
  if (/\.tiff?$/i.test(file.name)) {
    const { fromArrayBuffer } = await import("geotiff");
    const tiff = await fromArrayBuffer(await file.arrayBuffer());
    const img = await tiff.getImage();
    const width = img.getWidth(), height = img.getHeight();
    if (width * height > 4096 * 4096) throw new Error(`${file.name}: ${width}×${height} is too large; crop it below 4096×4096`);
    const ras = (await img.readRasters()) as unknown as ArrayLike<number>[];
    const nodata = img.getGDALNoData();
    const bands = Array.from(ras, (b) => { const o = new Float32Array(b.length); for (let i = 0; i < b.length; i++) { const v = b[i]; o[i] = v === nodata || !isFinite(v) ? NaN : v; } return o; });
    let resM: number | null = null;
    try { const r = img.getResolution(); resM = Math.abs(r[0]) > 1 ? Math.abs(r[0]) : null; } catch { /* no georeferencing */ }
    return { name: file.name, width, height, bands, resM, kind: "tiff" };
  }
  const url = URL.createObjectURL(file);
  try {
    const im = await new Promise<HTMLImageElement>((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error(`${file.name}: not a readable image`)); i.src = url; });
    const c = document.createElement("canvas"); c.width = im.naturalWidth; c.height = im.naturalHeight;
    const x = c.getContext("2d", { willReadFrequently: true })!; x.drawImage(im, 0, 0);
    const d = x.getImageData(0, 0, c.width, c.height).data, n = c.width * c.height, g = new Float32Array(n);
    for (let i = 0; i < n; i++) g[i] = d[i * 4 + 3] === 0 ? NaN : d[i * 4];   // greyscale: red channel; transparent = missing
    return { name: file.name, width: c.width, height: c.height, bands: [g], resM: null, kind: "image" };
  } finally { URL.revokeObjectURL(url); }
}

export type BandMap = { green: number; red: number; nir: number; swir1: number };
export const PRESETS: Record<string, { label: string; map: BandMap | null; hint: string }> = {
  s2_12: { label: "Sentinel-2 L2A, 12 bands B1…B12 (B1,B2,B3,B4,B5,B6,B7,B8,B8A,B9,B11,B12)", map: { green: 2, red: 3, nir: 7, swir1: 10 }, hint: "Copernicus Browser / EO Browser 'all bands' export" },
  s2_13: { label: "Sentinel-2 L1C, 13 bands B1…B12 incl. B10", map: { green: 2, red: 3, nir: 7, swir1: 11 }, hint: "L1C products include the cirrus band B10" },
  four: { label: "4 bands: Green, Red, NIR, SWIR1 (B3, B4, B8, B11)", map: { green: 0, red: 1, nir: 2, swir1: 3 }, hint: "a compact Earth Engine export" },
  hls: { label: "HLS / Landsat-style 6 bands: Blue, Green, Red, NIR, SWIR1, SWIR2", map: { green: 1, red: 2, nir: 3, swir1: 4 }, hint: "the bands EcoRewind's 30 m cubes use" },
  ndvi: { label: "Single band: NDVI already computed", map: null, hint: "values in [−1, 1]" },
};

const nd = (a: Float32Array, b: Float32Array) => {
  const o = new Float32Array(a.length);
  for (let i = 0; i < a.length; i++) { const s = a[i] + b[i]; o[i] = !isFinite(a[i]) || !isFinite(b[i]) || Math.abs(s) < 1e-6 ? NaN : (a[i] - b[i]) / s; }
  return o;
};
/** NDVI/NDMI/NDWI from a raster. For single-band rasters the band is NDVI, optionally rescaled from [lo, hi] (PNG 0–255). */
export function indices(r: Raster, map: BandMap | null, range?: [number, number]) {
  if (!map) {
    const b = r.bands[0], o = new Float32Array(b.length), [lo, hi] = range ?? [-1, 1], sc = r.kind === "image" ? 255 : 1;
    for (let i = 0; i < b.length; i++) o[i] = isFinite(b[i]) ? (r.kind === "image" ? lo + (b[i] / sc) * (hi - lo) : b[i]) : NaN;
    return { NDVI: o, NDMI: null as Float32Array | null, NDWI: null as Float32Array | null };
  }
  const need = Math.max(map.green, map.red, map.nir, map.swir1);
  if (r.bands.length <= need) throw new Error(`${r.name}: has ${r.bands.length} band(s); this band layout needs ${need + 1}`);
  const B = (i: number) => r.bands[i];
  return { NDVI: nd(B(map.nir), B(map.red)), NDMI: nd(B(map.nir), B(map.swir1)), NDWI: nd(B(map.green), B(map.nir)) };
}

/** Average f × f blocks (e.g. 10 m → 30 m with f = 3), ignoring NaN. */
export function blockMean(a: Float32Array, w: number, h: number, f: number) {
  if (f <= 1) return { data: a, w, h };
  const W = Math.floor(w / f), H = Math.floor(h / f), o = new Float32Array(W * H);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    let s = 0, n = 0;
    for (let j = 0; j < f; j++) for (let i = 0; i < f; i++) { const v = a[(y * f + j) * w + x * f + i]; if (isFinite(v)) { s += v; n++; } }
    o[y * W + x] = n ? s / n : NaN;
  }
  return { data: o, w: W, h: H };
}
export function crop(a: Float32Array, w: number, x0: number, y0: number, S: number) {
  const o = new Float32Array(S * S);
  for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) o[y * S + x] = a[(y0 + y) * w + x0 + x] ?? NaN;
  return o;
}
export const nextQuarters = (start: string, n: number) => {
  const m = start.match(/^(\d{4})Q([1-4])$/); if (!m) return [];
  const t0 = +m[1] * 4 + +m[2] - 1;
  return Array.from({ length: n }, (_, i) => `${Math.floor((t0 + i) / 4)}Q${((t0 + i) % 4) + 1}`);
};
