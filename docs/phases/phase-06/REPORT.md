# Phase 6: Case memory (Kairos-lite), report

Status: done (awaiting the autopilot gate) · Date: 2026-10-28 · Commits: the single
`phase 6: case memory (Kairos-lite)` commit

## Summary

Phase 6 gives Kairos Defense a memory of what it knew and when:

- an append-only, hash-chained ledger in `data/memory.duckdb` with transaction time and valid time;
- snapshots of a case as known at any moment, contradictions that never auto-resolve, and diffs
  between two moments;
- 18 months of history seeded as it would have been learned (4,681 events in 0.14 s), with the
  planted DELTA case closed as `hobbyist` at 09:10 local on 2026-04-20;
- the §15.6 writes, with deduplicated proposals and analyst-only approvals;
- signed evidence packages that verify, and stop verifying when a byte changes;
- the shift delta, and eight real commands (`memory seed|reseed|verify|show|delta|demo`,
  `export`, `verify-evidence`).

The terminal demo prints the DELTA case "known then" (1 member, closed, no links) beside "known
now" (3 members after approving the real matcher's top 3).

## What was built

| Module | Purpose | Key files |
|---|---|---|
| Canonical JSON | §15.3 serialization and `row_hash`; 9-decimal floats rounded before storing, ISO `Z` times, NaN refused (D-095) | `memory/canonical.py` |
| Ledger rules | `normalize_event`, `validate` (event types, actor permissions, ids, supersedes), `seal`, `verify_rows`, `active_rows` (D-094, D-095) | `memory/ledger.py` |
| DuckDB adapter | `DuckCaseMemory`: §15.1 DDL and macro, one locked connection, atomic batches via pyarrow, `events`, `head`, `copy_from` (D-092, D-093) | `store/ledger_duck.py`, `store/ddl.py`, `store/guard.py` |
| Port | `CaseMemory.append_many`, `events`; the typed `CaseSnapshot` with `to_dict()` (D-093) | `ports.py` |
| Snapshots and diffs | members, pending, claims, contradictions, status, valid time; `case_diff` and groups (D-094, D-101) | `memory/asof.py`, `memory/diff.py`, `memory/views.py` |
| Seed | history before first contact, planted cases from the scenario, deterministic order (D-096) | `memory/seed.py` |
| Actions | `record_incident`, `register_model`, `propose_matches` (dedup), `decide_link`, `open_case`, `record_decision`, `retract` (D-097) | `memory/actions.py` |
| Delta | `delta(rows, since, until, installation_id)` → `ShiftDelta` (D-101) | `memory/delta.py` |
| Evidence | export with approval, Ed25519 manifest signature, verification; HTML summary with the static map (D-099) | `memory/evidence.py`, `memory/evidence_html.py` |
| CLI | the eight commands; tables (D-098, D-100) | `cli_memory.py`, `cli_memory_demo.py`, `cli_memory_view.py`, `cli.py` |
| Tests | 92 fast tests in `test_memory_*.py`, 3 slow; fixtures `seeded_p1`, `ledger_copy`; `memory_kit.py` | `tests/unit/`, `tests/slow/test_full_memory.py`, `tests/conftest.py` |

## Decisions and deviations from SPEC

- [D-092](../../DECISIONS.md): the DuckDB code lives in `store/ledger_duck.py`, not
  `memory/ledger.py` (SPEC §5 vs CLAUDE.md rule 6 and D-053); `memory/ledger.py` holds the
  store-free rules.
- [D-093](../../DECISIONS.md): two port methods (`append_many`, `events`) and a typed
  `CaseSnapshot`.
- [D-094](../../DECISIONS.md): event field conventions, membership, status, contradictions,
  actor permissions (rule 8) and id checks (rule 9).
- [D-095](../../DECISIONS.md): canonical JSON details and what `verify_chain` reports.
- [D-096](../../DECISIONS.md): the seed stops before the live incident's first contact (29
  later history events are left out: look-ahead at demo time).
- [D-097](../../DECISIONS.md): §15.6's two dedup sentences reconciled; `decide_link` accepts a
  proposal about an existing member.
- [D-098](../../DECISIONS.md): the terminal demo runs on a scratch copy. With the real matcher it
  links CHARLIE-260710 instead of ALPHA-260502 (the accepted phase 4 gap, D-081).
- [D-099](../../DECISIONS.md): evidence format and verification; the signing key comes from the
  OS CSPRNG, not the seed (rule 4 governs data).
- [D-100](../../DECISIONS.md), **deviation from the plan**: three CLI modules instead of two
  (`cli_memory_demo.py` added) to keep each module small.
- [D-101](../../DECISIONS.md), **deviation from the plan**: delta groups `retractions` and
  `models` added; `case_opened` grouped under `decisions`.
- [D-102](../../DECISIONS.md), not in the plan: `guard.refuse_truth`, because the truth scan
  forbids `is_truth_path` outside the guard and `copy_from` uses `ATTACH`.

Plan-review suggestions applied (`PLAN_REVIEW-1.json`): the tamper copy goes to
`data/cache/kd_tamper` with `rm -rf` first and `--ledger`; reseed closes the temp file and removes
stale WAL files before `os.replace`; ledger copies go through `ATTACH … (READ_ONLY)`; every
append-only pattern stays within one statement, with `ALTER TABLE ledger` added; `valid_at` takes
an explicit `known` time; `decide_link` accepts proposals about members (A6/D-097); the rule-9 test
uses "Person Name Example"; D-096 and D-099 state the base-side-only and key-dependence facts;
EXIT_CHECK.md records the collected count and the arithmetic.

## Tests

