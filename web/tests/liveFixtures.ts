// Live mode payloads for tests (shapes from GET /api/live/scenarios and the reveal route).
import type { RevealResponse, ScenarioInfo } from "../src/api/messages";

const every = [
  "ALPHA",
  "BRAVO",
  "CHARLIE",
  "DELTA",
  "ECHO",
  "FOXTROT",
  "HOTEL",
  "INDIA",
  "GOLF",
  "JULIET",
  "KILO",
  "LIMA",
];

export const SCENARIOS: ScenarioInfo[] = [
  {
    name: "returning-prober",
    title: "Returning prober",
    actor_label: "Prober",
    actors: [
      { id: "P1", nickname: "County Rd operator", bases: ["ALPHA", "BRAVO", "CHARLIE", "DELTA"] },
      { id: "P3", nickname: "Munitions figure-eight", bases: ["ECHO", "FOXTROT", "HOTEL"] },
      { id: "P4", nickname: "Fence runner", bases: ["GOLF", "JULIET"] },
    ],
    default_actor: "P1",
    allow_random: true,
    bases: every,
    second_base: false,
    expectation: "A same-actor history flight in the top 3 by T+120 s",
  },
  {
    name: "hobbyist",
    title: "Hobbyist",
    actor_label: null,
    actors: [],
    default_actor: null,
    allow_random: false,
    bases: every,
    second_base: false,
    expectation: "No expectation on identity; the top score is reported",
  },
  {
    name: "new-operator-twice",
    title: "New operator, twice",
    actor_label: null,
    actors: [],
    default_actor: null,
    allow_random: false,
    bases: every,
    second_base: true,
    expectation:
      "Flight 1: no same-actor history exists. Flight 2: flight 1, learned live, ranked first",
  },
];

export const REVEAL: RevealResponse = {
  incident_id: "LIVE-BRAVO-260901-210104",
  installation_id: "BRAVO",
  start_ts: "2026-09-02T02:01:04Z",
  n_tracks: 1,
  is_swarm: false,
  known: true,
  actor_id: "P1",
  actor_type: "prober",
  nickname: "County Rd operator",
  scenario: "returning-prober",
  seed: 1101,
  flight: 1,
  base: "BRAVO",
  mimics: null,
  reruns: [
    {
      t_s: 45,
      kind: "track",
      first_same_rank: 2,
      mimic_rank: null,
      top_incident: "P1-DELTA-260419",
      top_track: "P1-DELTA-260419-T1",
      top_actor: "P1",
      top_score: 0.97,
    },
    {
      t_s: 50,
      kind: "track",
      first_same_rank: 1,
      mimic_rank: null,
      top_incident: "P1-DELTA-260419",
      top_track: "P1-DELTA-260419-T1",
      top_actor: "P1",
      top_score: 0.99,
    },
  ],
  same_actor_history: 5,
  expectation: {
    text: "a same-actor (P1) history flight in the top 3 by T+120 s",
    met: true,
    observed: "rank 2 at T+45 s",
  },
  words: "P1, County Rd operator. First recognized at T+45 s (rank 2); top match from T+50 s.",
};
