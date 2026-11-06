/**
 * Centralized API layer for VoiceClone Studio.
 *
 * All frontend components should use this layer instead of calling
 * the raw fetch API. This ensures a single source of truth for
 * request shapes, response types, and error handling.
 *
 * IPC flow: Frontend -> this module -> Tauri invoke -> Rust command -> Python (HTTP / stdlib)
 */

import type { VoiceProfile } from "@/lib/types";
import type { EngineInfo } from "@/lib/types";
import type { HistoryEntry } from "@/lib/types";
import type { ModelInfo } from "@/lib/types";
import { invoke } from "@tauri-apps/api/core";
import { IS_TAURI } from "@/lib/desktop";
import type { DownloadJob } from "@/lib/types";
import type { AppSettings } from "@/lib/types";
import type { SynthesisParams } from "@/lib/types";
import type { JobStatus } from "@/lib/types";
import type { BatchJob } from "@/lib/types";

const API_BASE =
  import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8756";

/**
 * The desktop shell starts the API with a per-launch secret and hands it to
 * us over IPC. Outside Tauri (browser dev) the API runs without one.
 */
let apiToken = "";
const tokenReady: Promise<void> = IS_TAURI
  ? invoke<string>("api_token")
      .then((token) => {
        apiToken = token;
      })
      .catch(() => undefined)
  : Promise.resolve();

/** For `<audio src>` and other URLs that cannot carry a header. */
function withToken(url: string): string {
  if (!apiToken) return url;
  return `${url}${url.includes("?") ? "&" : "?"}token=${apiToken}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  await tokenReady;
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-VoiceClone-Token": apiToken,
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

/** Health check */
export async function checkHealth(): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    const response = await fetch(`${API_BASE}/api/health`, {
      signal: controller.signal,
    });
    clearTimeout(timer);
    return response.ok;
  } catch {
    return false;
  }
}

/** Fetches an audio blob (export / playback source) with shared error handling. */
export async function fetchAudioBlob(url: string): Promise<Blob> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Audio fetch failed: ${response.status} ${response.statusText}`);
  }
  return response.blob();
}
export async function getHealthDetails() {
  try {
    return await request<{
      ok: boolean;
      version: string;
      device: {
        type: string;
        name: string;
        total_memory_mb: number;
        warning: string | null;
      };
      engines: string[];
      data_dir: string;
    }>("/api/health");
  } catch {
    return null;
  }
}

/** Voice profiles */
export async function listVoices(): Promise<VoiceProfile[]> {
  return request<VoiceProfile[]>("/api/voices");
}

export async function createVoice(payload: {
  name: string;
  language: string;
  notes?: string;
  reference_path?: string;
  consent_confirmed?: boolean;
}): Promise<VoiceProfile> {
  return request<VoiceProfile>("/api/voices", {
    method: "POST",
    body: JSON.stringify({ consent_confirmed: true, ...payload }),
  });
}

export async function deleteVoice(id: number): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/voices/${id}`, { method: "DELETE" });
}

/** Engine catalogue */
export async function listEngines(): Promise<EngineInfo[]> {
  return request<EngineInfo[]>("/api/engines");
}

/** History */
export async function listHistory(query = ""): Promise<HistoryEntry[]> {
  return request<HistoryEntry[]>(
    `/api/history${query ? `?q=${encodeURIComponent(query)}` : ""}`,
  );
}

export async function getHistoryPeaks(id: number) {
  return request<{ id: number; peaks: number[]; duration_seconds: number }>(
    `/api/history/${id}/peaks`,
  );
}

export async function deleteHistory(id: number): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/history/${id}`, { method: "DELETE" });
}

export async function clearHistory(): Promise<{ deleted: number }> {
  return request<{ deleted: number }>("/api/history", { method: "DELETE" });
}

/** Models / downloads */
export async function listModels(): Promise<ModelInfo[]> {
  return request<ModelInfo[]>("/api/models");
}

export async function startModelDownload(modelId: string): Promise<DownloadJob> {
  return request<DownloadJob>(`/api/models/${modelId}/download`, { method: "POST" });
}

export async function deleteModel(modelId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/models/${modelId}`, { method: "DELETE" });
}

export async function getDownload(jobId: string): Promise<DownloadJob> {
  return request<DownloadJob>(`/api/downloads/${jobId}`);
}

export async function cancelDownload(jobId: string): Promise<DownloadJob> {
  return request<DownloadJob>(`/api/downloads/${jobId}/cancel`, { method: "POST" });
}

/** Settings */
export async function getSettings(): Promise<AppSettings> {
  return request<AppSettings>("/api/settings");
}

export async function updateSettings(
  settings: Partial<AppSettings>,
): Promise<AppSettings> {
  return request<AppSettings>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

/** Synthesis */
export async function synthesize(payload: {
  voice_id: number;
  engine_name: string;
  text: string;
  params: SynthesisParams;
  sentence_pause_ms: number;
}): Promise<JobStatus> {
  return request<JobStatus>("/api/synthesize", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getJob(id: string): Promise<JobStatus> {
  return request<JobStatus>(`/api/jobs/${id}`);
}

export async function cancelJob(id: string): Promise<JobStatus> {
  return request<JobStatus>(`/api/jobs/${id}/cancel`, { method: "POST" });
}

/** Batch */
export async function startBatch(payload: {
  voice_id: number;
  engine_name: string;
  items: { text: string; filename: string }[];
  params: SynthesisParams;
  sentence_pause_ms: number;
  output_dir?: string | null;
}): Promise<BatchJob> {
  return request<BatchJob>("/api/batch", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getBatch(id: string): Promise<BatchJob> {
  return request<BatchJob>(`/api/batch/${id}`);
}

export async function cancelBatch(id: string): Promise<BatchJob> {
  return request<BatchJob>(`/api/batch/${id}/cancel`, { method: "POST" });
}

/** URL builders */
export function audioUrl(path: string): string {
  return withToken(`${API_BASE}${path}`);
}

export function clipUrl(voiceId: number): string {
  return withToken(`${API_BASE}/api/voices/${voiceId}/clip`);
}

export function jobAudioUrl(jobId: string): string {
  return withToken(`${API_BASE}/api/jobs/${jobId}/audio`);
}

/** Export the api object with all functions for easy import */
export const api = {
  checkHealth,
  getHealthDetails,
  listVoices,
  createVoice,
  deleteVoice,
  listEngines,
  listHistory,
  getHistoryPeaks,
  deleteHistory,
  clearHistory,
  listModels,
  startModelDownload,
  deleteModel,
  getDownload,
  cancelDownload,
  getSettings,
  updateSettings,
  synthesize,
  getJob,
  cancelJob,
  startBatch,
  getBatch,
  cancelBatch,
  audioUrl,
  clipUrl,
  jobAudioUrl,
};