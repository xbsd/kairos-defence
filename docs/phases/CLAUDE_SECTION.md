## Autopilot and documentation

- Unattended runs use the `phase-auto` skill, driven by `scripts/autopilot.py` (see `docs/AUTOPILOT.md`).
  In those runs never wait for approval: record assumptions in the plan and in `docs/DECISIONS.md`.
- Every phase leaves `docs/phases/phase-NN/PLAN.md`, `REPORT.md` and `EXIT_CHECK.md`
  (templates in `docs/phases/TEMPLATES.md`).
- Every package under `src/kairos_defense/`, and `web/`, has a current `README.md` (template in
  `docs/phases/TEMPLATES.md`). The root README keeps a "Status" section.
- Never push, never rewrite history, never edit `.claude/`, `scripts/autopilot.py` or
  `docs/phases/gates.json`, and never weaken or skip a test or lower a target to pass a gate.
- End-to-end tests start and stop their own servers (Playwright `webServer`), so gates never hang.
  Serving commands in exit checks (`make demo`, `make mcp`) run in the background with a time limit
  and are stopped afterwards.
- From phase 4 the gate runs `scripts/check_targets.py N`, which enforces the SPEC §19 targets from
  `reports/eval_<date>.json`; `make eval` must write the metric keys it names.
- If truly blocked, write `docs/phases/phase-NN/BLOCKED.md` (what failed, what you tried, the decision a
  human must make) and stop.