- New fast tests (92, every one selected by `-k memory`):
  - `test_memory_canonical.py` (8): sorting, separators, `Z` times, rounding, `-0.0`, NaN refused,
    numpy, unicode, a pinned digest.
  - `test_memory_ledger.py` (20): the tamper tests (written first; caught at seqs 6, 3, 8, and 5
    for a deleted row), contiguity, D-010 clock, a 40-event round trip, atomic batches, 4 threads ×
    25 appends, validation (rule 9 with "Person Name Example"), rule 8, supersedes rules, the SQL
    macro against `active_rows`, read-only, truth refused, DDL columns, schema refusal, `copy_from`.
  - `test_memory_append_only.py` (2): the scan of `src/` and the pattern's self-test.
  - `test_memory_asof.py` (10), `test_memory_diff.py` (5), `test_memory_delta.py` (5),
    `test_memory_actions.py` (9), `test_memory_evidence.py` (12).
  - `test_memory_seed.py` (10) on the generator's six P1 nights, including both SPEC tests:
    `test_delta_known_at_1000_local_hobbyist_closed_no_links` and
    `test_three_demo_links_make_three_members_and_diff_lists_them`.
  - `test_memory_cli.py` (11).
- Changed: `test_cli.py` (`BUILT` lists the three new commands; the stub test now covers `replay`,
  `api`, `mcp`), `tests/conftest.py` (`tmp_config` also moves `exports` and the signing key;
  `with_paths`; `seeded_p1`, `ledger_copy`).
- Counts: `make check` **586** fast tests pass (497 at the start − 3 removed stub cases + 92 new).
  Slow: `tests/slow/test_full_memory.py` (3) passes in 13 s; `make test-all` **601** passed
  in 3 min 25 s (509 at the end of phase 5). No skip or xfail markers were added.

## Exit check

| Criterion | Result | Evidence |
|---|---|---|
| `memory reseed && memory verify && pytest tests/unit -q -k memory` | pass | exit 0 in 7.8 s; 4,681 rows; chain intact; 92 passed |
| No UPDATE/DELETE on `ledger` in `src/`; tamper caught at the right seq | pass | scan and tamper tests in the 92 |
| DELTA at 2026-04-20 10:00 local: hobbyist, closed, no links | pass | `memory show` and the unit test |
| Three members after approving the demo links; the diff lists them | pass | unit test with the scenario's ids; real-matcher demo: 3 members, 3 `members_added` |
| Evidence verify passes, then fails after editing one file | pass | exit 0, then `files` FAIL, exit 1 |
| Delta grouping | pass | 13 items grouped, BRAVO filter 7 |
| Terminal demo "known then" / "known now" side by side | pass | `memory demo --approve` |
| Real ledger untouched by the demo | pass | head seq 4,681 `a361b4bf…` before and after |

Full output: [EXIT_CHECK.md](EXIT_CHECK.md).

## Metrics

Phase 6 has no §19 metric and no `check_targets.py` step. For the record (dev laptop): the full
seed takes 0.14 s (4,681 rows), `memory reseed` 0.7 s wall, `memory demo --approve` 1.7 s wall
(the matcher dominates), `verify_chain` over 4,690 rows is well under 0.1 s. `make eval` was not
run: no matcher, recall or forecast code changed.

## Known issues and follow-ups

- **The demo links CHARLIE-260710, not ALPHA-260502.** The shipped model's T+90 top 3 is DELTA,
  ALPHA-260303, CHARLIE-260710 (phase 4's accepted gap, D-081). The SPEC unit test uses the
  scenario's three ids and passes; the terminal demo shows what the real matcher proposes, with no
  faked numbers (rule 10).
- The real top-3 scores print as 1.000, 0.999 and 0.997: the fusion model is very confident on
  these P1 flights. Not a phase 6 change.
- DuckDB's process lock: while `make demo` (phase 7) holds `data/memory.duckdb`, `memory reseed`
  and `memory verify` exit 1 with a clear message and `verify-evidence` SKIPs its ledger check.
  Phase 7 adds the D-010 admin endpoints (`POST /api/admin/reseed`) and decides which case live
  proposals target.
- A truncated chain tail is not visible from the chain alone (README, D-095).
- `linked_clue` claims from report recall (§15.1 predicate list) are not written yet; no phase
  asks for them.

## How to debug this phase

- Entry points: `uv run kairos-defense memory reseed`, `memory verify`, `memory show CASE --as-of
  TS`, `memory demo [--approve]`, `memory delta --since TS --ledger P`, `export --case C --approve
  --ledger P`, `verify-evidence DIR --ledger P`.
- Inspect the ledger directly (read-only): `duckdb -readonly data/memory.duckdb "SELECT seq,
  recorded_at, event_type, subject_id FROM ledger_asof(TIMESTAMP '2026-04-20 15:00') WHERE
  case_id = 'CASE-P1-DELTA-260419'"`. Never edit it by hand; run `memory reseed` to reset.
- "chain broken at seq N": print rows N−1 and N and recompute
  `kairos_defense.memory.canonical.row_hash(prev_hash, row)`; a float or time that did not go
  through `normalize` is the usual cause.
- `InvalidEvent … may not write`: rule 8 permissions in `memory/ledger.py` `WRITERS`.
- "ledger in use": another process holds the file; stop it.
- Verify a demo export with `--ledger data/cache/memory_demo.duckdb`; against `data/memory.duckdb`
  its ledger check FAILs, because those rows exist only in the scratch ledger.
- Tests: `uv run pytest tests/unit -q -k memory`; slow: `uv run pytest tests/slow/test_full_memory.py`.

## Fix attempts

<!-- appended by fix steps: cause, change, evidence -->
