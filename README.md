# Kairos Defense

A shared memory of drone behavior across military installations. **This is a demo product: all data is
synthetic.**

![Live watch, two minutes into the demo: tonight's drone orbiting Bravo's fuel farm, the amber ghosts of matched past flights, the dotted recovery forecast on County Rd 12 and the linked Delta report](docs/guide/img/live-watch-t120.png)

When a drone appears at one base, Kairos Defense answers one question while it is still in the air:
**have we seen this before, and what happened then?** It matches the live flight against every past
flight at every base, pulls up the reports written about those flights, predicts where the drone
will be recovered, and keeps a tamper-evident record of what was known when. An analyst approves
every link and every export.

**Watch the narrated demo (1 min 45 s):** [docs/demo/kairos-defense-demo.mp4](docs/demo/kairos-defense-demo.mp4)

## What it does

| | |
|---|---|
| **Recognize** | Compares the shape of the live track with every past track, even one flown faster or slower (dynamic time warping), then weighs radio type, approach, time of night, launch area, orbit and altitude. Every match comes with reasons. |
| **Recall** | Finds the written reports about the matched flights (meaning plus keyword search) and highlights shared clues, such as a vehicle on a road. |
| **Anticipate** | Forecasts where tonight's drone will be recovered, from how the matched flights ended. |
| **Remember** | An append-only case memory with two clocks (when something was true, when it was learned), hash-chained so tampering shows. Any case can be replayed as it was known at any moment. |
| **Formations** | Recognizes the choreography of drone swarms seen before, even in another region. |
| **Prove** | Exports signed evidence packages that anyone can verify, and a "what changed" brief for the next shift. |

## Quick start

You need git, [uv](https://docs.astral.sh/uv/), Node 22 LTS and a C compiler with OpenMP (on macOS:
`xcode-select --install` and `brew install libomp`).

```bash
uv sync && npm --prefix web install
make data index models   # about 3 minutes: the synthetic world, its indexes and the models
make eval                # measures everything below; writes reports/eval_<date>.md
make demo                # then open http://localhost:8000 and press D for Director mode
```

`make eval` exits with status 1 because of the one known demo gap described under Results; the
report is still written. Everything runs offline.

