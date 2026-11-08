/**
 * Centralized API layer for Timbre.
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
import type {
  HuggingFaceStatus,
  AgentProfile,
  AgentTurn,
  McpServerDraft,
  SoundEngineInfo,
  SoundKind,
  SoundParams,
  SystemSpecs,
} from "@/lib/types";

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

async function readErrorDetail(response: Response): Promise<string> {
  const text = await response.text().catch(() => "");
  try {
    const parsed: unknown = JSON.parse(text);
    const detail = (parsed as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  } catch {
    /* not JSON: show the raw body */
  }
  return text;
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
    throw new Error(
      (await readErrorDetail(response)) || `${response.status} ${response.statusText}`,
    );
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
async function listVoices(): Promise<VoiceProfile[]> {
  return request<VoiceProfile[]>("/api/voices");
}

async function createVoice(payload: {
  name: string;
  language: string;
  notes?: string;
  reference_path?: string;
  consent_confirmed: boolean;
}): Promise<VoiceProfile> {
  return request<VoiceProfile>("/api/voices", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Uploads a recording made in the app; returns the path create_voice expects. */
async function uploadReference(wav: Blob): Promise<string> {
  const { reference_path } = await request<{ reference_path: string }>("/api/voices/reference", {
    method: "POST",
    headers: { "Content-Type": "audio/wav" },
    body: wav,
  });
  return reference_path;
}

async function deleteVoice(id: number): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/voices/${id}`, { method: "DELETE" });
}

/** Engine catalogue */
async function listEngines(): Promise<EngineInfo[]> {
  return request<EngineInfo[]>("/api/engines");
}

/** History */
async function listHistory(query = ""): Promise<HistoryEntry[]> {
  return request<HistoryEntry[]>(
    `/api/history${query ? `?q=${encodeURIComponent(query)}` : ""}`,
  );
}

async function getHistoryPeaks(id: number) {
  return request<{ id: number; peaks: number[]; duration_seconds: number }>(
    `/api/history/${id}/peaks`,
  );
}

async function deleteHistory(id: number): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/history/${id}`, { method: "DELETE" });
}

async function clearHistory(): Promise<{ deleted: number }> {
  return request<{ deleted: number }>("/api/history", { method: "DELETE" });
}

/** Models / downloads */
async function listModels(): Promise<ModelInfo[]> {
  return request<ModelInfo[]>("/api/models");
}

async function startModelDownload(modelId: string): Promise<DownloadJob> {
  return request<DownloadJob>(`/api/models/${modelId}/download`, { method: "POST" });
}

