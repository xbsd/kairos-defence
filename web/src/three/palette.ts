// three.js colors from the design tokens (D-021): never a literal. Only the hex tokens are used
// in the scene (three's parser does not read the space-separated rgb() of --glass/--hairline).
import { Color } from "three";

import { token, type ColorToken } from "../theme/colors";

type SceneToken = Exclude<ColorToken, "--glass" | "--hairline">;

const cache = new Map<SceneToken, Color>();

/** A shared Color for a token (do not mutate it; clone first). */
export function color(name: SceneToken): Color {
  let c = cache.get(name);
  if (!c) {
    c = new Color(token(name));
    cache.set(name, c);
  }
  return c;
}

/** `a` mixed toward `b` by t (a new Color). */
export function mix(a: SceneToken, b: SceneToken, t: number): Color {
  return color(a).clone().lerp(color(b), t);
}
