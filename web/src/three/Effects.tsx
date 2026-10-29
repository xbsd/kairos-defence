import { Bloom, EffectComposer, Vignette } from "@react-three/postprocessing";

import { useThrottledStore } from "../lib/useThrottledStore";
import { effectsOn, uiStore } from "../state/uiStore";

/** Bloom (mipmap blur, threshold about 0.2) and a light vignette; off in reduce motion and when
 * the frame rate degrades (§17.3, §17.11). No film grain in phase 7. */
export function Effects() {
  const on = useThrottledStore(uiStore, effectsOn, 4);
  if (!on) return null;
  return (
    <EffectComposer multisampling={0}>
      <Bloom mipmapBlur luminanceThreshold={0.2} luminanceSmoothing={0.3} intensity={0.7} />
      <Vignette offset={0.3} darkness={0.45} />
    </EffectComposer>
  );
}
