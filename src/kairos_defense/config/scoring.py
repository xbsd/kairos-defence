"""Models for ``config/scoring.yaml`` (SPEC §6.5)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from kairos_defense.config._types import NonNeg, Pos, StrictModel


class FeaturesConfig(StrictModel):
    resample_hz: Pos
    max_interp_gap_s: NonNeg
    channels: Annotated[list[str], Field(min_length=1)]
    channel_weights: list[Pos]
    channel_scales: list[Pos]  # fixed units per channel for `windows.normalize: fixed` (D-068)

    @model_validator(mode="after")
    def _weights(self) -> FeaturesConfig:
        if len(self.channel_weights) != len(self.channels):
            raise ValueError("channel_weights must have one weight per channel")
        if len(self.channel_scales) != len(self.channels):
            raise ValueError("channel_scales must have one scale per channel")
        return self


class WindowsConfig(StrictModel):
    sizes_s: Annotated[list[Annotated[int, Field(gt=0)]], Field(min_length=1)]
    stride_s: Annotated[int, Field(gt=0)]
    paa_segments: Annotated[int, Field(gt=0)]
    # window: z-normalize each window over itself (§9.3 as written, phase 3);
    # fixed: divide by `features.channel_scales`, no centering (D-068)
    normalize: Literal["window", "fixed"]


class PrefilterConfig(StrictModel):
    k_windows: Annotated[int, Field(gt=0)]
    candidate_tracks: Annotated[int, Field(gt=0)]


class DtwConfig(StrictModel):
    band_fraction: Annotated[float, Field(gt=0, le=1)]
    anchor_before: NonNeg
    anchor_after: Pos
    tau: Literal["auto"] | Pos
    # series: z over each series (§9.3); floored: σ floored at features.channel_scales;
    # fixed: raw / channel_scales, no centering (D-079)
    normalize: Literal["series", "floored", "fixed"]


class FusionConfig(StrictModel):
    model: Literal["logistic"]
    features: Annotated[list[str], Field(min_length=1)]


class LiveConfig(StrictModel):
    min_track_s: Pos
    rerun_every_s: Pos


class RecallConfig(StrictModel):
    hours_window: Pos
    radius_m: Pos
    k: Annotated[int, Field(gt=0)]


class ForecastConfig(StrictModel):
    top_k: Annotated[int, Field(gt=0)]
    min_radius_m: Pos
    radius_factor: Pos


class SwarmScoringConfig(StrictModel):
    min_drones: Annotated[int, Field(ge=2)]
    max_spacing_m: Pos
    min_duration_s: Pos


class ScoringConfig(StrictModel):
    features: FeaturesConfig
    windows: WindowsConfig
    prefilter: PrefilterConfig
    dtw: DtwConfig
    fusion: FusionConfig
    live: LiveConfig
    recall: RecallConfig
    forecast: ForecastConfig
    swarm: SwarmScoringConfig

    @property
    def vector_dim(self) -> int:
        """PAA window vector length: channels × segments (80 by default)."""
        return len(self.features.channels) * self.windows.paa_segments
