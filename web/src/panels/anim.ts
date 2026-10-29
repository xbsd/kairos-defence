// Small Web Animations helpers for the panels. Each is a no-op where `Element.animate` is missing
// (jsdom) or when reduce motion is on (§17.11: state changes stay, motion goes).

export function animate(
  el: Element | null,
  keyframes: Keyframe[],
  options: KeyframeAnimationOptions,
  reduce: boolean,
): void {
  if (!el || reduce || typeof (el as HTMLElement).animate !== "function") return;
  (el as HTMLElement).animate(keyframes, options);
}

export const EASE_OUT = "cubic-bezier(0.22, 1, 0.36, 1)";
