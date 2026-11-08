"""Cancel queued (READY) EcoRewind 2.0 export tasks whose name contains a pattern.

    python gee/cancel.py --project <id> --match "_A_[0-9]{4}Q"        # queued Track A optical tasks (not S1)
    python gee/cancel.py --project <id> --match "_A_[0-9]{4}Q" --yes  # actually cancel (default only lists)
"""
import argparse
import re

from common import ee_init, load_configs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project")
    p.add_argument("--match", required=True, help="regular expression on the task name")
    p.add_argument("--yes", action="store_true")
    a = p.parse_args()
    ee = ee_init(load_configs(), a.project)
    hits = [t for t in ee.data.getTaskList()
            if t.get("description", "").startswith("ecorewind2_") and re.search(a.match, t["description"])
            and t.get("state") == "READY"]
    for t in hits:
        print(("cancel " if a.yes else "would cancel ") + t["description"])
        if a.yes:
            ee.data.cancelTask(t["id"])
    print(f"{len(hits)} tasks {'cancelled' if a.yes else 'matched (dry run; add --yes)'}")


if __name__ == "__main__":
    main()
