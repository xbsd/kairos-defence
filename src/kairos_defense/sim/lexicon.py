"""Clue vocabulary and text scanners (SPEC §8.8, §12.4, §23).

The fixed lexicons are the only words reports use for clues. ``find_clues`` reads a report's text
back into ``(clue_type, value)`` pairs (case-insensitive, so blotter capitals read the same), and
tests compare that with ``clue_truth``. ``forbidden`` is the guardrail scan: plate-like tokens,
plate and registration words, street addresses, phone numbers, e-mail, a title before a name,
words describing a person, and a lexicon of common given names and surnames. World vocabulary
(road, park and installation names, Remote ID serials) is removed before scanning (D-045).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

CLUE_TYPES = ("vehicle", "road", "lights", "sound", "launch_site", "departure")
VEHICLE_COLORS = ("white", "black", "dark", "silver", "red", "blue", "gray", "green", "tan")
VEHICLE_TYPES = ("pickup", "SUV", "sedan", "hatchback", "van", "truck", "motorcycle")
VEHICLES = tuple(f"{c} {t}" for c in VEHICLE_COLORS for t in VEHICLE_TYPES)
LIGHTS = (
    "no visible lights",
    "a steady white light",
    "a flashing white light",
    "red and green lights",
    "a flashing red light",
    "a steady green light",
)
SOUNDS = ("a high-pitched whine", "a low buzzing sound", "a loud buzzing sound", "a faint hum")
LAUNCH_SITES = ("a gravel pull-off", "an open field", "a dirt lot", "the tree line", "a farm track")
DIRECTIONS = ("north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest")
MINOR_ROADS = ("Quarry Rd", "Old Mill Rd", "Ridge Rd")  # not in the roads table: false road clues

SERIAL_RE = re.compile(r"\bSN-[0-9A-F]{16}\b")
_TYPES = {t.lower(): t for t in VEHICLE_TYPES}
_VEHICLE_RE = re.compile(
    r"\b(?:(" + "|".join(VEHICLE_COLORS) + r")\s+)?(" + "|".join(_TYPES) + r")\b", re.I
)
_DIRS = "|".join(sorted(DIRECTIONS, key=len, reverse=True))
_DEPARTURE_RE = re.compile(r"\b(?:departed(?:\s+to\s+the)?|flew)\s+(" + _DIRS + r")\b", re.I)


def compass8(bearing_deg: float) -> str:
    """Eight-point compass word for a bearing (degrees clockwise from north)."""
    return DIRECTIONS[int(((float(bearing_deg) % 360.0) + 22.5) // 45.0) % 8]


def park_name(park_id: str) -> str:
    """Display name of a park: ``COASTAL-PARK-5`` -> ``Coastal Park 5``."""
    return " ".join(w.title() if w.isalpha() else w for w in park_id.split("-"))


def _phrases(text: str, kind: str, phrases: Iterable[str]) -> set[tuple[str, str]]:
    out = set()
    for p in phrases:
        if re.search(r"(?<![\w-])" + re.escape(p) + r"(?![\w-])", text, re.I):
            out.add((kind, p))
    return out


def find_clues(text: str, roads: Iterable[str], parks: Iterable[str] = ()) -> set[tuple[str, str]]:
    """Every clue mentioned in ``text`` as ``(clue_type, canonical value)``. ``roads`` are the
    road names that may appear (world roads plus ``MINOR_ROADS``); ``parks`` the park names."""
    out = set()
    for m in _VEHICLE_RE.finditer(text):
        color, kind = m.group(1), _TYPES[m.group(2).lower()]
        out.add(("vehicle", f"{color.lower()} {kind}" if color else kind))
    out |= _phrases(text, "road", roads)
    out |= _phrases(text, "lights", LIGHTS)
    out |= _phrases(text, "sound", SOUNDS)
    out |= _phrases(text, "launch_site", (*LAUNCH_SITES, *parks))
    out |= {("departure", m.group(1).lower()) for m in _DEPARTURE_RE.finditer(text)}
    return out


# ----------------------------------------------------------------------------- forbidden content

_PLATES = [
    re.compile(r"\b[A-Z]{2,3}-?\d{3,4}\b"),  # ABC1234, AB-123
    re.compile(r"\b\d{3}-?[A-Z]{3}\b"),  # 123ABC
    re.compile(r"\b\d[A-Z]{3}\d{3}\b"),  # 7ABC123
    re.compile(r"\b[A-Z]\d{2}-?[A-Z]{3}\b"),  # A12BCD
]
_PLATE_WORDS = re.compile(r"\b(?:plates?|licen[cs]e|registration|tag\s+number|VIN)\b", re.I)
_ADDRESS = re.compile(
    r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}"
    r"(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Ln|Lane|Dr|Drive|Ct|Court|Way|Pl|Place)\b"
)
_PHONE = re.compile(r"\b\d{3}[-. ]\d{3}[-. ]\d{4}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.\w+\b")
_TITLE_NAME = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Sgt|SSgt|TSgt|MSgt|Capt|Lt|Col|Maj|Gen|Officer|Deputy|Airman|SrA|A1C|"
    r"Cpl|Pvt|Spc)\.?\s+[A-Z][a-z]+"
)
_PERSON = re.compile(
    r"\b(?:he|she|him|his|her|hers|man|woman|men|women|male|female|boy|girl|beard|face|faces|"
    r"hair|wearing|tall|teen|teenager|elderly)\b",
    re.I,
)
# Common given names and surnames. English words and the NATO installation names (Charlie, Juliet,
# …) are left out on purpose: in this world they name places, colors and things, not people.
NAMES = frozenset(
    """
    james john robert michael david william richard joseph thomas charles christopher daniel
    matthew anthony donald steven paul andrew joshua kenneth kevin brian george timothy ronald
    jason edward jeffrey ryan jacob gary nicholas eric jonathan stephen larry justin scott brandon
    benjamin samuel gregory alexander patrick jack dennis jerry tyler aaron jose adam nathan henry
    zachary douglas peter kyle noah ethan jeremy walter christian keith roger terry austin sean
    gerald carl harold dylan arthur lawrence jordan jesse bryan billy bruce gabriel joe logan
    alan juan albert willie elijah wayne randy vincent mason roy ralph bobby russell bradley
    philip eugene mary patricia jennifer linda elizabeth barbara susan jessica sarah karen lisa
    nancy betty sandra margaret ashley kimberly emily donna michelle carol amanda melissa deborah
    stephanie dorothy rebecca sharon laura cynthia amy kathleen angela shirley brenda emma anna
    pamela nicole samantha katherine christine helen debra rachel carolyn janet maria catherine
    heather diane olivia julie joyce victoria ruth virginia lauren kelly christina joan evelyn
    judith andrea hannah megan cheryl jacqueline martha madison teresa gloria sara janice ann
    kathryn abigail sophia frances jean alice judy isabella julia grace amber denise danielle
    marilyn beverly charlotte natalie theresa diana brittany doris kayla alexis lori
    smith johnson williams jones garcia miller davis rodriguez martinez hernandez lopez gonzalez
    wilson anderson taylor moore jackson martin thompson harris sanchez clark ramirez lewis
    robinson walker allen wright torres nguyen flores adams nelson rivera campbell mitchell
    roberts gomez phillips evans turner diaz parker cruz edwards collins reyes stewart morris
    morales murphy cook rogers gutierrez ortiz morgan cooper peterson bailey reed kelly howard
    ramos kim cox ward richardson watson brooks chavez bennett mendoza ruiz hughes price
    alvarez castillo sanders patel myers jimenez powell jenkins perry russell sullivan
    fisher henderson coleman simmons patterson jordan reynolds hamilton graham wallace
    """.split()  # noqa: SIM905
)


def forbidden(text: str, allowed: Iterable[str] = ()) -> list[str]:
    """Guardrail findings in ``text`` (empty when clean). ``allowed`` phrases (world road, park
    and installation names) are removed first, as are Remote ID serials."""
    t = SERIAL_RE.sub(" ", text)
    for phrase in sorted(set(allowed), key=len, reverse=True):
        t = re.sub(re.escape(phrase), " ", t, flags=re.I)
    found = []
    for rx in _PLATES:
        found += [f"plate-like {m}" for m in rx.findall(t)]
    found += [f"plate word {m}" for m in _PLATE_WORDS.findall(t)]
    found += [f"address {m}" for m in _ADDRESS.findall(t)]
    found += [f"phone {m}" for m in _PHONE.findall(t)]
    found += [f"email {m}" for m in _EMAIL.findall(t)]
    found += [f"title and name {m}" for m in _TITLE_NAME.findall(t)]
    found += [f"person word {m}" for m in _PERSON.findall(t)]
    found += [f"name {w}" for w in re.findall(r"[A-Za-z]+", t) if w.lower() in NAMES]
    return found
