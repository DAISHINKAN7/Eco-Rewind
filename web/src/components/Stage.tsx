import { CSSProperties, ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";

/** Pan/zoom state shared between stages. x, y are offsets of the image centre in units of the fitted image size. */
export type View = { k: number; x: number; y: number };
export const VIEW0: View = { k: 1, x: 0, y: 0 };
export type Layer = { src: string; opacity?: number; filter?: string; blend?: CSSProperties["mixBlendMode"]; key?: string } | null | false | undefined;
export type UV = [number, number];

/**
 * Stacked, georegistered image layers (all with the same footprint) with wheel/drag pan-zoom, an optional swipe
 * divider (right layers clipped at `split`), a shared crosshair and a pin. Coordinates out: image fractions (u, v).
 */
export default function Stage({ layers, right, aspect, view, onView, cursor, onCursor, pin, onPick, split, onSplit,
  children, interactive = true, className, style, labels, pixelated = true }: {
  layers: Layer[]; right?: Layer[]; aspect: number; view: View; onView?: (v: View) => void;
  cursor?: UV | null; onCursor?: (uv: UV | null) => void; pin?: UV | null; onPick?: (uv: UV) => void;
  split?: number; onSplit?: (s: number) => void; children?: ReactNode; interactive?: boolean; className?: string;
  style?: CSSProperties; labels?: [ReactNode, ReactNode]; pixelated?: boolean;
}) {
  const el = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  useLayoutEffect(() => {
    const e = el.current!;
    const ro = new ResizeObserver(() => setSize({ w: e.clientWidth, h: e.clientHeight }));
    ro.observe(e); setSize({ w: e.clientWidth, h: e.clientHeight });
    return () => ro.disconnect();
  }, []);
  // fitted (k = 1) image box
  const bw = Math.min(size.w, size.h * aspect) || 1, bh = bw / aspect;
  const left = size.w / 2 + view.x * bw - (bw * view.k) / 2, top = size.h / 2 + view.y * bh - (bh * view.k) / 2;
  const box: CSSProperties = { position: "absolute", left, top, width: bw * view.k, height: bh * view.k };
  const toUV = (cx: number, cy: number): UV => {
    const r = el.current!.getBoundingClientRect();
    return [(cx - r.left - left) / (bw * view.k), (cy - r.top - top) / (bh * view.k)];
  };
  const vref = useRef(view); vref.current = view;

  // wheel zoom about the cursor (non-passive listener so the page doesn't scroll)
  useEffect(() => {
    const e = el.current!;
    if (!interactive || !onView) return;
    const wheel = (ev: WheelEvent) => {
      ev.preventDefault();
      const v = vref.current, r = e.getBoundingClientRect();
      const k = Math.min(24, Math.max(1, v.k * Math.exp(-ev.deltaY * 0.0016)));
      const px = ev.clientX - r.left, py = ev.clientY - r.top;
      const l0 = r.width / 2 + v.x * bw - (bw * v.k) / 2, t0 = r.height / 2 + v.y * bh - (bh * v.k) / 2;
      const u = (px - l0) / (bw * v.k), w = (py - t0) / (bh * v.k);
      onView(clamp({ k, x: (px - r.width / 2) / bw - k * (u - 0.5), y: (py - r.height / 2) / bh - k * (w - 0.5) }));
    };
    e.addEventListener("wheel", wheel, { passive: false });
    return () => e.removeEventListener("wheel", wheel);
  }, [interactive, onView, bw, bh]);

  const drag = useRef<{ x: number; y: number; v: View; moved: boolean; id: number } | null>(null);
  const down = (ev: React.PointerEvent) => {
    if (!interactive || (ev.target as HTMLElement).closest(".stage-handle, .stage-ui")) return;
    drag.current = { x: ev.clientX, y: ev.clientY, v: view, moved: false, id: ev.pointerId };
    (ev.currentTarget as HTMLElement).setPointerCapture(ev.pointerId);
  };
  const move = (ev: React.PointerEvent) => {
    const d = drag.current;
    if (d) {
      const dx = ev.clientX - d.x, dy = ev.clientY - d.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) d.moved = true;
      if (d.moved && onView && d.v.k > 1) onView(clamp({ ...d.v, x: d.v.x + dx / bw, y: d.v.y + dy / bh }));
    }
    if (onCursor && ev.pointerType === "mouse") {
      const uv = toUV(ev.clientX, ev.clientY);
      onCursor(inside(uv) ? uv : null);
    }
  };
  const up = (ev: React.PointerEvent) => {
    const d = drag.current; drag.current = null;
    if (d && !d.moved && onPick) { const uv = toUV(ev.clientX, ev.clientY); if (inside(uv)) onPick(uv); }
  };

  const img = (L: Layer, i: number) => L && <img key={L.key ?? L.src + i} src={L.src} alt="" draggable={false} decoding="async"
    style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: L.opacity ?? 1, filter: L.filter, mixBlendMode: L.blend,
      imageRendering: pixelated && view.k * bw > 900 ? "pixelated" : "auto", pointerEvents: "none", transition: "opacity .25s" }} />;
  const mark = (uv: UV | null | undefined, kind: "cursor" | "pin") => uv && (
    <div className={`stage-${kind}`} style={{ left: left + uv[0] * bw * view.k, top: top + uv[1] * bh * view.k }} />);
  const swipe = right !== undefined && split !== undefined;

  const dragSplit = (e: React.PointerEvent) => {
    e.stopPropagation(); e.preventDefault();
    const r = el.current!.getBoundingClientRect();
    const mv = (ev: PointerEvent) => onSplit?.(Math.min(0.98, Math.max(0.02, (ev.clientX - r.left) / r.width)));
    const end = () => { window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", end); };
    window.addEventListener("pointermove", mv); window.addEventListener("pointerup", end);
  };

  return (
    <div ref={el} className={`stage ${className ?? ""}`} style={{ cursor: interactive ? (view.k > 1 ? "grab" : "crosshair") : "default", ...style }}
      onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerLeave={() => onCursor?.(null)}>
      <div style={box}>{layers.map(img)}</div>
      {swipe && <div style={{ position: "absolute", inset: 0, clipPath: `inset(0 0 0 ${split! * 100}%)`, pointerEvents: "none" }}>
        <div style={box}>{right!.map(img)}</div></div>}
      {mark(cursor, "cursor")}{mark(pin, "pin")}
      {swipe && <>
        <div className="stage-handle" style={{ left: `${split! * 100}%` }} onPointerDown={dragSplit} role="slider" tabIndex={0}
          aria-label="swipe divider" aria-valuenow={Math.round(split! * 100)}
          onKeyDown={(e) => { if (e.key === "ArrowLeft") onSplit?.(Math.max(0.02, split! - 0.04)); if (e.key === "ArrowRight") onSplit?.(Math.min(0.98, split! + 0.04)); }} />
        {labels && <>
          <div className="stage-label l" style={{ right: `calc(${(1 - split!) * 100}% + 12px)` }}>{labels[0]}</div>
          <div className="stage-label r" style={{ left: `calc(${split! * 100}% + 12px)` }}>{labels[1]}</div>
        </>}
      </>}
      {children}
    </div>
  );
}

const inside = ([u, v]: UV) => u >= 0 && v >= 0 && u < 1 && v < 1;
export function clamp(v: View): View {
  const lim = (v.k - 1) / 2 + 0.15;
  return { k: v.k, x: Math.max(-lim, Math.min(lim, v.x)), y: Math.max(-lim, Math.min(lim, v.y)) };
}
export const zoomBy = (v: View, f: number): View => {
  const k = Math.min(24, Math.max(1, v.k * f)), r = k / v.k;
  return clamp({ k, x: v.x * r, y: v.y * r });
};

export const ZoomButtons = ({ view, onView }: { view: View; onView: (v: View) => void }) => (
  <div className="stage-ui zoom-btns">
    <button onClick={() => onView(zoomBy(view, 1.6))} aria-label="zoom in">+</button>
    <button onClick={() => onView(zoomBy(view, 1 / 1.6))} aria-label="zoom out">−</button>
    <button onClick={() => onView({ k: 1, x: 0, y: 0 })} aria-label="reset view" style={{ fontSize: 13 }}>⤢</button>
  </div>
);
