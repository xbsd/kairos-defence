# Phase 6: Case memory (Kairos-lite), plan

Autopilot plan step, 2026-10-28. Written without a human in the loop (CLAUDE.md rule 5, `phase-auto`):
every assumption below is recorded in `docs/DECISIONS.md` during the build.

## Goal

Build the append-only, bitemporal, hash-chained case memory of SPEC §15 (`kairos_defense.memory`) and
its DuckDB adapter, so that any case can be rebuilt as it was known at any moment:

- `canonical.py` and `ledger.py`: the §15.1 schema, a single locked writer, canonical JSON, the
  SHA-256 hash chain and `verify_chain`;
- `asof.py` and `diff.py`: snapshots, contradictions, transaction-time and valid-time queries, diffs;
- `seed.py`: 18 months of history as Kairos Defense would have learned it, with the planted DELTA
  case; `kairos-defense memory seed | verify | reseed`;
- `evidence.py`: an approved export with an Ed25519-signed manifest, and
  `kairos-defense verify-evidence`;
- `delta.py`: the shift delta;
- `actions.py`: the §15.6 writes (record a live incident, register a model, propose matches with
  deduplication, approve or reject a link, open a case). Phase 7's API and phase 9's agent will call
  these; phase 6 uses them for the tests and the terminal demo.

Exit check (SPEC §20, and the phase 6 list in `docs/phases/gates.json`):

```bash
uv run kairos-defense memory reseed && uv run kairos-defense memory verify && uv run pytest tests/unit -q -k memory
```

Plus a terminal demo printing the DELTA case "known then" and "known now" side by side. Phase 6 has
no `check_targets.py` step and no §19 metric. `make check` is in every gate.

## Inputs read

- `CLAUDE.md`, `docs/PROGRESS.md` (phases 0 to 5 and the backfills), `docs/phases/TEMPLATES.md`,
  `docs/phases/phase-05/REPORT.md`, the phase 4 and 5 `PLAN_REVIEW-*.json` (to see what reviewers
  block on), `docs/phases/gates.json`, `docs/phases/accepted_gaps.json`, `docs/phases/INDEX.md`.
- SPEC §15 (all of it), plus §1.2 (Case Board and Evidence beats), §4.1, §4.2, §5, §6.1 (`paths.memory`,
  `paths.exports`, `signing`), §6.4 (the planted DELTA assessment), §7.1, §7.4, §7.6, §10.8,
  §16.3 (the `ledger` message), §16.4 (the case, ledger, admin and delta routes phase 7 will
  serve), §17.6, §17.8, §17.9 (Case board, Evidence, Shift delta), §18.1 (`as_of_view`, `diff_case`,
  `shift_delta`, `propose_link`), §20 phases 6, 7 and 9, §22, §23, Appendix B.
- `docs/DECISIONS.md`, in particular D-003 (first contact is T+0), D-008 (truth scan), D-010 (ledger
  time never goes backwards; one writing process), D-011 (DELTA case timing), D-014 (`verify_chain`
  returns the first broken seq), D-022 (stubs), D-053 (adapters vs ports), D-060, D-063, D-072 (adding
  port methods), D-075 (fix-it exits), D-077 (figure font), D-081 (the accepted live top-3 gap) and
  D-091 (CLI layout). Next free number: **D-092**.
- Code: `ports.py` (`CaseMemory`, `CaseSnapshot` placeholder), `store/guard.py`, `store/ddl.py`,
  `store/duck.py`, `config/app.py`, `config/scenario.py`, `cli.py` (the `memory`, `export` and
  `verify-evidence` stubs), `cli_recall.py` (`_query_and_matches`), `match/types.py`
  (`Match.to_dict`), `match/matcher.py`, `match/fusion.py` (`MODEL_FILE`), `eval/report.py`
  (D-077 font), `tests/conftest.py` (`tmp_config`, `p1_index`, `toy_models`), `tests/unit/test_cli.py`,
  `tests/unit/test_truth_isolation.py`, `Makefile`, `pyproject.toml`, `.gitignore`, the root,
  `src/kairos_defense/` and `store/` READMEs.

### Facts checked during planning

Read-only checks: queries on `data/kairos_defense.duckdb` and a scratch script in `/tmp`. Nothing in the
repo or `data/` was written.

1. **No memory code exists yet.** There is no `src/kairos_defense/memory/`. `CaseSnapshot` in
   `ports.py` is a placeholder (`events`, `state`) that nothing uses. `memory`, `export` and
   `verify-evidence` are phase 6 stubs in `cli.py`'s `STUBS`.
2. **Seed volume.** History has 1,876 incidents, 956 reports and 1,876 assessments (one per history
   incident; live incidents have none of either). The live incident DEMO-BRAVO-0828 starts (first
   contact) at 2026-08-29 02:40:06 UTC (21:40:06 local). History runs to 2026-09-01, and 29 history
   events would be recorded after that moment: 10 incidents (end + 5 min), 7 reports and 12
   assessments. Seeding everything before first contact gives 1,866 + 949 + 1,864 + 2 planted =
   **4,681 events** (the build confirms the exact count).
3. **The planted DELTA facts in the data.** `A-P1-DELTA-260419`: label `hobbyist`, author
   `DELTA BDOC`, `assessed_ts` 2026-04-20 14:10:00 UTC = 09:10 local (COASTAL is UTC−5, no DST).
   That is exactly the scenario's `assessed_local`. P1-DELTA-260419 runs from 02:35:02 to 02:46:40
   UTC on 04-20 (21:35 local on 04-19). Its only report, `R-P1-DELTA-260419-1` (security forces, B2,
   "white pickup … County Rd 12 from 21:20 to 22:05"), was filed at 03:40 UTC on 04-20, so it was
   already in memory at "known then". That fits the story: the report existed, nobody connected it.
4. **The real matcher's proposals.** At T+90 and T+120 the shipped model ranks DELTA 1, ALPHA-260303
   2, CHARLIE-260710 3 and ALPHA-260502 4 (the accepted phase 4 gap, D-081). `match --at 120` takes
   1.4 s wall time. A terminal demo that proposes the real top 3 will therefore link CHARLIE rather
   than ALPHA-260502.
