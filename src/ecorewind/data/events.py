"""Temporal cutoffs for real events and placebo windows (MASTER_PROMPT §3 rule 1, §5.5, §6.8).

For a cutoff date d (real landfall or fake placebo landfall), the quarter containing d is the cutoff
quarter. Model inputs, normalisation statistics and early stopping may only use quarters strictly
before it; evaluation starts at the quarter after it. A real event quarter has no regular composite
(only _PRE/_POST partials); for a placebo the regular composite of the cutoff quarter is skipped.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .periods import parse_q, quarter_of


@dataclass(frozen=True)
class Cutoff:
    name: str            # e.g. ida, ida_placebo_2018
    site: str
    date: date
    kind: str            # event | placebo
    max_horizon: int     # quarters after the cutoff quarter that may be evaluated

    @property
    def quarter(self) -> str:
        return quarter_of(self.date)


def split_indices(keys: list[str], cutoff: Cutoff, lead0: bool = False) -> tuple[list[int], list[int]]:
    """Indices of `keys` usable as model history (< cutoff quarter) and as evaluation targets
    (> cutoff quarter, at most max_horizon quarters after it). Keys are regular quarters 'YYYYQn', plus
    'YYYYQn_POST' event partials. With lead0 (amendment A2), the cutoff quarter is also a target ("lead 0"):
    its _POST partial for an event; for a placebo its _PPOST composite (same days, amendment A3) if present, else
    the full quarter. _PRE partials are never used."""
    cq = parse_q(cutoff.quarter)
    hist, target, zero = [], [], []
    for i, k in enumerate(keys):
        base, _, part = k.partition("_")
        q = parse_q(base)
        if part:
            if lead0 and q == cq and (part, cutoff.kind) in (("POST", "event"), ("PPOST", "placebo")):
                zero.append(i)
            continue
        if q == cq and lead0 and cutoff.kind == "placebo" and f"{base}_PPOST" not in keys:
            zero.append(i)
        elif q < cq:
            hist.append(i)
        elif q > cq and quarters_between(cq, q) <= cutoff.max_horizon:
            target.append(i)
    return hist, zero + target


def quarters_between(a: tuple[int, int], b: tuple[int, int]) -> int:
    return (b[0] - a[0]) * 4 + (b[1] - a[1])


def load_cutoffs(prereg: dict) -> list[Cutoff]:
    out = []
    for name, e in prereg["events"].items():
        out.append(Cutoff(name, e["site"], date.fromisoformat(str(e["landfall"])), "event", int(e["max_horizon"])))
    for name, p in prereg["placebos"].items():
        if p.get("excluded"):
            continue
        out.append(Cutoff(name, p["site"], date.fromisoformat(str(p["date"])), "placebo", int(p["max_horizon"])))
    return out
