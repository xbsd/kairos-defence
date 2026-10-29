import { Edges, type EdgesRef } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import { BufferGeometry, ExtrudeGeometry, Float32BufferAttribute, Shape, Vector2 } from "three";

import type { Scene } from "../api/messages";
import { replayStore } from "../state/replayStore";
import { Label } from "./Label";
import { color } from "./palette";
import {
  ASSET_HEIGHT_M,
  assetLabel,
  hatchSegments,
  ringCenter,
  toScene,
  type Origin,
  type Vec2,
} from "./sceneMath";

function segments(pairs: [Vec2, Vec2][], origin: Origin, y: number): BufferGeometry {
  const g = new BufferGeometry();
  const flat = pairs.flatMap(([a, b]) => [
    ...toScene(a[0], a[1], y, origin),
    ...toScene(b[0], b[1], y, origin),
  ]);
  g.setAttribute("position", new Float32BufferAttribute(flat, 3));
  return g;
}

function ring(poly: Vec2[], origin: Origin, y: number): BufferGeometry {
  const g = new BufferGeometry();
  g.setAttribute(
    "position",
    new Float32BufferAttribute(
      poly.flatMap(([x, yy]) => toScene(x, yy, y, origin)),
      3,
    ),
  );
  return g;
}

function Asset({ a, origin }: { a: Scene["assets"][number]; origin: Origin }) {
  const h = ASSET_HEIGHT_M[a.kind] ?? 8;
  const geom = useMemo(() => {
    const s = new Shape(a.polygon.map(([x, y]) => new Vector2(x - origin.x, y - origin.y)));
    return new ExtrudeGeometry(s, { depth: h, bevelEnabled: false });
  }, [a, origin, h]);
  const edges = useRef<EdgesRef>(null);
  const mid = color("--ink-mid");
  const flash = color("--flash");
  useFrame((_, dt) => {
    const e = edges.current;
    if (!e) return;
    // the targeted asset's edges turn flash blue once the target is identified (§9.2)
    const f = replayStore.getState().features;
    const target = f.length ? f[f.length - 1]?.target_asset_id : null;
    e.material.color.lerp(target === a.asset_id ? flash : mid, Math.min(1, dt * 6));
  });
  const [cx, , cz] = toScene(a.centroid_x_m, a.centroid_y_m, 0, origin);
  return (
    <group>
      <mesh geometry={geom} rotation={[-Math.PI / 2, 0, 0]}>
        <meshBasicMaterial color={mid} transparent opacity={0.08} depthWrite={false} />
        <Edges ref={edges} color={mid} lineWidth={1} threshold={20} />
      </mesh>
      {/* under the footprint: the drone and its tag fly above, so they do not collide */}
      <Label
        text={assetLabel(a.kind)}
        position={[cx, 0, cz]}
        px={12}
        tone="--ink-hi"
        anchorY="top"
        dyPx={-6}
      />
    </group>
  );
}

/** Fence, assets, labels and the radar shadow wedge of one installation (§17.3). */
export function Installation({ scene, origin }: { scene: Scene; origin: Origin }) {
  const fence = useMemo(() => ring(scene.fence, origin, 1), [scene.fence, origin]);
  const shadow = scene.radar_shadow;
  const hatch = useMemo(
    () =>
      shadow
        ? segments(
            shadow.polygons.flatMap((p) => hatchSegments(p, 140, 45)),
            origin,
            0.4,
          )
        : null,
    [shadow, origin],
  );
  const outline = useMemo(
    () => (shadow ? shadow.polygons.map((p) => ring(p, origin, 0.4)) : []),
    [shadow, origin],
  );
  const shadowLabel = useMemo(() => {
    const p = shadow?.polygons[0];
    if (!p) return null;
    const [x, y] = ringCenter(p);
    return toScene(x, y, 30, origin);
  }, [shadow, origin]);
  const low = color("--ink-low");
  return (
    <group>
      <lineLoop geometry={fence}>
        <lineBasicMaterial color={color("--ink-mid")} transparent opacity={0.9} />
      </lineLoop>
      {scene.assets.map((a) => (
        <Asset key={a.asset_id} a={a} origin={origin} />
      ))}
      {hatch ? (
        <lineSegments geometry={hatch}>
          <lineBasicMaterial color={low} transparent opacity={0.35} />
        </lineSegments>
      ) : null}
      {outline.map((g, i) => (
        <line key={i}>
          <primitive object={g} attach="geometry" />
          <lineBasicMaterial color={low} transparent opacity={0.6} />
        </line>
      ))}
      {shadow && shadowLabel ? (
        // right-anchored: the label reads leftward from the wedge's center, clear of the
        // recovery zone and the ghost labels that sit inside the shadow (D-166)
        <Label
          text={shadow.label}
          position={shadowLabel}
          px={13}
          tone="--ink-mid"
          anchorX="right"
          dxPx={-8}
        />
      ) : null}
    </group>
  );
}