5. **DuckDB 2.0.0** (scratch file):
   - a `JSON` column returns its text verbatim;
   - `TIMESTAMP` round-trips microseconds exactly, and `DOUBLE` round-trips exactly;
   - the §15.1 table macro `ledger_asof(t)` works as written, drops superseded rows only once the
     superseding row is recorded, and persists in the file.
   - While one process holds the file read-write, another process cannot open it, **even
     read-only** ("Could not set lock on file"). After it closes, read-only opens work.
6. **Ed25519 via `cryptography` 50.0.2** (already a dependency): `from_private_bytes` gives a fixed
   test key, signatures are deterministic (64 bytes), and public keys serialize to PEM
   SubjectPublicKeyInfo. `matplotlib` 3.11.2 is installed (D-077 pins DejaVu Sans).
7. **Test selection.** `pytest -k` matches module names: `-k duck_store` selects all 9 tests in
   `test_duck_store.py`. Today `-k memory` selects 1 test, the `memory` stub case. There are 497 fast
   tests (12 slow).
8. **`exports/` and `data/` are git-ignored**, so exit-check packages and the scratch ledger are
   never committed by `git add -A`.

## Assumptions and decisions

Each one becomes a `docs/DECISIONS.md` entry during the build (numbers are planned).

**A1 · Where the code lives (D-092).** SPEC §5 lists `memory/ledger.py` as the writer. CLAUDE.md
(rule 6, "I/O lives in adapters under `kairos_defense.store`") and D-053 put DuckDB code in `store/`.
So:
- the DuckDB adapter `DuckCaseMemory` lives in `store/ledger_duck.py`: DDL, the lock, reads and
  inserts;
- the §15.1 DDL and macro go in `store/ddl.py` next to the other schemas;
- `memory/ledger.py` keeps the store-free parts: event validation, `seal` (assign seq, stamp time,
  hash) and `verify_rows`.

Swapping in `KairosCaseMemory` (§22) then replaces one adapter.

**A2 · Port changes (D-093).** Two methods are added to `CaseMemory`, as D-072 did for `TrackStore`:
- `append_many(events) -> list[int]`: one atomic transaction. Seeding needs it, both to be atomic
  and to be fast (4,681 rows).
- `events(after=None, until=None) -> list[dict]`: rows with `after < recorded_at <= until`, in seq
  order, `object_json` parsed.

`delta`, valid-time queries and evidence are pure functions over these rows, so a future adapter
implements one read. `as_of`, `diff` and `verify_chain` keep their §4.1 signatures; the adapter
delegates them to the pure functions.

`CaseSnapshot` gets typed fields and `state` goes (nothing uses it): `case_id`, `as_of`, `exists`,
`status` (`unknown` / `open` / `closed`), `founder`, `members`, `links`, `pending`, `claims`,
`contradictions`, `decisions`, `exports`, `reports`, `events`, `head_seq` and `head_hash`, plus
`to_dict()`, JSON-safe with ISO `Z` times, for phase 7's `GET /api/cases/{id}` and phase 9's
`as_of_view`.

**A3 · Event field conventions (D-094).** All times are naive UTC in DuckDB. Aware inputs are
converted, and naive inputs count as UTC.

| `event_type` | `recorded_at` | `case_id` | `subject_id` | `predicate` | `object_json` | `valid_from` / `valid_to` | `source_*`, `confidence` | `actor` |
|---|---|---|---|---|---|---|---|---|
| `incident_recorded` (seed) | `end_ts` + 5 min | – | incident | – | `{base, region_id, n_tracks, is_swarm}` | `start_ts` / `end_ts` | – | `generator` |
| `incident_recorded` (live) | first contact | – | incident | – | same | `start_ts` / null | – | `system` |
| `report_recorded` | `report_ts` | – | report | – | `{incident_id, base, source, text}` | `event_ts` / null | `source`, `report_id`, grade | `generator` |
| `assessment_asserted` | `assessed_ts` | – | incident | `assessment` | `{label, rationale, author, assessment_id}` | incident `start_ts` / null | `assessment`, `assessment_id` | `generator` or `analyst:<h>` |
| `case_opened` | (DELTA: 09:10 local) | `CASE-<incident>` | founding incident | – | `{base, opened_by}` | `recorded_at` / null | – | `generator` or `analyst:<h>` |
| `decision_recorded` | (DELTA: 09:10 local) | case | founding incident | `decision` | `{decision, rationale, by}` | `recorded_at` / null | – | `generator` or `analyst:<h>` |
| `match_proposed` | replay clock | target case | matched incident | `member_of` | `{query_incident, query_track, match_track, rank, score, shape_sim, features, reasons, warp_ratio, model_version, t_s, top3}` | `recorded_at` / null | `matcher`, model version, score | `matcher@<v>` or `agent:<m>` |
| `link_approved` | clock | case | incident | `member_of` | `{proposal_seq, query_incident, rationale}` | `recorded_at` / null | – | `analyst:<h>` |
| `link_rejected` | clock | case | incident | `member_of` | `{rationale}`; `supersedes_seq` = proposal | – | – | `analyst:<h>` |
| `claim_retracted` | clock | case or – | subject of the claim | its predicate | `{rationale}`; `supersedes_seq` = claim | – | – | `analyst:<h>` or `generator` |
| `evidence_exported` | clock | case | founding incident | – | `{manifest_sha256, path, approved_by}` | – | – | `system` |
| `model_registered` | clock | – | – | – | `{version, sha256, file, validation}` | – | – | `system` |

The rules that follow from the table:

- **Members.** A case's members are its founder (from `case_opened`) plus the subjects of active
  `link_approved` rows, in that order.
- **Approval is not a retraction.** `link_approved` points to its proposal through
  `object_json.proposal_seq`, not `supersedes_seq`. A proposal is pending while it is:
  - active (not superseded),
  - undecided, and
  - about an incident that is not already a member.
- **Status.** A case is `closed` if its latest active decision is `close`; otherwise it is `open`, or
  `unknown` before `case_opened`.
