"""Full-size case memory (SPEC §15): the 18-month seed, the terminal demo with the shipped model,
and an evidence round trip with the static map. Run with ``make test-all``.

The data is regenerated at seed 42 (identical to ``make data``) and indexed in a temporary
folder; the matcher uses the committed ``models/`` (the model ``make models`` trained), so nothing
here retrains or touches ``data/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from typer.testing import CliRunner

import kairos_defense.cli as cli
from kairos_defense.cli import app
from kairos_defense.features.build import build_index
from kairos_defense.memory.evidence import Signer, export_evidence, verify_evidence
from kairos_defense.memory.seed import seed
from kairos_defense.sim.generate import generate
from kairos_defense.sim.writers import write_all
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.ledger_duck import DuckCaseMemory
from tests.conftest import ROOT, tmp_config, with_models
from tests.unit.memory_kit import local

pytestmark = pytest.mark.slow

CASE = "CASE-P1-DELTA-260419"
DELTA = "P1-DELTA-260419"
ROWS = 4_681  # 1,866 incidents + 949 reports + 1,864 assessments + case + decision (D-096)


@pytest.fixture(scope="module")
def full(cfg, tmp_path_factory):
    c = with_models(tmp_config(cfg, tmp_path_factory.mktemp("full_memory")), ROOT / "models")
    g = generate(cfg, 42)
    write_all(c.app, g.tables, g.truth)
    build_index(c)
    with DuckTrackStore(c.app.paths.duckdb, c.app) as store, DuckCaseMemory(
        c.app.paths.memory, c.app) as mem:  # fmt: skip
        summary = seed(mem, store, c.scenario)
    return c, summary


def test_full_seed_counts_and_delta_case(full) -> None:
    c, s = full
    assert s.rows == ROWS and s.head_seq == ROWS
    assert s.counts == {"incident_recorded": 1_866, "report_recorded": 949,
                        "assessment_asserted": 1_864, "case_opened": 1,
                        "decision_recorded": 1}  # fmt: skip
    with DuckCaseMemory(c.app.paths.memory, c.app, read_only=True) as mem:
        assert mem.verify_chain() is None
        snap = mem.as_of(CASE, local(2026, 4, 20, 10, 0))
    assert snap.status == "closed" and [x["value"] for x in snap.claims] == ["hobbyist"]
    assert snap.links == [] and snap.members == [DELTA] and snap.pending == []


def test_full_demo_known_then_now(full, tmp_path, monkeypatch) -> None:
    c, s = full
    scratch = tmp_path / "demo.duckdb"
    monkeypatch.setattr(cli, "_load_config", lambda _c: c)
    res = CliRunner().invoke(app, ["memory", "demo", "--approve", "--scratch", str(scratch)],
                             terminal_width=250)  # fmt: skip
    assert res.exit_code == 0, res.output
    assert "known then" in res.output and "known now" in res.output
    with DuckCaseMemory(scratch, c.app, read_only=True) as m:
        proposed = [r["subject_id"] for r in m.events() if r["event_type"] == "match_proposed"]
        now = m.as_of(CASE, m.head().recorded_at)
        then = m.as_of(CASE, local(2026, 4, 20, 9, 10))
    assert proposed[:2] == [DELTA, "P1-ALPHA-260303"] and len(proposed) == 3  # shipped model
    assert set(now.members) == {DELTA, *proposed} and now.pending == []
    assert then.members == [DELTA] and then.status == "closed"
    with DuckCaseMemory(c.app.paths.memory, c.app, read_only=True) as mem:
        assert mem.head().seq == s.head_seq  # the real ledger is untouched


def test_full_evidence_roundtrip(full, tmp_path) -> None:
    c, _ = full
    copy = tmp_path / "copy.duckdb"
    key = Signer(Ed25519PrivateKey.from_private_bytes(b"\x03" * 32))
    with DuckTrackStore(c.app.paths.duckdb, c.app) as store, DuckCaseMemory(copy, c.app) as mem:
        mem.copy_from(c.app.paths.memory)
        res = export_evidence(mem, CASE, approve=True, approved_by="analyst:test",
                              clock=mem.head().recorded_at, out_root=tmp_path / "exports",
                              signer=key, store=store)  # fmt: skip
        assert all(x.status == "PASS" for x in verify_evidence(res.path, mem))
        page = (res.path / "case.html").read_text()
        assert page.count("data:image/png;base64,") == 1 and "white pickup" in page
        doc = json.loads((res.path / "case.json").read_text())
        assert doc["verification"]["intact"] and doc["head"]["seq"] == ROWS
        Path(res.path / "case.json").write_text(json.dumps(doc).replace("hobbyist", "probing"))
        checks = {x.name: x.status for x in verify_evidence(res.path, mem)}
    assert checks["files"] == "FAIL" and checks["ledger"] == "FAIL"
