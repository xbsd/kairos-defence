"""SPEC §17.9 Evidence page, D-136: the package list and ``POST /api/evidence/verify``."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

CASE = "CASE-P1-DELTA-260419"


def _ok(r, code: int = 200):
    assert r.status_code == code, r.text
    return r.json()


@pytest.fixture(scope="module")
def exported(api) -> dict:
    """One package exported through the API (an explicit approval, rule 8)."""
    _ok(api.post("/api/admin/reseed"))
    r = api.post(f"/api/cases/{CASE}/evidence", json={"approve": True, "analyst": "demo"})
    done = json.loads(r.text.splitlines()[-1])
    assert done["type"] == "done" and done["passed"], done
    return done


def test_evidence_list_after_export(api, exported) -> None:
    pkgs = _ok(api.get("/api/evidence"))
    name = Path(exported["dir"]).name
    p = next(p for p in pkgs if p["dir"] == name)
    assert p["case_id"] == CASE and p["signed"] is True
    assert p["manifest_sha256"] == exported["manifest_sha256"]
    assert {"case.json", "case.html", "manifest.json", "manifest.sig", "pubkey.pem"} <= set(
        p["files"]
    )
    assert p["created_at"]
    assert _ok(api.get(f"/api/evidence?case={CASE}")) == [p]
    assert _ok(api.get("/api/evidence?case=CASE-NOPE")) == []


def test_evidence_verify_passes_then_fails_after_one_byte(api, exported) -> None:
    name = Path(exported["dir"]).name
    v = _ok(api.post("/api/evidence/verify", json={"dir": name}))
    assert v["passed"] is True and v["dir"] == name
    assert {c["name"]: c["status"] for c in v["checks"]} == {
        "files": "PASS", "signature": "PASS", "chain": "PASS", "ledger": "PASS"}  # fmt: skip
    html = Path(api.cfg.app.paths.exports) / name / "case.html"
    raw = bytearray(html.read_bytes())
    raw[100] ^= 1
    html.write_bytes(bytes(raw))
    bad = _ok(api.post("/api/evidence/verify", json={"dir": name}))
    assert bad["passed"] is False
    assert {c["name"]: c["status"] for c in bad["checks"]}["files"] == "FAIL"
    raw[100] ^= 1
    html.write_bytes(bytes(raw))  # restore for the other tests


def test_evidence_verify_refuses_a_path_outside_exports(api, exported, tmp_path) -> None:
    root = Path(api.cfg.app.paths.exports)
    for bad in ("..", "../memory.duckdb", "../../etc", str(tmp_path), "/etc", ""):
        r = api.post("/api/evidence/verify", json={"dir": bad})
        assert r.status_code == 400, (bad, r.text)
    outside = tmp_path / "pkg"
    outside.mkdir()
    link = root / "escape"
    os.symlink(outside, link)
    try:
        assert api.post("/api/evidence/verify", json={"dir": "escape"}).status_code == 400
    finally:
        link.unlink()
    assert api.post("/api/evidence/verify", json={"dir": "NOPE_1"}).status_code == 404
