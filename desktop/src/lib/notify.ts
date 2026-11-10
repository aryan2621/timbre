import { useSyncExternalStore } from "react";
import { IS_TAURI } from "@/lib/desktop";

const KEY = "timbre.notifyWhenDone";

function read(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

let enabled = read();
const listeners = new Set<() => void>();

async function permitted(): Promise<boolean> {
  if (IS_TAURI) {
    const { isPermissionGranted, requestPermission } = await import("@tauri-apps/plugin-notification");
    return (await isPermissionGranted()) || (await requestPermission()) === "granted";
  }
  return "Notification" in window && (Notification.permission === "granted" || (await Notification.requestPermission()) === "granted");
}

export async function setNotifyWhenDone(next: boolean): Promise<boolean> {
  const allowed = next ? await permitted().catch(() => false) : false;
  enabled = allowed;
  try {
    localStorage.setItem(KEY, allowed ? "1" : "0");
  } catch {
    enabled = allowed;
  }
  listeners.forEach((listener) => listener());
  return allowed || !next;
}

export function useNotifyWhenDone(): boolean {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => enabled,
  );
}

export async function notifyDone(title: string, body: string): Promise<void> {
  if (!enabled) return;
  try {
    if (IS_TAURI) {
      const { sendNotification } = await import("@tauri-apps/plugin-notification");
      sendNotification({ title, body });
    } else {
      new Notification(title, { body });
    }
  } catch (error) {
    console.error("Notification failed", error);
  }
}
