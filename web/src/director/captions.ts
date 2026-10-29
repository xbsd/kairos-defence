// Director captions (SPEC §17.10, D-125): one plain sentence per beat, computed from the stream
// and the pages, never hard-coded values (rule 10). A missing value drops its clause: a caption
// never shows "undefined", "NaN" or a placeholder.
import type { ForecastMsg, HelloMsg, MatchMsg, RecallMsg, Scene } from "../api/messages";
import { baseName, localDate } from "../lib/format";
import { chooseReport, zoneRoad } from "../overlay/clues";
import { compass8, distanceBearing, pointInPolygons, roughDistance } from "../three/forecastMath";
import { weeksWord, type SwarmFacts } from "../swarm/swarmMath";
import type { Vec2 } from "../three/sceneMath";
import type { BeatId } from "./beats";

export interface DirectorFacts {
  caseBase?: string;
  caseLabel?: string;
  caseClosedOn?: string;
  pending?: number;
  /** Set by the Swarm view from its §14 result (the encore, D-155). */
  swarm?: SwarmFacts;
}

export interface CaptionCtx {
  hello: HelloMsg | null;
  /** Tonight's first radar point, region meters. */
  firstPoint: Vec2 | null;
  scene: Scene | null;
  /** Hours from UTC by installation (for report dates). */
  offsets: Record<string, number>;
  rows: number;
  writeMs: number | null;
  match: MatchMsg | null;
  /** The match the lens shows in the time-warp beat. */
  lensTrack: string | null;
  forecast: ForecastMsg | null;
  recall: RecallMsg | null;
  facts: DirectorFacts;
}

const ok = (v: unknown): boolean =>
  v !== null && v !== undefined && v !== "" && !(typeof v === "number" && !Number.isFinite(v));

/** "21:40" at an offset from UTC (hours), from an ISO time; null when unreadable. */
export function localHM(iso: string | null | undefined, offsetH: number): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return null;
  const d = new Date(t + offsetH * 3600_000);
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}

/** "Apr 19" at an offset from UTC, from an ISO time. */
export function localDay(iso: string | null | undefined, offsetH: number): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return null;
  return localDate(new Date(t + offsetH * 3600_000).toISOString());
}

function article(word: string): string {
  return /^[aeiou]/i.test(word) ? "an" : "a";
}

function detection(c: CaptionCtx): string {
  const h = c.hello;
  const base = h ? baseName(h.installation_id) : null;
  let side: string | null = null;
  if (c.firstPoint && c.scene)
    side = compass8(
      distanceBearing([c.scene.origin_x_m, c.scene.origin_y_m], c.firstPoint).bearing,
    );
  const at = h ? localHM(h.start_ts, h.utc_offset_hours) : null;
  const where = base ? ` at ${base}'s ${side ? `${side} ` : ""}fence` : "";
  return `First radar contact${where}${at ? `, ${at} local` : ""}.`;
}

function recording(c: CaptionCtx): string {
  const parts: string[] = [];
  if (c.rows > 0) parts.push(`${c.rows.toLocaleString("en-US")} rows so far`);
  if (ok(c.writeMs) && c.writeMs !== null)
    parts.push(`${c.writeMs < 10 ? c.writeMs.toFixed(1) : Math.round(c.writeMs)} ms per write`);
  return `Every detection is written as it arrives${parts.length ? `: ${parts.join(", ")}` : ""}.`;
}

function recognition(c: CaptionCtx): string {
  const s = c.hello?.min_track_s;
  const after = ok(s) && s !== undefined ? `After ${Math.round(s)} seconds of track, ` : "";
  return `${after}Kairos Defense searches every past flight at every base.`;
}

function timeWarp(c: CaptionCtx): string {
  const ms = c.match?.matches ?? [];
  const m = ms.find((x) => x.track_id === c.lensTrack) ?? ms[0];
  if (!m) return "Warping time lines tonight's flight up with the flights seen before.";
  const name = `${baseName(m.installation_id)}, ${localDate(m.local_start)}`;
  const pace = m.warp_ratio !== null ? paceOf(m.warp_ratio) : null;
  return `${name}: the same shape${pace ? `, ${pace}` : ""}. Warping time lines the two flights up.`;
}

