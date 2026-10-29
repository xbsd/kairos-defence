# Kairos Defense demo runbook

A four-minute presenter's script for the Command Center, built from SPEC Appendix B and checked
against this build (phase 9). Everything on screen is synthetic: invented installations, flights,
reports and people-free paperwork. Nothing needs the internet.

Times below come from the recorded Director run at 1× (`reports/figures/ui/director_1x.json`,
phase 8) plus the phase 9 encore. "T+N" is seconds after the first radar contact of the live
incident `DEMO-BRAVO-0828` (21:40:06 local at Installation Bravo, 28 Aug 2026).

## Before the audience arrives

1. Build from scratch, or reuse a verified build:
   ```bash
   make clean && make data index models eval   # about 15 to 25 minutes on a laptop
   ```
   `make eval` ends with "demo assertion failed: live_top3_incidents …" and exit 1. That one row
   is an accepted gap (phase 4 `GAPS.md`, D-081): ALPHA-260502 ranks fifth at T+90 instead of
   third. Every other row passes, the swarm encore included (`check_targets.py 9` shows WARN for
   that row and PASS for the rest).
2. Reset the case memory and check its chain:
   ```bash
   uv run kairos-defense memory reseed && uv run kairos-defense memory verify
   ```
   `memory verify` prints "chain intact: N rows …".
3. Serve the app (one process, offline):
   ```bash
   make demo        # builds web/dist, fills the replay cache, serves http://localhost:8000
   ```
   Open http://localhost:8000 in Chrome, press **F** for full screen.
4. Open **Pages → Eval** and confirm the demo assertions: every row passes except
   `live_top3_incidents` (shown with its accepted-gap note), and Swarm top-1 meets its target.
5. Open **Live watch** for Installation Bravo (the root page opens it) and press **D** for Director
   mode. Press **R** to reset to T+0 if you have been exploring.
6. Rehearse twice on the presentation machine and projector. If the frame rate drops, press **M**
   (reduce motion) or turn on **Performance mode** in the command bar: the story still works,
   every number stays, only camera flights, bloom, particles and grain go.

## The recorded demo video

`docs/demo/kairos-defense-demo.mp4` (about 1 min 45 s, 1920 × 1080) is the same story recorded from
the running app with a narration layer: chapter titles, callouts that explain each mechanism and a
visible pointer for every click. Show it when there is no time for a live run, or send it ahead.
`make demo-video` records it again (its own scratch ledger on port 8766; the real ledger is
untouched). In the cloud container it records in slow motion (`DEMO_SLOW=5`, about 9 minutes);
on a laptop with a GPU `DEMO_SLOW=1 make demo-video` takes about 2 minutes (D-168).

## Director keys

| Key | Action |
|---|---|
| D | Director mode on or off (from any page) |
| Space | Play or pause the replay clock |
| → / ← | Next or previous beat (page beats start only on →) |
| R | Reset: empty the live tables, reseed the memory, back to T+0 and beat 1 |
| M | Reduce motion |
| F | Full screen |
| ? | Keyboard shortcuts |

A thin rail at the bottom shows progress through the nine beats; one plain-language caption sits at
the bottom center. Director never approves, rejects or exports anything by itself: those are your
clicks (rule 8).

## Script (about four minutes)

| # | Beat | When | What the audience sees | Say |
|---|---|---|---|---|
| 1 | Detection | T+0 (21:40:06) | First radar contact at BRAVO's north fence, out of the radar shadow; the Stream's first row | "A drone just came out of the radar shadow at BRAVO's north fence. Tonight, every base sees only its own night." |
| 2 | Recording | T+15 | Recorder total and ledger blocks growing: every detection is written as it arrives | (let it run) |
| 3 | Recognition | T+45 | The first matches: 45 seconds of track is enough to search | "Forty-five seconds of track is enough to start. Kairos Defense compares the shape of this flight with every past flight at every base, even one flown slower…" |
| – | Loiter | T+80 to T+87 | The Signals loiter marker as the drone settles into its orbit | "…and by the time it settles into its orbit…" |
| 4 | Time warp | T+90 | Afterglow ghosts of the past flights, the time-warp lens morphing from Same time to Warped | "…the same flights it has seen before stay on top. DELTA's flight was flown faster; the lens shows how the shapes line up." |
| 5 | Forecast | T+105 | Dotted exit path and the pulsing recovery zone, "Predicted recovery zone, 2.2 km northwest, from 3 matches" | "Those flights ended about two kilometers northwest, in BRAVO's radar shadow. That is where the operator will recover it." |
| 6 | Recall | T+120 (21:42:06) | The April DELTA report resolves at the lower left with a beam to County Rd 12 inside the zone | "And this April report from DELTA, which nobody connected, mentions a white pickup on the same county road that runs through tonight's predicted zone." |
| 7 | Known then and now | → | Case board: toggle **Known then** / **Known now** | "DELTA closed this as a hobbyist. Here is exactly what was known then, and what changed." Approve the proposed links (your clicks). |
| 8 | Evidence | → | Evidence page: **Export evidence package** shows per-file hashing, then **Verify package** | "Every step is signed and replayable." |
| 9 | Encore: Swarm view | → | ECHO's five-drone swarm with its formation edges and the matched GOLF swarm as an afterglow ghost, aligned by DTW time; descriptor curves | "Same choreography, six weeks apart, in another region." |

