"""Live mode on the full data (D-183): ``live check`` flies a returning prober through the real
API and simulator process at speed 50, scores it, and leaves no live rows behind."""

from __future__ import annotations

from pathlib import Path

import pytest

from kairos_defense.config import load_config
from kairos_defense.eval.live_check import run_live_check
from kairos_defense.store.live_feed import DuckFeedStore

pytestmark = pytest.mark.slow


def test_live_check_flies_and_scores_a_returning_prober(root: Path) -> None:
    cfg = load_config(root / "config")
    if not Path(cfg.app.paths.duckdb).exists():
        pytest.fail("no data: run `make data index models` first")
    lines: list[str] = []
    code = run_live_check(cfg, root / "config", ["returning-prober"], 50.0, 900.0, lines.append)
    assert code in (0, 1), lines  # 2 would be a crash or a timeout
    assert lines[0].startswith(("PASS returning-prober:", "GAP returning-prober:"))
    assert "seed 1101" in lines[0]
    with DuckFeedStore(Path(cfg.app.paths.cache) / "live_check" / "live_mode", cfg.app) as f:
        assert all(v == 0 for v in f.counts().values())  # reset at the end
