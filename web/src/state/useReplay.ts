// Open one replay stream for the page's lifetime, plus the ledger tail and verify state.
import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { Scene } from "../api/messages";
import { ReplayStream, replayUrl } from "../api/stream";
import { caseStore } from "./caseStore";
import { setStream } from "./controls";
import { dispatch } from "./dispatch";
import { matchStore } from "./matchStore";
import { replayStore } from "./replayStore";

/** Re-check the chain whenever the head moves (debounced: a batch of 3 proposals is one check). */
function watchVerify(): () => void {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let head = -1;
  const check = () =>
    api
      .ledgerVerify()
      .then((v) => caseStore.getState().setVerify(v))
      .catch((e: unknown) => caseStore.getState().setVerify(null, String(e)));
  const unsub = caseStore.subscribe((s) => {
    const h = s.blocks[s.blocks.length - 1]?.seq ?? -1;
    if (h === head) return;
    head = h;
    if (timer) clearTimeout(timer);
    timer = setTimeout(check, 400);
  });
  check();
  return () => {
    unsub();
    if (timer) clearTimeout(timer);
  };
}

export function useReplay(incidentId: string): { scene: Scene | null; sceneError: string | null } {
  const [scene, setScene] = useState<Scene | null>(null);
  const [sceneError, setSceneError] = useState<string | null>(null);
  const installation = useInstallation();

  useEffect(() => {
    replayStore.getState().reset();
    matchStore.getState().clear();
    caseStore.getState().reset();
    const stream = new ReplayStream({
      url: replayUrl(incidentId),
      onMessage: (m) => dispatch(m),
      onStatus: (s) => replayStore.getState().setStatus(s),
    });
    setStream(stream);
    stream.connect();
    api
      .ledgerTail(12)
      .then((bs) => caseStore.getState().addBlocks(bs))
      .catch(() => undefined);
    const stopVerify = watchVerify();
    return () => {
      stopVerify();
      setStream(null);
      stream.close();
    };
  }, [incidentId]);

  useEffect(() => {
    if (!installation) return;
    let alive = true;
    api
      .scene(installation)
      .then((s) => alive && setScene(s))
      .catch((e: unknown) => alive && setSceneError(String(e instanceof Error ? e.message : e)));
    return () => {
      alive = false;
    };
  }, [installation]);

  return { scene, sceneError };
}

function useInstallation(): string | null {
  const [id, setId] = useState<string | null>(
    replayStore.getState().hello?.installation_id ?? null,
  );
  useEffect(
    () =>
      replayStore.subscribe((s) => {
        const next = s.hello?.installation_id ?? null;
        setId((prev) => (prev === next ? prev : next));
      }),
    [],
  );
  return id;
}
