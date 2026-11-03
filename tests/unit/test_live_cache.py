"""D-013, D-105: the precomputed live results cache (``replay --precompute``)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kairos_defense.live.loop import result_name
from kairos_defense.live.precompute import fingerprint, precompute
from kairos_defense.store.live_cache import FileResultCache
from tests.conftest import make_loop

# wall-clock measurements inside the matcher trace (D-187), left out like the result's own
TRACE_TIMINGS = {"prefilter": ("ms",), "dtw": ("ms", "ms_each"), "fusion": ("ms",)}


def _strip(doc: dict) -> dict:
    out = {k: v for k, v in doc.items() if k not in ("elapsed_ms", "timings", "cached")}
    if out.get("trace"):  # every other trace field (paths, distances, scores) is compared
        t = {k: v for k, v in out["trace"].items()
             if k not in ("explain_ms", "total_ms", "trace_ms")}  # fmt: skip
        for part, keys in TRACE_TIMINGS.items():
            t[part] = {k: v for k, v in t[part].items() if k not in keys}
        out["trace"] = t
    return out


def test_round_trip(tmp_path) -> None:
    c = FileResultCache(tmp_path)
    doc = {"t_s": 90, "matches": [{"incident_id": "P1-X", "score": 0.5}], "forecast": None}
    c.put("DEMO-BRAVO-0828", "t0090", doc)
    assert c.get("DEMO-BRAVO-0828", "t0090") == doc
    assert c.get("DEMO-BRAVO-0828", "t0095") is None
    assert c.clear("DEMO-BRAVO-0828") == 1 and c.get("DEMO-BRAVO-0828", "t0090") is None
    with pytest.raises(ValueError):
        c.put("../evil", "t0090", doc)
    with pytest.raises(ValueError):
        c.get("DEMO-BRAVO-0828", "../../x")
    with pytest.raises(ValueError):  # NaN is refused (the cache is strict JSON)
        c.put("DEMO-BRAVO-0828", "t0001", {"x": float("nan")})


def test_damaged_file_is_a_miss(tmp_path) -> None:
    c = FileResultCache(tmp_path)
    p = Path(tmp_path) / "DEMO-BRAVO-0828" / "t0090.json"
    p.parent.mkdir(parents=True)
    p.write_text("{not json")
    assert c.get("DEMO-BRAVO-0828", "t0090") is None


@pytest.fixture
def short(live_kit, tmp_path):
    """A loop with a cache and a two-rerun schedule (the full sweep is the slow test)."""
    fp = fingerprint(live_kit.store, live_kit.cfg.scoring, live_kit.cfg.app, "DEMO-BRAVO-0828")
    cache = FileResultCache(tmp_path / "live")
    loop = make_loop(live_kit, cache, fp)
    loop.schedule = [45, 90]
    loop.save_features = lambda: len(loop.features_range(80, 92))  # keep it fast
    return loop, cache, fp


def test_precompute_writes_every_rerun_second_and_features(short) -> None:
    loop, cache, fp = short
    s = precompute(loop)
    assert (s.reruns, s.computed, s.cached) == (2, 2, 0) and s.fingerprint == fp
    for r in (45, 90):
        assert cache.get("DEMO-BRAVO-0828", result_name(r))["t_s"] == r
    man = cache.get("DEMO-BRAVO-0828", "manifest")
    assert man["fingerprint"] == fp and man["reruns"] == [45, 90] and man["complete"]


def test_cached_result_equals_computed(short, live_kit) -> None:
    loop, cache, fp = short
    precompute(loop)
    fresh = make_loop(live_kit, cache, fp)
    hit = fresh.result_at(92)
    assert hit["cached"] is True
    again = make_loop(live_kit).compute(90)
    assert json.dumps(_strip(hit), sort_keys=True) == json.dumps(_strip(again), sort_keys=True)
    assert hit["elapsed_ms"] == cache.get("DEMO-BRAVO-0828", "t0090")["elapsed_ms"]


def test_second_precompute_is_noop_when_fresh(short) -> None:
    loop, _, _ = short
    precompute(loop)
    s = precompute(loop)
    assert (s.computed, s.cached) == (0, 2)


def test_model_change_makes_cache_stale(short, live_kit) -> None:
    loop, cache, _ = short
    precompute(loop)
    stale = make_loop(live_kit, cache, "0" * 64)  # a different model or config
    assert cache.get("DEMO-BRAVO-0828", "t0090") is None
    assert cache.get("DEMO-BRAVO-0828", "manifest")["fingerprint"] == "0" * 64
    assert stale.cache_state()["results"] == 0


def test_fingerprint_follows_the_model_file(live_kit, tmp_path) -> None:
    import shutil

    from tests.conftest import with_models

    c = live_kit.cfg
    a = fingerprint(live_kit.store, c.scoring, c.app, "DEMO-BRAVO-0828")
    other = shutil.copytree(c.app.paths.models, tmp_path / "models")
    p = other / "fusion_v1.json"
    p.write_text(p.read_text().replace('"toy"', '"toy2"'))
    b = fingerprint(live_kit.store, c.scoring, with_models(c, other).app, "DEMO-BRAVO-0828")
    assert a != b and len(a) == 64


def test_force_recomputes(short) -> None:
    loop, _, _ = short
    precompute(loop)
    s = precompute(loop, force=True)
    assert (s.computed, s.cached) == (2, 0)
