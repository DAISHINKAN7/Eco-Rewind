"""Build the Zarr data cubes from the Phase 0 exports (MASTER_PROMPT §6.1). CPU only.

    python scripts/build_cube.py --exports /content/exports --out /content/cubes \
        [--site everglades] [--track A] [--zip-to /content/drive/MyDrive/EcoRewind2/cubes]

Writes <out>/<site>_<track>.zarr (directory store, fast locally). --zip-to also packs each cube into a
single <site>_<track>.zarr.zip there (Drive copes badly with thousands of small chunk files).
"""
from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from ecorewind.data.cube import Cube, build_cube  # noqa: E402


def load_cfg():
    cfg = {}
    for n in ("sites", "tracks", "events", "phase1"):
        cfg.update(yaml.safe_load((REPO / "configs" / f"{n}.yaml").read_text()))
    return cfg


def landfall(cfg, site):
    return next(date.fromisoformat(str(e["landfall"])) for e in cfg["events"].values() if e["site"] == site)


def zip_store(src: Path, dst: Path):
    tmp = dst.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(src).as_posix())
    tmp.replace(dst)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exports", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--site", nargs="*")
    ap.add_argument("--track", nargs="*")
    ap.add_argument("--zip-to")
    ap.add_argument("--force", action="store_true", help="rebuild even if a complete cube exists")
    a = ap.parse_args()
    cfg = load_cfg()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for site in a.site or list(cfg["sites"]):
        for track in a.track or list(cfg["tracks"]):
            t = cfg["tracks"][track]
            path = out / f"{site}_{track}.zarr"
            try:
                done = not a.force and Cube(path).data_hash
            except Exception:  # noqa: BLE001 - missing or partial cube
                done = False
            if done:
                print(f"{path.name}: exists (data_hash {Cube(path).data_hash[:12]}), skipping")
            else:
                print(f"building {path.name}")
                build_cube(Path(a.exports), path, site, track, t["start"], t["end"], landfall(cfg, site),
                           cfg["max_reflectance"], cfg["chunk"])
            if a.zip_to:
                dst = Path(a.zip_to) / f"{path.name}.zip"
                dst.parent.mkdir(parents=True, exist_ok=True)
                zip_store(path, dst)
                print(f"  packed -> {dst} ({dst.stat().st_size / 1e9:.2f} GB)")
            c = Cube(path)
            sz = sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) / 1e9
            print(f"  {path.name}: T={len(c.keys)} partials={c.partial_keys} C={len(c.channels)} "
                  f"HxW={c.shape} {sz:.2f} GB hash {c.data_hash[:12]}")
    if a.zip_to:
        shutil.copy(REPO / "configs" / "phase1.yaml", Path(a.zip_to) / "phase1.yaml")


if __name__ == "__main__":
    main()
