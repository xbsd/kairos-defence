// Shared setup for the panel tests: fresh stores, the throttle wait, canvas and dialog stubs.
import { act } from "@testing-library/react";
import { vi } from "vitest";

import { caseStore } from "../src/state/caseStore";
import { matchStore } from "../src/state/matchStore";
import { replayStore } from "../src/state/replayStore";
import { uiStore } from "../src/state/uiStore";

export function resetStores(): void {
  replayStore.getState().reset();
  matchStore.setState({
    match: null,
    forecast: null,
    recall: null,
    dtw: null,
    trace: null,
    entrance: 0,
    top3: "",
    decisions: {},
    busy: {},
    error: null,
  });
  caseStore.getState().reset();
  uiStore.setState({ userReduce: true, osReduce: false });
}

/** Let the 10 Hz throttle flush (and pending promises settle). */
export function flush(ms = 130) {
  return act(async () => {
    await new Promise((r) => setTimeout(r, ms));
  });
}

export function stubCanvas(): ReturnType<typeof vi.fn> {
  const calls = vi.fn();
  const ctx = new Proxy(
    {},
    {
      get: (_t, prop) => {
        if (prop === "createLinearGradient") return () => ({ addColorStop: () => undefined });
        return (...args: unknown[]) => calls(prop, ...args);
      },
      set: () => true,
    },
  );
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
    ctx as unknown as CanvasRenderingContext2D,
  );
  return calls;
}

export function stubDialog(): void {
  const proto = HTMLDialogElement.prototype as unknown as Record<string, unknown>;
  proto.showModal = function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  proto.close = function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
}

/** xs[i], or a test failure (no non-null assertions). */
export function nth<T>(xs: T[], i: number): T {
  const v = xs[i];
  if (v === undefined) throw new Error(`no element ${i} (of ${xs.length})`);
  return v;
}
