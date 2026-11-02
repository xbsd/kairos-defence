"""Who really flew a closed live incident, and how the matcher did (D-170, D-179, D-180).

The one place live ground truth is read (with ``live check``, which calls ``reveal``). It joins
the incident's sensor track ids (from the live-mode store) to the simulator's ``live_truth``
table, the matches each rerun showed (``live_results``) to the history's ``track_truth`` (and to
``live_truth`` again for learned live tracks), and scores the scenario's expectation. Nothing it
returns is stored anywhere; the API serves it only for a closed incident and only on request.
Times are seconds after the incident's first radar point (T+0).
"""

from __future__ import annotations

import time
from collections import Counter

import duckdb
import pandas as pd

from kairos_defense.config import Config
from kairos_defense.eval.truth import track_truth

BY_S = 120  # "by T+120 s" (PHASE_11.md scenario table)
TOP3, TOP5 = 3, 5
RETRIES = 40  # x 0.25 s while the simulator writes the truth file
TRUTH_COLS = ["sensor_track_id", "actor_id", "actor_type", "nickname", "scenario", "seed", "base",
              "flight", "drone", "launch_ts"]  # fmt: skip


class NotClosed(RuntimeError):
    """The incident is still open: who flew it is not revealed while it is live."""


def live_truth(cfg: Config) -> pd.DataFrame:
    """Every live flight's truth row (empty when the simulator never ran)."""
    for attempt in range(RETRIES):
        try:
            con = duckdb.connect(str(cfg.app.paths.truth), read_only=True)
            break
        except duckdb.IOException:
            if attempt == RETRIES - 1:
                raise
            time.sleep(0.25)
    try:
        names = {r[0] for r in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}
        if "live_truth" not in names:
            return pd.DataFrame(columns=TRUTH_COLS)
        return con.execute("SELECT * FROM live_truth ORDER BY sensor_track_id").df()
    finally:
        con.close()


class _Actors:
    """Who flew any track or incident: history from ``track_truth``, live from ``live_truth``."""

    def __init__(self, cfg: Config, feed, lt: pd.DataFrame) -> None:
        hist = track_truth(cfg.app)
        self.track = dict(zip(hist["track_id"], hist["actor_id"], strict=True))
        self.incident = hist.groupby("incident_id")["actor_id"].first().to_dict()
        self.start = dict(zip(hist["track_id"], pd.to_datetime(hist["launch_ts"]), strict=True))
        lt = lt.set_index("sensor_track_id") if len(lt) else lt
        self.truth = lt
        for r in feed.live_tracks().itertuples(index=False):
            if len(lt) and r.sensor_track_id in lt.index:
                row = lt.loc[r.sensor_track_id]
                self.track[r.track_id] = row["actor_id"]
                self.incident.setdefault(r.incident_id, row["actor_id"])
                self.start[r.track_id] = pd.Timestamp(r.start_ts)
        self.live_rows = {r.track_id: r for r in feed.live_tracks().itertuples(index=False)}

    def of(self, match: dict) -> str | None:
        if "track_id" in match and match.get("track_id"):
            return self.track.get(match["track_id"])
        return self.incident.get(match.get("incident_id"))


def _first_rank(matches: list[dict], actor: str | None, actors: _Actors) -> int | None:
    for m in matches:
        if actor is not None and actors.of(m) == actor:
            return int(m["rank"])
    return None


def _mimics(cfg: Config, actor: str) -> str | None:
    return next((c.mimics for c in cfg.actors.copycats if c.id == actor), None)


