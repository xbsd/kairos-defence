# kairos_defense.api

The FastAPI backend (SPEC §16): REST endpoints, the replay WebSocket and the built web app on one
origin.

## Responsibilities

- Compose the adapters once (`services.py`, the composition root, rule 6): the read-only main
  store, LanceDB, the matcher and recall (when models and indexes exist), the live sink, the result
  cache and the broadcasting ledger (D-104, D-110).
- Serve every §16.4 route plus `/api/health`, `/api/ledger/tail` and `/api/ledger/{seq}`
  (`routes.py`, `routes_memory.py`, D-108).
- Stream `/ws/replay/{incident_id}` (`stream.py`, §16.3, D-107).
- Define the message and REST models (`schemas.py`, §16.5): `StreamMessage`, `ClientMessage`.
- Serve `web/dist` with a client-route fallback (`static.py`, D-112).

## Public API

- `app.create_app(cfg=None, *, static_dir=None, memory_path=None, live_path=None, reseed=False)`:
  `cfg=None` builds a schema-only app (`--dump-openapi`). `app.factory()` for `uvicorn --reload`
  (`KD_CONFIG`, `KD_STATIC`, `KD_MEMORY`, `KD_LIVE_DB`).
- `services.Services(cfg, *, memory_path=None, live_path=None, reseed=False)`: `incident(id)`,
  `loop(id)`, `session(id)`, `reset_live()`, `reseed()`, `health()`, `close()`; raises
  `ServiceError` with the fix when data is missing or a file is locked.
- `schemas.StreamMessage` (13 types), `schemas.MESSAGE_MODELS`, `schemas.ClientMessage`, and the
  REST models (`Scene`, `MatchResponse`, `LedgerBlock`, `LedgerRecord`, `LinkRequest`,
  `EvidenceLine` …).
- `stream.encode(msg, validate=False) -> str` (NaN-free JSON).
- Routes (all JSON unless noted):
  - `GET /api/health`, `/api/installations`, `/api/installations/{id}/scene`,
    `/api/incidents?status=live|history&limit=`, `/api/match/{incident}?at=`,
    `/api/dtw/{incident}/{match_track}?at=&channel=`, `/api/history/{track}?frame=target|region`,
    `/api/eval/latest`, `/api/schema/stream`.
  - `GET /api/cases/{case}?as_of=`, `/api/cases/{case}/diff?t1=&t2=`,
    `/api/cases/{case}/graph?as_of=`, `/api/ledger/verify`, `/api/ledger/tail?n=`,
    `/api/ledger/{seq}`, `/api/delta?since=&until=&installation=`.
  - `POST /api/cases/{case}/links` (`LinkRequest`), `POST /api/cases/{case}/evidence`
    (`{"approve": true}`; NDJSON `file` lines then `done`), `POST /api/admin/reset`,
    `POST /api/admin/reseed`.
  - `WS /ws/replay/{incident}`.

## Data in and out

Reads the main database read-only, LanceDB, `models/`, `reports/eval_*.json`; writes
`data/live.duckdb`, `data/memory.duckdb` (appends only), `data/cache/live/`, `exports/`.

## How it works

The lifespan builds `Services` on startup. REST handlers are sync (thread pool) and hold the store
lock for reads. The WebSocket accepts, sends `hello`, then every 100 ms applies the client messages
that arrived and runs `Session.step` in the thread pool, sending what it returns. Ledger appends
from any route are published to every open session as `ledger` messages. `POST /api/admin/reseed`
closes the ledger under the locks, rebuilds it with `store.ledger_duck.reseed_ledger` and reopens
it (D-010). Times in queries and bodies need `Z` or an offset (422 otherwise).

## Configuration

`config/app.yaml` paths (`duckdb`, `memory`, `live`, `lancedb`, `models`, `reports`, `exports`,
`cache`, `signing`), `replay.default_speed`; `config/scoring.yaml` (`live`, the matcher's keys).

## Tests

`tests/unit/test_api_rest.py`, `test_api_ws.py` (real WebSocket through `TestClient`, validated
messages), `test_api_static.py`, `test_api_contract.py` (one example of every message type; the
union is exactly §16.3; `web/openapi.json` is current). Fixture `api` in `tests/conftest.py`
(module scope; tests that write call `POST /api/admin/reseed`). `KD_VALIDATE_STREAM=1` validates
every outgoing message against `StreamMessage`.

## Gotchas

- After changing `schemas.py`: `uv run kairos-defense api --dump-openapi web/openapi.json && npm
  --prefix web run gen:types` (the contract test and `npm run check:types` fail otherwise).
- A process holding the main database read-write (`make index`) stops the API from starting.
- The server binds 127.0.0.1 and has no authentication (§2: not in v1).
- Lock order: the store lock before the memory lock.

## Changelog

- Phase 7: package created.
