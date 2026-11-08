"""Copy the Phase 0 exports from Drive to the Colab VM disk, verifying sizes, with retries.

Reading many large files at random positions through the Drive mount is unreliable ("Transport endpoint
is not connected"); one sequential copy is not. Files already copied with the right size are skipped.

    python scripts/copy_exports.py --src /content/drive/MyDrive/EcoRewind2_exports --dst /content/exports
"""
import argparse
import os
import shutil
import time


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--retries", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(a.dst, exist_ok=True)
    names = sorted(f for f in os.listdir(a.src) if f.endswith(".tif"))
    bad = []
    for i, f in enumerate(names, 1):
        s, d = os.path.join(a.src, f), os.path.join(a.dst, f)
        for attempt in range(a.retries):
            try:
                want = os.path.getsize(s)
                if os.path.exists(d) and os.path.getsize(d) == want:
                    break
                shutil.copyfile(s, d)
                if os.path.getsize(d) == want:
                    break
            except OSError as e:
                print(f"  retry {f}: {e.__class__.__name__}", flush=True)
                time.sleep(5 * (attempt + 1))
        else:
            bad.append(f)
        if i % 40 == 0:
            print(f"{i}/{len(names)}", flush=True)
    print(f"copied {len(names) - len(bad)}/{len(names)}; failed: {bad}")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
