"""Stable per-component random streams (SPEC §8.9, CLAUDE.md rule 4).

Every random draw in the project comes from a ``numpy.random.Generator`` made here and passed in
explicitly. A stream depends only on the global seed and the component names, so adding an actor
never changes another actor's draws.
"""

from __future__ import annotations

import hashlib

import numpy as np


def stable_int(name: str) -> int:
    """First 8 bytes of SHA-256(name), little-endian: stable across runs and platforms."""
    return int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "little")


def rng_for(seed: int, *names: str) -> np.random.Generator:
    """Independent stream per component, e.g. rng_for(42, "P2", "flight", "7")."""
    return np.random.default_rng(
        np.random.SeedSequence(seed, spawn_key=tuple(stable_int(n) for n in names))
    )
