"""File adapter for the ``ResultCache`` port (D-013, D-104): ``data/cache/live/<incident>/``.

One JSON document per name (``manifest.json``, ``features.json``, ``t0045.json`` …), written
atomically (temp file, then ``os.replace``) so a reader never sees half a file.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

_NAME = re.compile(r"^[a-z0-9_]{1,40}$")
_INCIDENT = re.compile(r"^[A-Z0-9][A-Z0-9-]*$")


class FileResultCache:
    """``ResultCache`` under one root folder."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def _dir(self, incident_id: str) -> Path:
        if not _INCIDENT.match(incident_id):
            raise ValueError(f"bad incident id {incident_id!r}")
        return self.root / incident_id

    def _path(self, incident_id: str, name: str) -> Path:
        if not _NAME.match(name):
            raise ValueError(f"bad cache name {name!r}")
        return self._dir(incident_id) / f"{name}.json"

    def get(self, incident_id: str, name: str) -> dict | None:
        p = self._path(incident_id, name)
        if not p.is_file():
            return None
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return None  # a damaged file is a miss: it is recomputed

    def put(self, incident_id: str, name: str, doc: dict) -> None:
        p = self._path(incident_id, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, separators=(",", ":"), allow_nan=False))
        os.replace(tmp, p)

    def clear(self, incident_id: str) -> int:
        d = self._dir(incident_id)
        n = 0
        if d.is_dir():
            for p in d.glob("*.json"):
                p.unlink()
                n += 1
        return n
