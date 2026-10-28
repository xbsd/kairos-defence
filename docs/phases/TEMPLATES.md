# Documentation templates

Every phase leaves three files in `docs/phases/phase-NN/`, and every package keeps a README.
The autopilot gate fails a phase whose documents are missing or nearly empty.

## PLAN.md

```markdown
# Phase N: <title>, plan

## Goal
## Inputs read
<!-- SPEC sections, previous REPORT.md, PROGRESS.md notes -->
## Assumptions and decisions
<!-- each one is also recorded in docs/DECISIONS.md during the build -->
## Work breakdown
<!-- ordered steps; files to create or change in each -->
## Tests
<!-- test name: what it asserts -->
## Exit-check mapping
<!-- criterion (SPEC §20) → command → evidence it will produce -->
## Documentation to write or update
## Risks and mitigations
## Out of scope
## Review changes
<!-- filled in when a reviewer's blocking issues are resolved -->
```

## REPORT.md

```markdown
# Phase N: <title>, report

Status: done | blocked · Date: YYYY-MM-DD · Commits: <short SHAs>

## Summary
<!-- 3 to 5 lines a newcomer can read first -->
## What was built
<!-- module → purpose → key files -->
## Decisions and deviations from SPEC
<!-- link D-xxx entries in docs/DECISIONS.md -->
## Tests
<!-- new or changed tests; pass counts; slow tests -->
## Exit check
<!-- criterion → pass or fail → one-line evidence; full output in EXIT_CHECK.md -->
## Metrics
<!-- evaluation numbers when relevant, against targets and the previous phase -->
## Known issues and follow-ups
## How to debug this phase
<!-- entry points, logs, commands to reproduce, likely failure points -->
## Fix attempts
<!-- appended by fix steps: cause, change, evidence -->
```

## EXIT_CHECK.md

````markdown
# Phase N: exit-check evidence

| Criterion (SPEC §20) | Command | Result |
|---|---|---|

## <command>
```text
$ <command>
<trimmed output, at most about 60 lines>
```
````

## Package README (`src/kairos_defense/<package>/README.md`, `web/README.md`)

```markdown
# kairos_defense.<package>

<one-line purpose>

## Responsibilities
## Public API
<!-- function or class → one line, with units and array shapes -->
## Data in and out
<!-- DuckDB tables, LanceDB tables, files -->
## How it works
<!-- 5 to 10 lines; link SPEC sections -->
## Configuration
<!-- config keys this package reads -->
## Tests
<!-- where they live and how to run them -->
## Gotchas
## Changelog
<!-- phase → change -->
```
