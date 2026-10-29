"""Models for ``config/app.yaml`` (SPEC §6.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from kairos_defense.config._types import StrictModel


class PathsConfig(StrictModel):
    duckdb: Path
    truth: Path
    memory: Path
    live: Path  # live_* scratch tables written by replays (D-103)
    lancedb: Path
    models: Path
    reports: Path
    exports: Path
    cache: Path  # downloaded models, e.g. FastEmbed (D-084)

    @model_validator(mode="after")
    def _distinct_dbs(self) -> PathsConfig:
        if len({self.duckdb, self.truth, self.memory, self.live}) != 4:
            raise ValueError("duckdb, truth, memory and live must be four different files")
        return self


class EmbeddingsConfig(StrictModel):
    provider: Literal["hashing", "fastembed"]
    dim: Annotated[int, Field(gt=0)]
    fastembed_model: str


class LlmConfig(StrictModel):
    provider: Literal["none", "anthropic", "openai", "ollama"]
    model: str
    base_url: str


class SigningConfig(StrictModel):
    enabled: bool
    key_path: Path


class ReplayConfig(StrictModel):
    default_speed: Literal[1.0, 2.0, 5.0]


class AppConfig(StrictModel):
    paths: PathsConfig
    embeddings: EmbeddingsConfig
    reports_llm_paraphrase: bool
    llm: LlmConfig
    signing: SigningConfig
    replay: ReplayConfig
