"""Configuration: one pydantic model per YAML file in ``config/`` and one loader (SPEC §6).

``load_config()`` validates every file, then checks references across files (bases, targets,
roads, teams) and resolves ``app.paths`` against the project root (the config folder's parent).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError, model_validator

from kairos_defense.config._types import StrictModel
from kairos_defense.config._yaml import load_yaml
from kairos_defense.config.actors import ActorsConfig
from kairos_defense.config.app import AppConfig
from kairos_defense.config.scenario import ScenarioConfig
from kairos_defense.config.scoring import ScoringConfig
from kairos_defense.config.world import WorldConfig

__all__ = [
    "CONFIG_FILES",
    "ActorsConfig",
    "AppConfig",
    "Config",
    "ConfigError",
    "ScenarioConfig",
    "ScoringConfig",
    "WorldConfig",
    "load_config",
    "load_yaml",
]

CONFIG_FILES = {
    "app": "app.yaml",
    "world": "world.yaml",
    "actors": "actors.yaml",
    "scenario": "scenario_demo.yaml",
    "scoring": "scoring.yaml",
}


class ConfigError(ValueError):
    """A config file is missing, unparsable or invalid."""


class Config(StrictModel):
    """All five config files, validated together."""

    root: Path
    app: AppConfig
    world: WorldConfig
    actors: ActorsConfig
    scenario: ScenarioConfig
    scoring: ScoringConfig

    @model_validator(mode="after")
    def _cross_refs(self) -> Config:
        bases = set(self.world.installation_ids())
        targets = {*self.world.installation_template.assets, "fence"}
        roads = {road.name for region in self.world.regions for road in region.roads}
        probers = {p.id: p for p in self.actors.probers}
        swarms = {s.id: s for s in self.actors.swarms}

        def need(ok: bool, msg: str) -> None:
            if not ok:
                raise ValueError(msg)

        for a in [*self.actors.probers, *self.actors.copycats, *self.actors.swarms]:
            for b in a.bases:
                need(b in bases, f"actor {a.id}: unknown base {b!r}")
        for a in [*self.actors.probers, *self.actors.swarms]:
            need(a.target in targets, f"actor {a.id}: unknown target {a.target!r}")
        for p in self.actors.probers:
            snap = p.launch.snap_to_road
            need(snap is None or snap in roads, f"prober {p.id}: unknown road {snap!r}")
        for region in self.world.regions:
            for road in region.roads:
                ok = road.actor is None or road.actor in probers
                need(ok, f"road {road.name!r}: unknown actor {road.actor!r}")
        p1 = probers.get("P1")
        need(p1 is not None, "actors.yaml must define prober P1 (the demo actor)")
        for f in self.scenario.p1_flights:
            need(p1 is not None and f.base in p1.bases, f"{f.incident_id}: P1 never flies {f.base}")
            t = f.target_override
            need(t is None or t in targets, f"{f.incident_id}: unknown target {t!r}")
        for s in self.scenario.swarm_events:
            team = swarms.get(s.team)
            need(team is not None, f"{s.incident_id}: unknown swarm team {s.team!r}")
            need(team is not None and s.base in team.bases, f"{s.incident_id}: bad base")
        return self


def _read(config_dir: Path, name: str) -> Any:
    path = config_dir / CONFIG_FILES[name]
    if not path.is_file():
        raise ConfigError(f"missing config file: {path}")
    try:
        return load_yaml(path)
    except Exception as exc:  # yaml.YAMLError or OSError
        raise ConfigError(f"{path}: cannot parse YAML: {exc}") from exc


def _resolve_paths(app: dict[str, Any], root: Path) -> dict[str, Any]:
    """Make ``paths.*`` and ``signing.key_path`` absolute, relative to the project root."""
    if isinstance(app.get("paths"), dict):
        app["paths"] = {k: str(root / v) for k, v in app["paths"].items()}
    if isinstance(app.get("signing"), dict) and "key_path" in app["signing"]:
        app["signing"]["key_path"] = str(root / app["signing"]["key_path"])
    return app


def load_config(config_dir: Path | str = "config") -> Config:
    """Load and validate every file in ``config_dir``.

    Raises ``ConfigError`` naming the file and the first problems found.
    """
    config_dir = Path(config_dir).resolve()
    root = config_dir.parent
    raw = {name: _read(config_dir, name) for name in CONFIG_FILES}
    raw["app"] = _resolve_paths(raw["app"], root) if isinstance(raw["app"], dict) else raw["app"]
    models: dict[str, Any] = {"root": root}
    for name, cls in [
        ("app", AppConfig),
        ("world", WorldConfig),
        ("actors", ActorsConfig),
        ("scenario", ScenarioConfig),
        ("scoring", ScoringConfig),
    ]:
        try:
            models[name] = cls.model_validate(raw[name])
        except ValidationError as exc:
            raise ConfigError(f"{config_dir / CONFIG_FILES[name]}: {exc}") from exc
    try:
        return Config.model_validate(models)
    except ValidationError as exc:
        raise ConfigError(f"{config_dir}: cross-file check failed: {exc}") from exc
