# Phase 6: exit-check evidence

Run on the dev laptop, 2026-10-28, against `data/` from `make data index models` (seed 42) and the
committed `models/fusion_v1.json`. Every command below exited as shown. Outputs are trimmed, with
nothing changed. No command starts a server. The commands rewrite only git-ignored files:
`data/memory.duckdb`, `data/cache/memory_demo.duckdb`, `data/cache/kd_tamper/` and `exports/`.

| Criterion (SPEC §20) | Command | Result |
|---|---|---|
| Reseed the ledger | `uv run kairos-defense memory reseed` | PASS: 4,681 rows (1,866 incidents, 949 reports, 1,864 assessments, 1 case, 1 decision), cutoff 2026-08-29 02:40:06Z, head seq 4,681 `a361b4bf…5e923`, 0.14 s |
| Chain verifies | `uv run kairos-defense memory verify` | PASS: "chain intact: 4,681 rows", exit 0 |
| Memory tests | `uv run pytest tests/unit -q -k memory` | PASS: 92 passed (all 92 are the new `test_memory_*.py` tests) |
| The three gate commands chained with `&&`, exactly as SPEC writes them | see first block | PASS: exit 0, 7.8 s |
| No UPDATE or DELETE on `ledger` in `src/` (scan); tampering caught at the right seq | part of `-k memory` | PASS: `test_no_update_or_delete_on_ledger_in_src`, `test_scan_pattern_catches_mutations`, and `test_tamper_*` / `test_deleted_row_*` (seqs 6, 3, 8, 5); CLI: "chain broken at seq 7" |
| DELTA as of 2026-04-20 10:00 local: `hobbyist`, closed, no links | `memory show CASE-P1-DELTA-260419 --as-of 2026-04-20T10:00-05:00` | PASS: closed; members 1; links none; hobbyist (DELTA BDOC); planted report present. Unit test `test_delta_known_at_1000_local_hobbyist_closed_no_links` |
| Case unknown before 09:10 local | `memory show … --as-of 2026-04-20T09:00-05:00` | PASS: "unknown: no such case yet", head seq 3,567 |
| After approving the three demo links: three members, and the diff lists them | `test_three_demo_links_make_three_members_and_diff_lists_them`; `memory demo --approve` | PASS: unit test with the scenario's three ids (DELTA, ALPHA-260303, ALPHA-260502). The terminal demo with the real matcher links DELTA, ALPHA-260303 and CHARLIE-260710 (accepted phase 4 gap, D-081): members 3, diff lists 3 `members_added` (one already a member) |
| Terminal demo: "known then" and "known now" side by side | `uv run kairos-defense memory demo --approve` | PASS: side-by-side table and grouped diff, exit 0, 1.7 s |
| The real ledger is untouched by the demo | `memory verify` (again) | PASS: same head seq 4,681 and hash `a361b4bf…5e923` |
| Shift delta grouping | `memory delta --since 2026-08-28T00:00-05:00 --ledger data/cache/memory_demo.duckdb` (and `--installation BRAVO`) | PASS: 13 items in groups (incidents, reports, proposals, links_approved, assessments_added, exports, models); BRAVO: 7 items. Unit test `test_delta_groups_and_refs` |
| Export needs approval | `export --case CASE-P1-DELTA-260419 --ledger data/cache/memory_demo.duckdb` | PASS: exit 1 "approval required (rule 8)", nothing written |
| Export with approval | the same with `--approve` | PASS: `exports/CASE-P1-DELTA-260419_20260829T024136/`, signed (key `0baa8950118c86eb`), records head seq 4,689, appended seq 4,690 |
| Evidence verify passes | `verify-evidence exports/<dir> --ledger data/cache/memory_demo.duckdb` | PASS: files, signature, chain and ledger all PASS, exit 0 |
| Evidence verify fails after editing one file | copy to `data/cache/kd_tamper`, append one byte to `case.html`, verify | PASS: `files` FAIL ("case.html: missing or hash differs"), exit 1 |
| Whole suite | `make check`; `make test-all` | PASS: `make check` 586 fast tests passed (497 at the start: 497 − 3 removed stub cases + 92 new); `make test-all` 601 passed in 3 min 25 s |

