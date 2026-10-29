// Slow-motion clocks for frame-perfect capture (D-168). Injected before the app's own scripts with
// `page.addInitScript(installTimeShim, k)`, so it must stay self-contained (no imports, no
// closures over module scope). Every page clock runs k times slower than wall time:
// performance.now, Date.now, requestAnimationFrame timestamps and timer delays. CSS and Web
// Animations are slowed by the recorder through CDP (Animation.setPlaybackRate). The API runs its
// replays with `--time-scale 1/k`, so the server and the page agree on what a second is, and the
// encoder plays the captured frames back k times faster: the video shows the app at its real pace.

export function installTimeShim(k: number): void {
  const w = window as unknown as { __kdTimeScale?: number };
  if (w.__kdTimeScale || !(k > 1)) return;
  w.__kdTimeScale = k;

  const realNow = performance.now.bind(performance);
  const base = realNow();
  performance.now = () => base + (realNow() - base) / k;

  const realDateNow = Date.now.bind(Date);
  const dateBase = realDateNow();
  Date.now = () => dateBase + (realDateNow() - dateBase) / k;

  // Frame timestamps come from the slowed performance.now, once per frame: the browser's own
  // rAF timestamp follows the document timeline, which the recorder also slows over CDP, and
  // code that mixes the two clocks (the report's resolve) would stall at its first frame.
  const realRaf = window.requestAnimationFrame.bind(window);
  let frameReal = -1;
  let frameSlow = 0;
  window.requestAnimationFrame = (cb: FrameRequestCallback) =>
    realRaf((ts) => {
      if (ts !== frameReal) {
        frameReal = ts;
        frameSlow = performance.now();
      }
      cb(frameSlow);
    });

  const realTimeout = window.setTimeout.bind(window);
  window.setTimeout = ((fn: TimerHandler, ms?: number, ...args: unknown[]) =>
    realTimeout(fn, (Number(ms) || 0) * k, ...args)) as typeof window.setTimeout;

  const realRepeat = window.setInterval.bind(window);
  window.setInterval = ((fn: TimerHandler, ms?: number, ...args: unknown[]) =>
    realRepeat(fn, (Number(ms) || 0) * k, ...args)) as typeof window.setInterval;
}
