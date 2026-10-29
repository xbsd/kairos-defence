"""Phase 10 documentation tests (docs/phases/PHASE_10.md, D-164): every relative link, image and
in-page anchor in the four user-facing documents resolves; every `kairos-defense` command is
documented in the user guide; the guide's screenshots are real, distinct PNGs at a reviewed size,
each written by `web/e2e/guide.spec.ts` (so `make e2e` regenerates every one of them)."""

from __future__ import annotations

import hashlib
import re
import struct
from pathlib import Path

import pytest
import typer

from kairos_defense.cli import app

DOCS = ("README.md", "docs/USER_GUIDE.md", "docs/ONE_PAGER.md", "docs/ROLLBACK.md")
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")  # as scripts/check_docs.py
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
SIZES = {(1920, 1080), (1440, 900)}
SNAP = re.compile(r'snap\(page, "([a-z0-9-]+)"')


def links(doc: Path, pattern: re.Pattern = LINK) -> list[str]:
    return pattern.findall(doc.read_text(encoding="utf-8"))


def local(doc: Path, target: str) -> Path | None:
    """The file a relative link points at (None for URLs and in-page anchors)."""
    if re.match(r"^[a-z]+:", target) or target.startswith("#"):
        return None
    return (doc.parent / target.split("#", 1)[0]).resolve()


def slug(heading: str) -> str:
    """GitHub's anchor for a Markdown heading: lower case, punctuation dropped, spaces to dashes."""
    s = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return s.replace(" ", "-")


def anchors(doc: Path) -> set[str]:
    text = re.sub(r"```.*?```", "", doc.read_text(encoding="utf-8"), flags=re.S)
    return {slug(m) for m in re.findall(r"^#{1,6} (.+)$", text, flags=re.M)}


@pytest.mark.parametrize("name", DOCS)
def test_every_relative_link_and_image_resolves(root: Path, name: str) -> None:
    doc = root / name
    assert doc.exists(), f"{name} is missing"
    targets = links(doc)
    assert targets, f"{name} has no link"
    missing = []
    for t in targets:
        path = local(doc, t)
        if path is not None and not path.exists():
            missing.append(t)
        if "#" in t and not re.match(r"^[a-z]+:", t):
            target_doc = doc if t.startswith("#") else path
            if (
                target_doc is not None
                and target_doc.suffix == ".md"
                and target_doc.exists()
                and t.split("#", 1)[1] not in anchors(target_doc)
            ):
                missing.append(t)
    assert missing == [], f"{name} has broken links or anchors: {missing}"


def cli_commands() -> list[str]:
    """Every command of the Typer app; a group's subcommands as `<group> <name>` (any depth)."""
    out: list[str] = []

    def walk(group, prefix: str) -> None:
        for name, cmd in sorted(group.commands.items()):
            out.append(f"{prefix}{name}")
            if getattr(cmd, "commands", None):
                walk(cmd, f"{prefix}{name} ")

    walk(typer.main.get_command(app), "")
    return out


def test_every_cli_command_is_documented_in_the_user_guide(root: Path) -> None:
    guide = (root / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")
    commands = cli_commands()
    assert {"gen", "index", "swarm", "mcp", "memory verify"} <= set(commands)
    missing = [c for c in commands if f"kairos-defense {c}" not in guide]
    assert missing == [], f"commands not documented in docs/USER_GUIDE.md: {missing}"


def png_size(data: bytes) -> tuple[int, int]:
    return struct.unpack(">II", data[16:24])  # IHDR width, height


def test_guide_images_are_real_distinct_pngs_from_the_guide_spec(root: Path) -> None:
    guide = root / "docs" / "USER_GUIDE.md"
    images = [local(guide, t) for t in links(guide, IMAGE)]
    assert len(images) >= 10
    written = set(SNAP.findall((root / "web" / "e2e" / "guide.spec.ts").read_text()))
    hashes: dict[str, Path] = {}
    for img in images:
        assert img is not None and img.parent == root / "docs" / "guide" / "img", img
        assert img.stem in written, f"{img.name} is not written by web/e2e/guide.spec.ts"
        data = img.read_bytes()
        assert data.startswith(PNG_MAGIC), f"{img.name} is not a PNG"
        assert len(data) >= 20_000, f"{img.name} is only {len(data)} bytes"
        assert png_size(data) in SIZES, f"{img.name} is {png_size(data)}"
        h = hashlib.sha256(data).hexdigest()
        assert hashes.get(h, img) == img, f"{img.name} is identical to {hashes[h].name}"
        hashes[h] = img
