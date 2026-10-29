import { Bloom, EffectComposer, Vignette } from "@react-three/postprocessing";
import { BlendFunction, Effect } from "postprocessing";
import { forwardRef, useMemo } from "react";
import { Uniform } from "three";

import { useThrottledStore } from "../lib/useThrottledStore";
import { effectsOn, uiStore } from "../state/uiStore";

// Static film grain (D-012, D-144): a hash of the pixel coordinate, no time uniform, so the grain
// never moves on its own.
const GRAIN = /* glsl */ `
uniform float amount;
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  float n = hash(floor(gl_FragCoord.xy)) - 0.5;
  outputColor = vec4(inputColor.rgb + n * amount, inputColor.a);
}`;

class GrainEffect extends Effect {
  constructor(amount = 0.03) {
    super("StaticGrain", GRAIN, {
      blendFunction: BlendFunction.NORMAL,
      uniforms: new Map([["amount", new Uniform(amount)]]),
    });
  }
}

const Grain = forwardRef<GrainEffect, { amount?: number }>(function Grain({ amount = 0.03 }, ref) {
  const effect = useMemo(() => new GrainEffect(amount), [amount]);
  return <primitive ref={ref} object={effect} dispose={null} />;
});

/** Bloom (mipmap blur, threshold about 0.2), a light vignette and a faint static grain; all off
 * in reduce motion, Performance mode and when the frame rate degrades (§17.3, §17.11). */
export function Effects() {
  const on = useThrottledStore(uiStore, effectsOn, 4);
  if (!on) return null;
  return (
    <EffectComposer multisampling={0}>
      <Bloom mipmapBlur luminanceThreshold={0.2} luminanceSmoothing={0.3} intensity={0.7} />
      <Vignette offset={0.3} darkness={0.45} />
      <Grain amount={0.006} />
    </EffectComposer>
  );
}
