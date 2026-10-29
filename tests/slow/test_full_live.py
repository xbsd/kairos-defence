"""SPEC §16.1, D-013: the full precompute of the P1 live incident equals the loop's own results
at every rerun second (same second ⇒ identical results), and every feature second exists."""

from __future__ import annotations

import json

import pytest

from kairos_defense.live.loop import result_name
from kairos_defense.live.precompute import fingerprint, precompute
from kairos_defense.store.live_cache import FileResultCache
from tests.conftest import make_loop

pytestmark = pytest.mark.slow


def _strip(doc: dict) -> str:
    skip = ("elapsed_ms", "timings", "cached")
    return json.dumps({k: v for k, v in doc.items() if k not in skip}, sort_keys=True)


def test_precompute_every_rerun_second_matches_recompute(live_kit, tmp_path) -> None:
    inc = live_kit.incident.incident_id
    fp = fingerprint(live_kit.store, live_kit.cfg.scoring, live_kit.cfg.app, inc)
    cache = FileResultCache(tmp_path / "live")
    loop = make_loop(live_kit, cache, fp)
    s = precompute(loop)
    assert s.computed == s.reruns == len(loop.schedule) and s.cached == 0
    assert s.features == int(live_kit.incident.duration_s)
    fresh = make_loop(live_kit)
    for r in loop.schedule:
        assert _strip(cache.get(inc, result_name(r))) == _strip(fresh.compute(r)), r
    assert precompute(make_loop(live_kit, cache, fp)).computed == 0