- **Decisions.** The vocabulary is `close | reopen | escalate | notify_law_enforcement`.
- **Claims.** Claims are active `assessment_asserted` rows, valued by `label`. A contradiction is two
  or more active claims with the same subject and predicate and different values. Both stay visible,
  with source and time, until one is retracted (§15.4). Nothing resolves them automatically.
- **What touches a case.** A row touches a case when:
  - its `case_id` is the case; or
  - its incident is a member (`subject_id` for incident subjects, `object_json.incident_id` for
    reports); or
  - it supersedes a row that touches the case.

**Actor permissions** (§15.2 "Written by", rule 8) are checked at append:

| Actor | May write |
|---|---|
| `generator` | the seeded types |
| `system` | `incident_recorded`, `evidence_exported`, `model_registered` |
| `matcher@<v>`, `agent:<m>` | **only** `match_proposed` |
| `analyst:<h>` | assessments, cases, links, retractions, decisions |

The validation checks:
- ids match `^[A-Z0-9][A-Z0-9-]*$`, and case ids match `^CASE-…`; this covers rule 9, because a
  person's name cannot be a subject;
- handles match `[a-z0-9_.-]{1,32}`;
- `supersedes_seq` must name an earlier row of a compatible type:
  - a proposal, for `link_rejected`;
  - an assessment, a link or a decision, for `claim_retracted`.

**A4 · Canonical JSON and the chain (D-095).** §15.3 as written, with these details:
- `object_json` is canonicalized as a nested object (stored as its canonical text);
- timestamps are `%Y-%m-%dT%H:%M:%S.%fZ` (always 6 digits);
- floats are rounded to 9 decimals before storing (so a round trip is exact), and −0.0 becomes 0.0;
- NaN and ±inf raise `ValueError`. Callers map NaN to null; `Match.warp_ratio` is NaN beyond the
  top 20;
- numpy scalars become Python numbers.

The chain:
- `seq` starts at 1, and the genesis `prev_hash` is 64 zeros;
- `hash = sha256(prev_hash + canonical_json(row without prev_hash, hash))`;
- the writer stamps `recorded_at = max(clock, head.recorded_at)` (D-010). Every event must carry a
  `recorded_at` clock: the seed uses data times, live code the replay clock, and the CLI the chain
  head unless `--at` is given.

`verify_rows` walks the expected seq 1, 2, … and returns the first expected seq whose row:
- is missing;
- has a `prev_hash` that is not the previous row's hash;
- has a hash that does not recompute; or
- has a `recorded_at` earlier than its predecessor's.

So a deleted row is reported at its own seq. Truncating the tail cannot be seen from the chain
alone. A head published elsewhere (an evidence package, the phase 7 `ledger` stream) catches it.
That limitation goes in the README.

**A5 · What the seed contains (D-096).** The seed holds every history event recorded strictly before
the live incident's first contact (`scenario.live_incident`'s `start_ts`). That cutoff is
"Kairos Defense's memory when tonight's drone appears": the 29 later events (fact 2) would be
look-ahead at demo time. Leaving them out also keeps the replay clock ahead of the chain head, so
§15.6's `max(clock, head)` stamps live writes at the replay clock. Live incidents are not seeded.

The planted cases come from the scenario, not hard-coded ids. Every `p1_flights` entry with an
`assessment` gets a `case_opened` (`CASE-<incident>`) and a `decision_recorded`
`{decision: close, rationale: "assessed hobbyist", by: <author>}`. Both are stamped at the
generator's assessment time for that incident, with actor `generator`. If that assessment row is
missing, `SeedError` names `make data`.

Ties are ordered by `(recorded_at, type rank, subject_id)` with the type rank: incident, report,
case_opened, assessment, decision. That gives `case_opened` → `assessment_asserted` →
`decision_recorded` at 09:10 local (D-011).

The seed reads the store only through `TrackStore.sql` (the port) and never opens truth.

**A6 · Live proposals (D-097).** §15.6 says both "only when the top-3 set changes or a score moves by
more than 0.05" and "a proposal already in the ledger for the same query incident and top-3 set is
not appended again". `propose_matches` reconciles the two. It appends a batch (one `match_proposed`
per top-3 match, sharing `top3` and `recorded_at`) only if no earlier batch for the same query has
the same top-3 set with every score within 0.05 of the new ones. So:
- a changed set is appended;
- a real score move is appended;
- a re-run or a seek back with the same results appends nothing.

Before the first proposal of a model version, `register_model` writes `model_registered` once per
(version, sha256). The CLI computes the sha256 of `models/fusion_v1.json` and passes in its
`validation` block.

`decide_link(memory, case_id, proposal_seq, decision, analyst, clock)` checks that the proposal:
- exists and is a `match_proposed`;
- targets this case;
- is active and undecided.

Otherwise it raises (`ProposalNotFound`, `ProposalAlreadyDecided`, `WrongCase`). An approval writes
`link_approved`; a rejection writes `link_rejected` superseding the proposal.

`open_case(memory, incident, actor, clock)` writes `case_opened` for `CASE-<incident>` and refuses an
existing id. Choosing which case a live proposal targets, and opening new cases from the UI, are
phase 7/8 choices.

**A7 · Terminal demo (D-098).** `kairos-defense memory demo [--at 90] [--approve] [--analyst demo]
[--case …] [--scratch …]` steps:
1. Copy the seeded ledger to a scratch file (default `data/cache/memory_demo.duckdb`), verify it,
   and check its head equals the source's. The real `data/memory.duckdb` stays at seed state
   (Appendix B: the running app never mutates ledger rows, and reseed resets).
2. Append, at the replay clock:
   - `incident_recorded` for `scenario.live_incident` at T+0;
   - `model_registered`;
   - the **real** `DtwMatcher` top 3 at T = `--at` (default `expectations.live_top3_at_s`, 90) as
     proposals into the planted case (default `CASE-P1-DELTA-260419`).
3. Only with `--approve`, approve each proposal as `analyst:<handle>` (rule 8: the flag is the
   explicit user action). Without it, "known now" shows three pending proposals.
