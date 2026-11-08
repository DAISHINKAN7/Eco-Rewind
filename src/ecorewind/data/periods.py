"""Quarterly compositing windows, including split event quarters.

All windows are half-open [start, end) dates, matching ee.Filter.date.
The event quarter has no regular composite; it is exported as two partials:
PRE  = quarter start -> landfall (exclusive)
POST = landfall + post_offset_days -> quarter end
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Period:
    key: str          # e.g. 2017Q3, 2017Q3_PRE
    start: date
    end: date         # exclusive
    kind: str = "quarter"   # quarter | pre | post


def parse_q(k: str) -> tuple[int, int]:
    y, q = k.split("Q")
    return int(y), int(q)


def quarter_keys(start: str, end: str) -> list[str]:
    (y, q), stop = parse_q(start), parse_q(end)
    out = []
    while (y, q) <= stop:
        out.append(f"{y}Q{q}")
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def quarter_window(key: str) -> tuple[date, date]:
    y, q = parse_q(key)
    start = date(y, 3 * q - 2, 1)
    end = date(y + 1, 1, 1) if q == 4 else date(y, 3 * q + 1, 1)
    return start, end


def quarter_of(d: date) -> str:
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def periods(start: str, end: str, landfall: date | None = None, post_offset_days: int = 3) -> list[Period]:
    ev = quarter_of(landfall) if landfall else None
    out = []
    for k in quarter_keys(start, end):
        s, e = quarter_window(k)
        if k != ev:
            out.append(Period(k, s, e))
            continue
        out.append(Period(f"{k}_PRE", s, landfall, "pre"))
        post_start = landfall + timedelta(days=post_offset_days)
        if post_start < e:
            out.append(Period(f"{k}_POST", post_start, e, "post"))
    return out


def placebo_post_periods(placebos: dict, site: str, track: str, post_offset_days: int = 3) -> list[Period]:
    """Amendment A3: for each pre-registered placebo of the site/track, the composite over the same days as an event
    _POST partial (fake date + offset -> end of its quarter), key 'YYYYQn_PPOST'. Placebo lead 0 uses these."""
    out = []
    for p in placebos.values():
        if p.get("excluded") or p["site"] != site or track not in p["tracks"]:
            continue
        d = date.fromisoformat(str(p["date"]))
        k = quarter_of(d)
        out.append(Period(f"{k}_PPOST", d + timedelta(days=post_offset_days), quarter_window(k)[1], "post"))
    return out
