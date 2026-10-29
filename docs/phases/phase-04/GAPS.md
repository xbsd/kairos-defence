# Phase 4: targets not met, accepted by the autopilot

After 3 fix attempts these targets were still short. Per the user's instruction of 2026-10-28 (D-063) the run recorded them and continued; later phases report them as WARN and do not retry them. Every other check in the gate passed.

- demo live_top3_incidents: fail
- demo:live_top3_incidents: status 'fail', observed 2/3 in top 3; P1-DELTA-260419 #1 (1.00, 'Same time of night'); P1-ALPHA-260303 #2 (1.00, 'Same time of night'); P1-ALPHA-260502 #5 (0.99, 'Same time of night')

Last gate log: `docs/phases/phase-04/gate-4.log`. Accepted keys: demo live_top3_incidents, demo:live_top3_incidents.
