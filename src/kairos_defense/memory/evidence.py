"""Evidence packages (SPEC §15.7, D-099): an approved export with an Ed25519-signed manifest, and
its verification.

``export_evidence`` refuses to run without ``approve=True`` (rule 8: the UI confirm or the CLI's
``--approve``) and then writes nothing and appends nothing. With approval it writes
``<out_root>/<case_id>_<yyyymmddThhmmss>/`` (UTC of the export clock; ``-2``, ``-3`` … if taken):

- ``case.json``: the snapshot at the export clock, every ledger row touching the case with its
  ``prev_hash`` and ``hash``, the chain head, the whole ledger's verification result and the
  model versions;
- ``case.html``: the self-contained summary with the static map (``evidence_html``);
- ``pubkey.pem``: the Ed25519 public key; ``manifest.json``: the sha256 of those three files;
- ``manifest.sig``: base64 Ed25519 signature of the exact ``manifest.json`` bytes.

Then it appends ``evidence_exported``, so a package records the head before its own export event.
The signing key comes from the OS CSPRNG (never the seeded generator: a key derived from a public
seed would be forgeable); content hashes stay deterministic.
"""

from __future__ import annotations

import base64
import itertools
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from kairos_defense.memory.asof import snapshot, touching_rows
from kairos_defense.memory.canonical import iso_z, normalize, row_hash, sha256_bytes
from kairos_defense.memory.evidence_html import render_html, static_map_png
from kairos_defense.memory.ledger import known_at, verify_rows
from kairos_defense.memory.views import describe, obj
from kairos_defense.ports import CaseMemory, TrackStore

FORMAT = "kairos-evidence/1"
SIGNED_FILES = ("case.json", "case.html", "pubkey.pem")
MANIFEST, SIGNATURE = "manifest.json", "manifest.sig"


class ApprovalRequired(PermissionError):
    """Exports need an explicit human approval (rule 8)."""


class EvidenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExportResult:
    path: Path
    manifest_sha256: str
    seq: int  # the evidence_exported row
    head_seq: int  # the chain head the package records
    signed: bool


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # PASS | FAIL | SKIP
    detail: str


class Signer:
    """An Ed25519 private key that signs manifests."""

    def __init__(self, key: Ed25519PrivateKey) -> None:
        self.key = key

    def sign(self, data: bytes) -> bytes:
        return self.key.sign(data)

    def public_pem(self) -> bytes:
        return self.key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )


def load_or_create_key(path: Path | str) -> Ed25519PrivateKey:
    """The PKCS8 PEM key at ``path``; created on first use (mode 0600) from the OS CSPRNG."""
    p = Path(path)
    if p.exists():
        key = serialization.load_pem_private_key(p.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise EvidenceError(f"{p} is not an Ed25519 key")
        return key
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())  # fmt: skip
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    return key


def signer_for(app) -> Signer | None:
    """The configured signer, or None when ``signing.enabled`` is false."""
    return Signer(load_or_create_key(app.signing.key_path)) if app.signing.enabled else None


def fingerprint(pem: bytes) -> str:
    """SHA-256 of the raw 32-byte public key, first 16 hex digits."""
    key = serialization.load_pem_public_key(pem)
    raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return sha256_bytes(raw)[:16]


def package_dir(out_root: Path | str, case_id: str, clock: datetime) -> Path:
    base = Path(out_root) / f"{case_id}_{clock:%Y%m%dT%H%M%S}"
    p, n = base, 1
    while p.exists():
        n += 1
        p = base.with_name(f"{base.name}-{n}")
    return p


def case_document(rows: list[dict], case_id: str, clock: datetime, approved_by: str) -> dict:
    """The ``case.json`` content (JSON-ready, canonical values)."""
    known = known_at(rows, clock)
    snap = snapshot(known, case_id, clock)
    if not snap.exists:
        raise EvidenceError(f"no case {case_id} as of {iso_z(clock)}")
    touching = touching_rows(known, case_id, snap.members)
    head = known[-1]
    broken = verify_rows(rows)
    versions = {obj(r).get("version") for r in known if r["event_type"] == "model_registered"}
    versions |= {obj(r).get("model_version") for r in touching
                 if r["event_type"] == "match_proposed"}  # fmt: skip
    models = sorted(v for v in versions if v)
    return normalize({
        "format": FORMAT, "case_id": case_id, "created_at": clock, "approved_by": approved_by,
        "snapshot": snap.to_dict(), "rows": touching,
        "timeline": [{"seq": r["seq"], "recorded_at": r["recorded_at"], "actor": r["actor"],
                      "event_type": r["event_type"], "summary": describe(r)} for r in touching],
        "head": {"seq": head["seq"], "hash": head["hash"], "recorded_at": head["recorded_at"]},
        "verification": {"intact": broken is None, "first_broken_seq": broken,
                         "rows": len(rows)},
        "models": models,
    })  # fmt: skip