/** The matcher's pace words (§10.4 step 5, mirrored from match/dtw_rerank.warp_text). */
export function paceOf(k: number): string | null {
  if (!Number.isFinite(k) || k <= 0) return null;
  if (k > 1.1) return `flown ${Math.round((1 - 1 / k) * 100)}% slower`;
  if (k < 0.9) return `flown ${Math.round((1 / k - 1) * 100)}% faster`;
  return null;
}

/** Distance and compass word from tonight's target asset to the zone center. */
export function forecastPlace(
  f: ForecastMsg | null,
  scene: Scene | null,
): { distance: number; word: string; shadow: boolean } | null {
  if (!f || !scene) return null;
  const a = scene.assets.find((x) => x.asset_id === f.target_asset_id);
  if (!a) return null;
  const c: Vec2 = [f.center_x_m, f.center_y_m];
  const { distance, bearing } = distanceBearing([a.centroid_x_m, a.centroid_y_m], c);
  const polys = (scene.radar_shadow?.polygons ?? []) as Vec2[][];
  return { distance, word: compass8(bearing), shadow: pointInPolygons(c, polys) };
}

function forecast(c: CaptionCtx): string {
  const p = forecastPlace(c.forecast, c.scene);
  if (!p) return "The matched flights' recovery points give tonight's predicted zone.";
  const base = c.hello ? baseName(c.hello.installation_id) : null;
  const shadow = p.shadow && base ? `, in ${base}'s radar shadow` : "";
  return `Those flights ended about ${roughDistance(p.distance)} ${p.word}${shadow}.`;
}

function recall(c: CaptionCtx): string {
  const ch = chooseReport(c.recall);
  if (!ch) return "No earlier report is tied to these flights yet.";
  const base = baseName(ch.match.installation_id);
  const off = c.offsets[ch.match.installation_id] ?? c.hello?.utc_offset_hours ?? 0;
  const day = localDay(ch.report.event_ts, off);
  const who = `A ${base} report${day ? ` from ${day}` : ""}`;
  const vehicle = ch.report.clues.find((x) => x.type === "vehicle");
  const road = zoneRoad(ch.report, c.recall) ?? ch.report.clues.find((x) => x.type === "road");
  const inZone = road !== undefined && road !== null && c.recall?.zone_roads.includes(road.value);
  const zone = inZone ? ", which runs through tonight's predicted zone" : "";
  if (vehicle && road)
    return `${who} mentions ${article(vehicle.value)} ${vehicle.value} on ${road.value}${zone}.`;
  if (road) return `${who} mentions ${road.value}${zone}.`;
  if (vehicle) return `${who} mentions ${article(vehicle.value)} ${vehicle.value}.`;
  return `${who} is the closest written record.`;
}

function known(c: CaptionCtx): string {
  const f = c.facts;
  const tail = "Here is what was known then, and what is known now.";
  if (!f.caseBase || !f.caseLabel) return tail;
  return `${f.caseBase} closed this as ${f.caseLabel}${f.caseClosedOn ? ` on ${f.caseClosedOn}` : ""}. ${tail}`;
}

function evidence(c: CaptionCtx): string {
  const n = c.facts.pending;
  const tail = "then export: every step is signed and replayable.";
  if (ok(n) && n !== undefined && n > 0)
    return `${n} proposed link${n === 1 ? " waits" : "s wait"} for an analyst. Approve the ones you agree with, ${tail}`;
  return `Approve the links you agree with, ${tail}`;
}

/** The encore (Appendix B row 7): computed from the swarm match, never "tonight" (that is
 * BRAVO's night); without a result it says what the page does. */
export function encoreCaption(f: SwarmFacts | undefined): string {
  if (!f) return "Every earlier swarm, searched for the same choreography.";
  const apart = f.weeks >= 1 ? `, ${weeksWord(f.weeks)} apart` : "";
  const where = f.otherRegion ? ", in another region" : f.sameBase ? "" : ", at another base";
  return `Same choreography${apart}${where}: ${f.matchBase} on ${f.matchDay} and ${f.queryBase} on ${f.queryDay}.`;
}

function encore(c: CaptionCtx): string {
  return encoreCaption(c.facts.swarm);
}

const BY_BEAT: Record<BeatId, (c: CaptionCtx) => string> = {
  detection,
  recording,
  recognition,
  "time-warp": timeWarp,
  forecast,
  recall,
  known,
  evidence,
  encore,
};

export function caption(beat: BeatId, c: CaptionCtx): string {
  return BY_BEAT[beat](c);
}
