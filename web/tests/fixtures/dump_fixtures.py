"""Rewrite the Vitest fixtures in this folder from the real API (phase 8, `web/tests/real.ts`).

Run from the repository root after `make data index models eval`:

    uv run python web/tests/fixtures/dump_fixtures.py web/tests/fixtures
    npm --prefix web run format    # the web lint checks the fixtures' formatting too

The app runs in-process on a scratch ledger, live file and export folder under
`data/cache/fixtures`, so `data/memory.duckdb` and `exports/` are never touched. The eval fixture
(`eval.json`) is trimmed from the newest `reports/eval_<date>.json`. Phase 9 adds the Swarm view's
`swarms.json` and `swarm.json` (the live demo swarm's §14 result over its whole flight); to keep
the file small, `swarm.json` keeps each flight's positions for its first `SWARM_POSITIONS_S`
seconds only and rounds the descriptor curves to one decimal.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from kairos_defense.api.app import create_app
from kairos_defense.config import load_config

log = logging.getLogger(__name__)
INC = "DEMO-BRAVO-0828"
CASE = "CASE-P1-DELTA-260419"
SWARM = "DEMO-SWARM-ECHO-0614"
SWARM_POSITIONS_S = 180


def _write(out: Path, name: str, doc: object) -> None:
    (out / name).write_text(json.dumps(doc, separators=(",", ":")) + "\n")


def _results_at(ws, t: int) -> dict:
    """Seek the stream to ``t`` and collect that second's match, forecast, dtw and recall."""
    want = {"match", "forecast"} | ({"dtw"} if t == 90 else set())
    want |= {"recall"} if t == 120 else set()
    ws.send_json({"type": "seek", "t_s": t})
    got: dict = {}
    while not want <= set(got):
        m = ws.receive_json()
        if m["type"] in ("match", "forecast", "dtw", "recall", "features") and m["t_s"] == t:
            got[m["type"]] = m
    return got


def _trim_flight(f: dict | None) -> dict | None:
    if f is None:
        return None
    keep = [i for i, t in enumerate(f["t_s"]) if t <= SWARM_POSITIONS_S]
    curves = {k: [v if v is None or isinstance(v, int) else round(v, 1) for v in col]
              for k, col in f["curves"].items()}  # fmt: skip
    return {**f, "curves": curves, "t_s": [f["t_s"][i] for i in keep],
            "positions": [[d[i] for i in keep] for d in f["positions"]]}  # fmt: skip


def trim_swarm(doc: dict) -> dict:
    """``swarm.json`` without most positions (see the module docstring)."""
    return {**doc, "query": _trim_flight(doc["query"]), "match": _trim_flight(doc["match"])}


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    scratch = Path("data/cache/fixtures")
    scratch.mkdir(parents=True, exist_ok=True)
    app = create_app(load_config("config"), memory_path=scratch / "memory.duckdb",
                     live_path=scratch / "live.duckdb", reseed=True,
                     exports_path=scratch / "exports")  # fmt: skip
    with TestClient(app) as c:
        c.post("/api/admin/reseed")
        c.post("/api/admin/reset")
        with c.websocket_connect(f"/ws/replay/{INC}") as ws:
            hello = ws.receive_json()
            r = {t: _results_at(ws, t) for t in (90, 105, 120)}
        _write(out, "t090.json", {"hello": hello, **r[90]})
        _write(out, "t105.json", {k: r[105].get(k) for k in ("match", "forecast", "features")})
        _write(out, "t120.json", {k: r[120][k] for k in ("match", "recall", "forecast")})
        _write(out, "scene_bravo.json", c.get("/api/installations/BRAVO/scene").json())
        _write(out, "installations.json", c.get("/api/installations").json())
        then = "as_of=2026-04-20T10:00:00-05:00"
        _write(out, "graph_then.json", c.get(f"/api/cases/{CASE}/graph?{then}").json())
        top = r[90]["match"]["matches"][0]["track_id"]
        _write(out, "explain_t090.json", c.get(f"/api/explain/{INC}/{top}?at=90").json())
        _write(out, "cases.json", c.get("/api/cases").json())
        _write(out, "diff.json", c.get(f"/api/cases/{CASE}/diff?t1=2026-04-20T15:00:00Z").json())
        _write(out, "graph_now.json", c.get(f"/api/cases/{CASE}/graph").json())
        _write(out, "delta.json", c.get("/api/delta?since=2026-08-27T00:00:00Z").json())
        hist = c.get("/api/history/P1-DELTA-260419-T1?frame=target").json()
        _write(out, "history_delta.json", hist)
        _write(out, "swarms.json", c.get("/api/swarms").json())
        _write(out, "swarm.json", trim_swarm(c.get(f"/api/swarm/{SWARM}").json()))
    reports = sorted(Path("reports").glob("eval_*.json"))
    if reports:
        e = json.loads(reports[-1].read_text())
        e["file"] = reports[-1].name
        e["outcomes"] = [{k: o[k] for k in ("actor_type", "at_s", "ran", "forecast_error_m")}
                         for o in e["outcomes"] if o["at_s"] in (90, 120)]  # fmt: skip
        e.pop("per_actor", None)
        _write(out, "eval.json", e)
    log.info("wrote %s", ", ".join(sorted(p.name for p in out.glob("*.json"))))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "web/tests/fixtures"))
