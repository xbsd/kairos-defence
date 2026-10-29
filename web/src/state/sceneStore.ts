// The live installation's scene and the list of installations, shared by the theater, the
// region constellation and Director captions (fetched once per Live watch, §16.4).
import { createStore } from "zustand/vanilla";

import type { Installation, Scene } from "../api/messages";

export interface SceneState {
  scene: Scene | null;
  installations: Installation[];
}

export interface SceneActions {
  setScene: (scene: Scene | null) => void;
  setInstallations: (list: Installation[]) => void;
}

export const sceneStore = createStore<SceneState & SceneActions>()((set) => ({
  scene: null,
  installations: [],
  setScene: (scene) => set({ scene }),
  setInstallations: (installations) => set({ installations }),
}));
