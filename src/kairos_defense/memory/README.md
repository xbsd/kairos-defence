# kairos_defense.memory

Case memory, "Kairos-lite" (SPEC §15): an append-only, bitemporal, hash-chained ledger of what
Kairos Defense learned and when, so any case can be rebuilt as it was known at any moment.

## Responsibilities

- Define the ledger's rules without touching storage: event validation, actor permissions (rule 8),
  id checks (rule 9), sealing (seq, `recorded_at`, hash) and chain verification (`ledger.py`,
  `canonical.py`).
- Rebuild a case as known at a time (transaction time), list contradictions, answer valid-time
  questions and diff two moments (`asof.py`, `diff.py`, `views.py`).
- Seed 18 months of history with the planted DELTA case (`seed.py`).
- The §15.6 writes the live loop, the API (phase 7), the agent (phase 9) and the CLI use
  (`actions.py`).
- Approved, signed evidence packages and their verification (`evidence.py`, `evidence_html.py`).
- The shift delta (`delta.py`).
- Storage is the `CaseMemory` port; the DuckDB adapter is `store/ledger_duck.py` (D-092).

## Public API

All times are naive UTC `datetime`s. Ledger rows are dicts with the 17 §15.1 columns
(`ledger.ROW_FIELDS`), `object_json` parsed.

- `canonical`:
  - `canonical_json(obj) -> str`: keys sorted, separators `(",", ":")`, timestamps
    `%Y-%m-%dT%H:%M:%S.%fZ`, floats rounded to 9 decimals, `-0.0` → `0.0`; NaN and infinities
    raise `ValueError`; numpy scalars become Python numbers.
  - `row_hash(prev_hash, row) -> str` (64 hex), `GENESIS` (64 zeros), `utc_naive(t)`, `iso_z(t)`,
    `normalize(obj)`, `sha256_bytes(b)`.
- `ledger`:
  - `normalize_event(event) -> dict`, `validate(event, lookup)`, `seal(head, event) -> row`;
  - `verify_rows(rows) -> int | None`: the first broken seq (D-014);
  - `active_rows(rows, t)` (the Python twin of the `ledger_asof(t)` macro), `known_at(rows, t)`;
  - `WRITERS` (event type → actor kinds), `SUPERSEDES`, `DECISIONS`, `analyst(handle)`;
  - `Head(seq, hash, recorded_at)`, `LedgerError`, `InvalidEvent`.
- `asof`:
  - `snapshot(rows, case_id, t) -> CaseSnapshot` (`ports.py`);
  - `members_at(rows, case_id, t)`, `touching_rows(rows, case_id, members)`;
  - `contradictions(claims)`, `case_status(decisions, exists)`, `is_decided(rows)`;
  - `valid_at(rows, case_id, t_valid, known) -> dict`: valid time, separate from transaction time.
- `diff`: `case_diff(rows, case_id, t1, t2) -> list[item]`, `group(items)`, `GROUPS`.
- `delta`: `delta(rows, since, until, installation_id=None) -> ShiftDelta` (`groups`, `count`,
  `head_seq`, `to_dict()`), `GROUPS`.
- `seed`: `seed(memory, store, scenario) -> SeedSummary`, `seed_events(store, scenario)`,
  `first_contact`, `planted_cases`, `SeedError`.
- `actions`: `record_incident`, `register_model`, `propose_matches`, `decide_link`, `open_case`,
  `record_decision`, `retract`, `json_safe`, `file_sha256`; errors `ActionError`,
  `ProposalNotFound`, `ProposalAlreadyDecided`, `WrongCase`, `CaseExists`.
- `evidence`: `export_evidence(memory, case_id, *, approve, approved_by, clock, out_root, signer,
  store=None) -> ExportResult`, `verify_evidence(folder, ledger=None, pubkey_pem=None) ->
  list[Check]`, `passed(checks)`, `Signer`, `signer_for(app)`, `load_or_create_key(path)`,
  `fingerprint(pem)`, `case_document(...)`, `ApprovalRequired`, `EvidenceError`.
