"""Ground-truth reader: the only code that opens the truth file (CLAUDE.md rule 2, SPEC §19).

It returns plain DataFrames; nothing outside ``kairos_defense.eval`` may call it.
"""

from __future__ import annotations

import duckdb
import pandas as pd

from kairos_defense.config import AppConfig


def _read(app: AppConfig, query: str, params: dict | None = None) -> pd.DataFrame:
    con = duckdb.connect(str(app.paths.truth), read_only=True)
    try:
        return con.execute(query, params or {}).df()
    finally:
        con.close()


def track_truth(app: AppConfig) -> pd.DataFrame:
    """``track_id, incident_id, actor_id, actor_type, launch_ts, recovery_x_m, recovery_y_m``
    (region meters, the true recovery point, §13 step 8) for every track."""
    return _read(app, "SELECT track_id, incident_id, actor_id, actor_type, launch_ts, "
                      "recovery_x_m, recovery_y_m FROM track_truth ORDER BY track_id")  # fmt: skip


def clue_truth(app: AppConfig) -> pd.DataFrame:
    """``report_id, clue_type, clue_value, is_true`` for every clue the generator wrote (§8.8)."""
    return _read(app, "SELECT report_id, clue_type, clue_value, is_true FROM clue_truth "
                      "ORDER BY report_id, clue_type, clue_value")  # fmt: skip


def true_path(app: AppConfig, track_id: str) -> pd.DataFrame:
    """Noiseless 1 Hz path of one track: ``t_s`` (s after launch), ``x_m``, ``y_m``, ``alt_m``."""
    return _read(app, "SELECT t_s, x_m, y_m, alt_m FROM true_paths WHERE track_id = $t "
                      "ORDER BY t_s", {"t": track_id})  # fmt: skip
