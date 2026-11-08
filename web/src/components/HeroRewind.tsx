import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "./ui";

/**
 * Scroll-driven hero: the real pre-storm marsh, Hurricane Ida crossing along its HURDAT2 track, the model's real damage
 * map burning in behind the eye, then a rewind that turns the storm-hit marsh into the model's storm-free counterfactual.
 */
export type HeroData = {
  rgb: string; damage: string; cf: string; obs: string; corners: number[][];
  deficit: number | null; passes: string; model: string; nModels: number; nTests: number;
};

// HURDAT2 AL092021 (IDA): time (h from 29 Aug 00Z), lat, lon, wind kt, pressure mb
const TRACK: [number, number, number, number, number][] = [[0, 28.5, -89.5, 130, 930], [12, 29.1, -90.2, 130, 930], [24, 29.9, -90.6, 90, 950]];
const COSLAT = Math.cos((29.4 * Math.PI) / 180);
const W = (lon: number, lat: number) => [lon * COSLAT, -lat];  // world coords (equirectangular, km-ish isotropic)
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const clamp01 = (t: number) => Math.max(0, Math.min(1, t));
const seg = (p: number, a: number, b: number) => clamp01((p - a) / (b - a));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

function trackAt(s: number) {                          // s in [0, 1] over 24 h
  const h = s * 24, i = h < 12 ? 0 : 1, f = (h - TRACK[i][0]) / 12;
  const [, la0, lo0, w0, p0] = TRACK[i], [, la1, lo1, w1, p1] = TRACK[i + 1];
  return { h, lat: lerp(la0, la1, f), lon: lerp(lo0, lo1, f), kt: lerp(w0, w1, f), mb: lerp(p0, p1, f) };
}

// chapters (scroll progress)
const CH = { pull: [0.1, 0.26], storm: [0.14, 0.5], push: [0.5, 0.6], rewind: [0.62, 0.84], end: 0.86 } as const;
const CHAPTERS: [string, number][] = [["Before", 0], ["Landfall", 0.24], ["Damage", 0.52], ["Rewind", 0.66], ["No-storm world", 0.9]];

function loadImg(src: string) {
  return new Promise<HTMLImageElement | null>((res) => { const i = new Image(); i.crossOrigin = "anonymous"; i.onload = () => res(i); i.onerror = () => res(null); i.src = src; });
}
/** natural-looking true colour: undo the export's display gamma (same curve as the #tc SVG filter) */
function trueColour(img: HTMLImageElement, dim = 1) {
  const c = document.createElement("canvas"); c.width = img.naturalWidth; c.height = img.naturalHeight;
  const x = c.getContext("2d")!; x.drawImage(img, 0, 0);
  const d = x.getImageData(0, 0, c.width, c.height), a = d.data;
  const lut = [[1.25, 2.4], [1.15, 2.2], [0.95, 2.0]].map(([amp, ex]) => Uint8ClampedArray.from({ length: 256 }, (_, v) => 255 * Math.min(1, amp * Math.pow(v / 255, ex)) * dim));
  for (let i = 0; i < a.length; i += 4) {
    const r = lut[0][a[i]], g = lut[1][a[i + 1]], b = lut[2][a[i + 2]], m = (r + g + b) / 3;
    a[i] = m + (r - m) * 1.6; a[i + 1] = m + (g - m) * 1.6; a[i + 2] = m + (b - m) * 1.6;
  }
  x.putImageData(d, 0, 0);
  return c;
}
function sprite() {
  const c = document.createElement("canvas"); c.width = c.height = 64;
  const x = c.getContext("2d")!, g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(0.4, "rgba(235,242,255,.45)"); g.addColorStop(1, "rgba(220,230,255,0)");
  x.fillStyle = g; x.fillRect(0, 0, 64, 64);
  return c;
}

