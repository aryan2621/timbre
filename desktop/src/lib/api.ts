import type {
  AppSettings,
  BatchJob,
  BatchRequestItem,
  DownloadJob,
  EngineInfo,
  HealthDetails,
  HistoryEntry,
  JobStatus,
  ModelInfo,
  SynthesisParams,
  VoiceProfile,
} from "./types";

export const API_BASE =
  import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8756";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

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

/** Device + engine details shown in the sidebar status block. */
export async function getHealthDetails(): Promise<HealthDetails | null> {
  try {
    return await request<HealthDetails>("/api/health");
  } catch {
    return null;
  }
}

export const api = {
  listVoices: () => request<VoiceProfile[]>("/api/voices"),
  createVoice: (payload: {
    name: string;
    language: string;
    notes?: string;
    reference_path?: string;
    consent_confirmed?: boolean;
  }) =>
    request<VoiceProfile>("/api/voices", {
      method: "POST",
      body: JSON.stringify({ consent_confirmed: true, ...payload }),
    }),
  deleteVoice: (id: number) =>
    request<{ ok: boolean }>(`/api/voices/${id}`, { method: "DELETE" }),

  listEngines: () => request<EngineInfo[]>("/api/engines"),

  listHistory: (query = "") =>
    request<HistoryEntry[]>(
      `/api/history${query ? `?q=${encodeURIComponent(query)}` : ""}`,
    ),
  getHistoryPeaks: (id: number) =>
    request<{ id: number; peaks: number[]; duration_seconds: number }>(
      `/api/history/${id}/peaks`,
    ),
  deleteHistory: (id: number) =>
    request<{ ok: boolean }>(`/api/history/${id}`, { method: "DELETE" }),
  clearHistory: () =>
    request<{ deleted: number }>("/api/history", { method: "DELETE" }),

  listModels: () => request<ModelInfo[]>("/api/models"),
  startModelDownload: (modelId: string) =>
    request<DownloadJob>(`/api/models/${modelId}/download`, { method: "POST" }),
  deleteModel: (modelId: string) =>
    request<{ ok: boolean }>(`/api/models/${modelId}`, { method: "DELETE" }),
  getDownload: (jobId: string) =>
    request<DownloadJob>(`/api/downloads/${jobId}`),
  cancelDownload: (jobId: string) =>
    request<DownloadJob>(`/api/downloads/${jobId}/cancel`, { method: "POST" }),

  getSettings: () => request<AppSettings>("/api/settings"),
  updateSettings: (settings: Partial<AppSettings>) =>
    request<AppSettings>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),

  synthesize: (payload: {
    voice_id: number;
    engine_name: string;
    text: string;
    params: SynthesisParams;
    sentence_pause_ms: number;
  }) =>
    request<JobStatus>("/api/synthesize", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getJob: (id: string) => request<JobStatus>(`/api/jobs/${id}`),
  cancelJob: (id: string) =>
    request<JobStatus>(`/api/jobs/${id}/cancel`, { method: "POST" }),

  startBatch: (payload: {
    voice_id: number;
    engine_name: string;
    items: BatchRequestItem[];
    params: SynthesisParams;
    sentence_pause_ms: number;
    output_dir?: string | null;
  }) =>
    request<BatchJob>("/api/batch", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getBatch: (id: string) => request<BatchJob>(`/api/batch/${id}`),
  cancelBatch: (id: string) =>
    request<BatchJob>(`/api/batch/${id}/cancel`, { method: "POST" }),

  audioUrl: (path: string) => `${API_BASE}${path}`,
  clipUrl: (voiceId: number) => `${API_BASE}/api/voices/${voiceId}/clip`,
  jobAudioUrl: (jobId: string) => `${API_BASE}/api/jobs/${jobId}/audio`,
};
