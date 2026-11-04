import type { SynthesisParams } from "@/lib/types";

/**
 * Delivery presets.
 *
 * Six sliders with no guidance is how the app lost new users: every value
 * looked equally important and equally mysterious. A preset is the fastest
 * path from "I have a script" to "that sounds right".
 */
export interface VoicePreset {
  id: string;
  label: string;
  description: string;
  params: Partial<SynthesisParams>;
}

export const VOICE_PRESETS: VoicePreset[] = [
  {
    id: "natural",
    label: "Natural",
    description: "Balanced, everyday speech. Start here.",
    params: { temperature: 0.7, cfg_weight: 2.5, exaggeration: 1.0, speed: 1.0 },
  },
  {
    id: "narrator",
    label: "Narrator",
    description: "Measured and warm, for audiobooks and documentation.",
    params: { temperature: 0.6, cfg_weight: 3.0, exaggeration: 1.1, speed: 0.95 },
  },
  {
    id: "podcast",
    label: "Podcast",
    description: "Brisk and close, for two-host shows.",
    params: { temperature: 0.75, cfg_weight: 2.4, exaggeration: 1.2, speed: 1.1 },
  },
  {
    id: "announcer",
    label: "Announcer",
    description: "Bright and emphatic, for promos and trailers.",
    params: { temperature: 0.8, cfg_weight: 2.2, exaggeration: 1.45, speed: 1.05 },
  },
  {
    id: "whisper",
    label: "Intimate",
    description: "Quiet and close-mic, for asides and narration.",
    params: { temperature: 0.55, cfg_weight: 3.4, exaggeration: 0.75, speed: 0.9 },
  },
  {
    id: "character",
    label: "Character",
    description: "Expressive and varied, for dialogue.",
    params: { temperature: 0.95, cfg_weight: 2.0, exaggeration: 1.6, speed: 1.0 },
  },
];
