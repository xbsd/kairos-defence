// What the Director keys do (SPEC §17.10, D-123, D-142, D-143): D toggles, → and ← step through
// the beats, R resets. The Director never approves, rejects, decides or exports (rule 8).
import { api } from "../api/client";
import { navigate } from "../app/routes";
import { caseStore } from "../state/caseStore";
import { controls } from "../state/controls";
import { directorStore } from "../state/directorStore";
import { matchStore } from "../state/matchStore";
import { replayStore } from "../state/replayStore";
import { BEATS } from "./beats";
import { currentBeat, nextBeat, prevBeat, type Step } from "./engine";

function liveIncidentFromPath(): string | null {
  const m = /^\/live\/([A-Za-z0-9-]+)\/?$/.exec(window.location.pathname);
  return m?.[1] ?? null;
}

/** The live single-track incident to present: the open one, else the first from the API. */
async function presentIncident(): Promise<string | null> {
  const here = liveIncidentFromPath() ?? replayStore.getState().hello?.incident_id ?? null;
  if (here) return here;
  const list = await api.liveIncidents();
  return (list.find((i) => !i.is_swarm) ?? list[0])?.incident_id ?? null;
}

/** D: start Director from T+0 at the selected speed, on Live watch; again to stop. */
export async function toggleDirector(): Promise<void> {
  const d = directorStore.getState();
  if (d.active) {
    d.stop();
    return;
  }
  const incident = await presentIncident();
  if (!incident) return;
  // the presenter drives with the keys from here: a clicked button must not keep Space
  (document.activeElement as HTMLElement | null)?.blur?.();
  directorStore.getState().start(incident);
  if (liveIncidentFromPath() !== incident) navigate(`/live/${incident}`);
}

/** The case the page beats show: the live proposals' case, else one with pending proposals. */
async function presentCase(): Promise<string | null> {
  const d = directorStore.getState();
  const known = matchStore.getState().match?.case_id ?? d.caseId;
  if (known) return known;
  const cases = await api.cases();
  return (cases.find((c) => c.pending > 0) ?? cases[0])?.case_id ?? null;
}

/** The swarm the encore shows: the live swarm incident, else the newest swarm (D-155). */
async function presentSwarm(): Promise<string | null> {
  const list = await api.swarms();
  return (list.find((s) => s.status === "live") ?? list[0])?.incident_id ?? null;
}

async function apply(step: Step): Promise<void> {
  const d = directorStore.getState();
  switch (step.kind) {
    case "seek":
      controls.seek(step.t);
      return;
    case "page": {
      if (BEATS[step.index]?.route === "swarm") {
        // the encore reads only: it never writes to the ledger (§15.6)
        const swarm = await presentSwarm();
        if (!swarm) return;
        directorStore.getState().setPage(step.index);
        navigate(`/swarm?incident=${encodeURIComponent(swarm)}`);
        return;
      }
      const caseId = await presentCase();
      if (!caseId) return;
      directorStore.getState().setCase(caseId);
      directorStore.getState().setPage(step.index);
      const beat = BEATS[step.index];
      navigate(
        beat?.route === "evidence"
          ? `/evidence?case=${encodeURIComponent(caseId)}`
          : `/cases/${encodeURIComponent(caseId)}`,
      );
      return;
    }
    case "live":
      d.setPage(null);
      d.requestSeek(step.t, false);
      if (d.incidentId) navigate(`/live/${d.incidentId}`);
      return;
    case "none":
      return;
  }
}

function here(): number {
  const d = directorStore.getState();
  return currentBeat(replayStore.getState().clock?.t_s ?? 0, d.page);
}

/** →: the next beat (a seek on Live watch, or the next page). */
export function directorNext(): Promise<void> {
  if (!directorStore.getState().active) return Promise.resolve();
  return apply(nextBeat(here()));
}

/** ←: the previous beat (from the Case board, back to Live watch at the recall beat). */
export function directorPrev(): Promise<void> {
  if (!directorStore.getState().active) return Promise.resolve();
  return apply(prevBeat(here()));
}

/**
 * R (D-010, D-143): empty the live tables, rebuild the ledger from seed, reload the chain and seek
 * to T+0; in Director, back to beat 1 (and to Live watch from a page beat).
 */
export async function resetDemo(): Promise<void> {
  await api.adminReset();
  await api.adminReseed();
  matchStore.setState({ decisions: {}, busy: {}, error: null });
  caseStore.getState().reset();
  api
    .ledgerTail(12)
    .then((bs) => caseStore.getState().addBlocks(bs))
    .catch(() => undefined);
  const d = directorStore.getState();
  if (d.active) d.reset();
  if (d.active && d.page !== null && d.incidentId) {
    d.requestSeek(0, false);
    navigate(`/live/${d.incidentId}`);
    return;
  }
  controls.seek(0);
}
