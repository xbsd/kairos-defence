"""Rich tables for the case-memory commands (``memory …``, ``export``, ``verify-evidence``).

Times print as the case's local time with UTC beside it, e.g. ``2026-04-20 09:10 local
(14:10Z)``; the offset is the region of the case's base (``config/world.yaml``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta

from rich.table import Table


def when(t: datetime | None, offset: int | None) -> str:
    """``2026-04-20 09:10 local (14:10Z)``; with no offset, UTC only (``2026-04-20 14:10Z``)."""
    if t is None:
        return "-"
    if offset is None:
        return f"{t:%Y-%m-%d %H:%M}Z"
    loc = t + timedelta(hours=offset)
    return f"{loc:%Y-%m-%d %H:%M} local ({t:%H:%M}Z)"


def _short(h: str | None) -> str:
    return "-" if not h else f"{h[:16]}…"


def snapshot_lines(s, offset: int) -> list[tuple[str, str]]:
    """(item, value) rows describing one ``CaseSnapshot``."""
    if not s.exists:
        return [("status", "unknown: no such case yet"), ("members", "-"), ("links", "-"),
                ("pending proposals", "-"), ("assessments", "-"), ("contradictions", "-"),
                ("decisions", "-"), ("reports", "-"), ("exports", "-"),
                ("chain head", f"seq {s.head_seq} {_short(s.head_hash)}")]  # fmt: skip
    claims = "\n".join(f"{c['value']} ({c['author'] or c['actor']}, seq {c['seq']})"
                       for c in s.claims) or "none"  # fmt: skip
    contra = "\n".join(f"{c['subject_id']}: {' vs '.join(map(str, c['values']))}"
                       for c in s.contradictions) or "none"  # fmt: skip
    links = "\n".join(f"{lk['incident_id']} ({lk['actor']}, seq {lk['seq']})"
                      for lk in s.links) or "none"  # fmt: skip
    pending = "\n".join(f"{p['incident_id']} (rank {p['rank']}, score "
                        f"{'-' if p['score'] is None else format(p['score'], '.3f')}, "
                        f"seq {p['seq']})" for p in s.pending) or "none"  # fmt: skip
    decisions = "\n".join(f"{d['decision']}: {d['rationale']} ({when(d['recorded_at'], offset)})"
                          for d in s.decisions) or "none"  # fmt: skip
    reports = "\n".join(f"{r['report_id']} ({r['source']}, {r['grade']})"
                        for r in s.reports) or "none"  # fmt: skip
    exports = "\n".join(f"{e['manifest_sha256'][:16]}… (seq {e['seq']})"
                        for e in s.exports) or "none"  # fmt: skip
    return [("status", s.status), ("members", f"{len(s.members)}: " + ", ".join(s.members)),
            ("links", links), ("pending proposals", pending), ("assessments", claims),
            ("contradictions", contra), ("decisions", decisions), ("reports", reports),
            ("exports", exports),
            ("chain head", f"seq {s.head_seq} {_short(s.head_hash)}")]  # fmt: skip


def snapshot_table(s, offset: int) -> Table:
    t = Table(title=f"{s.case_id} as known at {when(s.as_of, offset)}", title_justify="left")
    t.add_column("item")
    t.add_column("value")
    for k, v in snapshot_lines(s, offset):
        t.add_row(k, v)
    return t


def side_by_side(then, now, offset: int) -> Table:
    """The demo's "known then" and "known now" columns for one case."""
    t = Table(title=f"{then.case_id}: known then and known now", title_justify="left",
              show_lines=True)  # fmt: skip
    t.add_column("item")
    t.add_column(f"known then\n{when(then.as_of, offset)}")
    t.add_column(f"known now\n{when(now.as_of, offset)}")
    for (k, a), (_, b) in zip(snapshot_lines(then, offset), snapshot_lines(now, offset),
                              strict=True):  # fmt: skip
        t.add_row(k, a, b)
    return t


def items_table(title: str, groups: Mapping[str, Sequence[Mapping]],
                offset: int | None) -> Table:  # fmt: skip
    """Grouped diff or delta items: group, seq, recorded time, summary (empty groups skipped)."""
    t = Table(title=title, title_justify="left")
    for c in ("group", "seq", "recorded", "summary"):
        t.add_column(c, justify="right" if c == "seq" else "left")
    for g, items in groups.items():
        for i in items:
            extra = ""
            if "new_member" in i:
                extra = " · new member" if i["new_member"] else " · already a member"
            t.add_row(g, str(i["seq"]), when(i["recorded_at"], offset), i["summary"] + extra)
    if not t.rows:
        t.add_row("-", "-", "-", "nothing recorded in this window")
    return t


def seed_table(s, title: str) -> Table:
    t = Table(title=title, title_justify="left")
    t.add_column("item")
    t.add_column("value", justify="right")
    for k, v in sorted(s.counts.items()):
        t.add_row(k, f"{v:,}")
    t.add_row("rows", f"{s.rows:,}")
    t.add_row("cutoff (live first contact)", f"{s.cutoff:%Y-%m-%d %H:%M:%S}Z")
    t.add_row("head", f"seq {s.head_seq:,} {s.head_hash}")
    t.add_row("elapsed", f"{s.elapsed_s:.2f} s")
    return t


def checks_table(folder: str, checks: Sequence) -> Table:
    t = Table(title=f"verify-evidence {folder}", title_justify="left")
    t.add_column("check")
    t.add_column("result")
    t.add_column("detail")
    style = {"PASS": "green", "FAIL": "red", "SKIP": "yellow"}
    for c in checks:
        t.add_row(c.name, f"[{style[c.status]}]{c.status}[/{style[c.status]}]", c.detail)
    return t
