#!/usr/bin/env python3
"""Autopilot documentation gate for phase 10 (docs/phases/PHASE_10.md). Edited by humans only.

Checks that the user guide, one-pager, rollback guide and README exist, are substantial, link only to
files that exist, and embed real, distinct PNG screenshots.

Usage: python3 scripts/check_docs.py
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
GUIDE_TERMS = (
    "Live watch", "Match explainer", "Case board", "Swarm view", "Evidence", "Shift delta",
    "Director", "kairos-defense", "make demo", "MCP", "Troubleshooting", "Glossary", "synthetic",
)  # fmt: skip
ROLLBACK_TERMS = (*(f"phase-{n:02d}-done" for n in range(4, 11)), "autopilot-start", "git revert")
README_LINKS = ("docs/USER_GUIDE.md", "docs/ONE_PAGER.md", "docs/ROLLBACK.md", "docs/DEMO.md")


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][\w'-]*", re.sub(r"```.*?```", "", text, flags=re.S)))


def local_targets(doc: Path, pattern: re.Pattern) -> list[Path]:
    out = []
    for target in pattern.findall(doc.read_text(encoding="utf-8")):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue  # URLs and in-page anchors
        out.append((doc.parent / target.split("#", 1)[0]).resolve())
    return out


def check() -> list[str]:
    problems: list[str] = []
    docs = {
        name: ROOT / name
        for name in (
            "README.md",
            "docs/USER_GUIDE.md",
            "docs/ONE_PAGER.md",
            "docs/ROLLBACK.md",
            "docs/DEMO.md",
        )
    }
    for name, path in docs.items():
        if not path.exists():
            problems.append(f"{name} is missing")
    if problems:
        return problems

    for name, path in docs.items():
        for target in local_targets(path, LINK):
            if not target.exists():
                problems.append(
                    f"{name}: broken link to {target.relative_to(ROOT) if target.is_relative_to(ROOT) else target}"
                )

    guide = docs["docs/USER_GUIDE.md"].read_text(encoding="utf-8")
    n = words(guide)
    print(f"user guide: {n} words")
    if n < 3000:
        problems.append(f"docs/USER_GUIDE.md has {n} words; a complete guide needs at least 3000")
    for term in GUIDE_TERMS:
        if term.lower() not in guide.lower():
            problems.append(f"docs/USER_GUIDE.md never mentions {term!r}")

    images = local_targets(docs["docs/USER_GUIDE.md"], IMAGE)
    print(f"user guide: {len(images)} images")
    if len(images) < 10:
        problems.append(
            f"docs/USER_GUIDE.md embeds {len(images)} images; at least 10 screenshots are needed"
        )
    hashes: dict[str, Path] = {}
    for img in images:
        if not img.exists():
            continue  # reported as a broken link above
        data = img.read_bytes()
        if not data.startswith(PNG_MAGIC):
            problems.append(f"{img.name} is not a PNG")
        if len(data) < 20_000:
            problems.append(f"{img.name} is only {len(data)} bytes; expected a real screenshot")
        h = hashlib.sha256(data).hexdigest()
        if h in hashes and hashes[h] != img:
            problems.append(f"{img.name} is identical to {hashes[h].name}")
        hashes[h] = img

    one = docs["docs/ONE_PAGER.md"].read_text(encoding="utf-8")
    n1 = words(one)
    print(f"one-pager: {n1} words")
    if not 250 <= n1 <= 700:
        problems.append(f"docs/ONE_PAGER.md has {n1} words; one page is 250 to 700")
    if not local_targets(docs["docs/ONE_PAGER.md"], IMAGE):
        problems.append("docs/ONE_PAGER.md has no screenshot")

    rollback = docs["docs/ROLLBACK.md"].read_text(encoding="utf-8")
    for term in ROLLBACK_TERMS:
        if term not in rollback:
            problems.append(f"docs/ROLLBACK.md never mentions {term!r}")

    readme = docs["README.md"].read_text(encoding="utf-8")
    for link in README_LINKS:
        if link not in readme:
            problems.append(f"README.md does not link to {link}")
    return problems


def main() -> None:
    problems = check()
    if problems:
        print("\nDocumentation incomplete:\n" + "\n".join(f"- {p}" for p in problems))
        sys.exit(1)
    print("\nDocumentation complete.")


if __name__ == "__main__":
    main()