4. Print the two snapshots side by side and the diff, grouped.

"Known then" is the planted assessment's recorded time (09:10 local). "Known now" is the scratch
chain head.

Because of the accepted phase 4 gap (fact 4), the demo is expected to link DELTA, ALPHA-260303 and
CHARLIE-260710, and REPORT.md will say so. The SPEC unit test "after approving the three demo links
it shows three members" uses the scenario's `expectations.live_top3_incidents` (DELTA, ALPHA-260303,
ALPHA-260502) with hand-written proposals (actor `matcher@test`) on the generated P1 nights. It does
not depend on the matcher.

**A8 · Evidence (D-099).** `export_evidence(memory, case_id, *, approve, approved_by, clock, out_root,
signer, store=None, utc_offset_hours=0)`:
- raises `ApprovalRequired` unless `approve=True`. In that case it writes nothing and appends nothing.
- writes `exports/<case_id>_<yyyymmddThhmmss>/` (UTC of the export clock; a `-2`, `-3` … suffix if
  the folder exists).

The package:

| File | Content |
|---|---|
| `case.json` | Snapshot `to_dict()` at the export clock; every row touching the case with `prev_hash` and `hash`; the chain head (seq, hash, recorded_at); `verify_chain` result and row count; model versions (from `model_registered` and proposals); package format version |
| `case.html` | Self-contained summary: timeline, members, matches with reasons, report excerpts, decisions, chain head, and a static map (tracks of member incidents in target-relative meters from `TrackStore.features`, one PNG inlined as base64, DejaVu Sans, `metadata={"Software": None}`). No scripts, no external `src`/`href` |
| `pubkey.pem` | Ed25519 public key (SubjectPublicKeyInfo PEM) |
| `manifest.json` | `{format, case_id, created_at, algorithm: "sha256", files: {case.json, case.html, pubkey.pem → sha256}}` |
| `manifest.sig` | base64 Ed25519 signature of the exact `manifest.json` bytes |

After writing the package, the export appends `evidence_exported` (actor `system`,
`object_json.approved_by`). So the package records the head before its own export event.

Signing key:
- `signing.key_path` (`data/keys/ed25519.pem`), PKCS8 PEM, created on first use with mode 0600,
  then reused.
- Keys come from the OS CSPRNG through `cryptography`, not from the seeded generator. Rule 4 governs
  data; a key derived from a public seed would be forgeable. Content hashes are still deterministic.
- `signing.enabled: false` writes an unsigned package, which `verify-evidence` reports as FAIL
  (signature missing).

`verify_evidence(dir, ledger=None, pubkey=None)` returns one row per check, each PASS, FAIL or
SKIP:
- **files:** every listed file exists and its hash matches; any unlisted file other than
  `manifest.json` and `manifest.sig` fails;
- **signature:** valid against the package's `pubkey.pem`. The key's SHA-256 fingerprint is
  printed. `--pubkey` pins an expected key;
- **chain continuity:**
  - every included row recomputes to its hash from its `prev_hash`;
  - rows with consecutive seqs link;
  - the head is consistent with the rows;
- **ledger:** with `--ledger` (default `paths.memory`), every included row equals the ledger's row
  at that seq and the ledger chain verifies. This check is SKIPped, not failed, when the ledger is
  missing or locked by another process (fact 5).

**A9 · CLI shapes (D-100).** A new `cli_memory.py`, registered by `cli.py` like `cli_recall.py`.
`cli.py` is 372 lines; removing three stubs keeps it under 400. Rich tables go in
`cli_memory_view.py`.

| Command | What it does | Failure exits |
|---|---|---|
| `memory seed` | Seeds an empty or missing ledger. Prints counts per event type, the cutoff, the head seq and hash, and the elapsed time | Exit 1 if the ledger has rows ("use `memory reseed`") or data is missing ("run `make data`") |
| `memory reseed` | Builds into `<memory>.reseed.tmp`, verifies it, closes it, then `os.replace` | Exit 1 if another process holds the file lock. The message names `make demo` and D-010; phase 7 adds the `POST /api/admin/reseed` path |
| `memory verify [--ledger P]` | Prints "chain intact: N rows, head seq … hash …"; exit 0 | Exit 1 with "chain broken at seq N", or with no ledger |
| `memory show CASE --as-of TS [--ledger P]` | The snapshot as known at TS | – |
| `memory delta --since TS [--until TS] [--installation ID] [--ledger P]` | The shift delta | – |
| `memory demo …` | A7 | – |
| `export --case ID --approve [--analyst h] [--at TS] [--ledger P] [--out DIR]` | Exports the package; prints the folder and the manifest sha256 | Exit 1 without `--approve` ("approval required, rule 8"); nothing is written |
| `verify-evidence DIR [--ledger P] [--pubkey PEM]` | Prints a PASS/FAIL/SKIP table; exit 0 when nothing fails | Exit 1 on any FAIL |

All CLI times must carry `Z` or an offset (`2026-04-20T10:00-05:00`). Naive times exit 1 with that
hint, because a naive time is ambiguous across three regions. Output shows UTC and the case's local
time, using the region offset of its base from `config/world.yaml`.

**A10 · Shift delta groups (D-101).** `delta(rows, since, until, installation_id=None)` groups events
recorded in (since, until] into:
- `incidents` and `reports`: new facts, which §15.8 omits but a shift brief needs;
- `proposals`;
- `links_approved` and `links_rejected`;
- `assessments_added` and `assessments_retracted`;
- `contradictions_opened`: present at `until` and absent at `since`, keyed to the seq that opened
  them;
- `decisions` and `exports`.

Each item carries `seq`, `event_type`, `recorded_at`, `subject_id`, `case_id`, `supersedes_seq` and
`source_id` as evidence references.

The installation filter uses each incident's `base` from `incident_recorded` (reports use their
`base`). Rows with no installation (`model_registered`) are dropped when filtering.

Case diffs use the same idea per case: `diff(case_id, t1, t2)` returns items for events recorded in
(t1, t2] that touch the case's subjects as of t2. The items are grouped into:
- `members_added` (each with `new_member`);
- `proposals`;
- `claims_added` and `claims_retracted`;
- `contradictions`;
- `decisions` and `exports`;
- `facts`: incidents, reports, rejections and models.

