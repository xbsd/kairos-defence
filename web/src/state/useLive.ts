// Live mode's page lifetime (D-184): one live stream for the watched installation, its scene,
// the scenario catalog, the ledger tail and verify state, and GET /api/live/status every 2 s
// (the incident list survives a reload; the stream keeps it current in between).
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { LiveStream, liveUrl } from "../api/liveStream";
import type { Scene } from "../api/messages";
import { caseStore } from "./caseStore";
import { liveStore } from "./liveStore";
import { dispatchLive } from "./liveDispatch";
import { matchStore } from "./matchStore";
import { replayStore } from "./replayStore";
import { sceneStore } from "./sceneStore";
import { watchVerify } from "./useReplay";

export const STATUS_EVERY_MS = 2000;

export function refreshStatus(): Promise<void> {
  return api
    .liveStatus()
    .then((s) => liveStore.getState().setStatus(s))
    .catch((e: unknown) => liveStore.getState().setStatus(null, String(e)));
}

export function useLive(installation: string): { scene: Scene | null; sceneError: string | null } {
  const [scene, setScene] = useState<Scene | null>(null);
  const [sceneError, setSceneError] = useState<string | null>(null);

  useEffect(() => {
    replayStore.getState().reset();
    matchStore.getState().clear();
    const stream = new LiveStream({
      url: liveUrl(installation),
      onMessage: (m) => {
        dispatchLive(m);
        if (m.type === "incident_opened" || m.type === "incident_closed") void refreshStatus();
      },
      onStatus: (s) => replayStore.getState().setStatus(s),
    });
    stream.connect();
    return () => stream.close();
  }, [installation]);

  useEffect(() => {
    caseStore.getState().reset();
    api
      .ledgerTail(12)
      .then((bs) => caseStore.getState().addBlocks(bs))
      .catch(() => undefined);
    api
      .liveScenarios()
      .then((s) => liveStore.getState().setScenarios(s))
      .catch(() => undefined);
    const stopVerify = watchVerify();
    let timer: ReturnType<typeof setTimeout> | null = null;
    let alive = true;
    const poll = () => {
      void refreshStatus().finally(() => {
        if (alive) timer = setTimeout(poll, STATUS_EVERY_MS);
      });
    };
    poll();
    return () => {
      alive = false;
      stopVerify();
      if (timer) clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    let alive = true;
    api
      .scene(installation)
      .then((s) => {
        if (!alive) return;
        setScene(s);
        setSceneError(null);
        sceneStore.getState().setScene(s);
      })
      .catch((e: unknown) => alive && setSceneError(String(e instanceof Error ? e.message : e)));
    return () => {
      alive = false;
    };
  }, [installation]);

  return { scene, sceneError };
}
