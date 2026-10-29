// Director mode beats (SPEC §17.10, §1.2, D-122): one per §1.2 row, as data. Clock beats start
// when the replay clock crosses `start`; page beats start only on → (D-123). Phase 9 appends the
// swarm encore, a page beat on the Swarm view (D-155).
import type { CameraPreset } from "../state/uiStore";

export type BeatId =
  | "detection"
  | "recording"
  | "recognition"
  | "time-warp"
  | "forecast"
  | "recall"
  | "known"
  | "evidence"
  | "encore";

/** Panels a beat keeps lit; the others dim (§17.10). */
export type PanelId =
  "stream" | "signals" | "recorder" | "ledgerchain" | "matchlist" | "constellation" | "lens";

/** Theater and rail layers shown so far (cumulative, D-124). */
export interface Reveal {
  ghosts: boolean;
  lens: boolean;
  forecast: boolean;
  recall: boolean;
}

export interface Beat {
  id: BeatId;
  title: string;
  /** The §1.2 row it plays. */
  row: string;
  kind: "clock" | "page";
  /** Replay seconds (clock beats). */
  start: number | null;
  route: "live" | "case" | "evidence" | "swarm";
  camera: CameraPreset | null;
  focus: PanelId[];
  reveal: Reveal;
  /** data-testid of the element that shows the beat has landed (e2e). */
  key: string;
}

const NONE: Reveal = { ghosts: false, lens: false, forecast: false, recall: false };
const MEMORY: Reveal = { ...NONE, ghosts: true, lens: true };
const FORECAST: Reveal = { ...MEMORY, forecast: true };
const ALL: Reveal = { ...FORECAST, recall: true };

export const BEATS: readonly Beat[] = [
  {
    id: "detection",
    title: "Detection",
    row: "T+0",
    kind: "clock",
    start: 0,
    route: "live",
    camera: "overview",
    focus: ["stream", "signals"],
    reveal: NONE,
    key: "stream-row",
  },
  {
    id: "recording",
    title: "Recording",
    row: "T+0 to T+45",
    kind: "clock",
    start: 15,
    route: "live",
    camera: "overview",
    focus: ["stream", "recorder", "ledgerchain"],
    reveal: NONE,
    key: "recorder-total",
  },
  {
    id: "recognition",
    title: "Recognition",
    row: "T+45 (and T+80)",
    kind: "clock",
    start: 45,
    route: "live",
    camera: "follow",
    focus: ["signals", "matchlist"],
    reveal: NONE,
    key: "match-entry",
  },
  {
    id: "time-warp",
    title: "Time warp",
    row: "T+90",
    kind: "clock",
    start: 90,
    route: "live",
    camera: "memory",
    focus: ["matchlist", "constellation", "lens"],
    reveal: MEMORY,
    key: "lens-connector",
  },
  {
    id: "forecast",
    title: "Forecast",
    row: "T+105",
    kind: "clock",
    start: 105,
    route: "live",
    camera: "forecast",
    focus: ["matchlist", "signals"],
    reveal: FORECAST,
    key: "forecast-label",
  },
  {
    id: "recall",
    title: "Recall",
    row: "T+120",
    kind: "clock",
    start: 120,
    route: "live",
    camera: "forecast",
    focus: ["matchlist"],
    reveal: ALL,
    key: "recall-overlay",
  },
  {
    id: "known",
    title: "Known then and now",
    row: "Case Board",
    kind: "page",
    start: null,
    route: "case",
    camera: null,
    focus: [],
    reveal: ALL,
    key: "case-graph",
  },
  {
    id: "evidence",
    title: "Evidence",
    row: "Evidence",
    kind: "page",
    start: null,
    route: "evidence",
    camera: null,
    focus: [],
    reveal: ALL,
    key: "evidence-export",
  },
  {
    id: "encore",
    title: "Swarm encore",
    row: "Encore: Swarm View",
    kind: "page",
    start: null,
    route: "swarm",
    camera: null,
    focus: [],
    reveal: ALL,
    key: "swarm-ghost",
  },
];

export const REVEAL_ALL: Reveal = ALL;

export function beatIndex(id: BeatId): number {
  return BEATS.findIndex((b) => b.id === id);
}