## Work breakdown

The manual prompt says to write the tamper test first. Steps 1–3 follow it.

1. **Tests first, red.** Write `tests/unit/test_memory_ledger.py`'s tamper tests and
   `tests/unit/test_memory_append_only.py` against the planned API, and confirm they fail (import
   error) before any code.
2. **`memory/canonical.py`** (~80 lines): `canonical_json(obj) -> str`, `row_payload(row) -> dict`
   (drops `prev_hash` and `hash`), `row_hash(prev_hash, row) -> str`, `GENESIS = "0" * 64`. Tests:
   `test_memory_canonical.py`.
3. **`memory/ledger.py`** (~250 lines):
   - `EVENT_TYPES`, `ACTOR_RULES`, `validate(event, lookup)`, `seal(head, event) -> row`,
     `verify_rows(rows) -> int | None`;
   - `active_rows(rows, t)`, the Python twin of the `ledger_asof` macro;
   - errors `LedgerError`, `InvalidEvent`.

   **`store/ddl.py`**: `LEDGER_DDL` and `LEDGER_ASOF_MACRO`, verbatim §15.1.

   **`store/ledger_duck.py`** (~200 lines): `DuckCaseMemory(path, app, *, read_only=False)`:
   - opened through `connect_app_db`, so the truth guard applies;
   - creates the DDL if missing and refuses a different schema ("run `memory reseed`");
   - one connection behind a `threading.Lock`; `append` and `append_many` validate, seal and insert
     in one transaction (a DataFrame insert for batches);
   - `events(after, until)`, `head()`, `count()`, `rows_for_seqs(seqs)`;
   - `as_of`, `diff` and `verify_chain` delegate to the pure functions;
   - context manager.

   **`ports.py`**: the `CaseMemory` additions and the typed `CaseSnapshot` (A2). After this step,
   the tamper tests pass.
4. **`memory/asof.py`** (~250 lines): `touches(row, members)`, `members_at(rows, case_id)`,
   `snapshot(rows, case_id, t) -> CaseSnapshot`, `contradictions(claims)`,
   `valid_at(rows, case_id, t_valid) -> dict` (valid-time: rows whose `valid_from <= t < coalesce(valid_to, ∞)`,
   taken from the rows known at `known_at`). **`memory/diff.py`** (~120 lines):
   `case_diff(rows, case_id, t1, t2) -> list[dict]`, `group(items)`. Tests: `test_memory_asof.py`,
   `test_memory_diff.py` on a hand-built ledger.
5. **`memory/seed.py`** (~180 lines): `seed_events(store, scenario) -> list[dict]` (pure over the port),
   `planted_cases(scenario)`, `seed(memory, store, scenario) -> SeedSummary` (refuses a non-empty
   ledger), `SeedError`. Tests: `test_memory_seed.py` on `p1_index` (the real generator's P1 nights,
   DELTA included).
6. **`memory/actions.py`** (~200 lines): `record_incident`, `register_model`, `propose_matches`
   (A6, NaN → null via a `json_safe` helper), `decide_link`, `open_case`, plus errors. Tests:
   `test_memory_actions.py`, plus the SPEC "three demo links" test in `test_memory_seed.py`.
7. **`memory/delta.py`** (~150 lines): `delta(rows, since, until, installation_id) -> ShiftDelta`
   (`to_dict()`). Tests: `test_memory_delta.py`.
8. **`memory/evidence.py`** (~250 lines: export, keys, manifest, signing, verification) and
   **`memory/evidence_html.py`** (~180 lines: HTML and the static map). Tests:
   `test_memory_evidence.py` with a fixed test key (`from_private_bytes(b"\x01" * 32)`).
9. **CLI.** `cli_memory.py` (`memory` sub-app with `seed`, `reseed`, `verify`, `show`, `delta` and
   `demo`; `export`; `verify-evidence`) and `cli_memory_view.py` (side-by-side table, diff, delta and
   verification tables). Remove the three phase 6 entries from `STUBS`. The demo reuses
   `cli_recall._query_and_matches`. Tests: `test_memory_cli.py`, in the existing pattern
   (monkeypatch `cli._load_config`). `tests/conftest.py`: `tmp_config` also redirects `exports` and
   `signing.key_path` into the tmp folder; add a session fixture `seeded_p1` (the P1 nights seeded
   once) and a function fixture `ledger_copy` (a fresh copy per test that appends). CLI tests point
   `paths.memory`, `paths.exports`, `paths.cache` and the signing key at their own `tmp_path`, so no
   test writes the session-scoped `p1_index` ledger or shares one with another test.
10. **Slow tests.** `tests/slow/test_full_memory.py` on `data/` (skipped with a reason when the data
    or models are missing, like the other slow files).
11. **Exit check.** Run every command in the mapping below, write `EXIT_CHECK.md`, then `make check`
    and `make test-all`.
12. **Docs and commit.** READMEs, PROGRESS.md, DECISIONS.md, REPORT.md (see below). Then
    `git add -A && git commit -m "phase 6: case memory (Kairos-lite)"`, leaving the tree clean.

Run `make check` after each step. Every module stays under ~400 lines.

## Tests

All fast tests live in files named `test_memory_*.py`, so `pytest tests/unit -q -k memory` selects
every one of them (fact 7). Each new function gets known-answer and edge-case tests.

**`test_memory_canonical.py`** (8)
- `test_keys_sorted_and_compact_separators`: `{"b":1,"a":2}` → `{"a":2,"b":1}`.
- `test_timestamps_iso_utc_with_z`: naive = UTC; aware −05:00 is converted; pandas Timestamp; always
  `.ffffffZ`.
- `test_floats_rounded_to_9_decimals_and_negative_zero`: `0.1 + 0.2` → `0.3`; −0.0 → `0.0`.
- `test_none_is_null_and_nested_object_json_is_canonical`: key order inside `object_json` does not
  change the hash.
