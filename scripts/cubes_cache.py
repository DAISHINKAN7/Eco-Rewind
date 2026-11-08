"""Keep the Zarr cubes across Colab sessions: restore them from Drive, or build them and save them there.

    python scripts/cubes_cache.py --drive /content/drive/MyDrive/EcoRewind2/cubes --local /content/cubes \
        --exports-drive /content/drive/MyDrive/EcoRewind2_exports [--min-free-gb 15]

1. If <drive>/<site>_<track>.zarr.zip exists: copy + unzip it to --local (minutes).
2. Otherwise: copy the exports to the VM, build the missing cubes, and save them to Drive as zips if Drive has
   at least --min-free-gb free (else keep them on the VM only and say so).
"""
import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from ecorewind.data.cube import Cube  # noqa: E402

NAMES = [f"{s}_{t}" for s in ("everglades", "mississippi") for t in ("A", "B")]


def run(cmd):
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--drive", required=True)
    ap.add_argument("--local", required=True)
    ap.add_argument("--exports-drive", required=True)
    ap.add_argument("--exports-local", default="/content/exports")
    ap.add_argument("--min-free-gb", type=float, default=0, help="skip saving to Drive below this free space")
    a = ap.parse_args()
    drive, local = Path(a.drive), Path(a.local)
    local.mkdir(parents=True, exist_ok=True)
    for n in NAMES:
        z = drive / f"{n}.zarr.zip"
        if (local / f"{n}.zarr").is_dir() or not z.exists():
            continue
        print(f"restoring {n} from Drive ({z.stat().st_size / 1e9:.2f} GB)", flush=True)
        tmp = local / z.name
        shutil.copyfile(z, tmp)
        with zipfile.ZipFile(tmp) as zf:
            zf.extractall(local / f"{n}.zarr")
        tmp.unlink()
    missing = [n for n in NAMES if not (local / f"{n}.zarr").is_dir()]
    if missing:
        print(f"building {missing} from the exports", flush=True)
        run([sys.executable, str(REPO / "scripts/copy_exports.py"), "--src", a.exports_drive, "--dst", a.exports_local])
        probe = drive if drive.exists() else drive.parent
        free = shutil.disk_usage(probe).free / 1e9
        save = free >= a.min_free_gb
        print(f"Drive free: {free:.1f} GB -> {'saving cubes to Drive' if save else 'NOT saving (not enough space)'}", flush=True)
        cmd = [sys.executable, str(REPO / "scripts/build_cube.py"), "--exports", a.exports_local, "--out", str(local)]
        if save:
            drive.mkdir(parents=True, exist_ok=True)
            cmd += ["--zip-to", str(drive)]
        run(cmd)
    for n in NAMES:
        c = Cube(local / f"{n}.zarr")
        print(f"{n}: T={len(c.keys)} shape={c.shape} hash {c.data_hash[:12]}")


if __name__ == "__main__":
    main()
