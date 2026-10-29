"""SPEC §15.7 evidence packages: approval, the five files, the Ed25519 manifest signature and
verification (D-099). A fixed test key keeps the tests deterministic."""

from __future__ import annotations

import json
import re
import stat
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from kairos_defense.memory.actions import decide_link, propose_matches
from kairos_defense.memory.canonical import sha256_bytes
from kairos_defense.memory.evidence import (
    ApprovalRequired,
    Signer,
    export_evidence,
    load_or_create_key,
    package_dir,
    passed,
    signer_for,
    verify_evidence,
)
from kairos_defense.store.duck import DuckTrackStore
from kairos_defense.store.ledger_duck import DuckCaseMemory
from tests.unit.memory_kit import delta_story, local

CASE = "CASE-P1-DELTA-260419"
DELTA = "P1-DELTA-260419"
NOW = local(2026, 8, 28, 21, 42)
KEY = Signer(Ed25519PrivateKey.from_private_bytes(b"\x01" * 32))
OTHER = Signer(Ed25519PrivateKey.from_private_bytes(b"\x02" * 32))


@pytest.fixture
def mem(cfg, tmp_path):
    with DuckCaseMemory(tmp_path / "mem.duckdb", cfg.app) as m:
        m.append_many(delta_story())
        top = [{"incident_id": i, "score": s, "track_id": f"{i}-T1", "model_version": "fusion-v1",
                "reasons": ["Same RF family (FAM-07)"]}
               for i, s in ((DELTA, 0.97), ("P1-ALPHA-260303", 0.93))]  # fmt: skip
        for p in propose_matches(m, CASE, "DEMO-BRAVO-0828", top, NOW):
            decide_link(m, CASE, p, "approve", "test", NOW)
        yield m


def _export(mem, tmp_path, signer=KEY, **kw):
    return export_evidence(mem, CASE, approve=True, approved_by="analyst:test", clock=NOW,
                           out_root=tmp_path / "exports", signer=signer, **kw)  # fmt: skip


def _status(checks) -> dict[str, str]:
    return {c.name: c.status for c in checks}


def test_export_requires_approval(mem, tmp_path) -> None:
    n = mem.count()
    with pytest.raises(ApprovalRequired, match="rule 8"):
        export_evidence(mem, CASE, approve=False, approved_by="analyst:test", clock=NOW,
                        out_root=tmp_path / "exports", signer=KEY)  # fmt: skip
    assert not (tmp_path / "exports").exists() and mem.count() == n


def test_export_writes_five_files_and_appends_event(mem, tmp_path) -> None:
    head = mem.head()
    res = _export(mem, tmp_path)
    names = sorted(p.name for p in res.path.iterdir())
    assert names == ["case.html", "case.json", "manifest.json", "manifest.sig", "pubkey.pem"]
    assert res.path.name == f"{CASE}_20260829T024200" and res.signed
    row = mem.events()[-1]
    assert (row["seq"], row["event_type"], row["actor"], row["case_id"]) == (
        res.seq, "evidence_exported", "system", CASE)  # fmt: skip
    assert row["object_json"]["manifest_sha256"] == res.manifest_sha256 == sha256_bytes(
        (res.path / "manifest.json").read_bytes())  # fmt: skip
    assert row["object_json"]["approved_by"] == "analyst:test"
    assert res.head_seq == head.seq == res.seq - 1
    assert mem.as_of(CASE, NOW).exports[0]["manifest_sha256"] == res.manifest_sha256


def test_case_json_has_rows_head_verification_models(mem, tmp_path) -> None:
    res = _export(mem, tmp_path)
    doc = json.loads((res.path / "case.json").read_text())
    touching = {
        r["seq"]
        for r in mem.events()  # ALPHA-0502 is not a member
        if r["seq"] < res.seq and r["subject_id"] != "P1-ALPHA-260502"
    }
    seqs = [r["seq"] for r in doc["rows"]]
    assert set(seqs) == touching  # ALPHA-0303 is a member now: its incident row touches
    assert all(len(r["hash"]) == 64 and len(r["prev_hash"]) == 64 for r in doc["rows"])
    assert doc["head"]["seq"] == res.head_seq and doc["verification"] == {
        "intact": True, "first_broken_seq": None, "rows": res.head_seq}  # fmt: skip
    assert doc["models"] == ["fusion-v1"]
    assert doc["snapshot"]["members"] == [DELTA, "P1-ALPHA-260303"]
    assert doc["snapshot"]["status"] == "closed"


def test_html_is_self_contained(mem, tmp_path, seeded_p1, ledger_copy) -> None:
    html = (_export(mem, tmp_path).path / "case.html").read_text()
    assert "<script" not in html.lower()
    assert not re.search(r"""(src|href)\s*=\s*["']?(https?:)?//""", html, re.I)
    assert "No map" in html and "Same RF family (FAM-07)" in html and "white pickup" in html
    with DuckTrackStore(seeded_p1.cfg.app.paths.duckdb, seeded_p1.cfg.app) as store:
        t = seeded_p1.summary.cutoff + timedelta(seconds=90)
        top = [{"incident_id": i, "score": 0.9, "model_version": "test"}
               for i in ("P1-ALPHA-260303", "P1-CHARLIE-260710")]  # fmt: skip
        for p in propose_matches(ledger_copy, CASE, "DEMO-BRAVO-0828", top, t):
            decide_link(ledger_copy, CASE, p, "approve", "test", t)
        res = export_evidence(
            ledger_copy,
            CASE,
            approve=True,
            approved_by="analyst:test",
            clock=t,
            out_root=tmp_path / "p1",
            signer=KEY,
            store=store,
        )
    page = (res.path / "case.html").read_text()
    assert len(re.findall(r'src="data:image/png;base64,', page)) == 1
    assert "<script" not in page.lower() and not re.search(r"(src|href)=\"https?:", page)