- `evidence_html`: `render_html(doc, png)`, `static_map_png(store, members) -> bytes | None`.
- `views`: compact row views (`claim_view`, `proposal_view`, …), `describe(row)`, `item(row, group)`.

- Phase 7 additions:
  - `views.incident_statuses(rows, at, offsets) -> {incident: status}`: "Closed as hobbyist on
    Apr 20" for a member of a closed case, "Open case, n linked" for an open one; others default
    to `views.UNATTRIBUTED` ("Open, unattributed"), D-116.
  - `graph.case_graph(rows, case_id, t) -> dict`: case, incident (with base, membership and
    contradiction flags), report and assessment nodes; `member_of`, `proposed`, `report_of`,
    `assessed` edges, each with its `seq` and `recorded_at` (JSON-safe).
  - `evidence.export_evidence(…, progress=None)`: `progress(d)` after each file is written and
    hashed, `d = {name, bytes, sha256, i, n}` (five files when signed).

## Data in and out

- `data/memory.duckdb` (`paths.memory`): table `ledger` and macro `ledger_asof(t)`, verbatim §15.1.
  Rows are only ever inserted.
- Reads `data/kairos_defense.duckdb` through the `TrackStore` port (seed, map). Never reads truth.
- `exports/<case_id>_<yyyymmddThhmmss>/` (`paths.exports`): `case.json`, `case.html`,
  `pubkey.pem`, `manifest.json`, `manifest.sig`.
- `data/keys/ed25519.pem` (`signing.key_path`): PKCS8, created on first export, mode 0600.
- `data/cache/memory_demo.duckdb`: the terminal demo's scratch ledger.

## How it works

Event fields by type (D-094):

| `event_type` | `recorded_at` | `case_id` | `subject_id` | `object_json` | valid time | actor |
|---|---|---|---|---|---|---|
| `incident_recorded` | seed: end + 5 min; live: first contact | – | incident | `{base, region_id, n_tracks, is_swarm}` | start to end (live: open) | `generator`, `system` |
| `report_recorded` | `report_ts` | – | report | `{incident_id, base, source, text}`; grade in `source_grade` | from `event_ts` | `generator`, `system` |
| `assessment_asserted` | `assessed_ts` | – | incident | `{label, rationale, author, assessment_id}` | from incident start | `generator`, `analyst:<h>` |
| `case_opened` | clock | `CASE-<incident>` | founder | `{base, opened_by}` | from clock | `generator`, `analyst:<h>` |
| `decision_recorded` | clock | case | founder | `{decision, rationale, by}` | from clock | `generator`, `analyst:<h>` |
| `match_proposed` | replay clock | target case | matched incident | `{query_incident, query_track, match_track, rank, score, shape_sim, features, reasons, warp_ratio, model_version, t_s, top3}` | from clock | `matcher@<v>`, `agent:<m>` |
| `link_approved` | clock | case | incident | `{proposal_seq, query_incident, rationale}` | from clock | `analyst:<h>` |
| `link_rejected` | clock | case | incident | `{rationale}`, `supersedes_seq` = proposal | – | `analyst:<h>` |
| `claim_retracted` | clock | as the claim | as the claim | `{rationale}`, `supersedes_seq` = assessment, link or decision | – | `analyst:<h>`, `generator` |
| `evidence_exported` | clock | case | founder | `{manifest_sha256, path, approved_by}` | – | `system` |
| `model_registered` | clock | – | – | `{version, sha256, file, validation}` | – | `system` |

- **Chain** (§15.3, D-095): `hash = sha256(prev_hash + canonical_json(row without prev_hash and
  hash))`, genesis `prev_hash` is 64 zeros. The writer stamps `recorded_at = max(clock, head)`
  (D-010). `verify_rows` returns the first expected seq whose row is missing, does not link, does not
  recompute, or goes back in time. A deleted middle row is reported at its own seq.
