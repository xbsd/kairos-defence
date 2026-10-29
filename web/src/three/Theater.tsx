import { Canvas, useFrame } from "@react-three/fiber";
import { memo, useMemo, useRef } from "react";

import type { Scene } from "../api/messages";
import { useThrottledStore } from "../lib/useThrottledStore";
import { replayStore } from "../state/replayStore";
import { reduceMotion, uiStore, type CameraPreset } from "../state/uiStore";
import { token } from "../theme/colors";
import { OVERVIEW } from "./camera";
import { CameraRig } from "./CameraRig";
import { Core } from "./Core";
import { Drone } from "./Drone";
import { Effects } from "./Effects";
import { Ground } from "./Ground";
import { Installation } from "./Installation";
import { Packets } from "./Packets";
import { PERF_START, perfLabel, stepPerf } from "./perf";
import { Radar } from "./Radar";
import { Rf } from "./Rf";
import { Roads } from "./Roads";
import type { Origin } from "./sceneMath";
import { theaterSummary } from "./summary";

/** One Drone per live track (the set changes rarely: checked once a second). */
function Drones({ origin }: { origin: Origin }) {
  const ids = useThrottledStore(replayStore, (s) => Object.keys(s.tracks).sort().join("|"), 1);
  return (
    <>{ids ? ids.split("|").map((id) => <Drone key={id} trackId={id} origin={origin} />) : null}</>
  );
}

/** Auto-degrade (§17.11): feeds every frame's time into the policy. */
function PerfMonitor() {
  const st = useRef(PERF_START);
  useFrame((_, dt) => {
    const next = stepPerf(st.current, dt * 1000, performance.now() / 1000);
    if (next.level !== st.current.level) uiStore.getState().setPerfLevel(next.level);
    st.current = next;
  });
  return null;
}

const SceneContent = memo(function SceneContent({ scene }: { scene: Scene }) {
  const origin = useMemo(() => ({ x: scene.origin_x_m, y: scene.origin_y_m }), [scene]);
  const radar = scene.sensors.find((s) => s.kind === "radar");
  const rfs = scene.sensors.filter((s) => s.kind === "rf");
  return (
    <>
      <Installation scene={scene} origin={origin} />
      <Roads roads={scene.roads} origin={origin} />
      {radar ? <Radar sensor={radar} origin={origin} /> : null}
      {rfs.map((s) => (
        <Rf key={s.sensor_id} sensor={s} origin={origin} />
      ))}
      <Drones origin={origin} />
      <Packets scene={scene} origin={origin} />
      <CameraRig scene={scene} origin={origin} />
    </>
  );
});

const PRESETS: [CameraPreset, string][] = [
  ["overview", "Overview"],
  ["follow", "Follow"],
  ["target", "Target"],
];

function CameraButtons() {
  const cam = useThrottledStore(uiStore, (s) => s.camera, 10);
  return (
    <div
      role="group"
      aria-label="Camera"
      className="absolute top-2 right-2 flex gap-1 rounded-panel border border-hairline bg-glass p-1 backdrop-blur-glass"
    >
      {PRESETS.map(([id, label]) => (
        <button
          key={id}
          type="button"
          aria-pressed={cam === id}
          onClick={() => uiStore.getState().setCamera(id)}
          className={`rounded-button px-2 py-1 text-13 transition-colors duration-(--dur-micro) ease-(--ease-out) ${
            cam === id ? "bg-hairline text-flash" : "text-ink-mid hover:text-ink-hi"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function Summary() {
  const text = useThrottledStore(replayStore, (s) => theaterSummary(s), 1);
  return (
    <p className="sr-only" aria-live="polite" data-testid="theater-summary">
      {text}
    </p>
  );
}

/**
 * The live theater (SPEC §17.3): the installation in local meters, the radar and RF sensors, the
 * live tracks, data packets and the Kairos core, all driven by stream events and the replay clock.
 */
export function Theater({ scene }: { scene: Scene | null }) {
  const perf = useThrottledStore(uiStore, (s) => perfLabel(s.perfLevel, reduceMotion(s)), 4);
  const background = token("--scope");
  return (
    <div data-testid="theater" data-perf={perf} className="relative h-full w-full bg-scope">
      <Canvas
        dpr={[1, 2]}
        gl={{ antialias: true, powerPreference: "high-performance" }}
        camera={{ fov: 45, near: 5, far: 40000, position: OVERVIEW.position }}
        aria-hidden="true"
      >
        <color attach="background" args={[background]} />
        <Ground />
        <Core />
        {scene ? <SceneContent scene={scene} /> : <CameraRig scene={null} origin={null} />}
        <PerfMonitor />
        <Effects />
      </Canvas>
      {scene ? null : (
        <p className="absolute top-3 left-3 text-13 text-ink-mid">Loading the installation</p>
      )}
      <CameraButtons />
      <Summary />
    </div>
  );
}
