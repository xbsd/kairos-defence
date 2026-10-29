from __future__ import annotations

import re
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from kairos_defense.config import CONFIG_FILES, ConfigError, load_config, load_yaml


def test_shipped_config_loads(cfg, root: Path) -> None:
    w, a, s = cfg.world, cfg.actors, cfg.scenario
    assert cfg.root == root
    assert w.seed == 42
    assert [r.id for r in w.regions] == ["COASTAL", "PLAINS", "DESERT"]
    assert len(w.installation_ids()) == 12
    assert sum(len(r.parks) for r in w.regions) == 18  # 6 originals + 12 launch parks (D-005)
    assert [p.id for p in a.probers] == ["P1", "P2", "P3", "P4", "P5", "P6"]
    assert [c.id for c in a.copycats] == ["C1", "C2"]
    assert [x.id for x in a.swarms] == ["S1", "S2"]
    assert len(s.p1_flights) == 6
    assert cfg.scoring.vector_dim == 80


def test_decision_values_survive_loading(cfg) -> None:
    p1 = cfg.actors.probers[0]
    assert p1.cruise_speed_ms == 15  # D-003
    assert p1.pattern.angular_speed_dps == 3  # D-004
    bravo = cfg.world.installation("BRAVO")
    assert bravo.terrain_mask is not None
    assert bravo.terrain_mask.bearing_deg == (285, 20)  # D-003
    assert cfg.world.region_of("GOLF").id == "DESERT"
    roads = cfg.world.regions[0].roads
    assert roads[0].build == "through_launch_points" and roads[0].actor == "P1"  # D-006


def test_yaml_12_booleans(cfg, tmp_path: Path) -> None:
    assert [p.rid for p in cfg.actors.probers] == ["off", "spoofed", "off", "off", "off", "off"]
    clue = cfg.scenario.p1_flights[2].reports[0].clues[0]
    assert clue.is_true is True
    live = cfg.scenario.p1_flights[-1]
    assert (live.incident_id, live.jitter, live.status) == ("DEMO-BRAVO-0828", "none", "live")
    assert live.start_local == datetime(2026, 8, 28, 21, 38, 45)
    f = tmp_path / "x.yaml"
    f.write_text("a: off\nb: yes\nc: true\nd: False\ntrue: 1\n")
    assert load_yaml(f) == {"a": "off", "b": "yes", "c": True, "d": False, "true": 1}


def test_paths_resolve_against_project_root(cfg, root: Path) -> None:
    assert cfg.app.paths.duckdb == root / "data" / "kairos_defense.duckdb"
    assert cfg.app.signing.key_path == root / "data" / "keys" / "ed25519.pem"
    assert all(p.is_absolute() for p in cfg.app.paths.model_dump().values())


def test_models_are_frozen(cfg) -> None:
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError on frozen model
        cfg.world.seed = 7


# ----------------------------------------------------------------- invalid configs


def _variant(root: Path, tmp_path: Path, name: str, mutate: Callable[[Any], Any]) -> Path:
    """Copy config/ to tmp, apply ``mutate`` to one parsed file and write it back."""
    out = tmp_path / "config"
    shutil.copytree(root / "config", out)
    path = out / CONFIG_FILES[name]
    data = load_yaml(path)
    data = mutate(data) or data
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return out


def _set(path: str, value: Any) -> Callable[[Any], None]:
    def mutate(d: Any) -> None:
        *keys, last = path.split(".")
        for k in keys:
            d = d[int(k)] if isinstance(d, list) else d[k]
        if isinstance(d, list):
            d[int(last)] = value
        else:
            d[last] = value

    return mutate


BAD = [
    ("app", _set("paths.extra_db", "data/x.duckdb"), "extra"),
    ("app", _set("paths.truth", "data/kairos_defense.duckdb"), "three different files"),
    ("app", _set("replay.default_speed", 3.0), "default_speed"),
    ("app", _set("llm.provider", "acme"), "provider"),
    ("world", _set("calendar.end_local", "2025-01-01"), "before end_local"),
    ("world", _set("calendar.night_window_local", ["25:00", "03:00"]), "HH:MM"),
    ("world", _set("regions.0.installations.1.terrain_mask.bearing_deg", [285, 360]), "[0, 360)"),
    ("world", _set("regions.1.installations.0.id", "ALPHA"), "duplicate installation"),
    ("world", _set("regions.0.roads.1.points_m", [[0, 0]]), "two points"),
    ("world", _set("sensors_template.0.p_detect_near", 1.5), "p_detect_near"),
    ("world", _set("sensors_template.0.kind", "lidar"), "kind"),
    ("actors", _set("hobbyists.duration_s", [720, 180]), "reversed"),
    ("actors", _set("probers.0.rid", "maybe"), "rid"),
    ("actors", _set("probers.0.pattern.type", "spiral"), "type"),
    ("actors", _set("probers.1.flights", -1), "flights"),
    ("actors", _set("copycats.0.mimics", "P9"), "unknown prober"),
    ("actors", _set("swarms.0.choreography.2.groups", [2, 2]), "add up to 5"),
    ("actors", _set("swarms.0.choreography.1.factor", 2.0), "takes exactly"),
    ("actors", _set("probers.1.bases", ["ALPHA", "ZULU"]), "unknown base"),
    ("actors", _set("probers.2.target", "runway"), "unknown target"),
    ("actors", _set("probers.0.launch.snap_to_road", "Nowhere Ln"), "unknown road"),
    ("scenario", _set("live_incident", "P1-ALPHA-260303"), "live P1 flight"),
    ("scenario", _set("expectations.live_top3_incidents", ["A", "B", "C"]), "unknown P1"),
    ("scenario", _set("p1_flights.1.base", "GOLF"), "P1 never flies GOLF"),
    ("scenario", _set("p1_flights.2.reports.0.grade", "Z9"), "grade"),
    ("scenario", _set("swarm_events.0.team", "S9"), "unknown swarm team"),
    ("scoring", _set("features.channel_weights", [1.0, 1.0]), "one weight per channel"),
    ("scoring", _set("features.channel_scales", [1.0, 1.0]), "one scale per channel"),
    ("scoring", _set("features.channel_scales", [5.0, 10.0, 0.0, 30.0, 1.0]), "channel_scales"),
    ("scoring", _set("windows.normalize", "global"), "normalize"),
    ("scoring", _set("dtw.band_fraction", 0.0), "band_fraction"),
    ("scoring", _set("dtw.tau", "manual"), "tau"),
    ("scoring", _set("dtw.normalize", "window"), "normalize"),
]


@pytest.mark.parametrize(("name", "mutate", "match"), BAD, ids=[b[2] for b in BAD])
def test_invalid_config_is_rejected(
    root: Path, tmp_path: Path, name: str, mutate: Callable[[Any], Any], match: str
) -> None:
    cdir = _variant(root, tmp_path, name, mutate)
    with pytest.raises(ConfigError, match=re.escape(match)):
        load_config(cdir)


def test_missing_file_is_reported(root: Path, tmp_path: Path) -> None:
    out = tmp_path / "config"
    shutil.copytree(root / "config", out)
    (out / "scoring.yaml").unlink()
    with pytest.raises(ConfigError, match="missing config file"):
        load_config(out)


def test_unparsable_yaml_is_reported(root: Path, tmp_path: Path) -> None:
    out = tmp_path / "config"
    shutil.copytree(root / "config", out)
    (out / "app.yaml").write_text("paths: [unclosed\n")
    with pytest.raises(ConfigError, match="cannot parse YAML"):
        load_config(out)
