// The open replay stream, for the command bar and keyboard shortcuts.
import type { ReplayStream } from "../api/stream";

let current: ReplayStream | null = null;

export function setStream(s: ReplayStream | null): void {
  current = s;
}

export const controls = {
  play: () => current?.play(),
  pause: () => current?.pause(),
  restart: () => current?.seek(0),
  seek: (t: number) => current?.seek(t),
  speed: (v: 1 | 2 | 5) => current?.setSpeed(v),
  dtw: (track: string, channel?: string) => current?.requestDtw(track, channel),
  connected: () => current !== null,
};