def reveal(cfg: Config, feed, incident_id: str) -> dict:
    """The reveal of one closed live incident. Raises ``KeyError`` (unknown) or ``NotClosed``."""
    inc = feed.incident(incident_id)
    if inc is None:
        raise KeyError(f"no live incident {incident_id!r}")
    if inc["state"] != "closed":
        raise NotClosed(f"{incident_id} is still {inc['state']}: reveal after it closes")
    lt = live_truth(cfg)
    actors = _Actors(cfg, feed, lt)
    tracks = feed.live_tracks(incident_id)
    rows = [actors.truth.loc[s] for s in tracks["sensor_track_id"]
            if len(actors.truth) and s in actors.truth.index]  # fmt: skip
    start = pd.Timestamp(inc["start_ts"])
    out = {"incident_id": incident_id, "installation_id": inc["installation_id"],
           "start_ts": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "n_tracks": int(inc["n_tracks"]),
           "is_swarm": bool(inc["is_swarm"]), "known": bool(rows)}  # fmt: skip
    if not rows:
        return {**out, "actor_id": None, "actor_type": None, "nickname": None, "scenario": None,
                "seed": None, "flight": None, "base": inc["installation_id"], "reruns": [],
                "same_actor_history": 0,
                "expectation": {"text": "", "met": None, "observed": "no simulator truth for "
                                "this incident (not flown by the simulator)"},
                "words": "Not flown by the simulator: there is nothing to reveal."}  # fmt: skip
    actor = Counter(r["actor_id"] for r in rows).most_common(1)[0][0]
    t = next(r for r in rows if r["actor_id"] == actor)
    scenario, flight, mimic = str(t["scenario"]), int(t["flight"]), _mimics(cfg, actor)
    history = sum(1 for tid, a in actors.track.items()
                  if a == actor and tid in actors.start and actors.start[tid] < start
                  and tid not in set(tracks["track_id"]))  # fmt: skip
    reruns = []
    for r in feed.results(incident_id):
        ms = r["matches"]
        reruns.append({"t_s": int(r["t_s"]), "kind": r["kind"],
                       "first_same_rank": _first_rank(ms, actor, actors),
                       "mimic_rank": _first_rank(ms, mimic, actors) if mimic else None,
                       "top_incident": ms[0]["incident_id"] if ms else None,
                       "top_track": ms[0].get("track_id") if ms else None,
                       "top_actor": actors.of(ms[0]) if ms else None,
                       "top_score": (ms[0].get("score", ms[0].get("similarity"))
                                     if ms else None)})  # fmt: skip
    flight1 = [k for k, v in actors.live_rows.items() if v.sensor_track_id in actors.truth.index
               and int(actors.truth.loc[v.sensor_track_id]["flight"]) == 1
               and int(actors.truth.loc[v.sensor_track_id]["seed"]) == int(t["seed"])
               and actors.truth.loc[v.sensor_track_id]["scenario"] == scenario]  # fmt: skip
    exp = expectation(scenario, flight, reruns, history, flight1, actor, mimic)
    return {**out, "actor_id": actor, "actor_type": str(t["actor_type"]),
            "nickname": str(t["nickname"]), "scenario": scenario, "seed": int(t["seed"]),
            "flight": flight, "base": str(t["base"]), "mimics": mimic, "reruns": reruns,
            "same_actor_history": int(history), "expectation": exp,
            "words": words(actor, str(t["nickname"]), scenario, flight, reruns, exp,
                           flight1)}  # fmt: skip


def _at_or_before(reruns: list[dict], s: int) -> dict | None:
    early = [r for r in reruns if r["t_s"] <= s]
    return early[-1] if early else None


def top_from(reruns: list[dict]) -> int | None:
    """The earliest rerun from which the same actor stays ranked first."""
    best = None
    for r in reversed(reruns):
        if r["first_same_rank"] != 1:
            break
        best = r["t_s"]
    return best


