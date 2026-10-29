"""SPEC §12.4: clue extraction (vehicles, gazetteer roads, spans) and linking."""

from __future__ import annotations

import numpy as np
import pandas as pd

from kairos_defense.forecast.analog import roads_crossing
from kairos_defense.recall.clues import Clue, extract_clues, link_clues

ROADS = ["County Rd 12", "Farm Rd 300", "Route 66B", "State Hwy 7"]
DELTA = ("Security forces patrol observed a small drone near the fuel farm at about 21:35, est. "
         "300 ft, a flashing white light. A white pickup was parked on County Rd 12 from 21:20 to "
         "22:05 and left shortly after the drone flew northwest.")  # fmt: skip


def test_extracts_vehicle_and_road_with_spans() -> None:
    clues = extract_clues(DELTA, ROADS)
    assert [(c.type, c.value) for c in clues] == [("vehicle", "white pickup"),
                                                  ("road", "County Rd 12")]  # fmt: skip
    assert [DELTA[c.start : c.end] for c in clues] == ["white pickup", "County Rd 12"]


def test_blotter_capitals_read_the_same() -> None:
    text = "A WHITE PICKUP WAS PARKED ON COUNTY RD 12. A BLACK SUV LEFT."
    clues = extract_clues(text, ROADS)
    assert [(c.type, c.value) for c in clues] == [("vehicle", "white pickup"),
                                                  ("road", "County Rd 12"),
                                                  ("vehicle", "black SUV")]  # fmt: skip
    assert [text[c.start : c.end] for c in clues] == ["WHITE PICKUP", "COUNTY RD 12", "BLACK SUV"]


def test_only_lexicon_vehicles_and_gazetteer_roads() -> None:
    """Minor roads outside the roads table are not roads to link (D-086); vehicles come from the
    generator's lexicon only, with the color optional (the paperwork writes "a motorcycle")."""
    text = ("Seen near Ridge Rd and Quarry Rd: a car, a bicycle, a purple van and a motorcycle; "
            "County Rd 120 and Route 66 are not gazetteer roads.")  # fmt: skip
    got = [(c.type, c.value) for c in extract_clues(text, ROADS)]
    assert got == [("vehicle", "van"), ("vehicle", "motorcycle")]
    assert extract_clues("a pickups convoy, vans", ROADS) == []


def test_extraction_agrees_with_clue_truth(world, planted, g42) -> None:
    """On the generator's reports, vehicle and gazetteer-road clues equal ``clue_truth`` for
    those two types (true and false clues alike: extraction reads the text, not the truth)."""
    roads = [r.name for r in world.roads]
    reports = pd.concat([planted.tables["reports"], g42.tables["reports"]])
    truth = pd.concat([planted.truth["clue_truth"], g42.truth["clue_truth"]])
    truth = truth[(truth.clue_type == "vehicle") | truth.clue_value.isin(roads)]
    want = {rid: set(zip(g.clue_type, g.clue_value, strict=True))
            for rid, g in truth.groupby("report_id")}  # fmt: skip
    seen = 0
    for rid, text in zip(reports.report_id, reports.text, strict=True):
        got = {(c.type, c.value) for c in extract_clues(text, roads)}
        assert got == want.get(rid, set()), (rid, text)
        seen += bool(got)
    assert seen >= 3  # the planted DELTA report among them
    assert any(v == "County Rd 12" for s in want.values() for _, v in s)


def test_clue_linked_across_two_matched_incidents() -> None:
    a = [Clue("vehicle", "white pickup", 0, 12), Clue("vehicle", "red van", 20, 27)]
    b = [Clue("vehicle", "white pickup", 5, 17)]
    out = link_clues({"INC-A": {"R-A": a}, "INC-B": {"R-B": b}})
    pick_a, van = out["INC-A"]["R-A"]
    assert pick_a.linked and pick_a.links == ("white pickup also appears in reports of INC-B.",)
    assert out["INC-B"]["R-B"][0].links == ("white pickup also appears in reports of INC-A.",)
    assert not van.linked and van.to_dict()["linked"] is False
    # one report recalled for two matches does not link with itself
    same = link_clues({"INC-A": {"R-A": a}, "INC-B": {"R-A": a}})
    assert not any(c.linked for c in same["INC-A"]["R-A"])


def test_road_clue_linked_when_it_crosses_the_zone(p1_index) -> None:
    from shapely import wkt

    roads = p1_index.gen.tables["roads"]
    lines = {
        r.name: wkt.loads(r.line_wkt) for r in roads[roads.region_id == "COASTAL"].itertuples()
    }
    on_road = np.asarray(lines["County Rd 12"].interpolate(0.5, normalized=True).coords[0])
    clue = {"INC-A": {"R-A": [Clue("road", "County Rd 12", 0, 12)]}}
    zone = roads_crossing(on_road, 150.0, lines)
    assert "County Rd 12" in zone
    (c,) = link_clues(clue, zone)["INC-A"]["R-A"]
    assert c.links == ("County Rd 12 runs through tonight's predicted zone.",)
    far = min(
        (on_road + d for d in ([1000, 0], [-1000, 0], [0, 1000], [0, -1000])),
        key=lambda p: -lines["County Rd 12"].distance(wkt.loads(f"POINT ({p[0]} {p[1]})")),
    )
    assert lines["County Rd 12"].distance(wkt.loads(f"POINT ({far[0]} {far[1]})")) > 300
    (c,) = link_clues(clue, roads_crossing(far, 150.0, lines))["INC-A"]["R-A"]
    assert not c.linked
