from __future__ import annotations

import numpy as np

from kairos_defense.rng import rng_for, stable_int


def test_stable_int_is_pinned() -> None:
    # SHA-256 based, so identical on every platform and Python version
    assert stable_int("P1") == 11004096568002865915
    assert stable_int("") == 1449310910991872227


def test_same_names_same_draws() -> None:
    a = rng_for(42, "P2", "flight", "7").random(1000)
    b = rng_for(42, "P2", "flight", "7").random(1000)
    np.testing.assert_array_equal(a, b)


def test_draws_are_pinned() -> None:
    got = rng_for(42, "P2", "flight", "7").random(3)
    np.testing.assert_allclose(
        got, [0.9197345389084182, 0.5171690047090051, 0.5274379616724056], rtol=0, atol=0
    )


def test_different_names_different_draws() -> None:
    base = rng_for(42, "P2", "flight", "7").random(8)
    for other in [("P2", "flight", "8"), ("P3", "flight", "7"), ("P2", "flight"), ("P2",)]:
        assert not np.array_equal(base, rng_for(42, *other).random(8)), other


def test_name_order_and_seed_matter() -> None:
    a = rng_for(42, "P2", "flight").random(8)
    assert not np.array_equal(a, rng_for(42, "flight", "P2").random(8))
    assert not np.array_equal(a, rng_for(43, "P2", "flight").random(8))


def test_adding_a_component_leaves_others_unchanged() -> None:
    before = rng_for(42, "P1", "flight", "0").random(16)
    _ = [rng_for(42, "NEW", str(i)).random(100) for i in range(5)]  # a new actor's streams
    np.testing.assert_array_equal(before, rng_for(42, "P1", "flight", "0").random(16))
