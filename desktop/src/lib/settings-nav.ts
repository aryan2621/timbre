import { useSyncExternalStore } from "react";
import type { PageKey } from "./pages";

interface SettingsNav {
  activeSection: string;
  search: string;
  returnPage: PageKey;
}

let state: SettingsNav = { activeSection: "appearance", search: "", returnPage: "studio" };
const listeners = new Set<() => void>();

function set(patch: Partial<SettingsNav>) {
  state = { ...state, ...patch };
  listeners.forEach((listener) => listener());
}

export const settingsNav = {
  setActiveSection: (activeSection: string) => set({ activeSection }),
  setSearch: (search: string) => set({ search }),
  setReturnPage: (returnPage: PageKey) => set({ returnPage }),
};

export function useSettingsNav(): SettingsNav {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => state,
  );
}
