"""SPEC §15.3 canonical JSON and the row hash (D-095)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from kairos_defense.memory.canonical import GENESIS, canonical_json, iso_z, row_hash, utc_naive


def test_keys_sorted_and_compact_separators() -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert canonical_json({"z": {"y": [1, 2], "x": None}}) == '{"z":{"x":null,"y":[1,2]}}'


def test_timestamps_iso_utc_with_z() -> None:
    naive = datetime(2026, 4, 20, 14, 10)
    aware = datetime(2026, 4, 20, 9, 10, tzinfo=timezone(timedelta(hours=-5)))
    assert iso_z(naive) == "2026-04-20T14:10:00.000000Z"
    assert canonical_json(aware) == '"2026-04-20T14:10:00.000000Z"'
    assert canonical_json(pd.Timestamp("2026-04-20 14:10:00.123456")) == (
        '"2026-04-20T14:10:00.123456Z"'
    )
    assert canonical_json(pd.Timestamp("2026-04-20 09:10", tz="America/Bogota")) == (
        '"2026-04-20T14:10:00.000000Z"'
    )
    assert utc_naive("2026-04-20T10:00-05:00") == datetime(2026, 4, 20, 15)
    assert utc_naive("2026-04-20T15:00Z") == datetime(2026, 4, 20, 15)
    assert utc_naive(None) is None and utc_naive(pd.NaT) is None


def test_floats_rounded_to_9_decimals_and_negative_zero() -> None:
    assert canonical_json(0.1 + 0.2) == "0.3"
    assert canonical_json(-0.0) == "0.0"
    assert canonical_json(1.23456789012) == "1.23456789"
    assert canonical_json(-1e-12) == "0.0"
    assert canonical_json([1, 1.0]) == "[1,1.0]"


def test_none_is_null_and_nested_object_json_is_canonical() -> None:
    a = {"seq": 1, "object_json": {"b": [1, {"y": 2, "x": 1}], "a": None}, "case_id": None}
    b = {"case_id": None, "object_json": '{"a": null, "b": [1, {"x": 1, "y": 2}]}', "seq": 1}
    assert row_hash(GENESIS, a) == row_hash(GENESIS, b)
    assert '"a":null' in canonical_json(a)


def test_rejects_nan_and_infinity() -> None:
    for bad in (float("nan"), float("inf"), -np.inf, {"x": [np.nan]}):
        with pytest.raises(ValueError, match="NaN"):
            canonical_json(bad)
    with pytest.raises(TypeError):
        canonical_json({1: "integer key"})
    with pytest.raises(TypeError):
        canonical_json({"x": object()})


def test_numpy_scalars_and_unicode() -> None:
    v = {"f": np.float64(0.5), "i": np.int64(7), "b": np.bool_(True), "s": "é ☂",
         "arr": np.array([1, 2])}  # fmt: skip
    assert canonical_json(v) == '{"arr":[1,2],"b":true,"f":0.5,"i":7,"s":"é ☂"}'
    assert json.loads(canonical_json(v))["s"] == "é ☂"


def test_row_hash_known_answer() -> None:
    row = {"seq": 1, "recorded_at": datetime(2026, 4, 20, 14, 10), "event_type": "case_opened",
           "case_id": "CASE-P1-DELTA-260419", "subject_id": "P1-DELTA-260419",
           "object_json": {"base": "DELTA"}, "confidence": None, "actor": "generator"}  # fmt: skip
    text = ('{"actor":"generator","case_id":"CASE-P1-DELTA-260419","confidence":null,'
            '"event_type":"case_opened","object_json":{"base":"DELTA"},'
            '"recorded_at":"2026-04-20T14:10:00.000000Z","seq":1,'
            '"subject_id":"P1-DELTA-260419"}')  # fmt: skip
    assert canonical_json(row) == text
    expected = hashlib.sha256((GENESIS + text).encode()).hexdigest()
    assert row_hash(GENESIS, row) == expected
    assert expected == "3227b6bc560391fc00f34ed1c0f7feb90f03b7fc96149f421d7058b0cd254e0b"


def test_hash_ignores_prev_hash_and_hash_fields() -> None:
    row = {"seq": 2, "event_type": "x"}
    h = row_hash("a" * 64, row)
    assert row_hash("a" * 64, {**row, "prev_hash": "b" * 64, "hash": "c" * 64}) == h
    assert row_hash("b" * 64, row) != h
