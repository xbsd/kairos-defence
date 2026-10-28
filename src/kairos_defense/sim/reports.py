"""Reports and clues (SPEC §8.8, Appendix A).

Counts per incident: probers and copycats 1-3, swarms 2-3, hobbyists 0-1 (60% none); live
incidents none (they are happening now, D-041). Sources are drawn without repeats with weights
BDOC 0.4, security forces 0.35, local PD 0.15, FAA 0.1; delays are uniform in the source's range
after the incident end, whole minutes; grades uniform in the source's list. A hobbyist whose
registered Remote ID was received gets the hobbyist template (security forces or local PD).

Security-forces style per base (Appendix A): narrative at ALPHA, DELTA, ECHO and KILO, blotter at
BRAVO, FOXTROT, GOLF and LIMA, terse elsewhere (a terse SF template added, D-040). Blotter text is
upper case and spells directions in full.

Clue model: in security-forces and local-PD reports a vehicle is observed with p = 0.35 (the
actor's vehicle with p = 0.8, else a random wrong one; actors without a vehicle only ever get
wrong ones) and a road is mentioned with p = 0.3 (the true road with p = 0.8). Lights and the
departure direction appear in every security-forces report, a sound in 30% of narrative ones, and
local-PD reports carry a witness clause half the time (launch site or sound); each is true with
p = 0.8. Every clue in a report's text has a ``clue_truth`` row (tested with
``lexicon.find_clues``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from kairos_defense.rng import stable_int
from kairos_defense.sim import lexicon as lx
from kairos_defense.sim.calendar import local_to_utc_ms, utc_ms_to_local
from kairos_defense.sim.facts import IncidentFacts

SOURCES = {  # delay after the incident end (s), grades (§8.8)
    "bdoc_log": ((0, 600), ("A2", "B2")),
    "security_forces": ((1200, 5400), ("B2", "B3", "C3")),
    "local_pd": ((7200, 172_800), ("C3", "C4")),
    "faa": ((86_400, 432_000), ("B3",)),
}
SOURCE_WEIGHTS = {"bdoc_log": 0.4, "security_forces": 0.35, "local_pd": 0.15, "faa": 0.1}
COUNTS = {"prober": (1, 3), "copycat": (1, 3), "swarm": (2, 3)}
HOBBYIST_NONE_P = 0.6
STYLES = {b: "narrative" for b in ("ALPHA", "DELTA", "ECHO", "KILO")}
STYLES |= {b: "blotter" for b in ("BRAVO", "FOXTROT", "GOLF", "LIMA")}
P_VEHICLE, P_ROAD, P_TRUE, P_SOUND, P_WITNESS = 0.35, 0.3, 0.8, 0.3, 0.5
NUMBER_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}
N_DRAWS = 24  # uniforms per report, always drawn


@dataclass(frozen=True)
class Clue:
    type: str
    value: str
    is_true: bool


@dataclass(frozen=True)
class Report:
    report_id: str
    incident_id: str
    installation_id: str
    source: str
    grade: str
    event_ms: int
    report_ms: int
    text: str
    xy: tuple[float, float]
    clues: tuple[Clue, ...]


def style(installation_id: str) -> str:
    return STYLES.get(installation_id, "terse")


def _hhmm(ms: int, f: IncidentFacts) -> str:
    return f"{utc_ms_to_local(ms, f.utc_offset_hours):%H:%M}"


def _alt_ft(f: IncidentFacts) -> int:
    return int(round(f.alt_m * 3.28084 / 50.0) * 50)


def _a(noun: str, capital: bool = False) -> str:
    art = "an" if noun[:1].lower() in "aeiou" or noun.startswith("SUV") else "a"
    return f"{art.capitalize() if capital else art} {noun}"


def _pick(true_value: str | None, options, u_true: float, u_idx: float) -> Clue:
    """The true value with p = 0.8 (when there is one), else a random wrong value."""
    if true_value is not None and u_true < P_TRUE:
        return Clue("", true_value, True)
    wrong = [o for o in options if o != true_value]
    return Clue("", wrong[min(int(u_idx * len(wrong)), len(wrong) - 1)], False)


def _clue(kind: str, c: Clue) -> Clue:
    return Clue(kind, c.value, c.is_true)


def _floor5(t: datetime) -> datetime:
    return t.replace(minute=t.minute - t.minute % 5, second=0, microsecond=0)


def _seen(f: IncidentFacts, u1: float, u2: float) -> tuple[str, str]:
    """When a vehicle was seen: 5-25 min before launch to 5-25 min after the end, on 5-min marks
    (start rounded down, end rounded up)."""
    a = _floor5(utc_ms_to_local(f.launch_ms, f.utc_offset_hours) - timedelta(minutes=5 + 20 * u1))
    b = utc_ms_to_local(f.end_ms, f.utc_offset_hours) + timedelta(minutes=5 + 20 * u2)
    b = b if _floor5(b) == b else _floor5(b) + timedelta(minutes=5)
    return f"{a:%H:%M}", f"{b:%H:%M}"


@dataclass
class _Draft:
    """Clues chosen for one report, before the text is written."""

    vehicle: Clue | None = None
    road: Clue | None = None
    seen: tuple[str, str] | None = None
    lights: Clue | None = None
    departure: Clue | None = None
    sound: Clue | None = None
    launch_site: Clue | None = None

    def clues(self) -> tuple[Clue, ...]:
        names = ("vehicle", "road", "lights", "departure", "sound", "launch_site")
        return tuple(_clue(n, c) for n in names if (c := getattr(self, n)) is not None)


def _draft(f: IncidentFacts, source: str, u: np.ndarray) -> _Draft:
    d = _Draft()
    if source in ("security_forces", "local_pd"):
        if u[2] < P_VEHICLE:
            d.vehicle = _pick(f.vehicle, lx.VEHICLES, u[3], u[4])
        if u[5] < P_ROAD:
            d.road = _pick(f.road, (*f.roads, *lx.MINOR_ROADS), u[6], u[7])
        if d.vehicle is not None:
            d.seen = _seen(f, u[18], u[19])
    if source == "security_forces":
        d.lights = _pick(f.lights, lx.LIGHTS, u[8], u[9])
        d.departure = _pick(f.departure, lx.DIRECTIONS, u[10], u[11])
        if style(f.installation_id) == "narrative" and u[12] < P_SOUND:
            d.sound = _pick(f.sound, lx.SOUNDS, u[13], u[14])
    if source == "local_pd" and u[15] < P_WITNESS:
        if u[20] < 0.5:
            d.launch_site = _pick(f.launch_site, lx.LAUNCH_SITES, u[16], u[17])
        else:
            d.sound = _pick(f.sound, lx.SOUNDS, u[13], u[14])
    return d


def _vehicle_clause(d: _Draft, drones: str | None) -> str:
    """``drones`` ("the drone"/"the drones") adds the departure, as in Appendix A's example."""
    if d.vehicle is not None and d.road is not None:
        tail = f" and left shortly after {drones} flew {d.departure.value}" if drones else ""
        return f"{_a(d.vehicle.value, True)} was parked on {d.road.value} " \
               f"from {d.seen[0]} to {d.seen[1]}{tail}. "  # fmt: skip
    if d.vehicle is not None:
        return f"{_a(d.vehicle.value, True)} was seen parked nearby " \
               f"from {d.seen[0]} to {d.seen[1]}. "  # fmt: skip
    if d.road is not None:
        return f"The operator may have launched from near {d.road.value}. "
    return ""


