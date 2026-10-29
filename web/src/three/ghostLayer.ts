// The afterglow ghosts' data (SPEC §17.3, D-128): which past flights to draw, mapped into
// tonight's target frame, and the loader that fetches them as matches arrive.
import { useEffect } from "react";

import type { MatchItem, Scene } from "../api/messages";
import type { HistoryPath } from "../api/pages";
import { baseName, localDate } from "../lib/format";
import { ghostStore, readyPath } from "../state/ghostStore";
import { matchStore } from "../state/matchStore";
import { replayStore } from "../state/replayStore";
import { isFenceTarget, mapGhost, type GhostPoint } from "./ghostMath";
import type { Vec2 } from "./sceneMath";

/** Fetch the current top 3's paths as matches arrive (history does not change: once each). */
export function useGhostLoader(): void {
  useEffect(() => {
    const load = () => {
      for (const x of matchStore.getState().match?.matches.slice(0, 3) ?? [])
        ghostStore.getState().load(x.track_id);
    };
    load();
    return matchStore.subscribe(load);
  }, []);
}

export interface GhostSpec {
  track: string;
  incident: string;
  label: string;
  points: GhostPoint[];
}

/** A cheap identity of `currentGhosts` (target and the ready tracks), safe to call per frame. */
export function ghostsKey(): string {
  const m = matchStore.getState().match;
  if (!m || isFenceTarget(m.target_asset_id)) return "";
  const g = ghostStore.getState();
  const ready = m.matches.slice(0, 3).filter((x) => readyPath(g, x.track_id) !== null);
  return `${m.target_asset_id}|${ready.map((x) => x.track_id).join("|")}`;
}

/** Mapped ghosts by target, track and fetched path: the same inputs give the same object, so
 * React (and the Line2 built from a spec) sees a ghost change only when it really changes. */
const cache = new Map<string, { path: HistoryPath; spec: GhostSpec }>();

function specFor(target: string, x: MatchItem, path: HistoryPath, c: Vec2): GhostSpec {
  const key = `${target}|${x.track_id}`;
  const hit = cache.get(key);
  if (hit && hit.path === path) return hit.spec;
  const spec = {
    track: x.track_id,
    incident: x.incident_id,
    label: `${baseName(x.installation_id)}, ${localDate(x.local_start)}`,
    points: mapGhost(path, c),
  };
  cache.set(key, { path, spec });
  return spec;
}

/** The ghosts to draw now: the current top 3, mapped to tonight's identified target. */
export function currentGhosts(scene: Scene | null): { key: string; ghosts: GhostSpec[] } {
  const m = matchStore.getState().match;
  const f = replayStore.getState().features;
  const target = m?.target_asset_id ?? f[f.length - 1]?.target_asset_id ?? null;
  if (!m || !scene || isFenceTarget(target)) return { key: "", ghosts: [] };
  const a = scene.assets.find((x) => x.asset_id === target);
  if (!a) return { key: "", ghosts: [] };
  const c: Vec2 = [a.centroid_x_m, a.centroid_y_m];
  const g = ghostStore.getState();
  const ghosts: GhostSpec[] = [];
  for (const x of m.matches.slice(0, 3)) {
    const p = readyPath(g, x.track_id);
    if (!p) continue;
    ghosts.push(specFor(String(target), x, p, c));
  }
  return { key: `${target}|${ghosts.map((x) => x.track).join("|")}`, ghosts };
}