export default function HeroRewind({ data }: { data: HeroData | null }) {
  const wrap = useRef<HTMLDivElement>(null), cv = useRef<HTMLCanvasElement>(null);
  const hud = { t: useRef<HTMLSpanElement>(null), w: useRef<HTMLSpanElement>(null), p: useRef<HTMLSpanElement>(null), ll: useRef<HTMLSpanElement>(null),
    bar: useRef<HTMLDivElement>(null) };
  const [phase, setPhase] = useState(0);
  const [ready, setReady] = useState(false);
  const reduce = typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (!data) return;
    let raf = 0, live = true;
    const canvas = cv.current!, ctx = canvas.getContext("2d")!;
    const st = { imgs: null as null | { rgb: HTMLCanvasElement; rgbDim: HTMLCanvasElement; damage: HTMLImageElement; cf: HTMLImageElement }, mask: document.createElement("canvas"),
      dmg: document.createElement("canvas"), lastS: -1, phase: -1, t0: performance.now() };
    st.mask.width = st.mask.height = 256;
    const spr = sprite();
    // storm particles
    // storm particles: 5 logarithmic spiral rain bands + haze + a dense eyewall ring
    const gauss = () => (Math.random() + Math.random() + Math.random() - 1.5) / 1.5;
    const N = 1700, P = Array.from({ length: N }, (_, i) => {
      const kind = i < 260 ? 0 : i < 1350 ? 1 : 2;                  // 0 eyewall, 1 bands, 2 haze
      const r = kind === 0 ? 0.11 + Math.abs(gauss()) * 0.07 : kind === 1 ? 0.14 + Math.pow(Math.random(), 0.8) * 0.86 : 0.1 + Math.random() * 0.9;
      const arm = i % 4, a = kind === 1 ? (arm / 4) * Math.PI * 2 + arm * 0.6 + gauss() * (0.35 + r * 0.5) : Math.random() * Math.PI * 2;
      const bandGain = [1, 0.55, 0.85, 0.4][arm];                     // uneven bands, like a real satellite loop
      return { r, a, kind, tw: 2.5 + Math.random() * 1.2 + arm * 0.15, s: 0.6 + Math.random() * 0.9,
        o: kind === 0 ? 0.85 : kind === 1 ? (0.3 + Math.random() * 0.55) * bandGain : 0.1 + Math.random() * 0.22 };
    });
    Promise.all([loadImg(data.rgb), loadImg(data.damage), loadImg(data.cf)]).then(([rgb, damage, cf]) => {
      if (!live || !rgb || !damage || !cf) return;
      st.imgs = { rgb: trueColour(rgb), rgbDim: trueColour(rgb, 0.55), damage, cf };
      st.dmg.width = damage.naturalWidth; st.dmg.height = damage.naturalHeight;
      setReady(true);
    });
    // AOI geometry in world coords
    const cw = data.corners.map(([lo, la]) => W(lo, la));
    const ax0 = Math.min(...cw.map((p) => p[0])), ax1 = Math.max(...cw.map((p) => p[0])), ay0 = Math.min(...cw.map((p) => p[1])), ay1 = Math.max(...cw.map((p) => p[1]));
    const acx = (ax0 + ax1) / 2, acy = (ay0 + ay1) / 2, aw = ax1 - ax0, ah = ay1 - ay0;
    const toUV = (lo: number, la: number) => { const [x, y] = W(lo, la); return [(x - ax0) / aw, (y - ay0) / ah]; };

    const progress = () => {
      const el = wrap.current!, r = el.getBoundingClientRect(), total = el.offsetHeight - innerHeight;
      return clamp01(-r.top / (total || 1));
    };
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const dpr = Math.min(2, devicePixelRatio || 1), vw = canvas.clientWidth, vh = canvas.clientHeight;
      if (canvas.width !== Math.round(vw * dpr) || canvas.height !== Math.round(vh * dpr)) { canvas.width = Math.round(vw * dpr); canvas.height = Math.round(vh * dpr); }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const p = progress(), t = reduce ? 0 : (now - st.t0) / 1000;
      const s = ease(seg(p, CH.storm[0], CH.storm[1]));                   // storm along the track
      const pull = ease(seg(p, CH.pull[0], CH.pull[1])) * (1 - ease(seg(p, CH.push[0], CH.push[1])));
      const rw = ease(seg(p, CH.rewind[0], CH.rewind[1]));
      const ph = p < 0.2 ? 0 : p < 0.5 ? 1 : p < 0.62 ? 2 : p < CH.end ? 3 : 4;
      if (ph !== st.phase) { st.phase = ph; setPhase(ph); }
      // camera: tight cover of the AOI -> wide view of AOI + track
      const tightSpan = Math.min(ah * 1.02, (aw * vh) / vw * 1.02) * (1 - 0.04 * Math.sin(t * 0.15));
      const [tx, ty] = W(-90.42, 29.35);
      const span = lerp(tightSpan, 0.95, pull), cx = lerp(acx + 0.01 * Math.sin(t * 0.1), lerp(acx, tx, 0.62), pull), cy = lerp(acy, lerp(acy, ty, 0.35), pull);
      const k = vh / span, X = (x: number) => vw / 2 + (x - cx) * k, Y = (y: number) => vh / 2 + (y - cy) * k;

      // background: deep ocean + lat/lon grid
      ctx.fillStyle = "#0d1217"; ctx.fillRect(0, 0, vw, vh);
      const glow = ctx.createRadialGradient(vw * 0.7, vh * 0.6, 0, vw * 0.7, vh * 0.6, vw * 0.8);
      glow.addColorStop(0, "rgba(255,176,32,.05)"); glow.addColorStop(1, "rgba(5,7,13,0)"); ctx.fillStyle = glow; ctx.fillRect(0, 0, vw, vh);
      ctx.strokeStyle = "rgba(150,175,200,.07)"; ctx.lineWidth = 1; ctx.font = "10px IBM Plex Mono, monospace"; ctx.fillStyle = "rgba(255,255,255,.32)";
      const step = span > 0.6 ? 0.1 : 0.02;
      for (let lo = Math.floor((cx / COSLAT - span) / step) * step; lo < cx / COSLAT + span * 1.5; lo += step) {
        const x = X(lo * COSLAT); if (x < -5 || x > vw + 5) continue;
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, vh); ctx.stroke(); if (pull > 0.4) ctx.fillText(`${(-lo).toFixed(1)}°W`, x + 3, vh - 8);
      }
      for (let la = Math.floor((-cy - span) / step) * step; la < -cy + span; la += step) {
        const y = Y(-la); if (y < -5 || y > vh + 5) continue;
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(vw, y); ctx.stroke(); if (pull > 0.4) ctx.fillText(`${la.toFixed(1)}°N`, 6, y - 3);
      }

      // the marsh
      const I = st.imgs;
      const qx = X(ax0), qy = Y(ay0), qw = aw * k, qh = ah * k;
      if (I) {
        // damage mask: union of discs along the eye's path so far (deterministic in s)
        if (Math.abs(s - st.lastS) > 1e-4) {
          st.lastS = s;
          const m = st.mask.getContext("2d")!; m.clearRect(0, 0, 256, 256); m.globalCompositeOperation = "lighter";
          for (let i = 0; i <= 40; i++) {
            const e = trackAt((i / 40) * s), [u, v] = toUV(e.lon, e.lat), R = (0.42 / ah) * 256 * (e.kt / 130);
            const g = m.createRadialGradient(u * 256, v * 256, 0, u * 256, v * 256, R);
            g.addColorStop(0, "rgba(255,255,255,.22)"); g.addColorStop(0.55, "rgba(255,255,255,.12)"); g.addColorStop(1, "rgba(255,255,255,0)");
            m.fillStyle = g; m.fillRect(0, 0, 256, 256);
          }
          const d = st.dmg.getContext("2d")!; d.globalCompositeOperation = "source-over"; d.clearRect(0, 0, st.dmg.width, st.dmg.height);
          d.drawImage(I.damage, 0, 0); d.globalCompositeOperation = "destination-in"; d.drawImage(st.mask, 0, 0, st.dmg.width, st.dmg.height);
        }
        ctx.save();
        ctx.shadowColor = "rgba(0,0,0,.8)"; ctx.shadowBlur = 40 * pull;
        const dmgOn = clamp01(s * 1.4);
        ctx.drawImage(dmgOn > 0.02 ? I.rgbDim : I.rgb, qx, qy, qw, qh);
        if (dmgOn < 1 && dmgOn > 0.02) { ctx.globalAlpha = 1 - dmgOn; ctx.drawImage(I.rgb, qx, qy, qw, qh); ctx.globalAlpha = 1; }
        ctx.shadowBlur = 0;
        const split = qx + qw * (1 - rw);                                  // rewind scan line moves right -> left
        ctx.save(); ctx.beginPath(); ctx.rect(qx, qy, Math.max(0, split - qx), qh); ctx.clip();
        ctx.drawImage(st.dmg, qx, qy, qw, qh); ctx.restore();
        if (rw > 0) {
          ctx.save(); ctx.beginPath(); ctx.rect(split, qy, qx + qw - split, qh); ctx.clip();
          ctx.drawImage(I.cf, qx, qy, qw, qh); ctx.restore();
          if (rw < 1) {                                                    // glitch band at the scan line
            for (let i = 0; i < 9; i++) {
              const sy = qy + ((i * 97 + Math.floor(t * 23) * 31) % 100) / 100 * qh, sh = 4 + (i % 3) * 7, off = (Math.sin(t * 40 + i) * 18);
              const u0 = (split - qx) / qw;
              ctx.globalAlpha = 0.75;
              ctx.drawImage(I.cf, Math.max(0, u0 - 0.03) * I.cf.naturalWidth, ((sy - qy) / qh) * I.cf.naturalHeight, 0.06 * I.cf.naturalWidth, (sh / qh) * I.cf.naturalHeight,
                split - qw * 0.03 + off, sy, qw * 0.06, sh);
            }
            ctx.globalAlpha = 1;
            const g = ctx.createLinearGradient(split - 60, 0, split + 8, 0);
            g.addColorStop(0, "rgba(255,255,255,0)"); g.addColorStop(0.85, "rgba(255,255,255,.18)"); g.addColorStop(1, "rgba(255,255,255,.95)");
            ctx.fillStyle = g; ctx.fillRect(split - 60, qy, 68, qh);
            ctx.fillStyle = "#fff"; ctx.fillRect(split - 1, qy - 10, 2, qh + 20);
          }
        }
        ctx.restore();
        // AOI frame + label
        ctx.strokeStyle = `rgba(255,176,32,${0.25 + 0.5 * pull})`; ctx.setLineDash([6, 5]); ctx.strokeRect(qx, qy, qw, qh); ctx.setLineDash([]);
        if (pull > 0.3) { ctx.fillStyle = `rgba(255,255,255,${0.85 * pull})`; ctx.font = "500 11px IBM Plex Mono, monospace"; ctx.fillText("BARATARIA BASIN · STUDY AREA", qx, qy - 10); }
      }

      // track
      const trk = (ss: number) => { const e = trackAt(ss); const [x, y] = W(e.lon, e.lat); return [X(x), Y(y)]; };
      if (pull > 0.02) {
        ctx.globalAlpha = Math.min(1, pull * 1.5);
        ctx.setLineDash([3, 7]); ctx.strokeStyle = "rgba(255,79,46,.45)"; ctx.lineWidth = 1.5; ctx.beginPath();
        for (let i = 0; i <= 60; i++) { const [x, y] = trk(i / 60); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke(); ctx.setLineDash([]);
        ctx.strokeStyle = "rgba(255,79,46,.95)"; ctx.lineWidth = 2.5; ctx.beginPath();
        for (let i = 0; i <= 60; i++) { const ss = (i / 60) * s; const [x, y] = trk(ss); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke();
        TRACK.forEach(([h, la, lo, kt]) => {
          const [x, y] = W(lo, la), px = X(x), py = Y(y);
          ctx.fillStyle = "#ff4f2e"; ctx.beginPath(); ctx.arc(px, py, 4, 0, 7); ctx.fill();
          ctx.fillStyle = "rgba(255,255,255,.7)"; ctx.font = "10px IBM Plex Mono, monospace";
          ctx.fillText(`${h === 24 ? "30 AUG" : "29 AUG"} ${String(h % 24).padStart(2, "0")}Z · ${kt} kt`, px + 9, py + 4);
        });
        const [lx, ly] = W(-90.2, 29.1);
        ctx.fillStyle = "rgba(255,255,255,.9)"; ctx.font = "500 11px IBM Plex Mono, monospace"; ctx.fillText("LANDFALL · PORT FOURCHON", X(lx) + 9, Y(ly) - 10);
        ctx.globalAlpha = 1;
      }

      // the hurricane (visible from the approach until it has passed; rewinds backwards with the scan)
      const sv = rw > 0 ? s * (1 - rw) : s;
      const vis = p < CH.storm[0] ? 0.0 : (1 - seg(p, 0.5, 0.58)) + (rw > 0 && rw < 1 ? 0.6 * Math.sin(rw * Math.PI) : 0);
      if (vis > 0.01) {
        const e = trackAt(sv), [wx, wy] = W(e.lon, e.lat), ex = X(wx), ey = Y(wy), R = 0.72 * k * (0.75 + 0.25 * (e.kt / 130));
        const spin = (rw > 0 ? -1 : 1) * t * 0.9;
        ctx.save(); ctx.globalCompositeOperation = "screen";
        const va = Math.min(1, vis);
        for (const q of P) {
          const th = q.a - spin / Math.pow(q.r, 0.3) + (q.kind === 1 ? q.tw * Math.log(q.r) : q.kind === 2 ? 1.2 * Math.log(q.r) : 0);
          const rr = q.r * R, x = ex + Math.cos(th) * rr, y = ey + Math.sin(th) * rr;
          const len = R * (q.kind === 0 ? 0.09 : 0.05 + 0.22 * q.r) * q.s, wid = len * (q.kind === 2 ? 0.8 : 0.32);
          const ang = th - Math.PI / 2 - 0.35;                              // along the (counter-clockwise, inflowing) wind
          ctx.globalAlpha = va * q.o * (1 - Math.pow(q.r, 2.5) * 0.9);
          const c = Math.cos(ang), sn = Math.sin(ang);
          ctx.setTransform(dpr * c * len / 64, dpr * sn * len / 64, -dpr * sn * wid / 64, dpr * c * wid / 64, dpr * x, dpr * y);
          ctx.drawImage(spr, -32, -32);
        }
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.restore();
        const eye = ctx.createRadialGradient(ex, ey, 0, ex, ey, R * 0.07);
        eye.addColorStop(0, `rgba(13,18,23,${0.85 * Math.min(1, vis)})`); eye.addColorStop(1, "rgba(13,18,23,0)");
        ctx.fillStyle = eye; ctx.beginPath(); ctx.arc(ex, ey, R * 0.07, 0, 7); ctx.fill();
      }
      {
        const e = trackAt(sv);
        const H = Math.round(rw > 0 ? lerp(e.h, -24 * 60, rw) : e.h);
        if (hud.t.current) {
          if (rw >= 0.999) hud.t.current.textContent = "COUNTERFACTUAL · NO STORM";
          else if (rw > 0.02) {
            const d = new Date(Date.UTC(2021, 7, 29, 0) + H * 3600e3);
            hud.t.current.textContent = `◀◀ ${d.toISOString().slice(0, 10)}`;
          } else hud.t.current.textContent = `${e.h >= 24 ? "30" : "29"} AUG 2021 · ${String(Math.floor(e.h % 24)).padStart(2, "0")}:${String(Math.floor((e.h % 1) * 60)).padStart(2, "0")} UTC`;
        }
        if (hud.w.current) hud.w.current.textContent = rw >= 0.999 ? "—" : `${Math.round(e.kt)} kt · ${Math.round(e.kt * 1.151)} mph`;
        if (hud.p.current) hud.p.current.textContent = rw >= 0.999 ? "—" : `${Math.round(e.mb)} mb`;
        if (hud.ll.current) hud.ll.current.textContent = `${e.lat.toFixed(2)}°N ${(-e.lon).toFixed(2)}°W`;
      }
      // VHS scanlines while rewinding
      if (rw > 0 && rw < 1) {
        ctx.fillStyle = "rgba(255,255,255,.025)";
        for (let y = (t * 120) % 4; y < vh; y += 4) ctx.fillRect(0, y, vw, 1);
        ctx.fillStyle = `rgba(255,255,255,${0.025 * Math.sin(rw * Math.PI)})`; ctx.fillRect(0, 0, vw, vh);
      }
      if (hud.bar.current) hud.bar.current.style.transform = `scaleX(${p})`;
    };
    raf = requestAnimationFrame(frame);
    return () => { live = false; cancelAnimationFrame(raf); };
  }, [data, reduce]);

  const jump = (f: number) => { const el = wrap.current!; const top = el.offsetTop + f * (el.offsetHeight - innerHeight) + 2; scrollTo({ top, behavior: "smooth" }); };
  const d = data?.deficit;
  return (
    <section ref={wrap} className="rw" style={{ height: "520vh" }}>
      <div className="rw-sticky">
        <canvas ref={cv} className="rw-canvas" />
        {!ready && <div className="rw-loading"><span className="spin" /> loading satellite imagery…</div>}
        <div className="rw-vignette" />

        <div className="rw-hud mono">
          <div className="rw-hud-row"><span className="rw-rec" />HURDAT2 · AL092021 · IDA</div>
          <div className="rw-hud-big" ><span ref={hud.t}>29 AUG 2021 · 00:00 UTC</span></div>
          <div className="rw-hud-row">MAX WIND <span ref={hud.w}>130 kt · 150 mph</span></div>
          <div className="rw-hud-row">PRESSURE <span ref={hud.p}>930 mb</span> · EYE <span ref={hud.ll}>28.50°N 89.50°W</span></div>
        </div>

        <div className={`rw-copy ${phase === 0 ? "on" : ""}`}>
          <div className="eyebrow">EcoRewind · counterfactual satellite forecasting</div>
          <h1>What would these wetlands look like if the hurricane had <em className="accent">never happened?</em></h1>
          <p className="lead">Scroll to watch Hurricane Ida hit the Barataria marshes, then rewind the clock with a model that has never seen the storm.</p>
          <button className="rw-scroll" onClick={() => jump(0.3)}><span className="rw-mouse" />scroll to play</button>
        </div>
        <div className={`rw-caption ${phase === 1 ? "on" : ""}`}>
          <div className="rw-k mono">29 Aug 2021 · 11:55 local</div>
          <h2>Ida makes landfall at Port Fourchon as a Category 4.</h2>
          <p>The eye tracks north-north-west, passing about 20 km east of the study area with 150 mph winds.</p>
        </div>
        <div className={`rw-caption ${phase === 2 ? "on" : ""}`}>
          <div className="rw-k mono">damage = forecast − observed</div>
          <h2>Orange is vegetation lost to the storm: <span className="mono" style={{ color: "var(--dmg1)" }}>{d != null ? (d > 0 ? "+" : "") + d.toFixed(3) : "…"}</span> NDVI.</h2>
          <p>{data?.model ?? "SimVP"}'s map, real output on held-out blocks. {data?.passes ?? ""}</p>
        </div>
        <div className={`rw-caption center ${phase === 3 ? "on" : ""}`}>
          <div className="rw-rewind mono">◀◀ REWIND</div>
          <p>Trained only on the years before the storm, the model forecasts the marsh's normal rhythm forward.</p>
        </div>
        <div className={`rw-copy end ${phase === 4 ? "on" : ""}`}>
          <div className="eyebrow">The counterfactual</div>
          <h1>The same marsh, <em className="accent">without Ida.</em></h1>
          <p className="lead">Now the hard part: is that difference real? EcoRewind tests it against fake hurricanes in calm years, inland control
            areas and {data?.nModels ?? 19} competing models.</p>
          <div className="hero2-cta">
            <Link className="btn primary" to="/explore">Open the studio <Icon name="arrow" size={16} /></Link>
            <Link className="btn" to="/explore?mode=gallery&site=everglades&track=B">All {data?.nModels ?? 19} models</Link>
            <Link className="btn" to="/lab"><Icon name="play" size={14} /> Run SimVP live</Link>
          </div>
        </div>

        <nav className="rw-chapters">
          {CHAPTERS.map(([l, f], i) => <button key={l} className={phase === i ? "on" : ""} onClick={() => jump(f)}>{l}</button>)}
          <div className="rw-bar"><div ref={hud.bar} /></div>
        </nav>
        <button className="rw-skip" onClick={() => scrollTo({ top: (wrap.current!.offsetTop + wrap.current!.offsetHeight) - 60, behavior: "smooth" })}>skip intro ↓</button>
      </div>
    </section>
  );
}
