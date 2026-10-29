// The demo video's narration layer (D-168): title cards, a chapter pill, callouts that ring a real
// element and explain it, a pointer that shows where the recorder clicks, and a progress line.
// Injected with `page.addInitScript(installOverlay)`, so it is self-contained. It lives in a
// shadow root outside the app's React tree and never takes pointer events. It draws only words
// and shapes: every number it shows is read from the app's own screen by the recorder at that
// moment (rule 10), and it never changes the app's data.

export type Tone = "flash" | "afterglow" | "bone" | "verified";

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface CalloutSpec {
  id: string;
  /** The element to ring, CSS pixels; null for a card without a ring. */
  ring: Rect | null;
  /** Where the card sits: beside the ring, or at an explicit point (top-left corner). */
  side: "left" | "right" | "top" | "bottom" | "at";
  at?: { x: number; y: number };
  kicker: string;
  title: string;
  /** HTML: <b> for emphasis, <span class="v"> for a value read from the screen. */
  body: string;
  tone: Tone;
  /** Dim everything outside the ring. */
  spotlight?: boolean;
  width?: number;
}

export interface TitleSpec {
  kicker: string;
  title: string;
  sub: string;
  foot: string;
  /** Show the veil at once (the video's first frame) instead of fading it in. */
  instant?: boolean;
}

export interface Overlay {
  title(spec: TitleSpec): void;
  hideTitle(): void;
  chapter(num: number, total: number, name: string, line: string): void;
  hideChapter(): void;
  callout(spec: CalloutSpec): void;
  uncallout(id: string): void;
  clear(): void;
  cursorTo(x: number, y: number, ms: number): void;
  cursorHide(): void;
  ripple(): void;
  progress(f: number): void;
}

declare global {
  interface Window {
    __kd?: Overlay;
  }
}

