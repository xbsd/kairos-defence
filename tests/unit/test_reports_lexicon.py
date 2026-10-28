"""Guardrail scan and clue lexicon for reports (SPEC §8.8, §12.4, §23; CLAUDE.md rule 9)."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from kairos_defense.sim import lexicon as lx
from kairos_defense.sim.reports import make_reports


def test_reports_have_no_forbidden_content(g42, planted, world_names) -> None:
    texts = [r.text for g in (g42, planted) for r in g.paper.reports]
    texts += [a.rationale for g in (g42, planted) for a in g.paper.assessments]
    texts += [a.author for g in (g42, planted) for a in g.paper.assessments]
    for f in planted.paper.facts:  # many more, every source and style
        for base in ("ALPHA", "BRAVO", "CHARLIE"):
            for k in range(40):
                texts += [r.text for r in make_reports(replace(f, installation_id=base),
                                                       np.random.default_rng(k))]  # fmt: skip
    assert len(texts) > 1000
    for t in texts:
        assert lx.forbidden(t, world_names) == [], t


@pytest.mark.parametrize(
    "text",
    ["Plate ABC-1234 was noted.", "A sedan, tag number 7XYZ123.", "Vehicle ABC1234 left.",
     "John Smith was seen nearby.", "SGT MILLER RESPONDED.", "Sgt. Rivera responded.",
     "A tall man in a cap.", "She left on foot.", "Parked at 123 Main St overnight.",
     "Call 555-123-4567.", "Contact x.y@example.com.", "The registration was checked."],
)  # fmt: skip
def test_reports_scanner_catches_offenders(text: str) -> None:
    assert lx.forbidden(text) != []


@pytest.mark.parametrize(
    "text",
    ["A white pickup was parked on County Rd 12 from 21:20 to 22:05.",
     "SF BLOTTER 03 MAY 2026 22:10: PATROL OBSERVED SUAS VIC FUEL FARM, EST 350 FT.",
     "THE OPERATOR MAY HAVE LAUNCHED FROM NEAR FARM RD 300.",
     "Remote ID serial SN-0123456789ABCDEF received.",
     "Unauthorized UAS activity near Installation Charlie and Installation Juliet.",
     "Radar tracks 7008-7012. Route 66B. State Hwy 7.", "Deputy responded to a call."],
)  # fmt: skip
def test_reports_scanner_allows_world_vocabulary(text: str, world_names) -> None:
    assert lx.forbidden(text, world_names) == []


def test_reports_name_lexicon_avoids_world_words(world) -> None:
    words = set()
    for phrase in (*lx.VEHICLES, *lx.LIGHTS, *lx.SOUNDS, *lx.LAUNCH_SITES, *lx.DIRECTIONS,
                   *lx.MINOR_ROADS, *world.sites):  # fmt: skip
        words |= {w.lower() for w in phrase.replace("-", " ").split()}
    assert not words & lx.NAMES


def test_reports_find_clues_reads_capitals() -> None:
    text = "A DARK SUV WAS PARKED ON COUNTY RD 12. UAS DEPARTED NORTHWEST 22:05, NO VISIBLE LIGHTS."
    found = lx.find_clues(text, ["County Rd 12"])
    assert found == {("vehicle", "dark SUV"), ("road", "County Rd 12"),
                     ("departure", "northwest"), ("lights", "no visible lights")}  # fmt: skip
    assert lx.find_clues("near the north fence", ["County Rd 12"]) == set()  # place, not departure
    assert lx.find_clues("A motorcycle, flew east.", []) == {
        ("vehicle", "motorcycle"), ("departure", "east")}  # fmt: skip


@pytest.mark.parametrize(
    ("bearing", "word"),
    [(0, "north"), (22.4, "north"), (22.6, "northeast"), (90, "east"), (315, "northwest"),
     (337.4, "northwest"), (337.6, "north"), (359.9, "north")],
)  # fmt: skip
def test_reports_compass8(bearing: float, word: str) -> None:
    assert lx.compass8(bearing) == word


def test_reports_park_names() -> None:
    assert lx.park_name("COASTAL-PARK-5") == "Coastal Park 5"
    assert lx.park_name("DESERT-PARK-2") == "Desert Park 2"
