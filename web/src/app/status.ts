export type ReplayStatus = "Live" | "Paused" | "Reconnecting" | "Connecting" | "No replay loaded";

/** The live mode's chip (D-184): the stream, then the feed (rate from its heartbeats). */
export function liveStatus(
  status: string,
  feed: { active: boolean; rate: number } | null,
  flying: boolean,
): string {
  if (status === "reconnecting") return "Reconnecting";
  if (status !== "open") return "Connecting";
  if (!feed) return "No feed yet";
  if (!feed.active) return "Feed idle";
  return flying ? `Live feed, ${feed.rate}×` : `Feed on, ${feed.rate}×`;
}

/** What the status chip says, from the stream status and the replay clock (rule 10). */
export function replayStatus(
  status: string,
  hasHello: boolean,
  playing: boolean | undefined,
): ReplayStatus {
  if (status === "reconnecting") return "Reconnecting";
  if (status === "connecting" && !hasHello) return "Connecting";
  if (status !== "open" || !hasHello) return "No replay loaded";
  return playing ? "Live" : "Paused";
}
