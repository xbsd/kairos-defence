# kairos_defense.api

The FastAPI backend (SPEC §16): REST endpoints, the replay WebSocket and the built web app on one
origin.

## Responsibilities

- Compose the adapters once (`services.py`, the composition root, rule 6): the read-only main
  store, LanceDB, the matcher and recall (when models and indexes exist), the live sink, the result
  cache and the broadcasting ledger (D-104, D-110).
- Serve every §16.4 route plus `/api/health`, `/api/ledger/tail` and `/api/ledger/{seq}`
  (`routes.py`, `routes_memory.py`, D-108), and the phase 8 page routes: the Match explainer
  (`routes_explain.py`, D-135), the case list, decisions, the evidence list and verify (D-136).
- Stream `/ws/replay/{incident_id}` (`stream.py`, §16.3, D-107).
- Define the message and REST models (`schemas.py`, §16.5): `StreamMessage`, `ClientMessage`;
  the page models in `schemas_pages.py`.
- Serve `web/dist` with a client-route fallback (`static.py`, D-112).

## Public API

- `app.create_app(cfg=None, *, static_dir=None, memory_path=None, live_path=None, reseed=False,
  exports_path=None)`: `cfg=None` builds a schema-only app (`--dump-openapi`). `app.factory()`
  for `uvicorn --reload` (`KD_CONFIG`, `KD_STATIC`, `KD_MEMORY`, `KD_LIVE_DB`, `KD_EXPORTS`).
- `services.Services(cfg, *, memory_path=None, live_path=None, reseed=False, exports_path=None)`:
  `exports` (the evidence root, `paths.exports` unless overridden, D-137), `incident(id)`,
  `loop(id)`, `session(id)`, `reset_live()`, `reseed()`, `health()`, `close()`; raises
  `ServiceError` with the fix when data is missing or a file is locked.
- `schemas.StreamMessage` (13 types), `schemas.MESSAGE_MODELS`, `schemas.ClientMessage`, and the
  REST models (`Scene`, `MatchResponse`, `LedgerBlock`, `LedgerRecord`, `LinkRequest`,
  `EvidenceLine` …); `schemas_pages` (`ExplainResponse`, `ContributionRow`, `ExplainFlight`,
  `CaseSummary`, `DecisionRequest`, `DecisionResponse`, `EvidencePackage`,
  `EvidenceVerifyRequest`, `EvidenceVerifyResponse`).
- `stream.encode(msg, validate=False) -> str` (NaN-free JSON).
- Routes (all JSON unless noted):
  - `GET /api/health`, `/api/installations`, `/api/installations/{id}/scene`,
    `/api/incidents?status=live|history&limit=`, `/api/match/{incident}?at=`,
    `/api/dtw/{incident}/{match_track}?at=&channel=`, `/api/history/{track}?frame=target|region`,
    `/api/eval/latest` (the newest eval JSON, with `targets` from phase 8), `/api/schema/stream`,
    `/api/explain/{incident}/{track}?at=` (`ExplainResponse`: the decorated match, the fusion
    contributions, intercept, logit and score, tonight's path to the rerun second, the past
    flight, its window and the §10.4 step 6 alignment; 404 as `/api/dtw`).
  - `GET /api/cases?as_of=` (`CaseSummary` list), `/api/cases/{case}?as_of=`,
    `/api/cases/{case}/diff?t1=&t2=`,
    `/api/cases/{case}/graph?as_of=`, `/api/ledger/verify`, `/api/ledger/tail?n=`,
    `/api/ledger/{seq}`, `/api/delta?since=&until=&installation=`, `/api/evidence?case=`
    (`EvidencePackage` list, newest first).
  - `POST /api/cases/{case}/links` (`LinkRequest`), `POST /api/cases/{case}/evidence`
    (`{"approve": true}`; NDJSON `file` lines then `done`), `POST /api/cases/{case}/decisions`
    (`DecisionRequest`: close, reopen, escalate, notify_law_enforcement; 422 otherwise),
    `POST /api/evidence/verify` (`{"dir": name}`, 400 outside the exports root),
    `POST /api/admin/reset`, `POST /api/admin/reseed`.
  - `WS /ws/replay/{incident}`.

## Data in and out

Reads the main database read-only, LanceDB, `models/`, `reports/eval_*.json`; writes
`data/live.duckdb`, `data/memory.duckdb` (appends only), `data/cache/live/`, `exports/` (or the
`--exports` folder).

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
every outgoing message against `StreamMessage`. Phase 8: `test_api_explain.py` (contributions
reproduce the score, no look-ahead, window and alignment, 404s), `test_api_cases.py` (case list,
the known-then graph, decisions), `test_api_evidence.py` (list, verify passes then fails after
one byte, path traversal refused).

## Gotchas

- After changing `schemas.py`: `uv run kairos-defense api --dump-openapi web/openapi.json && npm
  --prefix web run gen:types` (the contract test and `npm run check:types` fail otherwise).
- A process holding the main database read-write (`make index`) stops the API from starting.
- The server binds 127.0.0.1 and has no authentication (§2: not in v1).
- Lock order: the store lock before the memory lock.
- `POST /api/evidence/verify` takes a folder name from `GET /api/evidence`, never a path: anything
  that resolves outside the exports root is a 400.

## Changelog

- Phase 7: package created.
- Phase 8: `routes_explain.py`, `schemas_pages.py`; `/api/cases`, decisions, evidence list and
  verify; `--exports` / `exports_path` (D-135 to D-137).
