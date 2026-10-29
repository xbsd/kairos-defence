// F: full screen on or off (§17.10). Browsers may refuse (no user gesture, iframes): ignored.
export function toggleFullscreen(doc: Document = document): void {
  if (doc.fullscreenElement) {
    void doc.exitFullscreen?.().catch(() => undefined);
    return;
  }
  void doc.documentElement.requestFullscreen?.().catch(() => undefined);
}
