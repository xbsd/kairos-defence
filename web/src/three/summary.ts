// The theater's text equivalent (§17.12): what the 3D view shows, as one sentence per track.
import { meters, tPlus } from "../lib/format";
import { clockNow, type ReplayState } from "../state/replayStore";

const RID_QUIET_S = 10;

export function theaterSummary(s: ReplayState, now?: number): string {
  const ids = Object.keys(s.tracks).sort();
  if (!s.hello) return "No replay loaded.";
  if (!ids.some((id) => (s.tracks[id]?.length ?? 0) > 0)) return "Waiting for the first detection.";
  const t = clockNow(s, now);
  const quiet = !s.rid.some((r) => t - r.t_s >= 0 && t - r.t_s <= RID_QUIET_S);
  const f = s.features[s.features.length - 1];
  return ids
    .map((id) => {
      const pts = s.tracks[id] ?? [];
      const last = pts[pts.length - 1];
      if (!last) return `${id}: no radar points yet.`;
      const n = `${pts.length} radar point${pts.length === 1 ? "" : "s"}`;
      const parts = [`${id}: ${n}`, `last at ${tPlus(last.t_s)}`];
      if (f && f.track_id === id && f.dist_target_m !== null)
        parts.push(`${meters(f.dist_target_m)} from ${f.target_asset_id}`, f.phase);
      if (quiet) parts.push("No Remote ID");
      return `${parts.join(", ")}.`;
    })
    .join(" ");
}

/**
 * The memory and forecast layers in words (§17.12): which ghosts are drawn and where the zone
 * is, the same values the 3D labels show.
 */
export function memorySummary(
  ghosts: { label: string }[],
  forecastLabel: string | null,
  roads: string[],
): string {
  const parts: string[] = [];
  if (ghosts.length)
    parts.push(
      `${ghosts.length} afterglow ghost${ghosts.length === 1 ? "" : "s"} of matched past flights: ${ghosts
        .map((g) => g.label)
        .join("; ")}.`,
    );
  if (forecastLabel) {
    const r = roads.length ? ` ${roads.join(" and ")} crosses it.` : "";
    parts.push(`${forecastLabel}.${r}`);
  }
  return parts.join(" ");
}