async function deleteModel(modelId: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/models/${modelId}`, { method: "DELETE" });
}

async function getDownload(jobId: string): Promise<DownloadJob> {
  return request<DownloadJob>(`/api/downloads/${jobId}`);
}

async function cancelDownload(jobId: string): Promise<DownloadJob> {
  return request<DownloadJob>(`/api/downloads/${jobId}/cancel`, { method: "POST" });
}

async function getSystemSpecs(): Promise<SystemSpecs> {
  return request<SystemSpecs>("/api/system");
}

async function getHuggingFaceStatus(): Promise<HuggingFaceStatus> {
  return request<HuggingFaceStatus>("/api/credentials/hugging-face");
}

async function saveHuggingFaceToken(token: string): Promise<HuggingFaceStatus> {
  return request<HuggingFaceStatus>("/api/credentials/hugging-face", {
    method: "PUT",
    body: JSON.stringify({ token }),
  });
}

async function removeHuggingFaceToken(): Promise<HuggingFaceStatus> {
  return request<HuggingFaceStatus>("/api/credentials/hugging-face", { method: "DELETE" });
}

/** Settings */
async function getSettings(): Promise<AppSettings> {
  return request<AppSettings>("/api/settings");
}

async function updateSettings(
  settings: Partial<AppSettings>,
): Promise<AppSettings> {
  return request<AppSettings>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

/** Synthesis */
async function synthesize(payload: {
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

async function listSoundEngines(): Promise<SoundEngineInfo[]> {
  return request<SoundEngineInfo[]>("/api/sounds/engines");
}

async function generateSound(payload: {
  engine_name: string;
  prompt: string;
  kind: SoundKind;
  params: SoundParams;
}): Promise<JobStatus> {
  return request<JobStatus>("/api/sounds", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function listAgents(): Promise<AgentProfile[]> {
  return request<AgentProfile[]>("/api/agents");
}

async function createAgent(payload: {
  name: string;
  voice_id: number | null;
  system_prompt: string;
  icon: string;
  llm_model: string;
  mcp_servers: McpServerDraft[];
}): Promise<AgentProfile> {
  return request<AgentProfile>("/api/agents", { method: "POST", body: JSON.stringify(payload) });
}

async function testMcpServer(url: string, token: string): Promise<string[]> {
  const { tools } = await request<{ tools: string[] }>("/api/agents/mcp/test", {
    method: "POST",
    body: JSON.stringify({ url, token }),
  });
  return tools;
}

async function deleteAgent(id: number): Promise<void> {
  await request(`/api/agents/${id}`, { method: "DELETE" });
}

async function warmAgents(): Promise<void> {
  await request("/api/agents/warm", { method: "POST" });
}

async function transcribe(wav: Blob): Promise<string> {
  const { text } = await request<{ text: string }>("/api/agents/transcribe", {
    method: "POST",
    body: wav,
    headers: { "Content-Type": "audio/wav" },
  });
  return text;
}

async function agentReply(id: number, messages: AgentTurn[]): Promise<string> {
  const { text } = await request<{ text: string }>(`/api/agents/${id}/reply`, {
    method: "POST",
    body: JSON.stringify({ messages }),
  });
  return text;
}

async function getJob(id: string): Promise<JobStatus> {
  return request<JobStatus>(`/api/jobs/${id}`);
}

async function cancelJob(id: string): Promise<JobStatus> {
  return request<JobStatus>(`/api/jobs/${id}/cancel`, { method: "POST" });
}

/** Batch */
async function startBatch(payload: {
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

async function getBatch(id: string): Promise<BatchJob> {
  return request<BatchJob>(`/api/batch/${id}`);
}

async function cancelBatch(id: string): Promise<BatchJob> {
  return request<BatchJob>(`/api/batch/${id}/cancel`, { method: "POST" });
}

/** One finished chunk of a running render, as WAV bytes. */
async function getJobChunk(jobId: string, index: number): Promise<ArrayBuffer> {
  await tokenReady;
  const response = await fetch(`${API_BASE}/api/jobs/${jobId}/chunks/${index}`, {
    headers: { "X-VoiceClone-Token": apiToken },
  });
  if (!response.ok) throw new Error(`Chunk ${index} unavailable (${response.status})`);
  return response.arrayBuffer();
}

/** URL builders */
function audioUrl(path: string): string {
  return withToken(`${API_BASE}${path}`);
}

function clipUrl(voiceId: number): string {
  return withToken(`${API_BASE}/api/voices/${voiceId}/clip`);
}

function jobAudioUrl(jobId: string): string {
  return withToken(`${API_BASE}/api/jobs/${jobId}/audio`);
}

/** Export the api object with all functions for easy import */
export const api = {
  checkHealth,
  getHealthDetails,
  listVoices,
  createVoice,
  uploadReference,
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
  getSystemSpecs,
  getHuggingFaceStatus,
  saveHuggingFaceToken,
  removeHuggingFaceToken,
  getSettings,
  updateSettings,
  synthesize,
  listSoundEngines,
  listAgents,
  createAgent,
  deleteAgent,
  testMcpServer,
  transcribe,
  warmAgents,
  agentReply,
  generateSound,
  getJob,
  cancelJob,
  startBatch,
  getBatch,
  cancelBatch,
  getJobChunk,
  audioUrl,
  clipUrl,
  jobAudioUrl,
};