- `test_rejects_nan_and_infinity`.
- `test_numpy_scalars_and_unicode`: `np.float64` and `np.int64`; "é" survives.
- `test_row_hash_known_answer`: a fixed row with genesis `prev_hash` gives a pinned hex digest.
- `test_hash_ignores_prev_hash_and_hash_fields`.

**`test_memory_ledger.py`** (16), written first
- `test_tamper_object_json_caught_at_that_seq`: 10 rows; raw SQL changes seq 6's `object_json`;
  `verify_chain() == 6`.
- `test_tamper_recorded_at_caught_at_that_seq`: seq 3 → 3.
- `test_tamper_hash_caught_at_that_seq`: seq 8 → 8.
- `test_deleted_row_caught_at_missing_seq`: raw SQL removes seq 5 → 5.
- `test_intact_and_empty_chains_verify_none`.
- `test_seq_contiguous_from_1_and_prev_hash_links`: genesis is 64 zeros.
- `test_recorded_at_never_goes_backwards`: a clock earlier than the head is stamped with the head's
  time (D-010).
- `test_round_trip_recomputes_same_hash`: 40 events drawn with a seeded Generator (floats, unicode,
  None, nested JSON), read back, recomputed.
- `test_append_many_is_atomic`: a batch with one invalid event appends nothing.
- `test_concurrent_appends_are_serialized`: 4 threads × 25 appends give seqs 1–100, and the chain
  verifies.
- `test_validation_rejects_unknown_type_bad_actor_and_bad_ids`: includes a person-like subject
  "John Smith" (rule 9).
- `test_only_analysts_approve_or_reject_links`: `matcher@…` and `agent:…` may append only
  `match_proposed` (rule 8).
- `test_supersedes_must_reference_an_earlier_compatible_event`.
- `test_ledger_asof_macro_matches_python_active_rows`: SQL `ledger_asof(t)` seqs equal
  `active_rows(t)` at five times, including across a retraction.
- `test_read_only_memory_refuses_append`.
- `test_memory_refuses_truth_path`: `DuckCaseMemory(paths.truth)` raises `TruthAccessError`.

**`test_memory_append_only.py`** (2)
- `test_no_update_or_delete_on_ledger_in_src`. The scan covers every `.py` under
  `src/kairos_defense/`, comments included, with whitespace normalized. It fails on, case-insensitive:
  `UPDATE ledger`, `DELETE FROM ledger`, `TRUNCATE ledger`, `DROP TABLE … ledger`,
  `INSERT OR REPLACE INTO ledger` and `ON CONFLICT … DO UPDATE`.
- `test_scan_pattern_catches_mutations`: the pattern hits positive examples (including one split
  across lines) and passes `INSERT INTO ledger`, so the scan cannot pass vacuously.

**`test_memory_asof.py`** (10): a hand-built ledger, with times in DELTA's local offset.
- `test_case_unknown_before_it_is_opened`.
- `test_known_then_shows_label_closed_no_links`.
- `test_contradiction_keeps_both_claims_with_sources`: `hobbyist` from DELTA BDOC plus `probing` from
  `analyst:a` → one contradiction, both claims listed with their source and time.
- `test_retraction_resolves_contradiction_never_auto`: still contradicted until a
  `claim_retracted`; after it, one claim.
- `test_approved_link_adds_member_and_clears_pending`.
- `test_rejected_proposal_is_no_longer_pending`.
- `test_retracted_link_removes_member`.
- `test_pending_excludes_existing_members`.
- `test_valid_time_differs_from_transaction_time`. An assessment recorded 04-20 09:10 with valid_from
  04-19 21:35:
  - the valid-time query at 04-19 22:00, as known now, returns the claim;
  - `as_of(04-19 22:00)` does not.
- `test_snapshot_head_and_to_dict_is_json`: `json.dumps(snapshot.to_dict())` works; the head is the
  last row ≤ t.

**`test_memory_diff.py`** (5)
- `test_diff_window_is_t1_exclusive_t2_inclusive`.
- `test_diff_groups`: every group, with the `new_member` flag.
- `test_diff_includes_facts_of_members_added_later`: an incident recorded inside the window and
  linked at t2 shows up under `facts`.
- `test_diff_empty_when_nothing_changed`.
- `test_port_diff_equals_pure_function`.

**`test_memory_seed.py`** (10), on `p1_index`, i.e. the generator's real output for the six P1 nights
- `test_seed_counts_match_the_store`: counts per type equal the store's rows before the cutoff, plus
  the 2 planted events.
- `test_seed_times_follow_15_5`: incidents at end + 5 min with valid time [start, end]; reports at
  `report_ts` with `valid_from = event_ts`; assessments at `assessed_ts`; actor `generator`.
- `test_seed_is_ordered_and_cut_before_first_contact`: `recorded_at` never decreases; every event is
  before DEMO-BRAVO-0828's first contact; no live incident is seeded.
- `test_planted_delta_trio_in_order_at_0910_local`: `case_opened`, `assessment_asserted` and
  `decision_recorded` have consecutive seqs. Their `recorded_at` equals the scenario's
  `assessed_local` plus the COASTAL offset.
- `test_delta_known_at_1000_local_hobbyist_closed_no_links` (SPEC): as of 2026-04-20 10:00 −05:00,
  the snapshot has:
  - claims == [`hobbyist`];
  - status `closed`;
  - `links == []`, `members == [P1-DELTA-260419]`, no pending;
  - the planted report among `reports`.
- `test_delta_case_unknown_at_0900_local`.
- `test_no_cross_base_links_in_history`: no `match_proposed` or `link_*` events, and the DELTA case is
  the only case.
- `test_seed_is_deterministic`: two seeds give the same head hash.
- `test_seed_refuses_non_empty_ledger`.
- `test_three_demo_links_make_three_members_and_diff_lists_them` (SPEC):
  1. Propose `expectations.live_top3_incidents` for DEMO-BRAVO-0828 into CASE-P1-DELTA-260419
     (`matcher@test`, given scores) at T+90, then approve all three as `analyst:test`.
  2. Members are DELTA, ALPHA-260303 and ALPHA-260502 (three).
  3. `diff(then, now)` lists three `members_added` (two new members) and three proposals, plus
     ALPHA-260502's incident, reports and assessment under `facts`, because it "had not yet
     happened".

