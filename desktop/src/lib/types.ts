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

export interface SynthesisParams {
  temperature: number;
  cfg_weight: number;
  exaggeration: number;
  speed: number;
  seed: number;
  language: string;
  enable_watermark: boolean;
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
  is_available: boolean;
  is_loaded: boolean;
  default_params: SynthesisParams;
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
  default_engine: string;
  device_preference: string;
  use_half_precision: boolean;
  idle_unload_minutes: number;
  clear_device_cache_after_job: boolean;
  default_export_format: string;
  enable_audio_watermark: boolean;
  inject_metadata_tag: boolean;
  default_temperature: number;
  default_cfg_weight: number;
  default_exaggeration: number;
  default_speed: number;
  default_sentence_pause_ms: number;
  max_chars_per_chunk: number;
  log_level: string;
}

export interface HealthDetails {
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
}

export interface BatchRequestItem {
  text: string;
  filename: string;
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
