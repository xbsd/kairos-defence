"""SPEC §12.1: the hashing embedder (offline default); FastEmbed never downloads at runtime."""

from __future__ import annotations

import sys
import types
from typing import ClassVar

import numpy as np
import pytest

from kairos_defense.recall.embed import (
    EmbedderUnavailable,
    FastEmbedEmbedder,
    HashingEmbedder,
    features,
    fetch_model,
    make_embedder,
)
from kairos_defense.rng import stable_int

DELTA = ("Security forces patrol observed a small drone near the fuel farm at about 21:35, "
         "est. 300 ft, a flashing white light. A white pickup was parked on County Rd 12 "
         "from 21:20 to 22:05 and left shortly after the drone flew northwest.")  # fmt: skip
DELTA_BLOTTER = ("SF BLOTTER 19 APR 2026 21:35: PATROL OBSERVED SUAS VIC FUEL FARM, EST 300 FT, A "
                 "FLASHING WHITE LIGHT. A WHITE PICKUP WAS PARKED ON COUNTY RD 12 FROM 21:20 TO "
                 "22:05. UAS DEPARTED NORTHWEST 21:46.")  # fmt: skip
BDOC = "21:29 BDOC: UAS detected near the east fence. Radar track 1111. No Remote ID. SF notified."


def test_hashing_embedder_is_deterministic() -> None:
    texts = [DELTA, DELTA_BLOTTER, BDOC, ""]
    a, b = HashingEmbedder(384).embed(texts), HashingEmbedder(384).embed(texts)
    assert a.tobytes() == b.tobytes()


def test_hashing_rows_are_unit_float32() -> None:
    m = HashingEmbedder(384).embed([DELTA, DELTA_BLOTTER, BDOC])
    assert m.shape == (3, 384) and m.dtype == np.float32
    assert np.allclose(np.linalg.norm(m, axis=1), 1.0, atol=1e-6)


def test_hashing_known_answer() -> None:
    """``drone`` -> ``t:drone`` and the five 3-grams of ``<drone>``; each feature lands at
    ``stable_int(f) % 384`` with sign from bit 32, all distinct here, so each is ±1/sqrt(6)."""
    assert features("drone") == ["t:drone", "g:<dr", "g:dro", "g:ron", "g:one", "g:ne>"]
    v = HashingEmbedder(384).embed(["drone"])[0]
    nz = np.flatnonzero(v)
    assert nz.tolist() == [33, 53, 192, 288, 290, 368]
    assert np.sign(v[nz]).tolist() == [-1, 1, -1, -1, -1, -1]
    assert np.allclose(np.abs(v[nz]), 1 / np.sqrt(6))
    for f in features("drone"):  # the pinned numbers follow from the rule, not from a snapshot
        h = stable_int(f)
        assert np.sign(v[h % 384]) == (-1 if h & (1 << 32) else 1)


def test_hashing_ignores_case_and_punctuation() -> None:
    e = HashingEmbedder(384)
    assert np.array_equal(e.embed(["White Pickup!"]), e.embed(["white pickup"]))
    assert np.array_equal(e.embed(["COUNTY RD 12"]), e.embed(["county rd, 12."]))


def test_hashing_empty_text_is_zero() -> None:
    m = HashingEmbedder(384).embed(["", "!!! ---"])
    assert np.isfinite(m).all() and not m.any()
    assert HashingEmbedder(16).embed([]).shape == (0, 16)
    with pytest.raises(ValueError):
        HashingEmbedder(0)


def test_similar_reports_are_closer() -> None:
    a, b, c = HashingEmbedder(384).embed([DELTA, DELTA_BLOTTER, BDOC])
    assert float(a @ b) > float(a @ c) + 0.1


class FakeTextEmbedding:
    """Records how ``fastembed.TextEmbedding`` was constructed; returns fixed 4-dim rows."""

    calls: ClassVar[list[dict]] = []

    def __init__(self, **kwargs) -> None:
        FakeTextEmbedding.calls.append(kwargs)

    def embed(self, texts):
        for i, _ in enumerate(texts):
            yield np.array([3.0, 4.0, 0.0, float(i)])


@pytest.fixture
def fake_fastembed(monkeypatch):
    FakeTextEmbedding.calls = []
    monkeypatch.setitem(sys.modules, "fastembed", types.SimpleNamespace(
        TextEmbedding=FakeTextEmbedding))  # fmt: skip
    return FakeTextEmbedding


def _fastembed_app(cfg, tmp_path, dim=4):
    paths = cfg.app.paths.model_copy(update={"cache": tmp_path / "cache"})
    emb = cfg.app.embeddings.model_copy(update={"provider": "fastembed", "dim": dim})
    return cfg.app.model_copy(update={"paths": paths, "embeddings": emb})


def test_fastembed_adapter_never_downloads(cfg, tmp_path, fake_fastembed) -> None:
    app = _fastembed_app(cfg, tmp_path)
    with pytest.raises(EmbedderUnavailable, match="fetch-models"):
        make_embedder(app)  # not cached: refused before fastembed is even constructed
    assert fake_fastembed.calls == []
    (tmp_path / "cache" / "fastembed" / "models--qdrant--bge-small-en-v1.5-onnx-q").mkdir(
        parents=True
    )
    e = make_embedder(app)
    assert isinstance(e, FastEmbedEmbedder) and e.name == "fastembed:BAAI/bge-small-en-v1.5"
    call = fake_fastembed.calls[-1]
    assert call["local_files_only"] is True
    assert call["cache_dir"] == str(tmp_path / "cache" / "fastembed")
    m = e.embed(["a", "b"])
    assert m.dtype == np.float32 and m.shape == (2, 4)
    assert np.allclose(np.linalg.norm(m, axis=1), 1.0, atol=1e-6)
    with pytest.raises(EmbedderUnavailable, match="dimensions"):
        FastEmbedEmbedder(app.embeddings.fastembed_model, tmp_path / "cache" / "fastembed",
                          8).embed(["a"])  # fmt: skip


def test_make_embedder_without_fastembed_raises(cfg, tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "fastembed", None)  # import fastembed -> ImportError
    with pytest.raises(EmbedderUnavailable) as exc:
        make_embedder(_fastembed_app(cfg, tmp_path))
    assert "uv sync --extra fastembed" in str(exc.value) and "fetch-models" in str(exc.value)
    assert isinstance(make_embedder(cfg.app), HashingEmbedder)  # the offline default


def test_fetch_model_downloads_into_the_cache(cfg, tmp_path, fake_fastembed) -> None:
    app = _fastembed_app(cfg, tmp_path)
    path = fetch_model(app)
    assert path == tmp_path / "cache" / "fastembed" and path.is_dir()
    call = fake_fastembed.calls[-1]
    assert "local_files_only" not in call  # the one code path allowed to download
    assert call["model_name"] == "BAAI/bge-small-en-v1.5"
    fetch_model(app, "BAAI/other-model")
    assert fake_fastembed.calls[-1]["model_name"] == "BAAI/other-model"
