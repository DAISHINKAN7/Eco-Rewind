"""Verified copy of the PPOST exports from Drive (Drive can hand over partial files)."""
import glob, os, shutil, sys, time

import rasterio

src, dst_dir = sys.argv[1], sys.argv[2]
os.makedirs(dst_dir, exist_ok=True)
for f in sorted(glob.glob(f"{src}/*PPOST*.tif")):
    dst = os.path.join(dst_dir, os.path.basename(f))
    for i in range(5):
        try:
            if not (os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(f)):
                shutil.copyfile(f, dst)
            with rasterio.open(dst) as ds:
                ds.read()
            break
        except Exception as e:
            print("retry", os.path.basename(f), type(e).__name__, flush=True)
            if os.path.exists(dst):
                os.remove(dst)
            time.sleep(10)
print("PPOST files ok:", len(os.listdir(dst_dir)))