def test_verify_passes(mem, tmp_path) -> None:
    res = _export(mem, tmp_path)
    checks = verify_evidence(res.path, mem, KEY.public_pem())
    assert _status(checks) == {"files": "PASS", "signature": "PASS", "chain": "PASS",
                               "ledger": "PASS"} and passed(checks)  # fmt: skip


def test_verify_fails_after_editing_one_file(mem, tmp_path) -> None:
    """SPEC §20 phase 6: evidence verify passes, then fails after editing one file."""
    res = _export(mem, tmp_path)
    assert passed(verify_evidence(res.path, mem))
    page = res.path / "case.html"
    page.write_bytes(page.read_bytes().replace(b"closed", b"clozed", 1))
    checks = verify_evidence(res.path, mem)
    files = next(c for c in checks if c.name == "files")
    assert files.status == "FAIL" and "case.html" in files.detail and not passed(checks)
    assert _status(checks)["signature"] == "PASS"  # the manifest itself is untouched


def test_verify_fails_on_missing_or_extra_file(mem, tmp_path) -> None:
    res = _export(mem, tmp_path)
    (res.path / "notes.txt").write_text("added later")
    assert "notes.txt" in next(c for c in verify_evidence(res.path) if c.name == "files").detail
    (res.path / "notes.txt").unlink()
    (res.path / "pubkey.pem").unlink()
    st = _status(verify_evidence(res.path))
    assert st["files"] == "FAIL" and st["signature"] == "FAIL"


def test_verify_fails_on_bad_signature_or_pinned_key_mismatch(mem, tmp_path) -> None:
    res = _export(mem, tmp_path)
    m = res.path / "manifest.json"
    original = m.read_bytes()
    m.write_bytes(original.replace(b"sha256", b"sha257", 1))
    assert _status(verify_evidence(res.path))["signature"] == "FAIL"
    m.write_bytes(original)
    other = _export(mem, tmp_path, signer=OTHER)
    assert _status(verify_evidence(other.path))["signature"] == "PASS"  # self-consistent ...
    pinned = verify_evidence(other.path, pubkey_pem=KEY.public_pem())
    sig = next(c for c in pinned if c.name == "signature")
    assert sig.status == "FAIL" and "pinned" in sig.detail  # ... but not the expected key


def test_verify_checks_the_ledger_when_available(mem, tmp_path) -> None:
    res = _export(mem, tmp_path)
    assert _status(verify_evidence(res.path, None, ledger_note="ledger missing"))["ledger"] == (
        "SKIP")  # fmt: skip
    mem.con.execute('UPDATE ledger SET object_json = \'{"label":"probing"}\' WHERE seq = 5')
    led = next(c for c in verify_evidence(res.path, mem) if c.name == "ledger")
    assert led.status == "FAIL" and "seq 5" in led.detail


def test_signing_key_created_once_with_0600(tmp_path, cfg) -> None:
    path = tmp_path / "keys" / "ed25519.pem"
    a = load_or_create_key(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    b = load_or_create_key(path)
    assert Signer(a).public_pem() == Signer(b).public_pem()
    app = cfg.app.model_copy(update={"signing": cfg.app.signing.model_copy(
        update={"key_path": path})})  # fmt: skip
    assert signer_for(app).public_pem() == Signer(a).public_pem()


def test_unsigned_package_fails_verification(mem, tmp_path, cfg) -> None:
    off = cfg.app.model_copy(update={"signing": cfg.app.signing.model_copy(
        update={"enabled": False})})  # fmt: skip
    assert signer_for(off) is None
    res = _export(mem, tmp_path, signer=None)
    assert not res.signed and not (res.path / "manifest.sig").exists()
    st = _status(verify_evidence(res.path))
    assert st["signature"] == "FAIL" and st["files"] == "PASS"


def test_export_folder_name_and_collision_suffix(mem, tmp_path) -> None:
    a = _export(mem, tmp_path)
    b = _export(mem, tmp_path)
    assert b.path.name == f"{a.path.name}-2"
    assert package_dir(tmp_path / "exports", CASE, NOW).name == f"{a.path.name}-3"


def test_progress_callback_reports_every_file_with_its_hash(mem, tmp_path) -> None:
    seen: list[dict] = []
    res = export_evidence(mem, CASE, approve=True, approved_by="analyst:test", clock=NOW,
                          out_root=tmp_path / "exports", signer=KEY,
                          progress=seen.append)  # fmt: skip
    assert [s["name"] for s in seen] == ["case.json", "case.html", "pubkey.pem",
                                         "manifest.json", "manifest.sig"]  # fmt: skip
    assert [s["i"] for s in seen] == [1, 2, 3, 4, 5] and {s["n"] for s in seen} == {5}
    for s in seen:
        data = (res.path / s["name"]).read_bytes()
        assert s["sha256"] == sha256_bytes(data) and s["bytes"] == len(data)
    assert seen[3]["sha256"] == res.manifest_sha256
