"""Canonical JSON and the row hash of the case-memory chain (SPEC §15.3, D-095).

``canonical_json`` is the one serialization the chain hashes:

- keys sorted, separators ``(",", ":")``, UTF-8 kept as is, ``None`` as ``null``;
- timestamps as ISO 8601 UTC with ``Z`` and always six fractional digits;
- floats rounded to 9 decimals (``-0.0`` becomes ``0.0``); NaN and infinities are refused, so
  callers map them to ``None`` first (``memory.actions.json_safe``);
- numpy scalars become Python numbers.

``row_hash(prev_hash, row) = sha256(prev_hash + canonical_json(row without prev_hash and hash))``.
``object_json`` is hashed as a parsed object, so the text DuckDB hands back never matters.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd

GENESIS = "0" * 64  # prev_hash of seq 1
HASH_FIELDS = ("prev_hash", "hash")
FLOAT_DECIMALS = 9
TS_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def utc_naive(t: datetime | pd.Timestamp | str | None) -> datetime | None:
    """A time as naive UTC, at microsecond precision. Aware times are converted; naive ones are
    taken as UTC already; ISO strings are parsed (``Z`` or an offset allowed)."""
    if t is None or t is pd.NaT or (isinstance(t, float) and math.isnan(t)):
        return None
    if isinstance(t, str):
        t = datetime.fromisoformat(t)
    if isinstance(t, pd.Timestamp):
        t = t.floor("us").to_pydatetime()
    if isinstance(t, np.datetime64):
        return utc_naive(pd.Timestamp(t))
    if not isinstance(t, datetime):
        if isinstance(t, date):
            return datetime(t.year, t.month, t.day)
        raise TypeError(f"not a time: {t!r}")
    if t.tzinfo is not None:
        t = t.astimezone(UTC).replace(tzinfo=None)
    return t


def iso_z(t: datetime | pd.Timestamp) -> str:
    """``2026-04-20T14:10:00.000000Z``."""
    return utc_naive(t).strftime(TS_FORMAT)


def round_float(x: float) -> float:
    """Round to 9 decimals; refuse NaN and infinities; ``-0.0`` becomes ``0.0``."""
    x = float(x)
    if not math.isfinite(x):
        raise ValueError(f"canonical JSON has no NaN or infinity (got {x}); map it to None first")
    r = round(x, FLOAT_DECIMALS)
    return 0.0 if r == 0 else r


def normalize(obj: object) -> object:
    """The JSON-ready form of ``obj`` that ``canonical_json`` serializes (and the ledger stores)."""
    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return round_float(obj)
    if isinstance(obj, (datetime, pd.Timestamp, np.datetime64)):
        return iso_z(utc_naive(obj))
    if isinstance(obj, Mapping):
        out = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                raise TypeError(f"canonical JSON keys must be strings, got {k!r}")
            out[k] = normalize(v)
        return out
    if isinstance(obj, (list, tuple, np.ndarray)):
        return [normalize(v) for v in obj]
    raise TypeError(f"not canonical-JSON serializable: {type(obj).__name__}")


def canonical_json(obj: object) -> str:
    """Keys sorted, compact separators, ``null`` for ``None``, normalized values (see module)."""
    return json.dumps(normalize(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)  # fmt: skip


def row_payload(row: Mapping) -> dict:
    """The hashed part of a row: every field except ``prev_hash`` and ``hash``, with
    ``object_json`` parsed if it arrives as text."""
    out = {k: v for k, v in row.items() if k not in HASH_FIELDS}
    if isinstance(out.get("object_json"), str):
        out["object_json"] = json.loads(out["object_json"])
    return out


def row_hash(prev_hash: str, row: Mapping) -> str:
    """``sha256(prev_hash + canonical_json(row_payload(row))).hexdigest()``."""
    return hashlib.sha256((prev_hash + canonical_json(row_payload(row))).encode()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