**Live mode.** `make live`, then open <http://127.0.0.1:8000/live>, pick a scenario (for example
*Returning prober*, P1, Bravo, 20×) and press **Launch**: a separate simulator flies a new flight
and streams only its sensor detections; the app forms the incident, matches it every 5 s, learns
it when it closes, and **Reveal who flew** says afterwards whether it was recognized. **DTW
workbench** under the matches replays the matcher's real computation in slow motion.
`uv run kairos-defense live check` scores all five scenarios headless. See
[the user guide's section 13](docs/USER_GUIDE.md#13-live-mode).

| Command | What it does |
|---|---|
| `make check` | Lint, type checks and the fast tests (Python and web) |
| `make test-all` | Every Python test, slow ones included |
| `make dev` | API and web app with hot reload |
| `make e2e` | Browser tests, screenshots and accessibility checks (first time: `npx --prefix web playwright install chromium`) |
| `make mcp` | MCP server for AI assistants: `claude mcp add kairos-defense -- uv run kairos-defense mcp` |
| `make demo-video` | Re-records the narrated demo video |
| `make help` | Every target |

## Results

Measured by `make eval` on the synthetic dataset:

| Measure | Result | Target |
|---|---|---|
| Same operator in the top 5 at T+120 s (Recall@5) | 1.00 | ≥ 0.80 |
| Same operator in the top 3 by T+90 s | 96% | ≥ 70% |
| A copycat ranked above every true match | 0% | ≤ 5% |
| Gain of shape matching over a simple baseline (DTW lift) | +0.52 | ≥ +0.10 |
| Clue-bearing reports retrieved in the top 5 | 1.00 (65 of 65) | ≥ 0.70 |
| Recovery forecast, median error at T+90 s | 340 m | ≤ 400 m |
| Correct swarm ranked first | 1.00 (4 of 4) | ≥ 0.80 |

**Known gap.** The demo script expects three named flights in the top 3 at T+90 s. All four top
matches are flights by the same operator, but the third is CHARLIE 07-10 (planted as a weaker match,
because it circles a different asset) and ALPHA 05-02 ranks fifth. At 90 seconds the drone's
target is not yet reliable evidence, so the matcher was not tuned to the demo to fix it. See
[phase 4 GAPS](docs/phases/phase-04/GAPS.md) and decision D-081 in [DECISIONS](docs/DECISIONS.md).

## Documentation

| Document | For | What it covers |
|---|---|---|
| [User guide](docs/USER_GUIDE.md) | New users, operators, analysts | Install, every screen with screenshots, the demo, evidence, CLI, MCP, configuration, troubleshooting |
| [One-pager](docs/ONE_PAGER.md) | Non-technical readers | The problem, what it does, the demo in five beats |
| [Product overview (Word)](docs/Kairos-Defense-Overview.docx) | Stakeholders | An 8-page illustrated overview |
| [Glossary](docs/GLOSSARY.md) | Everyone | Military, security and counter-drone terms in plain language (recovery zone, BDOC, source grades …) |
| [Demo runbook](docs/DEMO.md) | Presenters | Preparation, the four-minute script, keys, fallbacks, likely questions |
| [Rollback guide](docs/ROLLBACK.md) | Maintainers | How the history and tags are organized; how to inspect or roll back a phase |
| [Specification](docs/SPEC.md) | Builders | The full product and build specification |
| [Progress](docs/PROGRESS.md), [decisions](docs/DECISIONS.md), [phase index](docs/phases/INDEX.md) | Everyone | What was built when, why, and the evidence |

## Code layout

| Path | Contents |
|---|---|
| [`src/kairos_defense/`](src/kairos_defense/README.md) | Command line, interfaces (ports), geometry, seeding |
| [`sim/`](src/kairos_defense/sim/README.md) | Synthetic world: bases, flights, sensors, swarms, reports, assessments |
| [`store/`](src/kairos_defense/store/README.md) | DuckDB and LanceDB adapters, and the guard that keeps ground truth out of the app |
| [`features/`](src/kairos_defense/features/README.md) | Flight-behavior channels, signatures, search windows, swarm descriptors |
| [`match/`](src/kairos_defense/match/README.md) | Prefilter, DTW re-rank, fusion model, explanations |
| [`recall/`](src/kairos_defense/recall/README.md), [`forecast/`](src/kairos_defense/forecast/README.md) | Report search and clue linking; the recovery forecast |
| [`memory/`](src/kairos_defense/memory/README.md) | Case memory: ledger, hash chain, as-of views, diffs, evidence, shift delta |
| [`live/`](src/kairos_defense/live/README.md), [`api/`](src/kairos_defense/api/README.md) | Live replay; REST and WebSocket API |
| [`agent/`](src/kairos_defense/agent/README.md) | Agent tools and the MCP server |
| [`eval/`](src/kairos_defense/eval/README.md), [`config/`](src/kairos_defense/config/README.md) | Evaluation harness (the only code that reads ground truth); configuration models |
| [`web/`](web/README.md) | The React Command Center: 3D theater, instruments, pages, Director mode |
| `config/`, `scripts/`, `tests/` | The YAML settings, build and gate scripts, Python tests |

## How it was built

Built phase by phase with Claude Code against [the specification](docs/SPEC.md). Phases 0 to 3 were
built interactively; phases 4 to 8 by an unattended autopilot ([docs/AUTOPILOT.md](docs/AUTOPILOT.md))
in which every plan was reviewed independently and every phase passed a scripted gate; phases 9 and
10 in a Claude Code on the web session with the same gate. Each phase is tagged `phase-NN-done`, and
its plan, report and exit-check evidence are in `docs/phases/phase-NN/`.

Phases 11 and 12 added live mode (a simulated sensor feed, live matching and learning, five
scenarios scored by `kairos-defense live check`) and the DTW workbench; they were built in one
Claude Code on the web session with the same gate.

<details>
<summary>Phases 0 to 12 are done</summary>

| Phase | Title | Status |
|---|---|---|
| 0 | Scaffold | [done](docs/phases/phase-00/REPORT.md) |
| 1 | World, flights and radar | [done](docs/phases/phase-01/REPORT.md) |
| 2 | Swarms, RF, Remote ID, reports and assessments | [done](docs/phases/phase-02/REPORT.md) |
| 3 | Features, windows, Euclidean baseline and evaluation skeleton | [done](docs/phases/phase-03/REPORT.md) |
| 4 | DTW matcher and fusion model | [done](docs/phases/phase-04/REPORT.md), one accepted gap |
| 5 | Report recall and analog forecast | [done](docs/phases/phase-05/REPORT.md) |
| 6 | Case memory | [done](docs/phases/phase-06/REPORT.md) |
| 7 | Streaming API and Command Center foundation | [done](docs/phases/phase-07/REPORT.md) |
| 8 | Command Center: the memorable moments | [done](docs/phases/phase-08/REPORT.md) |
| 9 | Swarms, agent, MCP, hardening and runbook | [done](docs/phases/phase-09/REPORT.md) |
| 10 | User guide, one-pager and rollback guide | [done](docs/phases/phase-10/REPORT.md) |
| 11 | Live mode MVP: simulated sensor feed, live matching, scenarios | [done](docs/phases/phase-11/REPORT.md) |
| 12 | DTW workbench and live-mode documentation | [done](docs/phases/phase-12/REPORT.md) |

</details>

## Guardrails

Synthetic data only. Links flights, never people. Humans approve every link and export. The memory is
append-only. Searches never look past the moment of the query. Runs offline by default.
