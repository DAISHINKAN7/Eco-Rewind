"""Check every event / placebo evaluation window against NOAA HURDAT2 (MASTER_PROMPT §6.8, §16).

For each cutoff in configs/preregistration.yaml it lists every Atlantic storm whose best-track centre
came within --radius-km of the site AOI centre between the cutoff quarter start and the end of the last
evaluable quarter, with the closest approach and the peak wind near the site. A placebo window must
contain no storm of tropical-storm strength (>= 34 kt) within the radius; anything found is reported
as a conflict for the user to decide (the script never edits the pre-registration).

    python scripts/check_storm_record.py --out reports/storm_record.md            # downloads HURDAT2
    python scripts/check_storm_record.py --hurdat path/to/hurdat2.txt --out ...   # offline copy
"""
from __future__ import annotations

import argparse
import math
import re
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from ecorewind.data.events import load_cutoffs, quarters_between  # noqa: E402
from ecorewind.data.periods import parse_q, quarter_window  # noqa: E402

INDEX = "https://www.nhc.noaa.gov/data/hurdat/"


def fetch_hurdat() -> str:
    html = urllib.request.urlopen(INDEX, timeout=60).read().decode()
    names = sorted(set(re.findall(r"hurdat2-1851-\d{4}-\d+\.txt", html)))
    if not names:
        raise SystemExit("no hurdat2-1851-*.txt listed at " + INDEX)
    return urllib.request.urlopen(INDEX + names[-1], timeout=120).read().decode(), names[-1]


def parse(text: str) -> list[dict]:
    """HURDAT2 -> list of {id, name, points: [(datetime, lat, lon, wind_kt, status)]}."""
    storms, cur = [], None
    for line in text.splitlines():
        f = [x.strip() for x in line.split(",")]
        if len(f) >= 3 and re.fullmatch(r"AL\d{6}", f[0]):
            cur = {"id": f[0], "name": f[1], "points": []}
            storms.append(cur)
        elif cur is not None and len(f) >= 7 and re.fullmatch(r"\d{8}", f[0]):
            t = datetime.strptime(f[0] + f[1].zfill(4), "%Y%m%d%H%M")
            lat = float(f[4][:-1]) * (1 if f[4].endswith("N") else -1)
            lon = float(f[5][:-1]) * (-1 if f[5].endswith("W") else 1)
            cur["points"].append((t, lat, lon, int(f[6]), f[3]))
    return storms


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def window(cut) -> tuple[date, date]:
    """Cutoff quarter start .. end of the last evaluable quarter (max_horizon quarters after it)."""
    y, q = parse_q(cut.quarter)
    q_last = q + cut.max_horizon
    y_last, q_last = y + (q_last - 1) // 4, (q_last - 1) % 4 + 1
    return quarter_window(cut.quarter)[0], quarter_window(f"{y_last}Q{q_last}")[1]


def nearby(storms, centre, start, end, radius_km) -> list[dict]:
    out = []
    for s in storms:
        pts = [p for p in s["points"] if start <= p[0].date() < end]
        close = [(haversine_km(centre[1], centre[0], p[1], p[2]), p) for p in pts]
        close = [(d, p) for d, p in close if d <= radius_km]
        if close:
            d, p = min(close, key=lambda x: x[0])
            out.append({"id": s["id"], "name": s["name"], "closest_km": round(d), "when": p[0].date().isoformat(),
                        "max_wind_kt_in_radius": max(pp[3] for _, pp in close)})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prereg", default=str(REPO / "configs" / "preregistration.yaml"))
    ap.add_argument("--sites", default=str(REPO / "configs" / "sites.yaml"))
    ap.add_argument("--hurdat", help="local HURDAT2 file (default: download the latest)")
    ap.add_argument("--radius-km", type=float, default=200)
    ap.add_argument("--out", default=str(REPO / "reports" / "storm_record.md"))
    a = ap.parse_args()
    prereg = yaml.safe_load(Path(a.prereg).read_text())
    sites = yaml.safe_load(Path(a.sites).read_text())["sites"]
    if a.hurdat:
        text, source = Path(a.hurdat).read_text(), Path(a.hurdat).name
    else:
        text, source = fetch_hurdat()
    storms = parse(text)
    last_year = max(p[0].year for s in storms for p in s["points"])
    md = ["# Storm record check of event and placebo windows", "",
          f"Source: NOAA HURDAT2 `{source}` (best tracks to {last_year}). Radius {a.radius_km:.0f} km around the AOI "
          "centre. A placebo window passes if no storm of ≥ 34 kt came within the radius.", "",
          "| Cutoff | Kind | Window | Storms within radius (closest km, date, max wind kt) | Verdict |", "|---|---|---|---|---|"]
    conflicts = []
    for cut in load_cutoffs(prereg):
        w, s_, e, n = sites[cut.site]["bounds_lonlat"]
        centre = ((w + e) / 2, (s_ + n) / 2)
        start, end = window(cut)
        hits = nearby(storms, centre, start, end, a.radius_km)
        strong = [h for h in hits if h["max_wind_kt_in_radius"] >= 34]
        if cut.kind == "event":
            verdict = "event window (storms expected)"
        elif end.year > last_year:
            verdict = "⚠️ window extends beyond the record"
            conflicts.append(cut.name)
        else:
            verdict = "✅ clean" if not strong else "❌ conflict"
            if strong:
                conflicts.append(cut.name)
        desc = "; ".join(f"{h['name']} {h['id']} ({h['closest_km']} km, {h['when']}, {h['max_wind_kt_in_radius']} kt)" for h in hits) or "none"
        md.append(f"| {cut.name} | {cut.kind} | {start} → {end} (cutoff {cut.quarter}, H ≤ {cut.max_horizon}) | {desc} | {verdict} |")
    md += ["", f"**Placebo conflicts: {', '.join(conflicts) or 'none'}.** "
           "Any conflict must be resolved by the user (shorten max_horizon or replace the window) and re-registered."]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