## uv run kairos-defense memory reseed && uv run kairos-defense memory verify && uv run pytest tests/unit -q -k memory
```text
kairos-defense memory reseed → /Users/ndkx/work/kairos_defence/data/memory.duckdb (verified)
┃ item                        ┃                                                                      value ┃
│ assessment_asserted         │                                                                      1,864 │
│ case_opened                 │                                                                          1 │
│ decision_recorded           │                                                                          1 │
│ incident_recorded           │                                                                      1,866 │
│ report_recorded             │                                                                        949 │
│ rows                        │                                                                      4,681 │
│ cutoff (live first contact) │                                                       2026-08-29 02:40:06Z │
│ head                        │ seq 4,681 a361b4bfe3b24afcf93d5220040d3a162bd522edfe14ddbc2964d9475635e923 │
│ elapsed                     │                                                                     0.14 s │
chain intact: 4,681 rows in /Users/ndkx/work/kairos_defence/data/memory.duckdb, head seq 4,681 hash
a361b4bfe3b24afcf93d5220040d3a162bd522edfe14ddbc2964d9475635e923 recorded 2026-08-29 00:33:38Z
........................................................................ [ 78%]
....................                                                     [100%]
92 passed, 494 deselected in 6.23s
(exit 0; wall time 7.8 s)
```

Fast-test arithmetic for the gate's no-drop check: 497 fast tests at the start of the run, minus the
3 parametrized `test_stub_names_its_phase` cases for the removed `memory`, `export` and
`verify-evidence` stubs, plus 92 new tests = **586**. No skip or xfail markers were added.

## uv run kairos-defense memory show CASE-P1-DELTA-260419 --as-of 2026-04-20T10:00-05:00
```text
CASE-P1-DELTA-260419 as known at 2026-04-20 10:00 local (15:00Z)
│ status            │ closed                                                     │
│ members           │ 1: P1-DELTA-260419                                         │
│ links             │ none                                                       │
│ pending proposals │ none                                                       │
│ assessments       │ hobbyist (DELTA BDOC, seq 3569)                            │
│ contradictions    │ none                                                       │
│ decisions         │ close: assessed hobbyist (2026-04-20 09:10 local (14:10Z)) │
│ reports           │ R-P1-DELTA-260419-1 (security_forces, B2)                  │
│ exports           │ none                                                       │
│ chain head        │ seq 3570 f24296f32d2b0c67…                                 │
```
At `--as-of 2026-04-20T09:00-05:00`: `status │ unknown: no such case yet`, `chain head │ seq 3567`.

