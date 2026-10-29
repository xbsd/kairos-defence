// The cost matrix's perceptual ramp (SPEC §17.7): scope glass → afterglow, interpolated in OKLab
// so equal steps look equal. Colors come from the tokens (D-021).
import { token } from "../theme/colors";

type RGB = [number, number, number];

export function hexToRgb(hex: string): RGB {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m?.[1]) return [255, 255, 255];
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

const toLin = (c: number) => {
  const x = c / 255;
  return x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
};
const toSrgb = (x: number) => {
  const c = x <= 0.0031308 ? 12.92 * x : 1.055 * Math.max(0, x) ** (1 / 2.4) - 0.055;
  return Math.round(Math.min(1, Math.max(0, c)) * 255);
};

function oklab([r, g, b]: RGB): RGB {
  const [R, G, B] = [toLin(r), toLin(g), toLin(b)];
  const l = Math.cbrt(0.4122214708 * R + 0.5363325363 * G + 0.0514459929 * B);
  const m = Math.cbrt(0.2119034982 * R + 0.6806995451 * G + 0.1073969566 * B);
  const s = Math.cbrt(0.0883024619 * R + 0.2817188376 * G + 0.6299787005 * B);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

function fromOklab([L, a, b]: RGB): RGB {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  return [
    toSrgb(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    toSrgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    toSrgb(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
  ];
}

/** A ramp function t ∈ [0, 1] → RGB between two colors (OKLab). */
export function makeRamp(from: string, to: string): (t: number) => RGB {
  const a = oklab(hexToRgb(from));
  const b = oklab(hexToRgb(to));
  return (t: number) => {
    const u = Math.min(1, Math.max(0, t));
    return fromOklab([
      a[0] + (b[0] - a[0]) * u,
      a[1] + (b[1] - a[1]) * u,
      a[2] + (b[2] - a[2]) * u,
    ]);
  };
}

/** The lens ramp from the tokens (read at call time). */
export function lensRamp(): (t: number) => RGB {
  return makeRamp(token("--scope"), token("--afterglow"));
}

/** RGBA pixels for an (n, m) matrix: NaN cells (outside the band) are transparent. */
export function costPixels(
  v: Float32Array,
  lo: number,
  hi: number,
  ramp: (t: number) => RGB,
): Uint8ClampedArray<ArrayBuffer> {
  const px = new Uint8ClampedArray(new ArrayBuffer(v.length * 4));
  const span = hi - lo || 1;
  for (let k = 0; k < v.length; k++) {
    const x = v[k] as number;
    if (!Number.isFinite(x)) continue; // alpha 0
    // square root: the accumulated cost grows fast along the path; this keeps its shape visible
    const [r, g, b] = ramp(Math.sqrt(Math.min(1, Math.max(0, (x - lo) / span))));
    px[4 * k] = r;
    px[4 * k + 1] = g;
    px[4 * k + 2] = b;
    px[4 * k + 3] = 255;
  }
  return px;
}
