interface VoiceClip {
  id: number;
  profile_id: number;
  file_path: string;
  original_filename: string;
  duration_seconds: number;
  sample_rate: number;
  is_active: boolean;
  quality_score: number;
  created_at: string;
}

export interface VoiceProfile {
  id: number;
  name: string;
  language: string;
  notes: string;
  consent_confirmed: boolean;
  consent_timestamp: string | null;
  created_at: string;
  updated_at: string;
  clips: VoiceClip[];
  primary_audio_path: string | null;
}

export interface ParamSpec {
  key: string;
  label: string;
  min: number;
  max: number;
  step: number;
  default: number | string;
  kind: "number" | "select";
  options: string[];
  description: string;
  group: "style" | "delivery" | "advanced";
}

export type ParamExtra = Record<string, number | string>;

export interface SynthesisParams {
  temperature: number;
  cfg_weight: number;
  exaggeration: number;
  speed: number;
  seed: number;
  language: string;
  enable_watermark: boolean;
  top_p?: number;
  repetition_penalty?: number;
  extra?: ParamExtra;
}

export interface EngineInfo {
  name: string;
  license_name: string;
  license_url: string;
  commercial_permitted: boolean;
  license_notice: string;
  supported_languages: string[];
  native_sample_rate: number;
  requires_gpu_recommended: boolean;
  /** Installed and supported by this machine's hardware. */
  is_available: boolean;
  /** Why the engine can't be used here, or null when it can. */
  unavailable_reason: string | null;
  model_id?: string | null;
  controls?: ParamSpec[];
  is_loaded: boolean;
  default_params: SynthesisParams;
}

export type SoundKind = "sfx" | "music";

export interface SoundParams {
  duration_seconds: number;
  steps: number;
  guidance: number;
  seed: number;
  negative_prompt: string;
  lyrics: string;
  extra?: ParamExtra;
}

export interface SoundEngineInfo {
  name: string;
  license_name: string;
  license_url: string;
  commercial_permitted: boolean;
  license_notice: string;
  native_sample_rate: number;
  max_duration_seconds: number;
  kinds: SoundKind[];
  supports_lyrics: boolean;
  supports_negative_prompt: boolean;
  requires_gpu_recommended: boolean;
  is_available: boolean;
  unavailable_reason: string | null;
  model_id: string | null;
  controls?: ParamSpec[];
  is_loaded: boolean;
  default_params: SoundParams;
}

type JobState = "queued" | "running" | "done" | "failed" | "cancelled";

export interface JobStatus {
  id: string;
  state: JobState;
  progress: number;
  current_chunk: number;
  total_chunks: number;
  eta: string;
  message: string;
  error?: string | null;
  audio_url?: string | null;
  peaks?: number[] | null;
  duration_seconds?: number;
  sample_rate?: number;
  preview_path?: string | null;
  seed?: number;
  /** Finished chunks the UI can already fetch and play (play-while-rendering). */
  chunks_ready?: number;
}

export interface HistoryEntry {
  id: number;
  voice_id: number | null;
  voice_name: string;
  engine_name: string;
  prompt_text: string;
  parameters_json: string;
  seed: number;
  audio_path: string;
  duration_seconds: number;
  sample_rate: number;
  created_at: string;
  kind: "speech" | "sfx" | "music";
}

export type ModelCategory = "voice-cloning" | "sound" | "music" | "voice-agent";

export type FitStatus = "recommended" | "possible" | "blocked";

export interface SystemSpecs {
  os_name: string;
  cpu_name: string;
  cpu_cores: number;
  ram_gb: number;
  accelerator: "cuda" | "mps" | "cpu";
  accelerator_name: string;
  memory_budget_gb: number;
  memory_reserved_gb: number;
  disk_free_bytes: number;
}

export interface HuggingFaceStatus {
  configured: boolean;
  username: string | null;
  valid?: boolean;
  reachable?: boolean;
}

export interface ModelInfo {
  id: string;
  name: string;
  version: string;
  license_name: string;
  commercial_allowed: boolean;
  license_notice: string;
  total_bytes: number;
  is_downloaded: boolean;
  category: ModelCategory;
  requires_token: boolean;
  gated_url: string;
  min_memory_gb: number;
  fit: { status: FitStatus; reasons: string[] };
  /** Why the matching engine can't run on this machine, or null. */
  unavailable_reason?: string | null;
  download_job?: DownloadJob | null;
}

type DownloadState = "queued" | "running" | "done" | "failed" | "cancelled";

export interface DownloadJob {
  id: string;
  model_id: string;
  model_name: string;
  state: DownloadState;
  progress: number;
  downloaded_bytes: number;
  total_bytes: number;
  speed_mb_s: number;
  message: string;
  error?: string | null;
  file_path?: string | null;
}

export interface AppSettings {
  theme: string;
  device_preference: string;
  clear_device_cache_after_job: boolean;
  max_chars_per_chunk: number;
  log_level: string;
}

type BatchItemState =
  | "pending"
  | "running"
  | "done"
  | "failed"
  | "cancelled";

interface BatchItem {
  index: number;
  filename: string;
  text: string;
  state: BatchItemState;
  duration_seconds: number;
  audio_url: string | null;
  error: string | null;
}

export interface BatchJob {
  id: string;
  state: "queued" | "running" | "done" | "failed" | "cancelled";
  progress: number;
  message: string;
  error: string | null;
  eta: string;
  total: number;
  completed: number;
  failed: number;
  current_index: number;
  items: BatchItem[];
  output_dir: string | null;
}

export interface AgentProfile {
  id: number;
  name: string;
  voice_id: number | null;
  system_prompt: string;
  icon: string;
  llm_model: string;
  mcp_servers: McpServerInfo[];
  created_at: string;
}

export interface McpServerInfo {
  name: string;
  url: string;
  has_token: boolean;
}

export interface McpServerDraft {
  name: string;
  url: string;
  token: string;
}

export interface AgentTurn {
  role: "user" | "assistant";
  content: string;
}
