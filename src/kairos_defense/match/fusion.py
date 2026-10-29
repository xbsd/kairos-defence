"""Fusion features and the frozen logistic model (SPEC §10.5, §10.6).

Context features compare the query's (partial) signature with a candidate's stored signature; an
unknown on either side fuses as 0.5 (§10.5). ``FusionModel`` is the trained artifact
(``models/fusion_v1.json``): the matcher only evaluates ``sigmoid(x · coef + b)``, so serving needs
neither scikit-learn nor truth. Training lives in ``kairos_defense.eval.training`` (D-073).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit

UNKNOWN = 0.5  # §10.5: what is not known yet fuses as 0.5
LAUNCH_SCALE_M = 1000.0
RADIUS_SCALE_M = 50.0
ALT_SCALE_M = 30.0
CONTEXT = ("rf_match", "bearing_sim", "tod_sim", "launch_sim", "radius_sim", "alt_sim")
MODEL_FILE = "fusion_v1.json"
CALIBRATION_FILE = "dtw_calibration.json"


class ModelError(RuntimeError):
    """A model artifact is missing, unreadable or does not fit the configuration."""


def _num(values) -> np.ndarray:
    """Floats with None as NaN, ``(n,)`` float64."""
    return pd.to_numeric(pd.Series(values, dtype=object), errors="coerce").to_numpy(np.float64)


def _band(family: str) -> str:
    """Band of an RF family: the first digit of its number (``FAM-07`` → ``0``, D-036)."""
    return family.split("-")[-1][:1]


def rf_match(a: str | None, b: str | None) -> float:
    """1.0 same family; 0.5 either unknown or same band; 0.0 otherwise (§10.5)."""
    if not a or not b or a == "unknown" or b == "unknown":
        return UNKNOWN
    if a == b:
        return 1.0
    return UNKNOWN if _band(a) == _band(b) else 0.0


def context_frame(qsig: dict, csigs: pd.DataFrame) -> pd.DataFrame:
    """The six §10.5 context features of the query against each candidate signature row
    (``SIGNATURE_COLUMNS``); one row per candidate, columns ``CONTEXT``, same index."""

    def q(key: str) -> float:
        v = qsig.get(key)
        return float("nan") if v is None else float(v)

    def known(x: np.ndarray, y: float) -> np.ndarray:
        return np.isfinite(x) & np.isfinite(y)

    out = pd.DataFrame(index=csigs.index)
    out["rf_match"] = [rf_match(qsig.get("rf_family"), f) for f in csigs["rf_family"]]
    brg = _num(csigs["approach_bearing_deg"])
    d = np.radians(brg - q("approach_bearing_deg"))
    out["bearing_sim"] = np.where(known(brg, q("approach_bearing_deg")), (1 + np.cos(d)) / 2,
                                  UNKNOWN)  # fmt: skip
    tod = _num(csigs["tod_minutes"])
    out["tod_sim"] = np.where(known(tod, q("tod_minutes")),
                              (1 + np.cos(2 * np.pi * (tod - q("tod_minutes")) / 1440)) / 2,
                              UNKNOWN)  # fmt: skip
    lx, ly = _num(csigs["launch_x_rel_m"]), _num(csigs["launch_y_rel_m"])
    dist = np.hypot(lx - q("launch_x_rel_m"), ly - q("launch_y_rel_m"))
    out["launch_sim"] = np.where(np.isfinite(dist), np.exp(-dist / LAUNCH_SCALE_M), UNKNOWN)
    rad = _num(csigs["loiter_radius_m"])
    out["radius_sim"] = np.where(known(rad, q("loiter_radius_m")),
                                 np.exp(-np.abs(rad - q("loiter_radius_m")) / RADIUS_SCALE_M),
                                 UNKNOWN)  # fmt: skip
    alt = _num(csigs["alt_median_m"])
    out["alt_sim"] = np.where(
        known(alt, q("alt_median_m")),
        np.exp(-np.abs(alt - q("alt_median_m")) / ALT_SCALE_M),
        UNKNOWN,
    )
    return out


def fusion_features(qsig: dict, csig: dict, shape_sim: float) -> dict[str, float]:
    """All seven §10.5 features for one pair (``shape_sim`` from §10.4)."""
    row = context_frame(qsig, pd.DataFrame([csig])).iloc[0]
    return {"shape_sim": float(shape_sim), **{k: float(row[k]) for k in CONTEXT}}


def feature_matrix(rows: pd.DataFrame | list[dict], order: list[str] | tuple[str, ...]):
    """``(n, len(order))`` float64 in the model's feature order."""
    df = pd.DataFrame(rows) if not isinstance(rows, pd.DataFrame) else rows
    if len(df) == 0:
        return np.zeros((0, len(order)))
    return df[list(order)].to_numpy(dtype=np.float64)


