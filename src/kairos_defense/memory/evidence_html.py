"""``case.html`` of an evidence package (SPEC §15.7): a self-contained summary with no scripts
and no external references, plus the static map (one matplotlib PNG inlined as base64).

The map draws each member incident's tracks in target-relative meters (east, north) around its
own target at the origin, so the shared pattern shows across installations. Colors are the
categorical slots of the dataviz reference palette in fixed order (validated: all checks pass on
the light surface; contrast is a WARN, so every track is also labeled directly and the members
table is the table view). Text is ink, never a series color.
"""

from __future__ import annotations

import base64
import html
import io
from collections.abc import Mapping, Sequence

from kairos_defense.ports import TrackStore

SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4")  # categorical slots 1-5
MAX_SERIES = len(SERIES)


def static_map_png(store: TrackStore, members: Sequence[str]) -> bytes | None:
    """PNG bytes of the member tracks (target-relative meters), or None if no member has
    indexed features. Deterministic: no timestamps or software tags in the file."""
    from kairos_defense.sim.figures import INK, INK_2, MUTED, SURFACE, _plt

    members = list(members)[:MAX_SERIES]
    tracks = store.sql("SELECT track_id, incident_id FROM track_signatures "
                       "WHERE list_contains($ids, incident_id) ORDER BY track_id",
                       {"ids": members})  # fmt: skip
    if tracks.empty:
        return None
    feats = store.features_many(tracks["track_id"].tolist())
    if feats.empty:
        return None
    plt = _plt()
    with plt.rc_context({"font.family": "DejaVu Sans"}):  # bundled with matplotlib (D-077)
        fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=100, facecolor=SURFACE)
        ax.set_facecolor(SURFACE)
        ends = []  # one direct label per incident, at the end of its first track
        for color, inc in zip(SERIES, members, strict=False):
            rows = tracks[tracks["incident_id"] == inc]
            for i, tid in enumerate(rows["track_id"]):
                f = feats[feats["track_id"] == tid]
                if f.empty:
                    continue
                x, y = f["x_rel_m"].to_numpy(), f["y_rel_m"].to_numpy()
                ax.plot(x, y, color=color, lw=2, label=inc if i == 0 else None)
                if i == 0:
                    ends.append((inc, float(x[-1]), float(y[-1])))
        ax.plot([0], [0], marker="+", ms=12, mew=2, color=INK, ls="none", label="target")
        ax.set_aspect("equal", adjustable="datalim")
        _direct_labels(fig, ax, ends, INK_2)
        ax.set_xlabel("meters east of the target", color=INK_2, fontsize=9)
        ax.set_ylabel("meters north of the target", color=INK_2, fontsize=9)
        ax.set_title("Member tracks around their own target", color=INK, fontsize=10, loc="left")
        ax.grid(color=MUTED, lw=0.5, alpha=0.4)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(MUTED)
        ax.tick_params(colors=INK_2, labelsize=8)
        ax.legend(frameon=False, fontsize=8, labelcolor=INK_2, loc="best")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=SURFACE, metadata={"Software": None})
        plt.close(fig)
    return buf.getvalue()


def _direct_labels(fig, ax, ends: list[tuple[str, float, float]], color: str) -> None:
    """Label each track end, stepping a label down while it would overlap one already placed
    (display pixels: 12 px rows, 150 px wide)."""
    fig.canvas.draw()
    placed: list[tuple[float, float]] = []
    for inc, x, y in sorted(ends, key=lambda e: -e[2]):
        px, py = ax.transData.transform((x, y))
        dy = 0.0
        while any(abs(py + dy - qy) < 12 and abs(px - qx) < 150 for qx, qy in placed):
            dy -= 12
        placed.append((px, py + dy))
        ax.annotate(inc, (x, y), xytext=(6, dy * 72 / fig.dpi), textcoords="offset points",
                    va="center", color=color, fontsize=8)  # fmt: skip


def _e(v: object) -> str:
    return html.escape("-" if v is None else str(v))


