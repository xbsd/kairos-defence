"""Starting the live simulator as a separate process (D-169, D-182).

``SimLauncher.launch`` runs ``python -m kairos_defense.cli simulate …`` with the ingest URL of
this API, one at a time. Who flies is passed to the child on its command line and kept nowhere
in the API: the launcher stores the scenario, bases, speed and seed only, never logs the
command, and sends the child's output to ``<live_mode>/sim/<n>.log``, which the simulator keeps
free of the actor (it names the actor only on an interactive terminal). When the child exits, the
``on_exit`` callback gets the bases it fed (the hub closes their idle incidents).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)


class SimulatorBusy(RuntimeError):
    """A simulator is already running (one at a time)."""


class SimLauncher:
    """``command``: builds the child's argv from the launch arguments (tests pass a stub)."""

    def __init__(self, folder: Path | str, config_dir: Path | str, *,
                 on_exit: Callable[[Sequence[str]], object] | None = None,
                 command: Callable[[dict], list[str]] | None = None) -> None:  # fmt: skip
        self.folder = Path(folder)
        self.config_dir = Path(config_dir)
        self.on_exit = on_exit
        self.command = command or self._command
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._state: dict = self._idle()
        self._n = 0

    @staticmethod
    def _idle() -> dict:
        return {"running": False, "scenario": None, "base": None, "second_base": None,
                "speed": None, "seed": None, "started_at": None, "exit_code": None}  # fmt: skip

    def _command(self, a: dict) -> list[str]:
        argv = [sys.executable, "-m", "kairos_defense.cli", "simulate",
                "--scenario", a["scenario"], "--speed", f"{float(a['speed']):g}",
                "--seed", str(int(a["seed"])), "--url", a["url"],
                "--live-mode-dir", str(self.folder), "--config", str(self.config_dir),
                "--parent-pid", str(os.getpid())]  # fmt: skip
        for key, flag in (("actor", "--actor"), ("base", "--base"),
                          ("second_base", "--second-base")):  # fmt: skip
            if a.get(key):
                argv += [flag, str(a[key])]
        return argv

    def running(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def state(self) -> dict:
        """The last launch's state; ``running`` is read from the process itself, so it is right
        the moment a child exits, before the exit watcher has updated the rest (D-192)."""
        with self._lock:
            alive = self._proc is not None and self._proc.poll() is None
            return {**self._state, "running": alive}

    def launch(self, args: dict) -> dict:
        """Start the child; ``args``: scenario, actor, base, second_base, speed, seed, url.
        Returns its pid. Raises ``SimulatorBusy`` while one runs."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                raise SimulatorBusy("a simulator is already running: wait for it or reset")
            self._n += 1
            logs = self.folder / "sim"
            logs.mkdir(parents=True, exist_ok=True)
            out = (logs / f"{self._n:03d}.log").open("w")
            env = {**os.environ, "PYTHONUNBUFFERED": "1"}
            try:
                proc = subprocess.Popen(self.command(args), stdout=out, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, env=env)  # fmt: skip
            finally:
                out.close()
            self._proc = proc
            self._state = {"running": True, "scenario": args["scenario"],
                           "base": args.get("base"), "second_base": args.get("second_base"),
                           "speed": float(args["speed"]), "seed": int(args["seed"]),
                           "started_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "exit_code": None}  # fmt: skip
        bases = [b for b in (args.get("base"), args.get("second_base")) if b]
        threading.Thread(target=self._watch, args=(proc, bases), daemon=True,
                         name="sim-watch").start()  # fmt: skip
        log.info("simulator started: %s (pid %d)", args["scenario"], proc.pid)
        return {"pid": proc.pid}

    def _watch(self, proc: subprocess.Popen, bases: list[str]) -> None:
        code = proc.wait()
        with self._lock:
            if self._proc is proc:
                self._state = {**self._state, "running": False, "exit_code": code}
        log.info("simulator exited with %s", code)
        if self.on_exit is not None:
            try:
                self.on_exit(bases)
            except Exception:  # the API keeps serving
                log.exception("simulator exit callback failed")

    def wait(self, timeout: float | None = None) -> int | None:
        with self._lock:
            proc = self._proc
        if proc is None:
            return None
        try:
            return proc.wait(timeout)
        except subprocess.TimeoutExpired:
            return None

    def stop(self, timeout: float = 5.0) -> bool:
        """Stop a running child (SIGTERM, then SIGKILL); True if one was running."""
        with self._lock:
            proc = self._proc
        if proc is None or proc.poll() is not None:
            return False
        proc.terminate()
        try:
            proc.wait(timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout)
        return True
