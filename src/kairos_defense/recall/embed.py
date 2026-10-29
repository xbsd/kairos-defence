"""Text embedders for report recall (SPEC §12.1, CLAUDE.md rule 5).

``HashingEmbedder`` is the offline default: lowercase, ``[a-z0-9]+`` tokens, each token
(``t:<token>``) and each character 3-gram of ``<token>`` (``g:<gram>``) hashed with
``stable_int`` to an index (``h % dim``) and a sign (bit 32 of ``h``), summed and L2-normalized
(D-083). It is deterministic across runs and platforms and needs no download.

``FastEmbedEmbedder`` wraps the optional ``fastembed`` package (``uv sync --extra fastembed``). It
never downloads: it refuses to start unless the model is already in ``paths.cache`` and passes
``local_files_only=True``. Only ``kairos-defense fetch-models`` (``fetch_model``) downloads (D-084).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

import numpy as np

from kairos_defense.config import AppConfig
from kairos_defense.ports import Embedder
from kairos_defense.rng import stable_int

log = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"[a-z0-9]+")
SIGN_BIT = 1 << 32
FASTEMBED_DIR = "fastembed"
INSTALL_HINT = "uv sync --extra fastembed"


class EmbedderUnavailable(RuntimeError):
    """The configured embedder cannot run offline (package missing or model not fetched)."""


@lru_cache(maxsize=1 << 18)
def _hashed(feature: str) -> int:
    return stable_int(feature)


def features(text: str) -> list[str]:
    """Hashing features of ``text``: ``t:<token>`` per token and ``g:<gram>`` per character 3-gram
    of the token padded as ``<token>``, in text order (duplicates kept: they add up)."""
    out: list[str] = []
    for tok in TOKEN_RE.findall(text.lower()):
        out.append(f"t:{tok}")
        padded = f"<{tok}>"
        out.extend(f"g:{padded[i : i + 3]}" for i in range(len(padded) - 2))
    return out


def _unit_rows(m: np.ndarray) -> np.ndarray:
    """L2-normalize each row; all-zero rows stay zero (never NaN)."""
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return np.divide(m, norms, out=np.zeros_like(m), where=norms > 0).astype(np.float32)


class HashingEmbedder:
    """Offline feature-hashing embedder; ``embed`` returns ``(n, dim)`` float32 unit rows."""

    def __init__(self, dim: int = 384) -> None:
        if dim <= 0:
            raise ValueError(f"dim must be positive, got {dim}")
        self.dim = int(dim)
        self.name = f"hashing-v1-{self.dim}"

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float64)
        for i, text in enumerate(texts):
            for f in features(text):
                h = _hashed(f)
                out[i, h % self.dim] += -1.0 if h & SIGN_BIT else 1.0
        return _unit_rows(out)


def _import_fastembed():
    try:
        import fastembed  # optional extra
    except ImportError as exc:
        raise EmbedderUnavailable(
            f"the fastembed package is not installed: run `{INSTALL_HINT}`, then "
            "`kairos-defense fetch-models`, or set embeddings.provider: hashing"
        ) from exc
    if fastembed is None:  # sys.modules entry set to None blocks the import (tests)
        raise EmbedderUnavailable(f"the fastembed package is not installed: run `{INSTALL_HINT}`")
    return fastembed


def model_cached(cache_dir: Path, model: str) -> bool:
    """True when ``cache_dir`` holds a folder for ``model`` (matched on its last path part, the
    way fastembed and the Hugging Face hub name their cache folders)."""
    key = model.rsplit("/", 1)[-1].lower()
    return cache_dir.is_dir() and any(key in p.name.lower() for p in cache_dir.iterdir())


class FastEmbedEmbedder:
    """``fastembed.TextEmbedding`` from the local cache only (never downloads, D-084)."""

    def __init__(self, model: str, cache_dir: Path | str, dim: int) -> None:
        fe = _import_fastembed()
        self.cache_dir = Path(cache_dir)
        if not model_cached(self.cache_dir, model):
            raise EmbedderUnavailable(
                f"embedding model {model} is not in {self.cache_dir}: run "
                "`kairos-defense fetch-models` once (it is the only command that downloads), "
                "or set embeddings.provider: hashing"
            )
        self.model = fe.TextEmbedding(model_name=model, cache_dir=str(self.cache_dir),
                                      local_files_only=True)  # fmt: skip
        self.dim = int(dim)
        self.name = f"fastembed:{model}"

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        rows = np.asarray(list(self.model.embed(list(texts))), dtype=np.float64)
        rows = rows.reshape(len(texts), -1)
        if rows.shape[1] != self.dim:
            raise EmbedderUnavailable(
                f"{self.name} returns {rows.shape[1]} dimensions; embeddings.dim is {self.dim}"
            )
        return _unit_rows(rows)


def make_embedder(app: AppConfig) -> Embedder:
    """The embedder ``config/app.yaml`` asks for; raises ``EmbedderUnavailable`` rather than
    silently switching providers (index and query vectors must come from the same one)."""
    e = app.embeddings
    if e.provider == "hashing":
        return HashingEmbedder(e.dim)
    return FastEmbedEmbedder(e.fastembed_model, Path(app.paths.cache) / FASTEMBED_DIR, e.dim)


def fetch_model(app: AppConfig, model: str | None = None) -> Path:
    """Download ``model`` (default ``embeddings.fastembed_model``) into ``paths.cache/fastembed``;
    the only code path that downloads anything (``kairos-defense fetch-models``)."""
    fe = _import_fastembed()
    name = model or app.embeddings.fastembed_model
    cache = Path(app.paths.cache) / FASTEMBED_DIR
    cache.mkdir(parents=True, exist_ok=True)
    log.info("downloading %s into %s", name, cache)
    fe.TextEmbedding(model_name=name, cache_dir=str(cache))
    return cache
