import { HashRouter, Route, Routes, useLocation } from "react-router-dom";
import { useEffect, useRef } from "react";
import { Footer, Nav } from "./components/ui";
import { useResults } from "./lib/data";
import Home from "./pages/Home";
import Explore from "./pages/Explore";
import Lab from "./pages/Lab";
import Models, { ModelDetail } from "./pages/Models";
import Evidence from "./pages/Evidence";
import Pipeline from "./pages/Pipeline";
import Story from "./pages/Story";
import Reports from "./pages/Reports";

function Shell() {
  const loc = useLocation();
  const { data } = useResults();
  useEffect(() => { window.scrollTo(0, 0); }, [loc.pathname]);
  // auto-reveal cards, notes and headings on every content page as they scroll into view
  useEffect(() => {
    if (loc.pathname.startsWith("/explore") || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { rootMargin: "0px 0px -8% 0px" });
    const seen = new WeakSet<Element>();
    const scan = () => document.querySelectorAll(".page .card, .page .note, .page h2, .page table.t, .chapter, .stage").forEach((el) => {
      if (seen.has(el) || el.classList.contains("in")) return;
      seen.add(el); el.classList.add("auto-rv"); io.observe(el);
    });
    scan();
    const mo = new MutationObserver(scan); mo.observe(document.querySelector("main")!, { childList: true, subtree: true });
    return () => { io.disconnect(); mo.disconnect(); };
  }, [loc.pathname]);
  const full = loc.pathname.startsWith("/explore");
  const prog = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const f = () => { const h = document.documentElement.scrollHeight - innerHeight; if (prog.current) prog.current.style.transform = `scaleX(${h > 0 ? scrollY / h : 0})`; };
    addEventListener("scroll", f, { passive: true }); f();
    return () => removeEventListener("scroll", f);
  }, [loc.pathname]);
  return (
    <>
      <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden>
        {/* undo the export's display gamma (1/1.6) and haze: natural-looking true colour */}
        <filter id="tc" colorInterpolationFilters="sRGB">
          <feComponentTransfer><feFuncR type="gamma" amplitude="1.25" exponent="2.4" /><feFuncG type="gamma" amplitude="1.15" exponent="2.2" />
            <feFuncB type="gamma" amplitude="0.95" exponent="2.0" /></feComponentTransfer>
          <feColorMatrix type="saturate" values="1.6" />
        </filter>
      </svg>
      <div ref={prog} className="scroll-prog" />
      <Nav />
      <main key={loc.pathname.split("/")[1]} className={full ? "" : "page-enter"}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/explore" element={<Explore />} />
          <Route path="/lab" element={<Lab />} />
          <Route path="/models" element={<Models />} />
          <Route path="/models/:id" element={<ModelDetail />} />
          <Route path="/evidence" element={<Evidence />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/story" element={<Story />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </main>
      {!full && <Footer generated={data?.generated} />}
    </>
  );
}
export default function App() { return <HashRouter><Shell /></HashRouter>; }
