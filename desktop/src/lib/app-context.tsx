import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { PageKey } from "./pages";

/**
 * App-wide actions and UI state.
 *
 * The command palette, the keyboard shortcuts and the header buttons all
 * need to trigger things that live inside a page (run a synthesis, export a
 * render, open the voice wizard). Pages register their handlers here; the
 * shell never needs to know how they work.
 */
export interface AppActionHandlers {
  runSynthesis?: () => void;
  exportRender?: () => void;
  clearScript?: () => void;
  focusScript?: () => void;
  togglePlayback?: () => void;
  createVoice?: () => void;
  importScript?: () => void;
}

/**
 * A one-shot request that crosses page boundaries.
 *
 * The command palette can ask for "create a voice" while the Studio is
 * mounted. The Voices page picks the intent up when it mounts and opens its
 * dialog. The intent is consumed exactly once.
 */
export type AppIntent = "new-voice" | "import-script" | "run-synthesis" | null;

interface AppContextValue {
  page: PageKey;
  navigate: (page: PageKey) => void;
  actions: AppActionHandlers;
  registerActions: (handlers: AppActionHandlers) => () => void;
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
  shortcutsOpen: boolean;
  setShortcutsOpen: (open: boolean) => void;
  intent: AppIntent;
  requestIntent: (intent: Exclude<AppIntent, null>) => void;
  consumeIntent: () => void;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({
  page,
  navigate,
  children,
}: {
  page: PageKey;
  navigate: (page: PageKey) => void;
  children: ReactNode;
}) {
  const actionsRef = useRef<AppActionHandlers>({});
  const [, forceRender] = useState(0);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [intent, setIntent] = useState<AppIntent>(null);

  const registerActions = useCallback((handlers: AppActionHandlers) => {
    actionsRef.current = { ...actionsRef.current, ...handlers };
    forceRender((value) => value + 1);
    return () => {
      const next = { ...actionsRef.current };
      for (const key of Object.keys(handlers) as Array<keyof AppActionHandlers>) {
        delete next[key];
      }
      actionsRef.current = next;
      forceRender((value) => value + 1);
    };
  }, []);

  const requestIntent = useCallback((next: Exclude<AppIntent, null>) => {
    setIntent(next);
  }, []);

  const consumeIntent = useCallback(() => {
    setIntent(null);
  }, []);

  const value = useMemo<AppContextValue>(
    () => ({
      page,
      navigate,
      actions: actionsRef.current,
      registerActions,
      paletteOpen,
      setPaletteOpen,
      shortcutsOpen,
      setShortcutsOpen,
      intent,
      requestIntent,
      consumeIntent,
    }),
    [
      page,
      navigate,
      registerActions,
      paletteOpen,
      setPaletteOpen,
      shortcutsOpen,
      setShortcutsOpen,
      intent,
      requestIntent,
      consumeIntent,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const context = useContext(AppContext);
  if (!context) throw new Error("useApp must be used within an AppProvider");
  return context;
}

/** Registers page-level actions for as long as the page is mounted. */
export function useAppActions(handlers: AppActionHandlers): void {
  const { registerActions } = useApp();
  const ref = useRef(handlers);
  ref.current = handlers;
  const keys = Object.keys(handlers).sort().join(",");

  useEffect(() => {
    // Register stable proxies so the shell always calls the latest closure
    // without re-binding the registration on every render.
    const stable: AppActionHandlers = {};
    for (const key of Object.keys(handlers) as Array<keyof AppActionHandlers>) {
      stable[key] = () => ref.current[key]?.();
    }
    return registerActions(stable);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [registerActions, keys]);
}
