"""``kairos-defense live check``: fly every live scenario headless and score it (D-180, D-183).

The API runs in this process (uvicorn in a thread, on a free loopback port) over scratch stores
in ``<paths.cache>/live_check/`` (a live-mode folder, a reseeded ledger copy, live tables,
exports), so the user's live data and ledger are never touched. Each scenario is launched through
``POST /api/sim/launch`` with its fixed seed (``SEEDS``: chosen once, never changed to pass),
which starts the simulator as a separate process; the check waits for it to exit, for every new
incident to close and for the worker queue to drain, then scores the incidents with the reveal
(``eval.reveal``, the same function the Live page's card uses). One line per scenario: ``PASS
<scenario>: …`` or ``GAP <scenario>: expected …; observed …``. Exit 0 when all pass, 1 when only
expectations were missed (soft, D-063), 2 on a crash or a timeout. The scratch live data is reset
at the end and the server and any child are stopped.
"""

from __future__ import annotations

import logging
import shutil
import socket
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from kairos_defense.config import Config

log = logging.getLogger(__name__)

SCENARIOS = ("returning-prober", "copycat", "hobbyist", "swarm-repeat", "new-operator-twice")
SEEDS = {"returning-prober": 1101, "copycat": 1102, "hobbyist": 1103, "swarm-repeat": 1104,
         "new-operator-twice": 1105}  # fmt: skip
POLL_S = 0.5


class CheckFailed(RuntimeError):
    """A crash or timeout: exit 2."""


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def score(name: str, seed: int, docs: list[dict], elapsed_s: float) -> tuple[bool, str]:
    """``(passed, line)`` for one scenario from the reveals of its incidents."""
    mine = [d for d in docs if d.get("scenario") == name and d.get("seed") == seed]
    if not mine:
        return False, (f"GAP {name}: expected an incident flown by seed {seed}; observed none "
                       f"({len(docs)} other incident(s))")  # fmt: skip
    by_flight: dict[int, dict] = {}
    for d in mine:  # a flight split by a radar gap: score its incident with the most reruns
        f = int(d.get("flight") or 1)
        if f not in by_flight or len(d["reruns"]) > len(by_flight[f]["reruns"]):
            by_flight[f] = d
    need = (1, 2) if name == "new-operator-twice" else (1,)
    missing = [f for f in need if f not in by_flight]
    if missing:
        return False, (f"GAP {name}: expected flight(s) {', '.join(map(str, need))}; observed "
                       f"no incident for flight {', '.join(map(str, missing))}")  # fmt: skip
    parts, ok = [], True
    for f in need:
        d = by_flight[f]
        e = d["expectation"]
        ok &= bool(e["met"])
        label = f"flight {f}: " if len(need) > 1 else ""
        parts.append(f"{label}{d['actor_id']} at {d['base']} ({d['incident_id']}, "
                     f"{len(d['reruns'])} reruns): {e['observed']}")  # fmt: skip
    head = f"{'PASS' if ok else 'GAP'} {name}: "
    if ok:
        return True, head + "; ".join(parts) + f"; seed {seed}, {elapsed_s:.0f} s"
    texts = "; ".join(by_flight[f]["expectation"]["text"] for f in need
                      if not by_flight[f]["expectation"]["met"])  # fmt: skip
    return False, head + f"expected {texts}; observed " + "; ".join(parts) + f"; seed {seed}"


class _Server:
    """The API in a background thread on a free port."""

    def __init__(self, cfg: Config, scratch: Path, config_dir: Path) -> None:
        import uvicorn

        from kairos_defense.api.app import create_app

        app = create_app(cfg, memory_path=scratch / "memory.duckdb",
                         live_path=scratch / "live.duckdb", reseed=True,
                         exports_path=scratch / "exports", live_mode_path=scratch / "live_mode",
                         config_dir=config_dir)  # fmt: skip
        self.port = free_port()
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port,
                                                    log_level="warning",
                                                    ws_ping_interval=20))  # fmt: skip
        self.thread = threading.Thread(target=self.server.run, daemon=True, name="live-check-api")

    def start(self, timeout_s: float = 300.0) -> None:
        self.thread.start()
        end = time.monotonic() + timeout_s
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() > end:
                raise CheckFailed("the API did not start")
            time.sleep(0.2)

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(60)


def _wait(client, before: set[str], timeout_s: float) -> dict:
    """Until the simulator has exited, every new incident is closed and nothing is pending."""
    end = time.monotonic() + timeout_s
    while True:
        st = client.get("/api/live/status").raise_for_status().json()
        new = [i for i in st["incidents"] if i["incident_id"] not in before]
        done = (not st["simulator"]["running"] and st["pending"] == 0
                and all(i["state"] == "closed" for i in new))  # fmt: skip
        if done:
            return st
        if time.monotonic() > end:
            raise CheckFailed(
                f"timed out after {timeout_s:.0f} s (simulator running: "
                f"{st['simulator']['running']}, pending {st['pending']}, "
                f"open: {[i['incident_id'] for i in new if i['state'] != 'closed']})"
            )
        time.sleep(POLL_S)


def run_live_check(cfg: Config, config_dir: Path, scenarios: Sequence[str], speed: float,
                   timeout_s: float, out: Callable[[str], None] = print) -> int:  # fmt: skip
    """Run the check; returns the exit code (0, 1 or 2)."""
    import httpx

    scratch = Path(cfg.app.paths.cache) / "live_check"
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True)
    server = None
    passed: list[bool] = []
    t_all = time.monotonic()
    try:
        server = _Server(cfg, scratch, config_dir)
        server.start()
        with httpx.Client(base_url=f"http://127.0.0.1:{server.port}", timeout=120) as client:
            for name in scenarios:
                seed = SEEDS[name]
                t0 = time.monotonic()
                before = {
                    i["incident_id"]
                    for i in client.get("/api/live/status").raise_for_status().json()["incidents"]
                }
                r = client.post("/api/sim/launch", json={"scenario": name, "speed": speed,
                                                         "seed": seed})  # fmt: skip
                if r.status_code != 200:
                    raise CheckFailed(f"{name}: launch refused ({r.status_code}): {r.text}")
                st = _wait(client, before, timeout_s)
                code = st["simulator"]["exit_code"]
                if code != 0:
                    raise CheckFailed(f"{name}: the simulator exited with {code} (see "
                                      f"{scratch / 'live_mode' / 'sim'})")  # fmt: skip
                new = [i["incident_id"] for i in st["incidents"] if i["incident_id"] not in before]
                docs = [client.get(f"/api/live/incidents/{i}/reveal").raise_for_status().json()
                        for i in new]  # fmt: skip
                ok, line = score(name, seed, docs, time.monotonic() - t0)
                passed.append(ok)
                out(line)
            client.post("/api/live/reset").raise_for_status()
    except (CheckFailed, OSError) as exc:
        out(f"FAIL live check: {exc}")
        return 2
    except Exception as exc:  # httpx errors, a crashed route
        log.exception("live check crashed")
        out(f"FAIL live check: {type(exc).__name__}: {exc}")
        return 2
    finally:
        if server is not None:
            server.stop()
    n_ok = sum(passed)
    out(
        f"live check: {n_ok} of {len(passed)} scenario(s) pass at speed {speed:g} in "
        f"{time.monotonic() - t_all:.0f} s"
    )
    return 0 if all(passed) else 1
