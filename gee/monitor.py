"""Show the state of all EcoRewind 2.0 export tasks; list failures with their error.

    python gee/monitor.py --project <id>            # once
    python gee/monitor.py --project <id> --watch 300 # refresh every 5 min until none are pending
"""
import argparse
import time
from collections import Counter

from common import ee_init, load_configs


def snapshot(ee):
    tasks = [t for t in ee.data.getTaskList() if t.get("description", "").startswith("ecorewind2_")]
    latest = {}
    for t in sorted(tasks, key=lambda t: t.get("creation_timestamp_ms", 0)):
        latest[t["description"]] = t          # keep the newest attempt per file
    return list(latest.values())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project")
    p.add_argument("--watch", type=int, help="seconds between refreshes")
    a = p.parse_args()
    ee = ee_init(load_configs(), a.project)
    while True:
        ts = snapshot(ee)
        c = Counter(t["state"] for t in ts)
        print(time.strftime("%H:%M:%S"), dict(c), f"total {len(ts)}")
        for t in ts:
            if t["state"] == "FAILED":
                print(f"  FAILED {t['description']}: {t.get('error_message', '')[:200]}")
        if not a.watch or not (c["READY"] + c["RUNNING"] + c.get("PENDING", 0)):
            break
        time.sleep(a.watch)


if __name__ == "__main__":
    main()
