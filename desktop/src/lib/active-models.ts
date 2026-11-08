import { useSyncExternalStore } from "react";
import type { ModelCategory } from "./types";

const KEY = "timbre.activeModels";
type Chosen = Partial<Record<ModelCategory, string>>;

function read(): Chosen {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}") as Chosen;
  } catch {
    return {};
  }
}

let state = read();
const listeners = new Set<() => void>();

export const activeModels = {
  set(category: ModelCategory, modelId: string) {
    state = { ...state, [category]: modelId };
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      // storage unavailable: the choice lasts for this session
    }
    listeners.forEach((listener) => listener());
  },
};

export function useActiveModels(): Chosen {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => state,
  );
}
