import { CSSProperties, ReactNode, useEffect, useRef, useState } from "react";

/** true once the element has scrolled into view */
export function useInView<T extends Element>(margin = "-10% 0px") {
  const ref = useRef<T>(null);
  const [v, set] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") { set(true); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { set(true); io.disconnect(); } }, { rootMargin: margin });
    io.observe(el);
    return () => io.disconnect();
  }, [margin]);
  return [ref, v] as const;
}

/** Fades/slides its children in when scrolled into view. */
export function Reveal({ children, delay = 0, className = "", style, as: As = "div" }: { children: ReactNode; delay?: number; className?: string; style?: CSSProperties; as?: any }) {
  const [ref, v] = useInView<HTMLDivElement>();
  return <As ref={ref} className={`reveal ${v ? "in" : ""} ${className}`} style={{ ...style, transitionDelay: `${delay}ms` }}>{children}</As>;
}

/** Animated number that counts up when visible. */
export function CountUp({ to, decimals = 0, prefix = "", suffix = "", duration = 1400, sign = false }: { to: number | null | undefined; decimals?: number;
  prefix?: string; suffix?: string; duration?: number; sign?: boolean }) {
  const [ref, v] = useInView<HTMLSpanElement>();
  const [x, setX] = useState(0);
  useEffect(() => {
    if (!v || to == null || !isFinite(to)) return;
    let raf = 0; const t0 = performance.now();
    const f = (t: number) => { const p = Math.min(1, (t - t0) / duration), e = 1 - Math.pow(1 - p, 4); setX(to * e); if (p < 1) raf = requestAnimationFrame(f); };
    raf = requestAnimationFrame(f);
    return () => cancelAnimationFrame(raf);
  }, [v, to, duration]);
  if (to == null || !isFinite(to)) return <span ref={ref}>—</span>;
  return <span ref={ref} className="countup">{prefix}{sign && to > 0 ? "+" : ""}{x.toFixed(decimals)}{suffix}</span>;
}

/** Card with a cursor-following spotlight and an optional 3D tilt. */
export function Glow({ children, className = "", tilt = false, style, as: As = "div", ...rest }: { children: ReactNode; className?: string; tilt?: boolean;
  style?: CSSProperties; as?: any; [k: string]: any }) {
  const move = (e: React.PointerEvent<HTMLElement>) => {
    const el = e.currentTarget, r = el.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
    el.style.setProperty("--mx", `${x * 100}%`); el.style.setProperty("--my", `${y * 100}%`);
    if (tilt) el.style.transform = `perspective(900px) rotateX(${(0.5 - y) * 7}deg) rotateY(${(x - 0.5) * 9}deg) translateZ(0)`;
  };
  const leave = (e: React.PointerEvent<HTMLElement>) => { if (tilt) e.currentTarget.style.transform = ""; };
  return <As className={`glow ${tilt ? "tilt" : ""} ${className}`} style={style} onPointerMove={move} onPointerLeave={leave} {...rest}>{children}</As>;
}

/** Infinite marquee. */
export const Marquee = ({ items, speed = 60 }: { items: ReactNode[]; speed?: number }) => (
  <div className="marquee" style={{ ["--dur" as string]: `${Math.max(20, items.length * (240 / speed) * 4)}s` }}>
    <div className="marquee-track">{[0, 1].map((k) => <div key={k} className="marquee-group" aria-hidden={k === 1}>
      {items.map((it, i) => <span key={i} className="marquee-item">{it}<span className="marquee-sep">✦</span></span>)}</div>)}</div>
  </div>
);

/** Big section heading with index number. */
export const SectionHead = ({ n, kicker, title, children }: { n: string; kicker: string; title: ReactNode; children?: ReactNode }) => (
  <Reveal className="sec-head2">
    <div className="sec-n mono">{n}</div>
    <div><div className="eyebrow">{kicker}</div><h2>{title}</h2>{children && <p className="muted sec-lead">{children}</p>}</div>
  </Reveal>
);
