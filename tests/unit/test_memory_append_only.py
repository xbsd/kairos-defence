"""CLAUDE.md rule 7 and SPEC §15.1: no source file under ``src/`` mutates ``ledger`` rows.

The scan reads every ``.py`` file (comments and docstrings included) with whitespace collapsed, so a
statement split across lines is still caught. Each pattern stays within one statement.
"""

from __future__ import annotations

import re
from pathlib import Path

MUTATIONS = re.compile(
    r"\bUPDATE\s+ledger\b"
    r"|\bDELETE\s+FROM\s+ledger\b"
    r"|\bTRUNCATE\s+(TABLE\s+)?ledger\b"
    r"|\bDROP\s+TABLE\s+(IF\s+EXISTS\s+)?ledger\b"
    r"|\bALTER\s+TABLE\s+(IF\s+EXISTS\s+)?ledger\b"
    r"|\bINSERT\s+OR\s+REPLACE\s+INTO\s+ledger\b"
    r"|\bON\s+CONFLICT\b[^;]{0,200}?\bDO\s+UPDATE\b",
    re.IGNORECASE,
)


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_no_update_or_delete_on_ledger_in_src(root: Path) -> None:
    files = sorted((root / "src" / "kairos_defense").rglob("*.py"))
    assert len(files) > 20, "scan found too few files: wrong path?"
    assert any("memory" in f.parts for f in files), "the memory package was not scanned"
    hits = [f"{f.relative_to(root)}: {m.group(0)}" for f in files
            for m in MUTATIONS.finditer(_flat(f.read_text(encoding="utf-8")))]  # fmt: skip
    assert not hits, "ledger rows must never be mutated (rule 7): " + "; ".join(hits)


def test_scan_pattern_catches_mutations() -> None:
    bad = [
        "con.execute('UPDATE ledger SET hash = 1')",
        "DELETE FROM ledger WHERE seq = 5",
        'sql = """\n  delete\n   from   ledger\n where seq=1"""',  # split across lines
        "TRUNCATE ledger",
        "DROP TABLE IF EXISTS ledger",
        "alter table ledger add column x int",
        "INSERT OR REPLACE INTO ledger VALUES (1)",
        "INSERT INTO ledger SELECT * FROM x ON CONFLICT (seq) DO UPDATE SET hash = 'x'",
    ]
    for s in bad:
        assert MUTATIONS.search(_flat(s)), s
    good = [
        "INSERT INTO ledger SELECT * FROM rows_in",
        "SELECT * FROM ledger WHERE seq = 1",
        "DROP TABLE IF EXISTS track_features; -- the ledger is append-only",
        "UPDATE the README; ledger rows are never touched",
        "CREATE TABLE IF NOT EXISTS ledger (seq BIGINT PRIMARY KEY)",
    ]
    for s in good:
        assert not MUTATIONS.search(_flat(s)), s
