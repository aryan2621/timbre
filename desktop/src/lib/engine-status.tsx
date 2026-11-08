/**
 * The engine connection store.
 *
 * The old app polled `/api/health` in `App.tsx` and showed the answer in two
 * places (a header pill and a sidebar footer that also claimed "100% offline").
 * There is now exactly one status, one poller and one rendering component.
 */
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
import { checkHealth, getHealthDetails } from "./api";

export type EngineConnection = "connecting" | "online" | "offline";

export interface EngineDevice {
  type: string;
  name: string;
  total_memory_mb: number;
}

interface EngineStatusValue {
  status: EngineConnection;
  device: EngineDevice | null;
  lastChecked: number | null;
  /** True while the first check is still running. */
  checking: boolean;
  refresh: () => void;
}

const EngineStatusContext = createContext<EngineStatusValue | null>(null);

const POLL_INTERVAL = 5000;
const STARTUP_POLL_INTERVAL = 1000;
const STARTUP_GRACE_MS = 120_000;

export function EngineStatusProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<EngineConnection>("connecting");
  const [device, setDevice] = useState<EngineDevice | null>(null);
  const [lastChecked, setLastChecked] = useState<number | null>(null);
  const [checking, setChecking] = useState(true);
  const mounted = useRef(true);
  const online = status === "online";
  const startedAt = useRef(0);
  const everOnline = useRef(false);

  const isStarting = () =>
    !everOnline.current && Date.now() - startedAt.current < STARTUP_GRACE_MS;

  const refresh = useCallback(() => {
    let cancelled = false;
    void (async () => {
      try {
        const healthy = await checkHealth();
        if (cancelled || !mounted.current) return;
        if (healthy) everOnline.current = true;
        setStatus(healthy ? "online" : isStarting() ? "connecting" : "offline");
        setLastChecked(Date.now());
        if (healthy) {
          const details = await getHealthDetails();
          if (!cancelled && mounted.current && details?.device) {
            setDevice(details.device);
          }
        }
      } catch {
        if (!cancelled && mounted.current) setStatus(isStarting() ? "connecting" : "offline");
      } finally {
        if (!cancelled && mounted.current) setChecking(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    mounted.current = true;
    if (startedAt.current === 0) startedAt.current = Date.now();
    refresh();
    const timer = window.setInterval(
      refresh,
      online ? POLL_INTERVAL : STARTUP_POLL_INTERVAL,
    );
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
    };
  }, [refresh, online]);

  const value = useMemo<EngineStatusValue>(
    () => ({ status, device, lastChecked, checking, refresh }),
    [status, device, lastChecked, checking, refresh],
  );

  return (
    <EngineStatusContext.Provider value={value}>{children}</EngineStatusContext.Provider>
  );
}

export function useEngineStatus(): EngineStatusValue {
  const context = useContext(EngineStatusContext);
  if (!context) {
    throw new Error("useEngineStatus must be used within an EngineStatusProvider");
  }
  return context;
}
