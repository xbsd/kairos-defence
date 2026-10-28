"""Small Markdown helpers shared by the data-card modules."""

from __future__ import annotations

import re
from datetime import datetime

from kairos_defense.sim.calendar import utc_ms_to_local
from kairos_defense.sim.generate import Generated

ACTOR_TYPES = ("hobbyist", "prober", "copycat", "swarm")


def n(x: int) -> str:
    """Thousands separators: ``1,234``."""
    return f"{x:,}"


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


_NUMBER = re.compile(r"^(?:≈?[\d,]+(?:\.\d+)?%?|\d+/\d+|\d+\.\d+–\d+\.\d+|–)$")


def table(head: list[str], rows: list[list], right: int = 1) -> list[str]:
    """A Markdown table. Columns after the first ``right`` whose cells are all numbers are
    right-aligned; text columns stay left-aligned."""

    def numeric(j: int) -> bool:
        return j >= right and bool(rows) and all(_NUMBER.match(str(r[j])) for r in rows)

    align = ["---:" if numeric(j) else "---" for j in range(len(head))]
    out = ["| " + " | ".join(head) + " |", "|" + "|".join(align) + "|"]
    return out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]


def local(g: Generated, base: str, ms: int) -> datetime:
    """UTC epoch ms -> naive local time at an installation."""
    return utc_ms_to_local(ms, g.world.sites[base].utc_offset_hours)
