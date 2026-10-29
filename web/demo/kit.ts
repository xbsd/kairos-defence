// Node-side tools of the demo recorder (D-168): the slow-motion factor, frame capture over CDP,
// and a narrator that drives the overlay, holds for video seconds and clicks like a person.
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import type { CDPSession, Locator, Page } from "@playwright/test";

import type { CalloutSpec, Rect, TitleSpec, Tone } from "./overlay";

/** Slow-motion factor: the page and the API run K times slower than wall time (D-168). */
export const K = Number(process.env.DEMO_SLOW ?? 5);
/** Where frames and the manifest go; the encoder reads them (demo/encode.mjs). */
export const FRAMES = "../data/cache/demo/frames";

interface Frame {
  file: string;
  t: number;
}

/** Every painted frame of the page, as JPEG with its wall-clock time (CDP screencast). */
export class Capture {
  private cdp: CDPSession | null = null;
  private frames: Frame[] = [];
  private marks: { name: string; t: number }[] = [];
  private t0 = 0;
  private n = 0;

  constructor(private page: Page) {}

  async start(): Promise<void> {
    rmSync(FRAMES, { recursive: true, force: true });
    mkdirSync(FRAMES, { recursive: true });
    this.cdp = await this.page.context().newCDPSession(this.page);
    await this.cdp.send("Animation.enable");
    await this.cdp.send("Animation.setPlaybackRate", { playbackRate: 1 / K });
    this.cdp.on("Page.screencastFrame", (f) => {
      const file = `${String(++this.n).padStart(6, "0")}.jpg`;
      writeFileSync(join(FRAMES, file), Buffer.from(f.data, "base64"));
      this.frames.push({ file, t: f.metadata.timestamp ?? Date.now() / 1000 });
      void this.cdp?.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
    });
    this.t0 = Date.now() / 1000;
    await this.cdp.send("Page.startScreencast", {
      format: "jpeg",
      quality: 92,
      maxWidth: 1920,
      maxHeight: 1080,
      everyNthFrame: 1,
    });
  }

  mark(name: string): void {
    this.marks.push({ name, t: Date.now() / 1000 });
  }

  async stop(): Promise<void> {
    const t1 = Date.now() / 1000;
    await this.cdp?.send("Page.stopScreencast");
    writeFileSync(
      join(FRAMES, "manifest.json"),
      JSON.stringify({ k: K, t0: this.t0, t1, frames: this.frames, marks: this.marks }, null, 1),
    );
  }
}

const esc = (s: string) =>
  s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c] ?? c);

/** A value read from the screen, escaped and styled as a value. */
export const v = (s: string) => `<span class="v">${esc(s.trim())}</span>`;

export class Narrator {
  constructor(private page: Page) {}

  /** Hold for `s` seconds of video (K × s of wall time). */
  hold(s: number): Promise<void> {
    return this.page.waitForTimeout(s * 1000 * K);
  }

  title(spec: TitleSpec) {
    return this.page.evaluate((x) => window.__kd?.title(x), spec);
  }
  hideTitle() {
    return this.page.evaluate(() => window.__kd?.hideTitle());
  }
  chapter(num: number, total: number, name: string, line: string) {
    return this.page.evaluate(([n, t, a, b]) => window.__kd?.chapter(n, t, a, b), [
      num,
      total,
      name,
      line,
    ] as const);
  }
  hideChapter() {
    return this.page.evaluate(() => window.__kd?.hideChapter());
  }
  progress(f: number) {
    return this.page.evaluate((x) => window.__kd?.progress(x), f);
  }
  uncallout(id: string) {
    return this.page.evaluate((x) => window.__kd?.uncallout(x), id);
  }
  clear() {
    return this.page.evaluate(() => window.__kd?.clear());
  }

  /** Ring an element (or several: their union) and explain it in a card beside it. */
  async callout(
    id: string,
    target: Locator | Locator[] | null,
    card: {
      side: CalloutSpec["side"];
      kicker: string;
      title: string;
      body: string;
      tone: Tone;
      at?: { x: number; y: number };
      spotlight?: boolean;
      width?: number;
    },
  ): Promise<void> {
    const ring = target ? await union(Array.isArray(target) ? target : [target]) : null;
    const spec: CalloutSpec = { id, ring, ...card };
    await this.page.evaluate((x) => window.__kd?.callout(x), spec);
  }

  /** Move the pointer to an element over `ms` of video time, ripple, and click it for real. */
  async click(target: Locator, ms = 700): Promise<void> {
    await target.scrollIntoViewIfNeeded();
    const b = await target.boundingBox();
    if (!b) throw new Error("click target has no box");
    const x = b.x + b.width / 2;
    const y = b.y + b.height / 2;
    await this.page.evaluate(([px, py, d]) => window.__kd?.cursorTo(px, py, d), [
      x,
      y,
      ms,
    ] as const);
    await this.page.waitForTimeout(ms * K + 120 * K);
    await this.page.evaluate(() => window.__kd?.ripple());
    await target.click();
    await this.page.waitForTimeout(250 * K);
  }

  cursorTo(x: number, y: number, ms = 700) {
    return this.page.evaluate(([px, py, d]) => window.__kd?.cursorTo(px, py, d), [
      x,
      y,
      ms,
    ] as const);
  }
  cursorHide() {
    return this.page.evaluate(() => window.__kd?.cursorHide());
  }
}

async function union(targets: Locator[]): Promise<Rect | null> {
  const boxes = (await Promise.all(targets.map((t) => t.boundingBox()))).filter(
    (b): b is Rect => b !== null,
  );
  if (!boxes.length) return null;
  const x = Math.min(...boxes.map((b) => b.x));
  const y = Math.min(...boxes.map((b) => b.y));
  const r = Math.max(...boxes.map((b) => b.x + b.width));
  const btm = Math.max(...boxes.map((b) => b.y + b.height));
  return { x, y, width: r - x, height: btm - y };
}
