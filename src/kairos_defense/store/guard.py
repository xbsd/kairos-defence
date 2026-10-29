"""Truth-isolation guard (SPEC §7.6, CLAUDE.md rule 2).

Every app-side DuckDB connection goes through ``connect_app_db``, which refuses the ground-truth
file however its path is spelled (relative, ``..``, symlink or hard link). Only
``kairos_defense.eval`` reads truth, and only the generator's writer writes it.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import duckdb

from kairos_defense.config import AppConfig

log = logging.getLogger(__name__)


class TruthAccessError(PermissionError):
    """Raised when app code tries to open the ground-truth database."""


def _same_file(a: Path, b: Path) -> bool:
    if a.resolve() == b.resolve():
        return True
    try:
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def is_truth_path(path: Path | str, app: AppConfig) -> bool:
    """True if ``path`` names the ground-truth database file."""
    if str(path) == ":memory:":
        return False
    return _same_file(Path(path), Path(app.paths.truth))


def refuse_truth(path: Path | str, app: AppConfig) -> None:
    """Raise ``TruthAccessError`` if ``path`` names the ground-truth file (for code that reaches a
    DuckDB file without ``connect_app_db``, e.g. ``ATTACH``)."""
    if is_truth_path(path, app):
        raise TruthAccessError(f"refusing to open ground truth from app code: {path}")


def connect_app_db(
    path: Path | str, app: AppConfig, *, read_only: bool = False
) -> duckdb.DuckDBPyConnection:
    """Open an app DuckDB file (store, memory or ``:memory:``); refuse the truth file."""
    refuse_truth(path, app)
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    log.debug("connect_app_db %s (read_only=%s)", path, read_only)
    return duckdb.connect(str(path), read_only=read_only)