def _table(head: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    if not rows:
        return "<p class=muted>none</p>"
    th = "".join(f"<th>{_e(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


CSS = """body{font-family:"DejaVu Sans",system-ui,sans-serif;background:#fcfcfb;color:#0b0b0b;
margin:2rem auto;max-width:72rem;padding:0 1rem;line-height:1.45}
h1{font-size:1.4rem}h2{font-size:1.1rem;margin-top:2rem;border-bottom:1px solid #e6e5e1}
table{border-collapse:collapse;width:100%;font-size:.85rem}
th,td{text-align:left;padding:.3rem .5rem;border-bottom:1px solid #e6e5e1;vertical-align:top}
th{color:#52514e;font-weight:600}.muted{color:#52514e}code{font-size:.8rem;word-break:break-all}
.note{background:#e6e5e1;padding:.5rem .75rem;border-radius:4px}"""


def render_html(doc: Mapping, map_png: bytes | None) -> str:
    """The summary page for one ``case.json`` document (``evidence.case_document``)."""
    s, head, ver = doc["snapshot"], doc["head"], doc["verification"]
    links = {lk["incident_id"]: lk for lk in s["links"]}
    members = [(m, "founder" if m == s["founder"] else "linked",
                links.get(m, {}).get("actor"), links.get(m, {}).get("proposal_seq"))
               for m in s["members"]]  # fmt: skip
    proposals = [r for r in doc["rows"] if r["event_type"] == "match_proposed"]
    matches = [
        (
            r["seq"],
            r["subject_id"],
            r["object_json"].get("query_incident"),
            r["object_json"].get("rank"),
            r["object_json"].get("score"),
            "; ".join(r["object_json"].get("reasons") or []) or "-",
        )
        for r in proposals
    ]
    timeline = [(r["seq"], r["recorded_at"], r["event_type"], r["actor"], r["summary"])
                for r in doc["timeline"]]  # fmt: skip
    reports = [(r["report_id"], r["incident_id"], r["source"], r["grade"], r["event_at"],
                (r["text"] or "")[:400]) for r in s["reports"]]  # fmt: skip
    claims = [(c["seq"], c["subject_id"], c["value"], c["author"] or c["actor"],
               c["source_grade"], c["recorded_at"]) for c in s["claims"]]  # fmt: skip
    contra = [
        (
            c["subject_id"],
            c["predicate"],
            " vs ".join(map(str, c["values"])),
            ", ".join(str(x["seq"]) for x in c["claims"]),
        )
        for c in s["contradictions"]
    ]
    decisions = [(d["seq"], d["decision"], d["rationale"], d["by"] or d["actor"],
                  d["recorded_at"]) for d in s["decisions"]]  # fmt: skip
    img = ("<p class=muted>No map: the member tracks are not in the store.</p>" if not map_png
           else '<img alt="Member tracks around their own target, in meters" width="640" '
           f'src="data:image/png;base64,{base64.b64encode(map_png).decode()}">')  # fmt: skip
    intact = "intact" if ver["intact"] else f"BROKEN at seq {ver['first_broken_seq']}"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{_e(doc["case_id"])} evidence</title>
<style>{CSS}</style></head><body>
<h1>{_e(doc["case_id"])}: evidence package</h1>
<p class=note>Synthetic demo data. Kairos Defense links flights, never people.</p>
<p>Status <b>{_e(s["status"])}</b> as of {_e(doc["created_at"])} · exported with the approval
of {_e(doc["approved_by"])} · {len(s["members"])} member incident(s)</p>
<p>Chain head seq {_e(head["seq"])}, recorded {_e(head["recorded_at"])}:
<code>{_e(head["hash"])}</code>. Ledger verification: {intact} over {_e(ver["rows"])} rows.
Models: {_e(", ".join(doc["models"]) or "none")}.</p>
<h2>Members</h2>{_table(("incident", "role", "linked by", "proposal seq"), members)}
<h2>Map</h2>{img}
<h2>Matches and reasons</h2>
{_table(("seq", "incident", "query", "rank", "score", "reasons"), matches)}
<h2>Assessments</h2>{_table(("seq", "incident", "label", "by", "grade", "recorded"), claims)}
<h2>Contradictions</h2>{_table(("subject", "predicate", "values", "claim seqs"), contra)}
<h2>Report excerpts</h2>
{_table(("report", "incident", "source", "grade", "event time", "excerpt"), reports)}
<h2>Decisions</h2>{_table(("seq", "decision", "rationale", "by", "recorded"), decisions)}
<h2>Timeline</h2>{_table(("seq", "recorded (UTC)", "event", "actor", "summary"), timeline)}
</body></html>
"""