def expectation(scenario: str, flight: int, reruns: list[dict], history: int,
                flight1: list[str], actor: str, mimic: str | None) -> dict:  # fmt: skip
    """The scenario table's expectation (PHASE_11.md, D-180): ``text``, ``met``, ``observed``."""
    if not reruns:
        return {"text": "at least one rerun", "met": False,
                "observed": "the incident closed before any rerun was computed"}  # fmt: skip
    last = reruns[-1]
    if scenario == "returning-prober":
        hit = next((r for r in reruns if r["t_s"] <= BY_S and r["first_same_rank"]
                    and r["first_same_rank"] <= TOP3), None)  # fmt: skip
        at = _at_or_before(reruns, BY_S) or reruns[0]
        obs = (
            f"rank {hit['first_same_rank']} at T+{hit['t_s']} s"
            if hit
            else f"best same-actor rank by T+{BY_S} s: "
            f"{_best(reruns, BY_S)}; at T+{at['t_s']} s the top match was {at['top_actor']}"
        )
        return {"text": f"a same-actor ({actor}) history flight in the top 3 by T+{BY_S} s",
                "met": hit is not None, "observed": obs}  # fmt: skip
    if scenario == "copycat":
        at = _at_or_before(reruns, BY_S) or reruns[0]
        own, mim = at["first_same_rank"], at["mimic_rank"]
        met = own is not None and own <= TOP5 and (mim is None or own < mim)
        return {"text": f"a same-actor ({actor}) history flight in the top 5 by T+{BY_S} s, "
                        f"above every {mimic} flight", "met": met,
                "observed": f"at T+{at['t_s']} s: {actor} rank {own or 'none'}, "
                            f"{mimic} rank {mim or 'none'}"}  # fmt: skip
    if scenario == "hobbyist":
        score = last["top_score"]
        return {"text": "no expectation on identity; the top score is reported", "met": True,
                "observed": f"top match {last['top_incident']} at score "
                            f"{score if score is None else round(float(score), 3)} "
                            f"at T+{last['t_s']} s"}  # fmt: skip
    if scenario == "swarm-repeat":
        met = last["top_actor"] == actor
        return {"text": f"a past {actor} swarm event ranked first", "met": met,
                "observed": f"final rerun T+{last['t_s']} s: first {last['top_incident']} "
                            f"({last['top_actor']})"}  # fmt: skip
    if scenario == "new-operator-twice" and flight == 1:
        return {"text": "no same-actor history exists (nothing to find)", "met": history == 0,
                "observed": f"{history} earlier flight(s) of {actor}; top match "
                            f"{last['top_incident']} at T+{last['t_s']} s"}  # fmt: skip
    if scenario == "new-operator-twice":
        ok = last["top_track"] in flight1
        return {
            "text": "flight 1, learned live, ranked first",
            "met": ok,
            "observed": f"final rerun T+{last['t_s']} s: first {last['top_track']}"
            + ("" if ok else f" (flight 1 is {', '.join(flight1) or 'unknown'})"),
        }
    return {"text": "", "met": None, "observed": f"unknown scenario {scenario!r}"}


def _best(reruns: list[dict], until: int) -> str:
    ranks = [r["first_same_rank"] for r in reruns if r["t_s"] <= until and r["first_same_rank"]]
    return str(min(ranks)) if ranks else "not in the top 10"


def words(actor: str, nickname: str, scenario: str, flight: int, reruns: list[dict], exp: dict,
          flight1: list[str]) -> str:  # fmt: skip
    """The verdict in plain words for the reveal card."""
    who = f"{actor}, {nickname}."
    if not reruns:
        return f"{who} The incident closed before the matcher ran."
    last = reruns[-1]
    if scenario == "returning-prober":
        first = next((r for r in reruns if r["first_same_rank"]
                      and r["first_same_rank"] <= TOP3), None)  # fmt: skip
        if first is None:
            return f"{who} Not recognized: no {actor} flight reached the top 3."
        tf = top_from(reruns)
        tail = f" top match from T+{tf} s." if tf is not None else " never ranked first."
        return (
            f"{who} First recognized at T+{first['t_s']} s (rank {first['first_same_rank']});{tail}"
        )
    if scenario == "copycat":
        return f"{who} {exp['observed'][0].upper()}{exp['observed'][1:]}."
    if scenario == "hobbyist":
        return f"{who} No identity to find: {exp['observed']} (a calibration view)."
    if scenario == "swarm-repeat":
        rank = last["first_same_rank"]
        if rank == 1:
            return f"{who} Its past event {last['top_incident']} ranked first."
        return f"{who} Its own past events ranked {rank or 'below the top 5'} at the last rerun."
    if flight == 1:
        return f"{who} No earlier flights to find: this operator never flew before."
    rank = last["first_same_rank"]
    if last["top_track"] in flight1:
        return (
            f"{who} Matched {last['top_track']}, its own first flight learned live minutes "
            f"earlier: ranked first at T+{last['t_s']} s."
        )
    return f"{who} Its first flight ({', '.join(flight1) or 'unknown'}) ranked {rank or 'lower'}."
