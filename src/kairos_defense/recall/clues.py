"""Clue extraction and linking (SPEC §12.4, D-086).

Two clue types are extracted, each with its canonical value and its character span:

- ``vehicle``: ``[<color>] <type>`` from the generator's fixed lexicons (``sim.lexicon``: white,
  black, dark, silver, red, blue, gray, green, tan × pickup, SUV, sedan, hatchback, van, truck,
  motorcycle). The color is optional because the paperwork also mentions a bare "motorcycle".
- ``road``: a name from the ``roads`` table (the gazetteer). Minor roads outside it ("Ridge Rd")
  are not roads to link.

Matching is case-insensitive, so blotter capitals read the same (D-040). ``report_clues`` stores
``(report_id, clue_type, clue_value)``; spans are recomputed from the text when shown.

A clue is **linked** when the same (type, value) appears in reports of two or more matched
incidents, or when it is a road that crosses tonight's predicted recovery zone (the forecast's
``roads``). Each link carries the sentence the UI shows.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Mapping
from dataclasses import asdict, dataclass

from kairos_defense.sim.lexicon import VEHICLE_COLORS, VEHICLE_TYPES

CLUE_TYPES = ("vehicle", "road")
_TYPES = {t.lower(): t for t in VEHICLE_TYPES}
VEHICLE_RE = re.compile(
    r"\b(?:(" + "|".join(VEHICLE_COLORS) + r")\s+)?(" + "|".join(_TYPES) + r")\b", re.I
)


@dataclass(frozen=True)
class Clue:
    """One clue in a report: ``text[start:end]`` is the phrase as written."""

    type: str  # vehicle | road
    value: str  # canonical: "white pickup", "black SUV", "County Rd 12"
    start: int
    end: int


@dataclass(frozen=True)
class LinkedClue:
    """A clue with the sentences that link it (empty: not linked)."""

    type: str
    value: str
    start: int
    end: int
    links: tuple[str, ...] = ()

    @property
    def linked(self) -> bool:
        return bool(self.links)

    def to_dict(self) -> dict:
        return {**asdict(self), "links": list(self.links), "linked": self.linked}


def _road_re(name: str) -> re.Pattern[str]:
    return re.compile(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", re.I)


def extract_clues(text: str, road_names: Iterable[str]) -> list[Clue]:
    """Vehicle and gazetteer-road clues in ``text``, in text order."""
    out = []
    for m in VEHICLE_RE.finditer(text):
        color, kind = m.group(1), _TYPES[m.group(2).lower()]
        out.append(Clue("vehicle", f"{color.lower()} {kind}" if color else kind, *m.span()))
    for name in sorted(set(road_names)):
        out += [Clue("road", name, *m.span()) for m in _road_re(name).finditer(text)]
    return sorted(out, key=lambda c: (c.start, c.end, c.type))


def link_clues(
    reports: Mapping[str, Mapping[str, list[Clue]]], zone_roads: Collection[str] = ()
) -> dict[str, dict[str, list[LinkedClue]]]:
    """Link the clues of recalled reports. ``reports``: matched incident -> report id -> clues;
    ``zone_roads``: names of tonight's roads crossing the predicted zone. Returns the same shape
    with each clue's link sentences. A cross-match link needs another report recalled for another
    matched incident (one report recalled for two matches does not link with itself)."""
    seen: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for inc, by_report in reports.items():
        for rid, clues in by_report.items():
            for c in clues:
                seen.setdefault((c.type, c.value), set()).add((inc, rid))
    out: dict[str, dict[str, list[LinkedClue]]] = {}
    for inc, by_report in reports.items():
        out[inc] = {}
        for rid, clues in by_report.items():
            linked = []
            for c in clues:
                links = []
                others = sorted({i for i, r in seen[(c.type, c.value)] if i != inc and r != rid})
                if others:
                    links.append(f"{c.value} also appears in reports of {', '.join(others)}.")
                if c.type == "road" and c.value in zone_roads:
                    links.append(f"{c.value} runs through tonight's predicted zone.")
                linked.append(LinkedClue(c.type, c.value, c.start, c.end, tuple(links)))
            out[inc][rid] = linked
    return out
