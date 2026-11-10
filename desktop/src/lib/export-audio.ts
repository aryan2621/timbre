import { useSyncExternalStore } from "react";
import { toast } from "sonner";
import { fetchAudioBlob } from "@/lib/api";
import { IS_TAURI, downloadBlob, writeBlobToPath } from "@/lib/desktop";

export interface ExportRequest {
  url: string;
  name: string;
}

let current: ExportRequest | null = null;
const listeners = new Set<() => void>();

function publish(next: ExportRequest | null): void {
  current = next;
  listeners.forEach((listener) => listener());
}

function randomSuffix(): string {
  return Math.random().toString(36).slice(2, 6);
}

export function exportAudio(url: string, prefix: string): void {
  const base = prefix.trim().replace(/[^\w-]+/g, "-").replace(/^-+|-+$/g, "") || "timbre";
  publish({ url, name: `${base}-${randomSuffix()}` });
}

export function closeExport(): void {
  publish(null);
}

export function useExportRequest(): ExportRequest | null {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => current,
  );
}

export function sanitizeFilename(name: string): string {
  return name.trim().replace(/\.wav$/i, "").replace(/[\\/:*?"<>|]+/g, "-");
}

export async function saveAudio(url: string, name: string): Promise<boolean> {
  const filename = `${sanitizeFilename(name)}.wav`;
  try {
    const blob = await fetchAudioBlob(url);
    if (IS_TAURI) {
      const { downloadDir, join } = await import("@tauri-apps/api/path");
      const path = await join(await downloadDir(), filename);
      if (await writeBlobToPath(path, blob)) {
        toast.success("Saved to Downloads", { description: filename });
        return true;
      }
    }
    downloadBlob(blob, filename);
    toast.success("Download started", { description: filename });
    return true;
  } catch {
    toast.error("Export failed");
    return false;
  }
}