**`test_memory_actions.py`** (9)
- `test_record_incident_event_fields`.
- `test_register_model_once_per_version`.
- `test_propose_matches_writes_one_event_per_top3_match`: fields as in A3, and a NaN `warp_ratio`
  becomes null.
- `test_propose_skips_same_set_within_005`.
- `test_propose_appends_when_score_moves_more_than_005`.
- `test_propose_appends_on_set_change_and_skips_on_rerun`: a seek back with the earlier results
  appends nothing.
- `test_decide_link_approve_and_reject`.
- `test_decide_link_twice_or_wrong_case_raises`.
- `test_open_case_uses_case_dash_incident_and_refuses_existing`.

**`test_memory_delta.py`** (5)
- `test_delta_groups_and_refs`: each item carries its seq and references.
- `test_delta_window_bounds`.
- `test_delta_installation_filter`.
- `test_delta_contradictions_opened_in_window`.
- `test_delta_assessment_retracted`.

**`test_memory_evidence.py`** (12)
- `test_export_requires_approval`: no folder, and no ledger row.
- `test_export_writes_five_files_and_appends_event`: `manifest_sha256` in the event equals the
  manifest's hash.
- `test_case_json_has_rows_head_verification_models`: every touching row with hashes; the head; the
  verification result; model versions.
- `test_html_is_self_contained`: no `<script`, no `src`/`href` to `http(s)`; one `data:image/png`
  image.
- `test_verify_passes`.
- `test_verify_fails_after_editing_one_file` (SPEC): one byte of `case.html` changed → its FAIL row,
  overall fail.
- `test_verify_fails_on_missing_or_extra_file`.
- `test_verify_fails_on_bad_signature_or_pinned_key_mismatch`: an edited `manifest.json`; a package
  re-signed with another key while `--pubkey` pins the original.
- `test_verify_checks_the_ledger_when_available`: a tampered ledger row fails; a missing ledger is
  SKIP.
- `test_signing_key_created_once_with_0600`.
- `test_unsigned_package_fails_verification`: `signing.enabled: false`.
- `test_export_folder_name_and_collision_suffix`.

**`test_memory_cli.py`** (11)
- `test_memory_seed_then_refuse_second_seed`.
- `test_memory_reseed_gives_same_head_hash`.
- `test_memory_verify_intact_and_broken`: after a raw-SQL tamper, exit 1 naming the seq.
- `test_memory_show_delta_known_at_1000_local`: "hobbyist" and "closed" printed.
- `test_memory_times_need_an_offset`: a naive `--as-of` exits 1 with the hint.
- `test_memory_demo_leaves_real_ledger_untouched`: `toy_models`; the real ledger's head hash is
  unchanged; both column titles are printed.
- `test_memory_demo_approve_adds_members`: the member count printed equals |{DELTA} ∪ toy top 3|.
- `test_export_needs_approve_flag`.
- `test_export_and_verify_evidence_cli`: exit 0, then a file is edited, then exit 1.
- `test_memory_delta_cli`.
- `test_memory_commands_need_a_ledger_or_data`.

**Slow, `tests/slow/test_full_memory.py`** (3)
- `test_full_seed_counts_and_delta_case`: 4,681 rows (A5); verifies; the DELTA case at 10:00 local
  as in the SPEC test.
- `test_full_demo_known_then_now`: real models; proposals of the T+90 top 3; after approval, members
  = {DELTA} ∪ top 3.
- `test_full_evidence_roundtrip`: export with the static map from the real store; verify passes,
  then fails after an edit.

**Count arithmetic.** Removing the three `memory`, `export` and `verify-evidence` stubs drops 3
parametrized `test_stub_names_its_phase` cases. About 88 fast tests are added, so 497 − 3 + 88 ≈ 582
(the gate requires ≥ 497). REPORT.md will give the exact arithmetic. The phase adds no skip or xfail
markers. The truth-isolation scan (`test_truth_isolation.py`) covers the new files automatically.

## Exit-check mapping

| Criterion (SPEC §20) | Command | Evidence it will produce |
|---|---|---|
| Reseed the ledger | `uv run kairos-defense memory reseed` | Counts per event type (≈ 1,866 / 949 / 1,864 / 1 / 1 = 4,681), cutoff 2026-08-29 02:40:06 UTC, head seq and hash, seconds |
| Chain verifies | `uv run kairos-defense memory verify` | "chain intact: 4,681 rows, head seq 4,681 hash …", exit 0 |
| Memory tests | `uv run pytest tests/unit -q -k memory` | ≈ 88 passed (the three commands above are run with `&&`, exactly as SPEC writes them) |
| DELTA as of 2026-04-20 10:00 local: hobbyist, closed, no links | `uv run kairos-defense memory show CASE-P1-DELTA-260419 --as-of 2026-04-20T10:00-05:00` | Status closed, assessment hobbyist (DELTA BDOC, 09:10), members DELTA only, no links, no pending, head seq |
| Terminal demo: "known then" and "known now" side by side | `uv run kairos-defense memory demo --approve` | Side-by-side table (status, members, assessments, reports, decisions, proposals, contradictions, chain head) and the grouped diff; scratch ledger path. Expected members now: DELTA, ALPHA-260303, CHARLIE-260710 (fact 4) |
| Real ledger untouched by the demo | `uv run kairos-defense memory verify` (again) | Same head seq and hash as after reseed |
| Shift delta | `uv run kairos-defense memory delta --since 2026-08-28T00:00-05:00 --ledger data/cache/memory_demo.duckdb` | Groups: incidents of that evening, the demo's proposals and approvals, the model registration |
| Evidence export with approval | `uv run kairos-defense export --case CASE-P1-DELTA-260419 --ledger data/cache/memory_demo.duckdb` then the same with `--approve` | First exits 1 ("approval required"); second prints `exports/CASE-P1-DELTA-260419_20260829T…/` and the manifest sha256 |
| Evidence verify passes | `uv run kairos-defense verify-evidence exports/<dir> --ledger data/cache/memory_demo.duckdb` | PASS for files, signature (key fingerprint), chain continuity and ledger; exit 0 |
| Evidence verify fails after editing one file | `cp -R exports/<dir> /tmp/kd_tamper && printf x >> /tmp/kd_tamper/case.html && uv run kairos-defense verify-evidence /tmp/kd_tamper` | `case.html` hash FAIL, overall FAIL, exit 1 |
| No UPDATE/DELETE on `ledger`; tamper caught at the right seq | Part of `pytest -k memory` | `test_no_update_or_delete_on_ledger_in_src`, `test_tamper_*` pass |
| Whole gate | `make check`, `make test-all`, then the `gates.json` phase 6 list in order | Pass counts (fast and all) |