def _json_bytes(doc: Mapping) -> bytes:
    return (json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()


def export_evidence(memory: CaseMemory, case_id: str, *, approve: bool, approved_by: str,
                    clock: datetime, out_root: Path | str, signer: Signer | None,
                    store: TrackStore | None = None,
                    progress: Callable[[dict], None] | None = None) -> ExportResult:  # fmt: skip
    """Write the package for ``case_id`` as known at ``clock`` and append ``evidence_exported``.
    ``progress`` (the API's streamed export, D-108) is called after each file is written and
    hashed with ``{"name", "bytes", "sha256", "i", "n"}``."""
    if not approve:
        raise ApprovalRequired("an evidence export needs explicit approval (rule 8): pass "
                               "--approve or confirm in the UI")  # fmt: skip
    rows = memory.events()
    doc = case_document(rows, case_id, clock, approved_by)
    png = static_map_png(store, doc["snapshot"]["members"]) if store is not None else None
    folder = package_dir(out_root, case_id, clock)
    folder.mkdir(parents=True)
    files = {"case.json": _json_bytes(doc), "case.html": render_html(doc, png).encode()}
    if signer is not None:
        files["pubkey.pem"] = signer.public_pem()
    n = len(files) + 1 + (signer is not None)
    done = itertools.count(1)

    def wrote(name: str, data: bytes) -> str:
        (folder / name).write_bytes(data)
        digest = sha256_bytes(data)
        if progress is not None:
            progress({"name": name, "bytes": len(data), "sha256": digest, "i": next(done),
                      "n": n})  # fmt: skip
        return digest

    hashes = {name: wrote(name, data) for name, data in files.items()}
    manifest = {
        "format": FORMAT,
        "case_id": case_id,
        "created_at": doc["created_at"],
        "algorithm": "sha256",
        "files": hashes,
    }
    mbytes = _json_bytes(manifest)
    msha = wrote(MANIFEST, mbytes)
    if signer is not None:
        wrote(SIGNATURE, base64.b64encode(signer.sign(mbytes)) + b"\n")
    seq = memory.append({
        "event_type": "evidence_exported", "actor": "system", "recorded_at": clock,
        "case_id": case_id, "subject_id": doc["snapshot"]["founder"],
        "object_json": {"manifest_sha256": msha, "path": folder.as_posix(),
                        "approved_by": approved_by}})  # fmt: skip
    return ExportResult(folder, msha, seq, doc["head"]["seq"], signer is not None)


# --- verification ------------------------------------------------------------------------------
def _files_check(d: Path, manifest: Mapping) -> Check:
    listed = manifest.get("files", {})
    bad = [n for n, h in listed.items()
           if not (d / n).is_file() or sha256_bytes((d / n).read_bytes()) != h]  # fmt: skip
    extra = sorted(p.name for p in d.iterdir()
                   if p.name not in listed and p.name not in (MANIFEST, SIGNATURE))  # fmt: skip
    if bad or extra:
        why = [f"{n}: missing or hash differs" for n in bad] + [f"{n}: not in the manifest"
                                                                for n in extra]  # fmt: skip
        return Check("files", "FAIL", "; ".join(why))
    return Check("files", "PASS", f"{len(listed)} files match the manifest: {', '.join(listed)}")


def _signature_check(d: Path, mbytes: bytes, pinned: bytes | None) -> Check:
    if not (d / SIGNATURE).is_file() or not (d / "pubkey.pem").is_file():
        return Check("signature", "FAIL", "manifest.sig or pubkey.pem missing (unsigned package)")
    pem = (d / "pubkey.pem").read_bytes()
    try:
        key = serialization.load_pem_public_key(pem)
        if not isinstance(key, Ed25519PublicKey):
            return Check("signature", "FAIL", "pubkey.pem is not an Ed25519 key")
        key.verify(base64.b64decode((d / SIGNATURE).read_bytes().strip(), validate=True), mbytes)
    except (InvalidSignature, ValueError) as exc:
        return Check("signature", "FAIL", f"Ed25519 signature does not verify ({exc or 'bad'})")
    fp = fingerprint(pem)
    if pinned is not None and fingerprint(pinned) != fp:
        return Check("signature", "FAIL", f"key {fp} is not the pinned key {fingerprint(pinned)}")
    return Check("signature", "PASS", f"Ed25519 over manifest.json, key {fp}"
                 + (" (pinned)" if pinned is not None else ""))  # fmt: skip


def _chain_check(doc: Mapping) -> Check:
    rows, head = doc.get("rows", []), doc.get("head", {})
    for r in rows:
        if row_hash(r["prev_hash"], r) != r["hash"]:
            return Check("chain", "FAIL", f"row {r['seq']} does not recompute to its hash")
    for a, b in itertools.pairwise(rows):
        if b["seq"] <= a["seq"] or (b["seq"] == a["seq"] + 1 and b["prev_hash"] != a["hash"]):
            return Check("chain", "FAIL", f"rows {a['seq']} and {b['seq']} do not link")
    by_seq = {r["seq"]: r for r in rows}
    if rows and head.get("seq", 0) < rows[-1]["seq"]:
        return Check("chain", "FAIL", "the head is older than the rows")
    if head.get("seq") in by_seq and by_seq[head["seq"]]["hash"] != head.get("hash"):
        return Check("chain", "FAIL", "the head hash differs from its row")
    return Check("chain", "PASS", f"{len(rows)} rows recompute and link; head seq "
                 f"{head.get('seq')}")  # fmt: skip


def _ledger_check(doc: Mapping, ledger: CaseMemory) -> Check:
    rows = {r["seq"]: r for r in ledger.events()}
    broken = verify_rows(rows.values())
    if broken is not None:
        return Check("ledger", "FAIL", f"the ledger's chain is broken at seq {broken}")
    head = doc.get("head", {})
    h = rows.get(head.get("seq"))
    if h is None or h["hash"] != head.get("hash"):
        return Check("ledger", "FAIL", f"the ledger has no row {head.get('seq')} with the "
                     "package's head hash (rows removed or rewritten)")  # fmt: skip
    for r in doc.get("rows", []):
        got = rows.get(r["seq"])
        if got is None or normalize(got) != r:
            return Check("ledger", "FAIL", f"row {r['seq']} differs from the ledger")
    return Check("ledger", "PASS", f"{len(doc.get('rows', []))} rows equal the ledger's; chain "
                 f"intact over {len(rows):,} rows")  # fmt: skip


def verify_evidence(folder: Path | str, ledger: CaseMemory | None = None,
                    pubkey_pem: bytes | None = None,
                    ledger_note: str = "no ledger given") -> list[Check]:  # fmt: skip
    """One row per check (files, signature, chain, ledger). ``ledger`` None gives a SKIP row
    with ``ledger_note`` (missing, or locked by another process)."""
    d = Path(folder)
    if not (d / MANIFEST).is_file():
        return [Check("manifest", "FAIL", f"no {MANIFEST} in {d}")]
    mbytes = (d / MANIFEST).read_bytes()
    try:
        manifest = json.loads(mbytes)
    except ValueError:
        return [Check("manifest", "FAIL", f"{MANIFEST} is not JSON")]
    checks = [_files_check(d, manifest), _signature_check(d, mbytes, pubkey_pem)]
    try:
        doc = json.loads((d / "case.json").read_bytes())
    except (OSError, ValueError):
        return [*checks, Check("chain", "FAIL", "case.json is missing or not JSON")]
    checks.append(_chain_check(doc))
    checks.append(Check("ledger", "SKIP", ledger_note) if ledger is None
                  else _ledger_check(doc, ledger))  # fmt: skip
    return checks


def passed(checks: list[Check]) -> bool:
    return not any(c.status == "FAIL" for c in checks)
