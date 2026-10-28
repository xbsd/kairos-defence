"""Table definitions (SPEC §7.1 raw tables, §7.3 ground truth).

``RAW_DDL`` belongs to the app database; ``TRUTH_DDL`` belongs to the ground-truth file, which only
``kairos_defense.sim.writers`` writes and only ``kairos_defense.eval`` reads (CLAUDE.md rule 2).
All ``TIMESTAMP`` columns are UTC. Coordinates are region-frame meters.
"""

from __future__ import annotations

import re

RAW_DDL: dict[str, str] = {
    "regions": "CREATE TABLE regions (region_id VARCHAR PRIMARY KEY, utc_offset_hours INTEGER)",
    "installations": """CREATE TABLE installations (
  installation_id VARCHAR PRIMARY KEY, name VARCHAR, region_id VARCHAR,
  origin_x_m DOUBLE, origin_y_m DOUBLE, rotation_deg DOUBLE, fence_wkt VARCHAR)""",
    "assets": """CREATE TABLE assets (
  asset_id VARCHAR PRIMARY KEY, installation_id VARCHAR, kind VARCHAR,
  polygon_wkt VARCHAR, centroid_x_m DOUBLE, centroid_y_m DOUBLE)""",
    "roads": """CREATE TABLE roads (
  road_id VARCHAR PRIMARY KEY, region_id VARCHAR, name VARCHAR, line_wkt VARCHAR)""",
    "parks": """CREATE TABLE parks (
  park_id VARCHAR PRIMARY KEY, region_id VARCHAR, center_x_m DOUBLE, center_y_m DOUBLE,
  radius_m DOUBLE)""",
    "sensors": """CREATE TABLE sensors (
  sensor_id VARCHAR PRIMARY KEY, installation_id VARCHAR, kind VARCHAR,
  x_m DOUBLE, y_m DOUBLE, range_m DOUBLE, params JSON)""",
    "incidents": """CREATE TABLE incidents (
  incident_id VARCHAR PRIMARY KEY, installation_id VARCHAR, region_id VARCHAR,
  start_ts TIMESTAMP, end_ts TIMESTAMP, n_tracks INTEGER, is_swarm BOOLEAN, status VARCHAR)""",
    "track_points": """CREATE TABLE track_points (
  incident_id VARCHAR, track_id VARCHAR, installation_id VARCHAR, region_id VARCHAR,
  sensor_id VARCHAR, ts TIMESTAMP, x_m DOUBLE, y_m DOUBLE, alt_m DOUBLE, quality DOUBLE)""",
    "rf_detections": """CREATE TABLE rf_detections (
  installation_id VARCHAR, sensor_id VARCHAR, ts TIMESTAMP, band VARCHAR,
  protocol_family VARCHAR, bearing_deg DOUBLE, snr_db DOUBLE)""",
    "remote_id": """CREATE TABLE remote_id (
  installation_id VARCHAR, ts TIMESTAMP, serial VARCHAR,
  drone_x_m DOUBLE, drone_y_m DOUBLE, op_x_m DOUBLE, op_y_m DOUBLE)""",
    "weather": """CREATE TABLE weather (
  region_id VARCHAR, ts TIMESTAMP, wind_ms DOUBLE, wind_dir_deg DOUBLE, visibility_km DOUBLE)""",
    "base_events": """CREATE TABLE base_events (
  installation_id VARCHAR, start_ts TIMESTAMP, end_ts TIMESTAMP, kind VARCHAR, label VARCHAR)""",
    "public_events": """CREATE TABLE public_events (
  region_id VARCHAR, start_ts TIMESTAMP, end_ts TIMESTAMP, kind VARCHAR, label VARCHAR,
  x_m DOUBLE, y_m DOUBLE)""",
    "reports": """CREATE TABLE reports (
  report_id VARCHAR PRIMARY KEY, incident_id VARCHAR, installation_id VARCHAR,
  source VARCHAR, source_grade VARCHAR,
  event_ts TIMESTAMP, report_ts TIMESTAMP, text VARCHAR, x_m DOUBLE, y_m DOUBLE)""",
    "assessments": """CREATE TABLE assessments (
  assessment_id VARCHAR PRIMARY KEY, incident_id VARCHAR,
  label VARCHAR, rationale VARCHAR, assessed_ts TIMESTAMP, author VARCHAR)""",
}

TRUTH_DDL: dict[str, str] = {
    "track_truth": """CREATE TABLE track_truth (
  track_id VARCHAR PRIMARY KEY, incident_id VARCHAR, actor_id VARCHAR, actor_type VARCHAR,
  launch_ts TIMESTAMP, time_warp DOUBLE,
  launch_x_m DOUBLE, launch_y_m DOUBLE, recovery_x_m DOUBLE, recovery_y_m DOUBLE)""",
    "true_paths": """CREATE TABLE true_paths (
  track_id VARCHAR, t_s DOUBLE, x_m DOUBLE, y_m DOUBLE, alt_m DOUBLE)""",
    "clue_truth": """CREATE TABLE clue_truth (
  report_id VARCHAR, clue_type VARCHAR, clue_value VARCHAR, is_true BOOLEAN)""",
    "assessment_truth": """CREATE TABLE assessment_truth (
  incident_id VARCHAR PRIMARY KEY, correct_label VARCHAR)""",
}

_COL = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s+[A-Z]", re.M)


def columns(ddl: str) -> list[str]:
    """Column names of one ``CREATE TABLE`` statement, in order."""
    body = ddl[ddl.index("(") + 1 : ddl.rindex(")")]
    return [m.group(1) for part in body.split(",") if (m := _COL.match(part.strip()))]


RAW_COLUMNS: dict[str, list[str]] = {t: columns(sql) for t, sql in RAW_DDL.items()}
TRUTH_COLUMNS: dict[str, list[str]] = {t: columns(sql) for t, sql in TRUTH_DDL.items()}