- **Snapshots** (§15.4): members are the founder plus subjects of active `link_approved` rows;
  pending proposals are active, undecided and not about a member; claims are active assessments of
  members; a contradiction is two active claims on the same subject and predicate with different
  labels, never resolved automatically; status is `closed` after an active `close` until a later
  `reopen`. Linking does not reopen a case.
- **Seed** (§15.5, D-096): every history event recorded strictly before the live incident's first
  contact (2026-08-29 02:40:06 UTC): 1,866 incidents, 949 reports, 1,864 assessments and the planted
  DELTA `case_opened` and `close` decision, 4,681 rows, seeded in about 0.15 s. The planted trio is
  recorded at 09:10 local in the order case, assessment, decision.
- **Live** (§15.6, D-097): a proposal batch is skipped if an earlier batch for the same query and
  case had the same top-3 set with every score within 0.05.
- **Evidence** (§15.7, D-099): export requires `approve=True`; the package records the chain head
  before its own `evidence_exported` row. Verification checks files, the Ed25519 signature, chain
  continuity of the included rows, and (with a ledger) that each row equals the ledger's and the
  head still exists there.
- **Delta** (§15.8, D-101): rows in `(since, until]` grouped into incidents, reports, proposals,
  links approved/rejected, assessments added/retracted, other retractions, contradictions opened,
  decisions (case opened included), exports and models.

## Configuration

`paths.memory`, `paths.exports`, `paths.cache` (demo scratch ledger), `signing.enabled`,
`signing.key_path` (`config/app.yaml`). The seed reads `scenario.live_incident` and
`scenario.p1_flights[*].assessment`; the demo reads `expectations.live_top3_at_s`.

## Tests

- `tests/unit/test_memory_*.py` (92 tests, all selected by `-k memory`): canonical JSON (8), ledger
  and tamper tests (20), the append-only scan (2), snapshots (10), diffs (5), seed on the P1 nights
  (10), actions (9), delta (5), evidence (12), CLI (11).
- `tests/slow/test_full_memory.py` (3): the full 4,681-row seed, the demo with the shipped model,
  an evidence round trip with the static map.
- Run: `uv run pytest tests/unit -q -k memory`; slow: `make test-all`.
- Shared helpers: `tests/unit/memory_kit.py` (hand-built events), fixtures `seeded_p1` and
  `ledger_copy` in `tests/conftest.py`.

## Gotchas

- DuckDB lets one process hold the file read-write, and while it does no other process can open it,
  even read-only. `memory reseed` and `verify` exit 1 while `make demo` (phase 7) runs;
  `verify-evidence` then SKIPs its ledger check.
- Truncating the tail of the chain cannot be seen from the chain alone; a head published elsewhere
  (an evidence package, the phase 7 `ledger` stream) catches it.
- Every write needs an explicit clock. Library code takes naive UTC; the CLI refuses naive times.
- `verify-evidence` defaults to `paths.memory`. Verify a package exported from the demo's scratch
  ledger with `--ledger data/cache/memory_demo.duckdb`, or its ledger check fails (the rows are not
  in the real ledger).
- `pubkey.pem`, `manifest.json` (it hashes the key), `manifest.sig` and the `evidence_exported`
  row depend on the random signing key; the seed, `case.json` and `case.html` do not.
- Never write `UPDATE`, `DELETE`, `TRUNCATE`, `DROP` or `ALTER` against `ledger` in `src/`, even in a
  comment: `test_memory_append_only.py` scans for it.

## Changelog

- Phase 6: the package (canonical JSON, ledger rules, snapshots, diffs, seed, actions, evidence,
  delta), D-092 to D-102.
- Phase 7: `views.incident_statuses` (the match list's memory status, D-116), `graph.case_graph`
  (Case board nodes and edges, D-108), `export_evidence(progress=…)` (the API's streamed hashing,
  D-108); the reseed core moved to `store.ledger_duck.reseed_ledger` (D-104).
