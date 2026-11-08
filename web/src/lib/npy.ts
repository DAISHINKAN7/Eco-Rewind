// Minimal NumPy .npy (v1/v2/v3) reader and writer for float16/32/64 C-order arrays.

export type Npy = { data: Float32Array; shape: number[] };

function f16(u: number) {
  const s = u & 0x8000 ? -1 : 1, e = (u >> 10) & 0x1f, f = u & 0x3ff;
  return e === 0 ? s * Math.pow(2, -14) * (f / 1024) : e === 31 ? (f ? NaN : s * Infinity) : s * Math.pow(2, e - 15) * (1 + f / 1024);
}

export function readNpy(buf: ArrayBuffer): Npy {
  const b = new Uint8Array(buf);
  if (b[0] !== 0x93 || String.fromCharCode(...b.slice(1, 6)) !== "NUMPY") throw new Error("not a .npy file (missing \\x93NUMPY magic)");
  const major = b[6], dv = new DataView(buf);
  const hlen = major === 1 ? dv.getUint16(8, true) : dv.getUint32(8, true), off = major === 1 ? 10 : 12;
  const header = new TextDecoder().decode(b.slice(off, off + hlen));
  const descr = header.match(/'descr':\s*'([^']+)'/)?.[1], fortran = /'fortran_order':\s*True/.test(header);
  const shape = (header.match(/'shape':\s*\(([^)]*)\)/)?.[1] ?? "").split(",").map((x) => x.trim()).filter(Boolean).map(Number);
  if (fortran) throw new Error("Fortran-order arrays are not supported; save with np.ascontiguousarray(x)");
  const n = shape.reduce((a, c) => a * c, 1), start = off + hlen, out = new Float32Array(n);
  if (descr === "<f4") out.set(new Float32Array(buf.slice(start, start + n * 4)));
  else if (descr === "<f8") { const d = new Float64Array(buf.slice(start, start + n * 8)); for (let i = 0; i < n; i++) out[i] = d[i]; }
  else if (descr === "<f2") { const d = new Uint16Array(buf.slice(start, start + n * 2)); for (let i = 0; i < n; i++) out[i] = f16(d[i]); }
  else throw new Error(`dtype ${descr} not supported; use float16, float32 or float64`);
  return { data: out, shape };
}

export function writeNpy(data: Float32Array, shape: number[]): Blob {
  let h = `{'descr': '<f4', 'fortran_order': False, 'shape': (${shape.join(", ")}${shape.length === 1 ? "," : ""}), }`;
  const pad = 64 - ((10 + h.length + 1) % 64);
  h = h + " ".repeat(pad % 64) + "\n";
  const head = new Uint8Array(10 + h.length);
  head.set([0x93, 78, 85, 77, 80, 89, 1, 0]);
  new DataView(head.buffer).setUint16(8, h.length, true);
  head.set(new TextEncoder().encode(h), 10);
  return new Blob([head, new Uint8Array(data.buffer, data.byteOffset, data.byteLength)], { type: "application/octet-stream" });
}