def _text(f: IncidentFacts, source: str, d: _Draft) -> str:
    n = f.n_drones
    many = n > 1
    start, end = _hhmm(f.start_ms, f), _hhmm(f.end_ms, f)
    serial = f.rid_serial
    if source == "bdoc_log":
        what = f"{n} UAS detected in formation" if many else "UAS detected"
        track = stable_int(f.incident_id) % 9000 + 1000
        tracks = f"Radar tracks {track}-{track + n - 1}" if many else f"Radar track {track}"
        rid = f"Remote ID serial {serial} received." if serial else "No Remote ID."
        return f"{start} BDOC: {what} near the {f.near}. {tracks}. {rid} SF notified. " \
               f"Track lost {end}."  # fmt: skip
    if source == "faa":
        date = f"{utc_ms_to_local(f.start_ms, f.utc_offset_hours):%Y-%m-%d}"
        rid = f"serial {serial} broadcast" if serial else "not detected"
        return (f"Summary: unauthorized UAS activity reported near {f.installation_name} on "
                f"{date}, {start}–{end} local. Reported altitude about {_alt_ft(f)} ft. "
                f"Remote ID: {rid}. Referred to the appropriate authorities.")  # fmt: skip
    if source == "local_pd":
        what = "drones" if many else "a drone"
        witness = ""
        if d.launch_site is not None:
            witness = f"A caller saw the drone launched from {d.launch_site.value}. "
        elif d.sound is not None:
            witness = f"A resident reported {d.sound.value}. "
        vehicle = _vehicle_clause(d, None)
        return f"Deputy responded to a call about {what} near {f.installation_name} at " \
               f"{start}. {witness}{vehicle}Area checked; no operator located."  # fmt: skip
    return _sf_text(f, d, start, end)


