# Data card

`kairos-defense gen --seed 42` · phase 1 (world, flights and radar). All data is synthetic. RF, Remote ID, reports, assessments and swarms arrive in phase 2.

## Volumes against SPEC §8.11

| Metric | Value | Expected | Status |
|---|---:|---:|---|
| incidents | 1,869 | ≈1,900 | within ±15% |
| tracks | 1,869 | ≈1,950 | within ±15% |
| track_points | 541,913 | ≈1,000,000 | outside ±15% (54%) |
| rf_detections | 0 | ≈500,000 | phase 2 |
| reports | 0 | ≈1,000 | phase 2 |
| assessments | 0 | ≈1,900 | phase 2 |

Track points come in below ≈1 M: hobbyist flights last 180–720 s (mean ≈450 s), the radar detects about 80% of scans at a launch park's range (2.2 km) and dropouts remove ≈15% (D-030).

## Flights

| Actor type | Flown | Detected | Not detected (no incident) |
|---|---:|---:|---:|
| hobbyist | 1,773 | 1,773 | 0 |
| prober | 66 | 66 | 0 |
| copycat | 30 | 30 | 0 |
| **all** | 1,869 | 1,869 | 0 |

## Incidents per installation and actor type

| Installation | hobbyist | prober | copycat | total |
|---|---:|---:|---:|---:|
| ALPHA | 158 | 2 | 0 | 160 |
| BRAVO | 146 | 6 | 10 | 162 |
| CHARLIE | 160 | 9 | 0 | 169 |
| DELTA | 155 | 7 | 5 | 167 |
| ECHO | 133 | 5 | 5 | 143 |
| FOXTROT | 163 | 5 | 0 | 168 |
| HOTEL | 144 | 6 | 0 | 150 |
| INDIA | 121 | 5 | 10 | 136 |
| GOLF | 163 | 9 | 0 | 172 |
| JULIET | 129 | 5 | 0 | 134 |
| KILO | 161 | 3 | 0 | 164 |
| LIMA | 140 | 4 | 0 | 144 |

## Probers and copycats

| Actor | Pattern | Incidents | Bases | Time warp range |
|---|---|---:|---|---|
| C1 | orbit | 15 | BRAVO, DELTA | 0.74–1.40 |
| C2 | figure8 | 15 | ECHO, INDIA | 0.72–1.27 |
| P1 | orbit | 6 | ALPHA, BRAVO, CHARLIE, DELTA | 0.95–1.22 |
| P2 | lawnmower | 12 | CHARLIE, DELTA | 0.76–1.39 |
| P3 | figure8 | 16 | ECHO, FOXTROT, HOTEL | 0.73–1.40 |
| P4 | perimeter | 10 | GOLF, JULIET | 0.75–1.38 |
| P5 | hover | 12 | INDIA, KILO, LIMA | 0.71–1.32 |
| P6 | transit_dips | 10 | BRAVO, CHARLIE, GOLF | 0.73–1.25 |

## Radar tracks

- Points per track: median 288, p5 108, p95 473.
- Flight seconds: 814,232; radar points per flight second: 0.67.

## Planted P1 flights (scenario_demo.yaml)

| Incident | Base | Launch (local) | First contact (local) | Warp | Points | Status |
|---|---|---|---|---:|---:|---|
| P1-BRAVO-251114 | BRAVO | 2025-11-14 21:12:00 | 2025-11-14 21:13:08 | 1.00 | 312 | history |
| P1-ALPHA-260303 | ALPHA | 2026-03-03 21:52:00 | 2026-03-03 21:52:07 | 1.22 | 520 | history |
| P1-DELTA-260419 | DELTA | 2026-04-19 21:35:00 | 2026-04-19 21:35:06 | 1.00 | 494 | history |
| P1-ALPHA-260502 | ALPHA | 2026-05-02 22:05:00 | 2026-05-02 22:05:06 | 0.95 | 523 | history |
| P1-CHARLIE-260710 | CHARLIE | 2026-07-10 21:30:00 | 2026-07-10 21:30:06 | 1.00 | 452 | history |
| DEMO-BRAVO-0828 | BRAVO | 2026-08-28 21:38:45 | 2026-08-28 21:39:51 | 1.00 | 464 | live |

## Live incident timing (§1.2, D-003)

- Launch 21:38:45; first radar contact (T+0) 21:39:51, 66 s after launch, 47 m outside the fence.
- Orbit established (within 15 m of the radius for 10 s): T+94 s.

## Row counts

| Database | Table | Rows |
|---|---|---:|
| app | regions | 3 |
| app | installations | 12 |
| app | assets | 60 |
| app | roads | 4 |
| app | parks | 18 |
| app | sensors | 36 |
| app | incidents | 1,869 |
| app | track_points | 541,913 |
| app | rf_detections | 0 |
| app | remote_id | 0 |
| app | weather | 14,823 |
| app | base_events | 7,757 |
| app | public_events | 272 |
| app | reports | 0 |
| app | assessments | 0 |
| truth | track_truth | 1,869 |
| truth | true_paths | 816,101 |
| truth | clue_truth | 0 |
| truth | assessment_truth | 0 |

## Report delays and clue rates

Phase 2: no reports yet.

## Sample flights

Three flights per pattern type, in each installation's frame (km from its origin): true path (blue line) and radar detections (orange dots).

![pattern_orbit](figures/pattern_orbit.png)
![pattern_lawnmower](figures/pattern_lawnmower.png)
![pattern_figure8](figures/pattern_figure8.png)
![pattern_perimeter](figures/pattern_perimeter.png)
![pattern_hover](figures/pattern_hover.png)
![pattern_transit_dips](figures/pattern_transit_dips.png)
![pattern_random_walk](figures/pattern_random_walk.png)
