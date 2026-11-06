import type {
  AppSettings,
  EngineInfo,
  HistoryEntry,
  ModelInfo,
  VoiceProfile,
} from "./types";
import { IS_TAURI } from "./desktop";

/**
 * Demo data is for browser previews only. In the desktop app it would show
 * voices and models that do not exist, so an unreachable engine shows nothing.
 */
export const demoList = <T,>(list: T[]): T[] => (IS_TAURI ? [] : list);

const now = new Date();
const daysAgo = (n: number) =>
  new Date(now.getTime() - n * 86_400_000).toISOString();

export const mockVoices: VoiceProfile[] = [
  {
    id: 1,
    name: "Elena Storyteller",
    language: "en",
    notes: "Warm, measured narration. Recorded in a treated room.",
    consent_confirmed: true,
    consent_timestamp: daysAgo(12),
    created_at: daysAgo(12),
    updated_at: daysAgo(12),
    clips: [
      {
        id: 1,
        profile_id: 1,
        file_path: "/demo/elena.wav",
        original_filename: "elena_reference.wav",
        duration_seconds: 14.2,
        sample_rate: 24000,
        is_active: true,
        quality_score: 92,
        created_at: daysAgo(12),
      },
    ],
    primary_audio_path: "/demo/elena.wav",
  },
  {
    id: 2,
    name: "Marcus Documentary",
    language: "en",
    notes: "Deep resonant documentary read.",
    consent_confirmed: true,
    consent_timestamp: daysAgo(9),
    created_at: daysAgo(9),
    updated_at: daysAgo(9),
    clips: [
      {
        id: 2,
        profile_id: 2,
        file_path: "/demo/marcus.wav",
        original_filename: "marcus_reference.wav",
        duration_seconds: 11.8,
        sample_rate: 24000,
        is_active: true,
        quality_score: 87,
        created_at: daysAgo(9),
      },
    ],
    primary_audio_path: "/demo/marcus.wav",
  },
  {
    id: 3,
    name: "Aiko Narration",
    language: "ja",
    notes: "Bright, friendly conversational tone.",
    consent_confirmed: true,
    consent_timestamp: daysAgo(4),
    created_at: daysAgo(4),
    updated_at: daysAgo(4),
    clips: [
      {
        id: 3,
        profile_id: 3,
        file_path: "/demo/aiko.wav",
        original_filename: "aiko_reference.wav",
        duration_seconds: 8.6,
        sample_rate: 24000,
        is_active: true,
        quality_score: 78,
        created_at: daysAgo(4),
      },
    ],
    primary_audio_path: "/demo/aiko.wav",
  },
];

const defaultParams = {
  temperature: 0.75,
  cfg_weight: 2.5,
  exaggeration: 1.0,
  speed: 1.0,
  seed: -1,
  language: "en",
  enable_watermark: true,
};

export const mockEngines: EngineInfo[] = [
  {
    name: "Chatterbox TTS",
    license_name: "MIT License",
    license_url: "https://opensource.org/licenses/MIT",
    commercial_permitted: true,
    license_notice: "MIT licensed and fully permitted for commercial and non-commercial local use.",
    supported_languages: ["ar","da","de","el","en","es","fi","fr","he","hi","it","ja","ko","ms","nl","no","pl","pt","ru","sv","sw","tr","zh"],
    native_sample_rate: 24000,
    requires_gpu_recommended: false,
    is_available: true,
    is_loaded: false,
    default_params: defaultParams,
  },
  {
    name: "XTTS v2 (Coqui)",
    license_name: "Coqui Public Model License (CPML)",
    license_url: "https://coqui.ai/cpml",
    commercial_permitted: false,
    license_notice: "NON-COMMERCIAL LICENSE WARNING: XTTS v2 may not be used for commercial purposes.",
    supported_languages: ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh", "ja", "ko", "hu", "hi"],
    native_sample_rate: 24000,
    requires_gpu_recommended: true,
    is_available: false,
    is_loaded: false,
    default_params: { ...defaultParams, cfg_weight: 2.0 },
  },
  {
    name: "F5-TTS",
    license_name: "MIT License",
    license_url: "https://opensource.org/licenses/MIT",
    commercial_permitted: true,
    license_notice: "MIT licensed and fully permitted for commercial and non-commercial local use.",
    supported_languages: ["en", "zh"],
    native_sample_rate: 24000,
    requires_gpu_recommended: true,
    is_available: false,
    is_loaded: false,
    default_params: { ...defaultParams, temperature: 0.8, cfg_weight: 2.0 },
  },
];

export const mockHistory: HistoryEntry[] = Array.from({ length: 8 }, (_, i) => ({
  id: i + 1,
  voice_id: (i % 3) + 1,
  voice_name: mockVoices[i % 3].name,
  engine_name: "Chatterbox TTS",
  prompt_text:
    i % 2 === 0
      ? "Welcome to VoiceClone Studio. Everything is processed locally on your machine."
      : "The quick brown fox jumps over the lazy dog while the synth warms up.",
  parameters_json: "{}",
  seed: 1000 + i * 37,
  audio_path: `/demo/history_${i + 1}.wav`,
  duration_seconds: 3.2 + i * 0.7,
  sample_rate: 24000,
  created_at: daysAgo(i),
}));

export const mockModels: ModelInfo[] = [
  {
    id: "chatterbox-tts",
    name: "Chatterbox TTS",
    version: "1.2.0",
    license_name: "MIT License",
    commercial_allowed: true,
    license_notice: "Open-source zero-shot voice cloner with Perth watermarking.",
    total_bytes: 2_129_653_744,
    is_downloaded: false,
  },
  {
    id: "xtts-v2",
    name: "Coqui XTTS v2",
    version: "2.0.3",
    license_name: "CPML (Non-Commercial)",
    commercial_allowed: false,
    license_notice: "Multi-lingual voice cloner. Commercial use is prohibited by CPML.",
    total_bytes: 1_887_436_800,
    is_downloaded: false,
  },
  {
    id: "f5-tts",
    name: "F5-TTS",
    version: "1.0.0",
    license_name: "MIT License",
    commercial_allowed: true,
    license_notice: "Diffusion transformer zero-shot cloner with Flow Matching.",
    total_bytes: 1_310_720_000,
    is_downloaded: false,
  },
];

export const mockSettings: AppSettings = {
  theme: "dark",
  default_engine: "Chatterbox TTS",
  device_preference: "auto",
  use_half_precision: true,
  idle_unload_minutes: 10,
  clear_device_cache_after_job: false,
  default_export_format: "wav",
  enable_audio_watermark: true,
  inject_metadata_tag: true,
  default_temperature: 0.75,
  default_cfg_weight: 2.5,
  default_exaggeration: 1.0,
  default_speed: 1.0,
  default_sentence_pause_ms: 250,
  max_chars_per_chunk: 110,
  log_level: "INFO",
};
