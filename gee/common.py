"""Shared Earth Engine export plumbing: configs, grids, task planning, export, manifest.

Task planning (which files, which date windows, which grid) is pure Python and
unit-tested offline. Only build_* and export functions touch Earth Engine.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from ecorewind.data.grid import Grid, site_grid  # noqa: E402
from ecorewind.data.periods import Period, periods  # noqa: E402

# Reports and export manifests; set ECOREWIND_REPORTS to a Drive folder in Colab so they persist.
REPORTS = Path(os.environ.get("ECOREWIND_REPORTS", REPO / "reports"))
S2_PRODUCT_FILE = REPORTS / "exports" / "s2_product.json"


def load_configs(config_dir: Path = REPO / "configs") -> dict:
    cfg = {}
    for name in ("sites", "tracks", "events"):
        cfg.update(yaml.safe_load((config_dir / f"{name}.yaml").read_text()))
    return cfg


def landfall_for(cfg: dict, site: str) -> date | None:
    for ev in cfg["events"].values():
        if ev["site"] == site:
            return date.fromisoformat(str(ev["landfall"]))
    return None


def grid_for(cfg: dict, site: str, track: str) -> Grid:
    s = cfg["sites"][site]
    return site_grid(s["bounds_lonlat"], s["crs"], cfg["tracks"][track]["res"], s.get("buffer_m", 0))


def site_periods(cfg: dict, site: str, track: str) -> list[Period]:
    t = cfg["tracks"][track]
    return periods(t["start"], t["end"], landfall_for(cfg, site), cfg.get("post_offset_days", 3))


@dataclass
class Task:
    kind: str           # A | B | S1 | static
    site: str
    track: str          # grid the file is on: A (10 m) or B (30 m)
    file: str           # Drive file name without .tif
    period: Period | None
    grid: Grid
    bands: list[str] = field(default_factory=list)

    @property
    def description(self) -> str:   # EE task names: <=100 chars, [A-Za-z0-9_-]
        return f"ecorewind2_{self.file}"[:100]


def file_name(site: str, track: str, key: str | None, sensor: str = "") -> str:
    parts = [site, track] + ([sensor] if sensor else []) + ([key] if key else [])
    return "_".join(parts)


def plan(cfg: dict, kind: str, sites: list[str] | None = None, tracks=("A", "B")) -> list[Task]:
    """List every export task of one kind, in a stable order."""
    out = []
    for site in sites or list(cfg["sites"]):
        if kind in ("A", "B"):
            out += [Task(kind, site, kind, file_name(site, kind, p.key), p, grid_for(cfg, site, kind))
                    for p in site_periods(cfg, site, kind)]
        elif kind == "S1":
            for tr in tracks:
                out += [Task("S1", site, tr, file_name(site, tr, p.key, "S1"), p, grid_for(cfg, site, tr))
                        for p in site_periods(cfg, site, tr)]
        elif kind == "static":
            out += [Task("static", site, tr, file_name(site, tr, None, "static"), None, grid_for(cfg, site, tr))
                    for tr in tracks]
        else:
            raise ValueError(kind)
    return out


def plan_placebo_post(cfg: dict, kind: str, sites: list[str] | None = None, tracks=("A", "B")) -> list[Task]:
    from ecorewind.data.periods import placebo_post_periods
    plc = yaml.safe_load((REPO / "configs/preregistration.yaml").read_text())["placebos"]
    out = []
    for site in sites or list(cfg["sites"]):
        for tr in ((kind,) if kind in ("A", "B") else tracks):
            for p in placebo_post_periods(plc, site, tr, cfg.get("post_offset_days", 3)):
                out.append(Task(kind, site, tr, file_name(site, tr, p.key, "S1" if kind == "S1" else ""), p,
                                grid_for(cfg, site, tr)))
    return out


# ---------------------------------------------------------------- Earth Engine
def ee_init(cfg: dict, project: str | None = None):
    import ee
    project = project or cfg["export"].get("ee_project")
    if not project:
        raise SystemExit("Set export.ee_project in configs/tracks.yaml or pass --project")
    try:
        ee.Initialize(project=project)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=project)
    return ee


def ee_region(ee, grid: Grid):
    return ee.Geometry.Rectangle(list(grid.bounds), proj=grid.crs, geodesic=False)


def ee_window(p: Period) -> tuple[str, str]:
    return p.start.isoformat(), p.end.isoformat()


def mosaic_by(ee, col, key_prop: str):
    """One image per (date, key_prop) so overlapping tiles/slices of the same pass count once."""
    def tag(img):
        day = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd")
        return img.set("_mkey", day.cat("_").cat(ee.String(img.get(key_prop))))
    col = col.map(tag)
    keys = col.aggregate_array("_mkey").distinct()

    def one(k):
        sub = col.filter(ee.Filter.eq("_mkey", k))
        return sub.mosaic().set("system:time_start", sub.first().get("system:time_start"))
    return ee.ImageCollection(keys.map(one))


def with_empty_fallback(ee, col, bands: list[str]):
    """Add one fully masked image so an empty quarter still composites to a masked image
    (counts become 0) instead of an image with no bands, which would fail the export."""
    dummy = ee.Image.constant([0] * len(bands)).rename(bands).toFloat().updateMask(0)
    return col.merge(ee.ImageCollection([dummy]))


def existing_tasks(ee) -> set[str]:
    """Descriptions of tasks that are queued, running or finished (so re-runs skip them)."""
    keep = {"READY", "RUNNING", "COMPLETED", "PENDING"}
    return {t["description"] for t in ee.data.getTaskList() if t.get("state") in keep}


def start_export(ee, cfg: dict, task: Task, image):
    ex = cfg["export"]
    t = ee.batch.Export.image.toDrive(
        image=image, description=task.description, folder=ex["drive_folder"],
        fileNamePrefix=task.file, region=ee_region(ee, task.grid), crs=task.grid.crs,
        crsTransform=task.grid.crs_transform, maxPixels=int(1e10), fileFormat="GeoTIFF",
        formatOptions={"cloudOptimized": bool(ex.get("cloud_optimized", True)), "noData": ex["nodata"]},
    )
    t.start()
    return t.id


def write_manifest(rows: list[dict], name: str, out_dir: Path = REPORTS / "exports"):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"manifest_{name}.json"
    old = json.loads(path.read_text()) if path.exists() else []
    by_file = {r["file"]: r for r in old}
    by_file.update({r["file"]: r for r in rows})
    path.write_text(json.dumps(sorted(by_file.values(), key=lambda r: r["file"]), indent=1, default=str))
    return path


def manifest_row(task: Task, extra: dict) -> dict:
    g = task.grid
    return {
        "file": task.file + ".tif", "kind": task.kind, "site": task.site, "track": task.track,
        "period": asdict(task.period) if task.period else None, "bands": task.bands,
        "crs": g.crs, "crs_transform": g.crs_transform, "width": g.width, "height": g.height,
        "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **extra,
    }


def cli(description: str) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--site", nargs="*", help="sites (default: all)")
    p.add_argument("--only", nargs="*", help="only these period keys, e.g. 2021Q4 2017Q3_POST")
    p.add_argument("--project", help="Earth Engine project id (overrides config)")
    p.add_argument("--dry-run", action="store_true", help="print the plan, submit nothing")
    p.add_argument("--limit", type=int, help="submit at most N tasks (for a first test)")
    p.add_argument("--placebo-post", action="store_true",
                   help="only the placebo _PPOST composites (amendment A3: same days as the event _POST partials)")
    p.add_argument("--force", action="store_true", help="resubmit even if a task with that name exists")
    return p.parse_args()


def run(kind: str, build, description: str, extra_fn=lambda cfg, task: {}, tracks=("A", "B")):
    """Shared main(): plan -> (dry-run | submit with skip-existing) -> manifest."""
    args = cli(description)
    cfg = load_configs()
    tasks = plan(cfg, kind, args.site, tracks)
    if args.placebo_post:
        tasks = plan_placebo_post(cfg, kind, args.site, tracks)
    if args.only:
        tasks = [t for t in tasks if t.period and t.period.key in args.only]
    if args.dry_run:
        for t in tasks:
            w = f"{t.period.start} -> {t.period.end}" if t.period else "static"
            print(f"{t.file:40s} {w:26s} {t.grid.crs} {t.grid.res} m {t.grid.width}x{t.grid.height}")
        print(f"{len(tasks)} tasks (dry run)")
        return
    ee = ee_init(cfg, args.project)
    done = set() if args.force else existing_tasks(ee)
    rows, n = [], 0
    for t in tasks:
        if t.description in done:
            print(f"skip (exists) {t.file}")
            continue
        if args.limit is not None and n >= args.limit:
            break
        image, bands = build(ee, cfg, t)
        t.bands = bands
        tid = start_export(ee, cfg, t, image)
        rows.append(manifest_row(t, {"task_id": tid, **extra_fn(cfg, t)}))
        n += 1
        print(f"submitted {t.file} ({tid})")
    if rows:
        print("manifest:", write_manifest(rows, kind))
    print(f"{n} submitted")