def _sf_text(f: IncidentFacts, d: _Draft, start: str, end: str) -> str:
    n = f.n_drones
    many = n > 1
    st = style(f.installation_id)
    lights, dep = d.lights.value, d.departure.value
    if st == "blotter":
        when = utc_ms_to_local(f.start_ms, f.utc_offset_hours)
        what = f"{n} SUAS IN FORMATION" if many else "SUAS"
        text = (f"SF BLOTTER {when:%d %b %Y} {start}: PATROL OBSERVED {what} VIC {f.near}, "
                f"EST {_alt_ft(f)} FT, {lights}. {_vehicle_clause(d, None)}UAS DEPARTED {dep} "
                f"{end}. NO OPERATOR CONTACT.")  # fmt: skip
        return text.upper()
    if st == "terse":
        what = f"{n} sUAS in formation" if many else "sUAS"
        return f"{start} SF: patrol observed {what} near the {f.near}, est {_alt_ft(f)} ft, " \
               f"{lights}. {_vehicle_clause(d, None)}Departed to the {dep} {end}. " \
               "No operator contact."  # fmt: skip
    what = f"{NUMBER_WORDS.get(n, str(n))} small drones flying in formation" if many else \
        "a small drone"  # fmt: skip
    drones = "the drones" if many else "the drone"
    sound = f"Witnesses reported {d.sound.value}. " if d.sound is not None else ""
    return (f"Security forces patrol observed {what} near the {f.near} at about {start}, est. "
            f"{_alt_ft(f)} ft, {lights}. {_vehicle_clause(d, drones)}{sound}"
            f"{drones.capitalize()} departed to the {dep} at about {end}. "
            "No contact with the operator.")  # fmt: skip


def _hobbyist_text(f: IncidentFacts) -> str:
    return (f"Operator located in {f.launch_site} flying a small quadcopter; Remote ID serial "
            f"{f.rid_serial} matched. Advised of airspace restrictions. "
            f"Flight ended {_hhmm(f.end_ms, f)}.")  # fmt: skip


def _report(f: IncidentFacts, k: int, source: str, u: np.ndarray, hobbyist: bool) -> Report:
    (lo, hi), grades = SOURCES[source]
    grade = grades[min(int(u[0] * len(grades)), len(grades) - 1)]
    delay_s = 60 * round((lo + (hi - lo) * u[1]) / 60.0)
    if hobbyist:
        text, clues = _hobbyist_text(f), (Clue("launch_site", f.launch_site, True),)
    else:
        d = _draft(f, source, u)
        text, clues = _text(f, source, d), d.clues()
    return Report(f"R-{f.incident_id}-{k}", f.incident_id, f.installation_id, source, grade,
                  f.start_ms, f.end_ms + 1000 * delay_s, text, f.xy, clues)  # fmt: skip


def make_reports(f: IncidentFacts, rng: np.random.Generator) -> list[Report]:
    """Generated reports for one incident, numbered in report-time order."""
    if f.status == "live":
        return []
    u_n = rng.random()
    if f.actor_type == "hobbyist":
        n = 0 if u_n < HOBBYIST_NONE_P else 1
    else:
        lo, hi = COUNTS[f.actor_type]
        n = lo + min(int(u_n * (hi - lo + 1)), hi - lo)
    names = list(SOURCE_WEIGHTS)
    hobbyist = f.actor_type == "hobbyist" and f.rid_mode == "on" and f.rid_serial is not None
    if hobbyist:
        sources = ["security_forces" if rng.random() < 0.6 else "local_pd"]
    else:
        p = np.array([SOURCE_WEIGHTS[s] for s in names])
        sources = list(rng.choice(names, size=n, replace=False, p=p)) if n else []
    sources = sources[:n]
    draws = [rng.random(N_DRAWS) for _ in sources]
    reps = [_report(f, 0, s, u, hobbyist) for s, u in zip(sources, draws, strict=True)]
    reps.sort(key=lambda r: (r.report_ms, r.source))
    return [_renumber(r, k) for k, r in enumerate(reps, start=1)]


def _renumber(r: Report, k: int) -> Report:
    return Report(f"R-{r.incident_id}-{k}", r.incident_id, r.installation_id, r.source, r.grade,
                  r.event_ms, r.report_ms, r.text, r.xy, r.clues)  # fmt: skip


def planted_report(f: IncidentFacts, planted) -> Report:
    """A report from ``scenario_demo.yaml`` (§8.10): its source, time, grade and clues, written in
    the base's style. Lights and departure, which the template needs, are the true values."""
    if planted.source not in SOURCES:
        raise ValueError(f"planted report: unknown source {planted.source!r}")
    d = _Draft(lights=Clue("", f.lights, True), departure=Clue("", f.departure, True))
    for c in planted.clues:
        if c.type != "vehicle":
            raise ValueError(f"planted report: unsupported clue type {c.type!r}")
        d.vehicle = Clue("", c.value, c.is_true)
        d.road = Clue("", c.road, c.is_true) if c.road else None
        d.seen = c.seen_local
    if planted.source != "security_forces":
        d.lights = d.departure = None
    report_ms = local_to_utc_ms(planted.report_local, f.utc_offset_hours)
    return Report(f"R-{f.incident_id}-1", f.incident_id, f.installation_id, planted.source,
                  planted.grade, f.start_ms, report_ms, _text(f, planted.source, d), f.xy,
                  d.clues())  # fmt: skip
