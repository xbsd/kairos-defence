export type ReplayStatus = "Live" | "Paused" | "Reconnecting" | "Connecting" | "No replay loaded";

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