export function installOverlay(): void {
  if (window.__kd) return;
  const CSS = `
  :host { all: initial; }
  .layer { position: fixed; inset: 0; pointer-events: none; z-index: 2147483000;
    font-family: "B612", system-ui, sans-serif; color: var(--ink-hi);
    -webkit-font-smoothing: antialiased; }
  .flash { --tone: var(--flash); } .afterglow { --tone: var(--afterglow); }
  .bone { --tone: var(--bone); } .verified { --tone: var(--verified); }

  .progress { position: absolute; left: 0; top: 0; height: 2px; width: 0;
    background: linear-gradient(90deg, var(--flash), var(--afterglow));
    box-shadow: 0 0 10px color-mix(in srgb, var(--afterglow) 70%, transparent);
    transition: width 900ms linear; }

  .chapter { position: absolute; top: 8px; height: 32px; display: flex; align-items: center;
    gap: 12px; padding: 0 16px 0 6px; border-radius: 999px; white-space: nowrap; overflow: hidden;
    background: color-mix(in srgb, var(--scope) 70%, transparent);
    border: 1px solid color-mix(in srgb, var(--afterglow) 38%, transparent);
    box-shadow: 0 0 24px color-mix(in srgb, var(--afterglow) 14%, transparent);
    opacity: 0; transform: translateY(-10px);
    transition: opacity 500ms var(--ease-out), transform 600ms var(--ease-out); }
  .chapter.on { opacity: 1; transform: none; }
  .chapter .num { height: 22px; min-width: 38px; padding: 0 8px; border-radius: 999px;
    display: grid; place-items: center; font: 700 13px "B612 Mono", monospace;
    color: var(--scope); background: var(--afterglow); }
  .chapter .name { font-size: 13px; font-weight: 700; letter-spacing: .18em; color: var(--ink-hi); }
  .chapter .line { font-size: 13px; color: var(--ink-mid); overflow: hidden; text-overflow: ellipsis; }

  .ring { position: absolute; border-radius: 10px; border: 1.5px solid var(--tone);
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--tone) 10%, transparent),
      0 0 30px color-mix(in srgb, var(--tone) 34%, transparent),
      inset 0 0 26px color-mix(in srgb, var(--tone) 9%, transparent);
    opacity: 0; transform: scale(1.025);
    transition: opacity 500ms var(--ease-out), transform 800ms var(--ease-out); }
  .ring.spot { box-shadow: 0 0 0 4px color-mix(in srgb, var(--tone) 10%, transparent),
      0 0 30px color-mix(in srgb, var(--tone) 34%, transparent), 0 0 0 200vmax rgb(2 6 10 / 0.5); }
  .ring.on { opacity: 1; transform: none; }
  .corner { position: absolute; width: 18px; height: 18px; border: 0 solid var(--tone); }
  .corner.tl { left: -9px; top: -9px; border-left-width: 2px; border-top-width: 2px; }
  .corner.tr { right: -9px; top: -9px; border-right-width: 2px; border-top-width: 2px; }
  .corner.bl { left: -9px; bottom: -9px; border-left-width: 2px; border-bottom-width: 2px; }
  .corner.br { right: -9px; bottom: -9px; border-right-width: 2px; border-bottom-width: 2px; }

  svg.wires { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
  .wire { fill: none; stroke: var(--tone); stroke-width: 1.4; stroke-dasharray: 600;
    stroke-dashoffset: 600; opacity: .9; transition: stroke-dashoffset 900ms var(--ease-out) 150ms; }
  .wire.on { stroke-dashoffset: 0; }
  .dot { fill: var(--tone); opacity: 0; transition: opacity 400ms ease 700ms; }
  .dot.on { opacity: 1; }

  .card { position: absolute; padding: 15px 18px 16px; border-radius: 10px;
    background: color-mix(in srgb, var(--scope) 88%, transparent);
    border: 1px solid color-mix(in srgb, var(--tone) 42%, transparent);
    box-shadow: 0 22px 60px rgb(0 0 0 / 0.55), 0 0 36px color-mix(in srgb, var(--tone) 13%, transparent);
    backdrop-filter: blur(12px); opacity: 0; transform: translateY(10px);
    transition: opacity 550ms var(--ease-out), transform 700ms var(--ease-out); }
  .card.on { opacity: 1; transform: none; }
  .kicker { display: flex; align-items: center; gap: 10px; font-size: 12px; font-weight: 700;
    letter-spacing: .2em; text-transform: uppercase; color: var(--tone); }
  .kicker::before { content: ""; width: 22px; height: 1.5px; background: var(--tone);
    box-shadow: 0 0 8px var(--tone); }
  .title { margin-top: 7px; font-size: 23px; line-height: 1.22; font-weight: 700; color: var(--ink-hi); }
  .body { margin-top: 7px; font-size: 16.5px; line-height: 1.5; color: var(--ink-mid); }
  .body b { color: var(--ink-hi); font-weight: 700; }
  .body .v { color: var(--tone); font-family: "B612 Mono", monospace; font-size: 15.5px; }

  .titlecard { position: absolute; inset: 0; display: grid; place-items: center; opacity: 0;
    background: radial-gradient(ellipse at 50% 46%, color-mix(in srgb, var(--scope) 62%, transparent) 0%,
      color-mix(in srgb, var(--scope) 93%, transparent) 62%, var(--scope) 100%);
    backdrop-filter: blur(7px); transition: opacity 1000ms var(--ease-out); }
  .titlecard.on { opacity: 1; }
  .titlecard.instant { transition: none; }
  .tc { position: relative; display: flex; flex-direction: column; align-items: center; gap: 22px;
    text-align: center; }
  .scope { position: absolute; left: 50%; top: 50%; width: 760px; height: 760px; margin: -380px 0 0 -380px;
    border-radius: 50%; opacity: .5;
    background: repeating-radial-gradient(circle, transparent 0 94px,
      color-mix(in srgb, var(--flash) 14%, transparent) 94px 95px); }
  .sweep { position: absolute; inset: 0; border-radius: 50%;
    background: conic-gradient(from 0deg, color-mix(in srgb, var(--flash) 22%, transparent),
      transparent 70deg, transparent 360deg);
    animation: sweep 5s linear infinite; }
  @keyframes sweep { to { transform: rotate(360deg); } }
  .tc > .el { opacity: 0; transform: translateY(14px);
    transition: opacity 900ms var(--ease-out), transform 1100ms var(--ease-out); }
  .titlecard.show .el { opacity: 1; transform: none; }
  .tc-kicker { font-size: 16px; font-weight: 700; letter-spacing: .62em; padding-left: .62em;
    color: var(--afterglow); transition-delay: 0ms; }
  .tc-title { font-size: 70px; line-height: 1.08; font-weight: 700; color: var(--ink-hi); max-width: 1300px;
    text-shadow: 0 0 46px color-mix(in srgb, var(--flash) 30%, transparent); transition-delay: 250ms !important; }
  .tc-rule { width: 0; height: 1.5px; opacity: 1 !important; transform: none !important;
    background: linear-gradient(90deg, transparent, var(--afterglow), transparent);
    transition: width 1600ms var(--ease-out) 500ms !important; }
  .titlecard.show .tc-rule { width: 560px; }
  .tc-sub { font-size: 24px; line-height: 1.5; color: var(--ink-mid); max-width: 1000px;
    transition-delay: 800ms !important; }
  .tc-foot { margin-top: 10px; font-size: 14px; letter-spacing: .26em; text-transform: uppercase;
    color: var(--ink-low); transition-delay: 1150ms !important; }

  .cursor { position: absolute; left: 0; top: 0; width: 30px; height: 30px; opacity: 0;
    transform: translate(960px, 1200px); transition-property: transform, opacity;
    transition-timing-function: cubic-bezier(.45, .05, .2, 1), ease;
    filter: drop-shadow(0 3px 8px rgb(0 0 0 / 0.65)); }
  .cursor.on { opacity: 1; }
  .ripple { position: absolute; width: 46px; height: 46px; margin: -23px 0 0 -23px; border-radius: 50%;
    border: 2px solid var(--flash); box-shadow: 0 0 18px var(--flash);
    animation: rip 750ms var(--ease-out) forwards; }
  @keyframes rip { from { transform: scale(.25); opacity: 1; } to { transform: scale(1.7); opacity: 0; } }
  `;

  const host = document.createElement("div");
  host.id = "kd-demo-overlay";
  const shadow = host.attachShadow({ mode: "open" });
  shadow.innerHTML = `<style>${CSS}</style>
    <div class="layer">
      <svg class="wires" xmlns="http://www.w3.org/2000/svg"></svg>
      <div class="progress"></div>
      <div class="chapter afterglow"><span class="num"></span><span class="name"></span><span class="line"></span></div>
      <div class="titlecard"><div class="scope"><div class="sweep"></div></div><div class="tc">
        <div class="el tc-kicker"></div><div class="el tc-title"></div><div class="el tc-rule"></div>
        <div class="el tc-sub"></div><div class="el tc-foot"></div></div></div>
      <svg class="cursor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M3 2 L3 19.5 L7.6 15.2 L10.6 22 L13.6 20.7 L10.7 14 L17 14 Z"
          fill="var(--ink-hi)" stroke="var(--scope)" stroke-width="1.4" stroke-linejoin="round"/>
      </svg>
    </div>`;
  // a manual popover lives in the top layer, above the app; raise() moves it above a modal
  // dialog that opened later (the evidence export's confirm), so the pointer stays visible
  host.setAttribute("popover", "manual");
  host.style.cssText =
    "position:fixed;inset:0;width:100vw;height:100vh;max-width:none;max-height:none;margin:0;" +
    "padding:0;border:0;background:transparent;overflow:visible;pointer-events:none";
  const mount = () => {
    document.body.appendChild(host);
    host.showPopover();
  };
  if (document.body) mount();
  else document.addEventListener("DOMContentLoaded", mount, { once: true });
  const raise = () => {
    if (!host.isConnected || !document.querySelector("dialog:modal")) return false;
    host.hidePopover();
    host.showPopover();
    return true;
  };

  const $ = <T extends Element>(sel: string) => shadow.querySelector(sel) as T;
  const layer = $<HTMLDivElement>(".layer");
  const wires = $<SVGSVGElement>("svg.wires");
  const cursor = $<SVGSVGElement>(".cursor");
  const NS = "http://www.w3.org/2000/svg";
  const callouts = new Map<string, Element[]>();
  let cx = 960;
  let cy = 1200;

  const nextFrame = (fn: () => void) => requestAnimationFrame(() => requestAnimationFrame(fn));
  const esc = (s: string) =>
    s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c] ?? c);

  function placeCard(spec: CalloutSpec, card: HTMLDivElement): { x: number; y: number } {
    const W = window.innerWidth;
    const H = window.innerHeight;
    const w = card.offsetWidth;
    const h = card.offsetHeight;
    const r = spec.ring;
    const gap = 34;
    let x: number;
    let y: number;
    if (spec.side === "at" || !r) {
      x = spec.at?.x ?? 24;
      y = spec.at?.y ?? 64;
    } else if (spec.side === "left") {
      x = r.x - gap - w;
      y = r.y + r.height / 2 - h / 2;
    } else if (spec.side === "right") {
      x = r.x + r.width + gap;
      y = r.y + r.height / 2 - h / 2;
    } else if (spec.side === "top") {
      x = r.x + r.width / 2 - w / 2;
      y = r.y - gap - h;
    } else {
      x = r.x + r.width / 2 - w / 2;
      y = r.y + r.height + gap;
    }
    x = Math.max(16, Math.min(W - w - 16, x));
    y = Math.max(56, Math.min(H - h - 16, y));
    return { x, y };
  }

  function wirePath(
    spec: CalloutSpec,
    c: { x: number; y: number; w: number; h: number },
  ): string | null {
    const r = spec.ring;
    if (!r) return null;
    let side = spec.side;
    if (side === "at") {
      // a free card: wire from the card's edge that faces the ring
      if (r.y > c.y + c.h) side = "top";
      else if (r.y + r.height < c.y) side = "bottom";
      else side = r.x > c.x + c.w ? "left" : "right";
    }
    let a: [number, number];
    let b: [number, number];
    if (side === "left") {
      a = [c.x + c.w, c.y + c.h / 2];
      b = [r.x - 6, Math.max(r.y + 12, Math.min(r.y + r.height - 12, a[1]))];
    } else if (side === "right") {
      a = [c.x, c.y + c.h / 2];
      b = [r.x + r.width + 6, Math.max(r.y + 12, Math.min(r.y + r.height - 12, a[1]))];
    } else if (side === "top") {
      a = [c.x + c.w / 2, c.y + c.h];
      b = [Math.max(r.x + 12, Math.min(r.x + r.width - 12, a[0])), r.y - 6];
    } else {
      a = [c.x + c.w / 2, c.y];
      b = [Math.max(r.x + 12, Math.min(r.x + r.width - 12, a[0])), r.y + r.height + 6];
    }
    const mx = (a[0] + b[0]) / 2;
    const my = (a[1] + b[1]) / 2;
    const horiz = side === "left" || side === "right";
    return horiz
      ? `M${a[0]},${a[1]} C${mx},${a[1]} ${mx},${b[1]} ${b[0]},${b[1]}`
      : `M${a[0]},${a[1]} C${a[0]},${my} ${b[0]},${my} ${b[0]},${b[1]}`;
  }

  function remove(id: string, fade = true) {
    const els = callouts.get(id);
    if (!els) return;
    callouts.delete(id);
    for (const el of els) {
      el.classList.remove("on");
      if (!fade) el.remove();
      else setTimeout(() => el.remove(), 900);
    }
  }

  const api: Overlay = {
    title(spec) {
      const tc = $<HTMLDivElement>(".titlecard");
      $<HTMLDivElement>(".tc-kicker").textContent = spec.kicker;
      $<HTMLDivElement>(".tc-title").textContent = spec.title;
      $<HTMLDivElement>(".tc-sub").textContent = spec.sub;
      $<HTMLDivElement>(".tc-foot").textContent = spec.foot;
      tc.classList.remove("show");
      tc.classList.toggle("instant", Boolean(spec.instant));
      tc.classList.add("on");
      nextFrame(() => {
        tc.classList.remove("instant");
        tc.classList.add("show");
      });
    },
    hideTitle() {
      const tc = $<HTMLDivElement>(".titlecard");
      tc.classList.remove("on");
      setTimeout(() => tc.classList.remove("show"), 1100);
    },
    chapter(num, total, name, line) {
      const el = $<HTMLDivElement>(".chapter");
      el.classList.remove("on");
      const show = () => {
        $<HTMLSpanElement>(".chapter .num").textContent =
          `${String(num).padStart(2, "0")}/${String(total).padStart(2, "0")}`;
        $<HTMLSpanElement>(".chapter .name").textContent = name.toUpperCase();
        $<HTMLSpanElement>(".chapter .line").textContent = line;
        // centre the pill in the command bar's free space, between the breadcrumb and the clock
        // the nav stretches (flex-1): measure where its text ends, not its box
        const nav = document.querySelector('nav[aria-label="Breadcrumb"]');
        let textRight = 0;
        if (nav) {
          const walker = document.createTreeWalker(nav, NodeFilter.SHOW_TEXT);
          const range = document.createRange();
          for (let t = walker.nextNode(); t; t = walker.nextNode()) {
            if (!t.textContent?.trim()) continue;
            range.selectNodeContents(t);
            for (const r of range.getClientRects()) textRight = Math.max(textRight, r.right);
          }
        }
        const clock = document
          .querySelector('[data-testid="replay-clock"]')
          ?.getBoundingClientRect();
        const left = (textRight || 420) + 28;
        const right = (clock ? clock.left : 1000) - 24;
        el.style.maxWidth = `${Math.max(240, right - left)}px`;
        el.style.left = `${left}px`;
        nextFrame(() => {
          const w = el.offsetWidth;
          el.style.left = `${left + Math.max(0, (right - left - w) / 2)}px`;
          el.classList.add("on");
        });
      };
      setTimeout(show, 250);
    },
    hideChapter() {
      $<HTMLDivElement>(".chapter").classList.remove("on");
    },
    callout(spec) {
      remove(spec.id, false);
      const els: Element[] = [];
      if (spec.ring) {
        const r = spec.ring;
        const ring = document.createElement("div");
        ring.className = `ring ${spec.tone}${spec.spotlight ? " spot" : ""}`;
        Object.assign(ring.style, {
          left: `${r.x - 6}px`,
          top: `${r.y - 6}px`,
          width: `${r.width + 12}px`,
          height: `${r.height + 12}px`,
        });
        ring.innerHTML =
          '<i class="corner tl"></i><i class="corner tr"></i><i class="corner bl"></i><i class="corner br"></i>';
        layer.appendChild(ring);
        els.push(ring);
      }
      const card = document.createElement("div");
      card.className = `card ${spec.tone}`;
      card.style.width = `${spec.width ?? 400}px`;
      card.innerHTML = `<div class="kicker">${esc(spec.kicker)}</div><div class="title">${esc(spec.title)}</div><div class="body">${spec.body}</div>`;
      card.style.visibility = "hidden";
      layer.appendChild(card);
      const p = placeCard(spec, card);
      Object.assign(card.style, { left: `${p.x}px`, top: `${p.y}px`, visibility: "visible" });
      els.push(card);
      const d = wirePath(spec, { x: p.x, y: p.y, w: card.offsetWidth, h: card.offsetHeight });
      if (d) {
        const g = document.createElementNS(NS, "g");
        g.setAttribute("class", spec.tone);
        const path = document.createElementNS(NS, "path");
        path.setAttribute("d", d);
        path.setAttribute("class", "wire");
        const end = d.split(" ").slice(-1)[0]?.split(",") ?? ["0", "0"];
        const dot = document.createElementNS(NS, "circle");
        dot.setAttribute("cx", end[0] ?? "0");
        dot.setAttribute("cy", end[1] ?? "0");
        dot.setAttribute("r", "3.5");
        dot.setAttribute("class", "dot");
        g.append(path, dot);
        wires.appendChild(g);
        els.push(path, dot, g);
      }
      callouts.set(spec.id, els);
      nextFrame(() => els.forEach((el) => el.classList.add("on")));
    },
    uncallout(id) {
      remove(id);
    },
    clear() {
      for (const id of [...callouts.keys()]) remove(id);
    },
    cursorTo(x, y, ms) {
      const move = () => {
        cursor.classList.add("on");
        cursor.style.transitionDuration = `${ms}ms, 400ms`;
        // the arrow's tip sits at (3, 2) of its 24-unit box, drawn at 30 px
        cursor.style.transform = `translate(${x - 3.75}px, ${y - 2.5}px)`;
      };
      // after a raise the pointer restarts from where it was, a frame later
      if (raise()) nextFrame(move);
      else move();
      cx = x;
      cy = y;
    },
    cursorHide() {
      cursor.classList.remove("on");
    },
    ripple() {
      const r = document.createElement("div");
      r.className = "ripple";
      Object.assign(r.style, { left: `${cx}px`, top: `${cy}px` });
      layer.appendChild(r);
      setTimeout(() => r.remove(), 900);
    },
    progress(f) {
      $<HTMLDivElement>(".progress").style.width = `${Math.max(0, Math.min(1, f)) * 100}%`;
    },
  };
  window.__kd = api;
}