def _read(path: Path, what: str) -> dict:
    path = Path(path)
    if not path.exists():
        raise ModelError(f"no {what}: run `make models` (missing {path})")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ModelError(f"unreadable {what}: run `make models` ({path})") from exc


def _write(path: Path, payload: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    return path


@dataclass(frozen=True)
class FusionModel:
    """Logistic fusion (§10.6). ``predict`` = ``sigmoid(X @ coefficients + intercept)``."""

    version: str
    features: tuple[str, ...]
    coefficients: tuple[float, ...]
    intercept: float
    tau: float
    training_hash: str
    created_at: str = ""
    train_split: dict = field(default_factory=dict)
    validation: dict = field(default_factory=dict)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """``(n, k)`` features in ``self.features`` order -> ``(n,)`` scores in (0, 1)."""
        X = np.asarray(X, dtype=np.float64).reshape(-1, len(self.features))
        return expit(X @ np.asarray(self.coefficients) + self.intercept)

    def contributions(self, x: dict[str, float]) -> dict[str, float]:
        """§10.7: ``coef_i × x_i`` per feature (missing features count 0)."""
        return {f: c * float(x.get(f, 0.0)) for f, c in zip(self.features, self.coefficients,
                                                            strict=True)}  # fmt: skip

    def to_json(self) -> dict:
        d = asdict(self)
        d["features"], d["coefficients"] = list(self.features), list(self.coefficients)
        return d

    def save(self, path: Path | str) -> Path:
        return _write(Path(path), self.to_json())

    @classmethod
    def load(cls, path: Path | str, expected_features: list[str] | tuple[str, ...]) -> FusionModel:
        """Read a saved model; refuse one whose feature order differs from the configuration."""
        d = _read(Path(path), "fusion model")
        try:
            m = cls(**{**d, "features": tuple(d["features"]),
                       "coefficients": tuple(float(c) for c in d["coefficients"])})  # fmt: skip
        except (TypeError, KeyError) as exc:
            raise ModelError(f"not a fusion model: run `make models` ({path})") from exc
        if list(m.features) != list(expected_features):
            raise ModelError(
                f"feature order differs from the configuration: run `make models` ({path} has "
                f"{list(m.features)}, scoring.yaml asks for {list(expected_features)})"
            )
        if len(m.coefficients) != len(m.features):
            raise ModelError(f"{path}: one coefficient per feature expected")
        return m


@dataclass(frozen=True)
class DtwCalibration:
    """τ for ``shape_sim = exp(−d_norm / τ)`` and the pair statistics behind it (§10.4 step 4)."""

    version: str
    tau: float
    n_pairs: int
    n_positive: int
    d_norm_same: dict  # p10, p50, p90 over same-actor pairs
    d_norm_other: dict  # p10, p50, p90 over the other pairs
    band_fraction: float
    anchor: list
    training_hash: str
    created_at: str = ""

    def save(self, path: Path | str) -> Path:
        return _write(Path(path), asdict(self))

    @classmethod
    def load(cls, path: Path | str) -> DtwCalibration:
        d = _read(Path(path), "DTW calibration")
        try:
            return cls(**d)
        except TypeError as exc:
            raise ModelError(f"not a DTW calibration: run `make models` ({path})") from exc
