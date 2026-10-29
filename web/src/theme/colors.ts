// Colors for canvases and the 3D scene, read from tokens.css at runtime so the tokens stay the
// only styling vocabulary (D-021). Cached per name; empty (tests without CSS) falls back to a
// named CSS color.
export type ColorToken =
  | "--scope"
  | "--glass"
  | "--hairline"
  | "--ink-hi"
  | "--ink-mid"
  | "--ink-low"
  | "--flash"
  | "--afterglow"
  | "--bone"
  | "--alert"
  | "--verified";

const cache = new Map<ColorToken, string>();

export function token(name: ColorToken): string {
  const hit = cache.get(name);
  if (hit) return hit;
  const v =
    typeof document === "undefined"
      ? ""
      : getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const out = v || "white";
  if (v) cache.set(name, out);
  return out;
}

/** Forget cached values (tests). */
export function clearTokenCache(): void {
  cache.clear();
}