The live top 3 at T+90 is what the matcher computes (DELTA, ALPHA-260303, CHARLIE-260710; the
captions and the lens show the computed values, never scripted ones). The encore compares the live
swarm `DEMO-SWARM-ECHO-0614` (ECHO, 14 Jun 2026) with every earlier swarm; `S1-GOLF-260503`
(GOLF, 3 May 2026, another region) ranks first.

## Fallbacks

- **Skip ahead:** press → for the next beat. Results are cached per replay second
  (`kairos-defense replay --precompute`, run by `make demo`), so jumps are instant.
- **Something looks wrong:** press **R** (resets the live tables and reseeds the memory through the
  running API), then **D**.
- **Reset between runs** without restarting the server:
  ```bash
  uv run kairos-defense replay --reset     # empties only the live_* scratch tables
  uv run kairos-defense memory reseed      # regenerates the memory file from seed
  ```
  While `make demo` runs, both go through the API (`POST /api/admin/reset`, `/api/admin/reseed`),
  because DuckDB allows one writing process per file (D-010). The running app never edits or
  deletes ledger rows.
- **Slow projector machine:** **M** or Performance mode; the encore and every page work the same.
- **Port 8000 busy:** stop the other server (`lsof -i :8000`), or run
  `uv run kairos-defense api --static web/dist --port 8001` after `make demo`'s build step.

## Optional: the agent tools (MCP)

Kairos Defense exposes read-only tools to any MCP client. In Claude Code:

```bash
claude mcp add kairos-defense -- uv run kairos-defense mcp
```

Then ask, for example, "Which past flights look like DEMO-BRAVO-0828 at 120 seconds?" or "What did
the DELTA case look like on 2026-04-20 at 10:00 local?". The six read-only tools are
`find_similar_flights`, `recall_reports`, `forecast_recovery`, `as_of_view`, `diff_case` and
`shift_delta`. The two proposal tools (`propose_link`, `propose_evidence_export`) appear only with
`uv run kairos-defense mcp --allow-proposals`, and even then they only propose: a link proposal is a
`match_proposed` event an analyst approves in the Case board, and an export proposal changes
nothing until someone runs the export with approval. To check the server by hand:

```bash
timeout 120 uv run python -m kairos_defense.agent.probe -- make mcp
```

## Likely questions

- **How is this different from detection vendors' dashboards?** One memory across all bases and
  vendors, tied to the written record: the matcher, the reports and the case history live together.
- **Why DTW?** The same operator flies at different paces; dynamic time warping matches the shape of
  a flight whatever its speed (the time-warp lens shows the alignment).
- **What about privacy?** Flights, not people: nothing identifies a person; humans approve every
  link and export; real use needs 10 U.S.C. 130i-compliant retention (SPEC §23).
- **Is any of this real?** No. Every installation, coordinate, flight, report and name is synthetic.
- **Where does KDB-X come in?** The same product on one engine: KDB-X for the tick data and
  temporal similarity search, Kairos for the signed temporal memory (SPEC §22). Only adapters change.

## Checklist

- [ ] `make eval` run on this machine; Eval page shows the demo rows (one accepted gap).
- [ ] `memory reseed` and `memory verify` done; "chain intact".
- [ ] `make demo` serving on :8000; Chrome full screen; Director rehearsed twice.
- [ ] Projector frame rate acceptable, or Performance mode on.
- [ ] Optional: `claude mcp add kairos-defense -- uv run kairos-defense mcp` tested.
