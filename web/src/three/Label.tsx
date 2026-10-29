import { Billboard, Text } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import { type Group, MeshBasicMaterial, type PerspectiveCamera, Vector3 } from "three";

import { FONT_UI } from "../theme/fontFiles";
import { color } from "./palette";
import { screenScale, type Vec3 } from "./sceneMath";

const tmp = new Vector3();

/**
 * The base material every label derives from. troika derives its text (and outline) materials
 * from the base by prototype, so depth settings must live here: a `material-depthTest` prop only
 * reaches the fill, and the labels were then cut by the grid and the asset boxes.
 */
const LABEL_BASE = new MeshBasicMaterial({
  transparent: true,
  depthTest: false,
  depthWrite: false,
  toneMapped: false,
});

type Tone =
  "--ink-hi" | "--ink-mid" | "--ink-low" | "--flash" | "--afterglow" | "--bone" | "--alert";

/**
 * A label that faces the camera and keeps a constant size on screen (`px` tall), in B612 from our
 * own origin (troika would otherwise fetch a CDN font, rule 5).
 */
export function Label(props: {
  text: string;
  position: Vec3;
  px?: number;
  tone?: Tone;
  anchorX?: "left" | "center" | "right";
  anchorY?: "top" | "middle" | "bottom";
  opacity?: number;
  /** Screen offset of the text from the anchor point, pixels (positive is up). */
  dyPx?: number;
  /** Screen offset to the right, pixels. */
  dxPx?: number;
}) {
  const ref = useRef<Group>(null);
  const px = props.px ?? 13;
  useFrame(({ camera, size }) => {
    const g = ref.current;
    if (!g) return;
    const d = camera.position.distanceTo(g.getWorldPosition(tmp));
    g.scale.setScalar(screenScale(d, (camera as PerspectiveCamera).fov ?? 45, size.height, px));
  });
  return (
    <Billboard ref={ref} position={props.position}>
      <Text
        position={[(props.dxPx ?? 0) / px, (props.dyPx ?? 0) / px, 0]}
        font={FONT_UI}
        fontSize={1}
        anchorX={props.anchorX ?? "center"}
        anchorY={props.anchorY ?? "bottom"}
        color={color(props.tone ?? "--ink-mid")}
        fillOpacity={props.opacity ?? 1}
        outlineWidth={0.08}
        outlineColor={color("--scope")}
        outlineOpacity={0.85}
        renderOrder={10}
        material={LABEL_BASE}
      >
        {props.text}
      </Text>
    </Billboard>
  );
}