The exit-check commands rewrite `data/memory.duckdb` (reseed), `data/cache/memory_demo.duckdb` and
`exports/`. All three are git-ignored. No command starts a server.

## Documentation to write or update

- `docs/phases/phase-06/EXIT_CHECK.md` and `REPORT.md` (templates), with the honest list of plan
  changes made during the build.
- **New** `src/kairos_defense/memory/README.md` (package template): event table (A3), membership and
  contradiction rules, the chain and its truncation limit, seed contents and cutoff, live actions and
  dedup, evidence format and verification, delta groups, the CLI, and how to debug.
- `src/kairos_defense/store/README.md`: `DuckCaseMemory` (`store/ledger_duck.py`), the ledger DDL
  and macro in `ddl.py`, the single-writer lock, and that a read-write open blocks other processes
  (fact 5).
- `src/kairos_defense/README.md` (it documents `cli.py` and `ports.py`):
  - `STUBS` is now `replay`, `api` and `mcp` (lines 9 and 34);
  - the new commands in `cli_memory.py` and `cli_memory_view.py`;
  - the `CaseMemory` additions and the typed `CaseSnapshot` (line 44);
  - the stub test now covers three stubs (line 91);
  - a phase 6 changelog line.
- Root `README.md` "Status": a phase 6 row, and the memory commands in "Works today".
- `docs/PROGRESS.md`: a session-log entry and the one-line exit-check evidence. The Status cell is
  left to the autopilot.
- `docs/DECISIONS.md`: D-092 to D-101 (A1–A10).
- `config/README.md` is unchanged: no config keys change (`paths.memory`, `paths.exports`, `signing`
  and `paths.cache` already exist).

## Risks and mitigations

| # | Risk | Mitigation |
|---|---|---|
| R1 | Canonical JSON drifts between write and read (float text, JSON reformatting, timestamp precision), so an intact ledger "fails" | Values are rounded before storing; `object_json` is hashed as a parsed object; the round-trip test over 40 random events; fact 5 (verbatim JSON, exact µs and doubles) |
| R2 | NaN in match features or `warp_ratio` breaks canonical JSON or the phase 7 API | `json_safe` maps NaN and inf to null in `actions.py`; canonical JSON rejects them loudly; a test |
| R3 | DuckDB's process lock: `make demo` (phase 7) holds `memory.duckdb`, so the CLI's reseed and verify cannot open it | Clear exit-1 messages; `verify-evidence` SKIPs the ledger check instead of failing; phase 7 implements the D-010 admin endpoints. Phase 6 runs no server |
| R4 | The terminal demo links CHARLIE, not ALPHA-260502 (accepted phase 4 gap) | The SPEC unit test uses the scenario's three ids and does not depend on the matcher; A7 and REPORT.md say what the real matcher proposes; no number is faked |
| R5 | Time-zone mistakes (local vs UTC) in "known then" and "10:00 local" | The library stores naive UTC; the CLI refuses naive input; tests state both 09:00 and 10:00 local with explicit −05:00 and check them against the scenario's `assessed_local` |
| R6 | `-k memory` misses a test, or matches unrelated ones | Every new file is `test_memory_*.py` (fact 7); EXIT_CHECK.md records the collected count |
| R7 | The append-only scan passes vacuously, or flags a docstring | A self-test of the pattern; library docstrings avoid literal mutation statements; tests (outside `src/`) may tamper with raw SQL by design |
| R8 | A seed of 4,681 rows is slow with per-row inserts | `append_many` seals in Python and inserts one DataFrame in one transaction; the elapsed time is printed in the evidence |
| R9 | Module size (> 400 lines) in evidence or the CLI | Split up front: `evidence.py` + `evidence_html.py`, `cli_memory.py` + `cli_memory_view.py` |
| R10 | Gate test count | −3 stub cases, +≈ 88 new; no skips; exact arithmetic in REPORT.md |
| R11 | Approving into the closed DELTA case may look like reopening it | Status stays `closed` until an analyst records `reopen` (never automatic); the snapshot shows both the April decision and the new links |
| R12 | A crash mid-reseed leaves a broken ledger | Reseed builds and verifies a temp file, then uses `os.replace`; the old file is kept until the new one verifies |

## Out of scope

- The REST routes, WebSocket `ledger` messages and admin reset/reseed endpoints (§16.4, D-010): phase 7.
  `memory reseed` calling `POST /api/admin/reseed` when the API runs comes with them.
- Writing ledger events from the live replay loop at the replay clock (§15.6): phase 7 calls
  `actions.py`. It also decides which case a live proposal targets and whether tonight's incident
  itself is linked as a member. In phase 6 the query incident is recorded as provenance
  (`query_incident`), and members are the linked past incidents (A3, A7).
- Case board, Evidence and Shift delta pages (§17.9): phases 7 and 8.
- Agent tools `as_of_view`, `diff_case`, `shift_delta`, `propose_link` and the MCP server (§18): phase
  9. A6's actor rules already restrict `agent:` to `match_proposed`.
- `linked_clue` claims from report recall (§15.1 predicate list): no phase asks for them yet.
- Retention policy (§23, real deployments) and the `KairosCaseMemory` adapter (§22).
- No §19 metric and no eval change; `make eval` and `check_targets.py` are not in the phase 6 gate.

## Review changes

<!-- filled in when a reviewer's blocking issues are resolved -->