## uv run kairos-defense memory demo --approve
```text
query DEMO-BRAVO-0828-T1 at T+90 s · model fusion-v1 · real top 3: P1-DELTA-260419 1.000, P1-ALPHA-260303 0.999,
P1-CHARLIE-260710 0.997
CASE-P1-DELTA-260419: known then and known now
┃                   ┃ known then                                     ┃ known now                                       ┃
┃ item              ┃ 2026-04-20 09:10 local (14:10Z)                ┃ 2026-08-28 21:41 local (02:41Z)                 ┃
│ status            │ closed                                         │ closed                                          │
│ members           │ 1: P1-DELTA-260419                             │ 3: P1-DELTA-260419, P1-ALPHA-260303,            │
│                   │                                                │ P1-CHARLIE-260710                               │
│ links             │ none                                           │ P1-DELTA-260419 (analyst:demo, seq 4687)        │
│                   │                                                │ P1-ALPHA-260303 (analyst:demo, seq 4688)        │
│                   │                                                │ P1-CHARLIE-260710 (analyst:demo, seq 4689)      │
│ pending proposals │ none                                           │ none                                            │
│ assessments       │ hobbyist (DELTA BDOC, seq 3569)                │ unknown (ALPHA BDOC, seq 3138)                  │
│                   │                                                │ hobbyist (DELTA BDOC, seq 3569)                 │
│                   │                                                │ unknown (CHARLIE BDOC, seq 4256)                │
│ decisions         │ close: assessed hobbyist (2026-04-20 09:10 …)  │ close: assessed hobbyist (2026-04-20 09:10 …)   │
│ reports           │ R-P1-DELTA-260419-1 (security_forces, B2)      │ R-P1-ALPHA-260303-1 … -3, R-P1-DELTA-260419-1,  │
│                   │                                                │ R-P1-CHARLIE-260710-1 … -3 (7 reports)          │
│ chain head        │ seq 3570 f24296f32d2b0c67…                     │ seq 4689 5b9397051aa77121…                      │
diff CASE-P1-DELTA-260419: (known then, known now]
│ members_added │ 4687 │ 2026-08-28 21:41 local (02:41Z) │ P1-DELTA-260419 linked … (proposal 4684) · already a member │
│ members_added │ 4688 │ 2026-08-28 21:41 local (02:41Z) │ P1-ALPHA-260303 linked … (proposal 4685) · new member       │
│ members_added │ 4689 │ 2026-08-28 21:41 local (02:41Z) │ P1-CHARLIE-260710 linked … (proposal 4686) · new member     │
│ proposals     │ 4684 │ 2026-08-28 21:41 local (02:41Z) │ P1-DELTA-260419 proposed … (rank 1, score 1.000)            │
│ proposals     │ 4685 │ 2026-08-28 21:41 local (02:41Z) │ P1-ALPHA-260303 proposed … (rank 2, score 0.999)            │
│ proposals     │ 4686 │ 2026-08-28 21:41 local (02:41Z) │ P1-CHARLIE-260710 proposed … (rank 3, score 0.997)          │
│ claims_added  │ 4256 │ 2026-07-11 13:03 local (18:03Z) │ P1-CHARLIE-260710 assessed 'unknown' by CHARLIE BDOC        │
│ facts         │ 4245 │ 2026-07-10 21:44 local (02:44Z) │ incident P1-CHARLIE-260710 at CHARLIE (1 track(s))          │
│ facts         │ 4246 │ … 4249 … 4255 (three CHARLIE reports)                                                         │
│ facts         │ 4683 │ 2026-08-28 21:41 local (02:41Z) │ model fusion-v1 registered (c5e17f03ed25…)                  │
3 proposals approved; scratch ledger /Users/ndkx/work/kairos_defence/data/cache/memory_demo.duckdb (4,689 rows, chain
intact); /Users/ndkx/work/kairos_defence/data/memory.duckdb is unchanged
```
(The table rows' separators and a few long cells are shortened with "…". The full output has one
row per report.)

## uv run kairos-defense memory verify (after the demo)
```text
chain intact: 4,681 rows in /Users/ndkx/work/kairos_defence/data/memory.duckdb, head seq 4,681 hash
a361b4bfe3b24afcf93d5220040d3a162bd522edfe14ddbc2964d9475635e923 recorded 2026-08-29 00:33:38Z
```

