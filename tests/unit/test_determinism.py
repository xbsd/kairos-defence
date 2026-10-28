"""Determinism (SPEC §8.9, CLAUDE.md rule 4): same seed ⇒ identical tables; actors independent."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from kairos_defense.sim.actors import schedule
from kairos_defense.sim.generate import generate, simulate
from kairos_defense.sim.writers import table_hashes, write_all
from tests.conftest import WINDOW


def _app(cfg, folder: Path):
    paths = cfg.app.paths.model_copy(
        update={
            "duckdb": folder / "kd.duckdb",
            "truth": folder / "gt.duckdb",
            "memory": folder / "mem.duckdb",
        }
    )
    return cfg.app.model_copy(update={"paths": paths})


def _write_and_hash(cfg, g, folder: Path) -> tuple[dict, dict]:
    app = _app(cfg, folder)
    write_all(app, g.tables, g.truth)
    return table_hashes(app.paths.duckdb), table_hashes(app.paths.truth)


def test_two_runs_give_identical_table_hashes(cfg, tmp_path_factory, g42) -> None:
    run_a = _write_and_hash(cfg, g42, tmp_path_factory.mktemp("a"))
    run_b = _write_and_hash(cfg, generate(cfg, 42, window=WINDOW), tmp_path_factory.mktemp("b"))
    assert run_a == run_b
    raw, truth = run_a
    assert len(raw) == 15 and len(truth) == 4
    assert len(g42.tables["incidents"]) > 50


def test_a_different_seed_gives_different_data(cfg, g42) -> None:
    short = (WINDOW[1], WINDOW[1])
    a = generate(cfg, 42, window=short)
    b = generate(cfg, 43, window=short)
    for t in ("track_points", "weather", "assets"):
        assert not a.tables[t].equals(b.tables[t]), t
    assert not a.truth["true_paths"].equals(b.truth["true_paths"])


def test_window_holds_the_live_flight(g42) -> None:
    inc = g42.tables["incidents"].set_index("incident_id")
    assert inc.loc["DEMO-BRAVO-0828"].status == "live"
    assert (inc.status == "live").sum() == 1
    assert g42.live is not None


def test_adding_an_actor_changes_no_other_flight(cfg, world, cal) -> None:
    probers = list(cfg.actors.probers)
    p7 = next(p for p in probers if p.id == "P2").model_copy(update={"id": "P7"})
    more = cfg.model_copy(
        update={"actors": cfg.actors.model_copy(update={"probers": [*probers, p7]})}
    )
    before = {p.key: p for p in schedule(cfg, world, cal, 42)}
    after = {p.key: p for p in schedule(more, world, cal, 42)}
    added = set(after) - set(before)
    assert added and all(k.startswith("P7/") for k in added)
    assert set(before) <= set(after)
    for k, p in before.items():
        assert p.as_dict() == after[k].as_dict(), k
    # flown together with the new actor's flights, the others' paths and radar hits are unchanged
    keys = [k for k in before if before[k].night >= WINDOW[0]][:24]
    alone = simulate([before[k] for k in keys], world, cal, 42)
    mixed_plans = [after[k] for k in keys] + [after[k] for k in sorted(added)[:3]]
    mixed = simulate(mixed_plans, world, cal, 42)
    for a, b in zip(alone, mixed, strict=False):
        np.testing.assert_allclose(a.path.xyz, b.path.xyz, rtol=0, atol=1e-9)
        np.testing.assert_array_equal(a.hits.t_s, b.hits.t_s)
        np.testing.assert_allclose(a.hits.xyz, b.hits.xyz, rtol=0, atol=1e-9)