## uv run kairos-defense memory delta --since 2026-08-28T00:00-05:00 --ledger data/cache/memory_demo.duckdb
Run after the export below, so the export appears too.
```text
shift delta all bases (UTC): 13 items, head seq 4690
│ incidents         │ 4681 │ 2026-08-29 00:33Z │ incident DELTA-260828-1915 at DELTA (1 track(s))           │
│ incidents         │ 4682 │ 2026-08-29 02:40Z │ incident DEMO-BRAVO-0828 at BRAVO (1 track(s))             │
│ reports           │ 4680 │ 2026-08-29 00:29Z │ report R-DELTA-260828-1915-1 (bdoc_log, B2) about …       │
│ proposals         │ 4684 │ 2026-08-29 02:41Z │ P1-DELTA-260419 proposed for CASE-P1-DELTA-260419 …        │
│ proposals         │ 4685 │ 2026-08-29 02:41Z │ P1-ALPHA-260303 proposed for CASE-P1-DELTA-260419 …        │
│ proposals         │ 4686 │ 2026-08-29 02:41Z │ P1-CHARLIE-260710 proposed for CASE-P1-DELTA-260419 …      │
│ links_approved    │ 4687 │ 2026-08-29 02:41Z │ P1-DELTA-260419 linked to CASE-P1-DELTA-260419 by …        │
│ links_approved    │ 4688 │ 2026-08-29 02:41Z │ P1-ALPHA-260303 linked …                                   │
│ links_approved    │ 4689 │ 2026-08-29 02:41Z │ P1-CHARLIE-260710 linked …                                 │
│ assessments_added │ 4678 │ 2026-08-28 13:13Z │ DELTA-260827-2241 assessed 'hobbyist' by DELTA BDOC        │
│ assessments_added │ 4679 │ 2026-08-28 23:37Z │ DELTA-260827-1925 assessed 'hobbyist' by DELTA BDOC        │
│ exports           │ 4690 │ 2026-08-29 02:41Z │ CASE-P1-DELTA-260419 exported (9ae2b669c842…)              │
│ models            │ 4683 │ 2026-08-29 02:41Z │ model fusion-v1 registered (c5e17f03ed25…)                 │
```
With `--installation BRAVO`: `shift delta BRAVO (local, UTC-5): 7 items` (the live incident, three
proposals and three approvals; no model row, no DELTA-only rows).

## uv run kairos-defense export --case CASE-P1-DELTA-260419 [--approve] --ledger data/cache/memory_demo.duckdb
```text
$ uv run kairos-defense export --case CASE-P1-DELTA-260419 --ledger data/cache/memory_demo.duckdb
approval required (rule 8): an export needs an explicit human approval; rerun with --approve. Nothing was written.
(exit 1; exports/ did not exist afterwards)
$ uv run kairos-defense export --case CASE-P1-DELTA-260419 --approve --ledger data/cache/memory_demo.duckdb
exported /Users/ndkx/work/kairos_defence/exports/CASE-P1-DELTA-260419_20260829T024136/ · manifest sha256
9ae2b669c84271ab990828b3a6f3e07acc82bc90bba28ef06bee8d0a2938f632 · signed, key 0baa8950118c86eb · records head seq 4,689
· appended evidence_exported seq 4,690
(exit 0; files: case.html 89 kB, case.json 49 kB, manifest.json, manifest.sig, pubkey.pem)
```

## uv run kairos-defense verify-evidence exports/CASE-P1-DELTA-260419_20260829T024136 --ledger data/cache/memory_demo.duckdb
```text
│ files     │ PASS   │ 3 files match the manifest: case.html, case.json, pubkey.pem │
│ signature │ PASS   │ Ed25519 over manifest.json, key 0baa8950118c86eb             │
│ chain     │ PASS   │ 21 rows recompute and link; head seq 4689                    │
│ ledger    │ PASS   │ 21 rows equal the ledger's; chain intact over 4,690 rows     │
PASS: the package verifies
(exit 0)
```

## Editing one file, then verifying
```text
$ rm -rf data/cache/kd_tamper && cp -R exports/CASE-P1-DELTA-260419_20260829T024136 data/cache/kd_tamper \
    && printf x >> data/cache/kd_tamper/case.html \
    && uv run kairos-defense verify-evidence data/cache/kd_tamper --ledger data/cache/memory_demo.duckdb
│ files     │ FAIL   │ case.html: missing or hash differs                       │
│ signature │ PASS   │ Ed25519 over manifest.json, key 0baa8950118c86eb         │
│ chain     │ PASS   │ 21 rows recompute and link; head seq 4689                │
│ ledger    │ PASS   │ 21 rows equal the ledger's; chain intact over 4,690 rows │
FAIL: the package does not verify
(exit 1)
```

## make check and make test-all
```text
$ make check
ruff check . / ruff format --check . : clean
586 passed, 15 deselected in 23.99s
web: lint, typecheck, Vitest 5 passed
$ make test-all
601 passed in 204.63s (0:03:24)
(exit 0; 586 fast + 15 slow, including tests/slow/test_full_memory.py)
```
