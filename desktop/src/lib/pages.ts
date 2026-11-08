/** The pages of the app, in navigation order. */

export type PageKey =
  | "studio"
  | "voices"
  | "batch"
  | "agents"
  | "history"
  | "models"
  | "settings";

const PAGE_ORDER: PageKey[] = [
  "studio",
  "voices",
  "batch",
  "agents",
  "history",
  "models",
  "settings",
];

export const PAGE_TITLES: Record<PageKey, string> = {
  studio: "Studio",
  voices: "Voices",
  batch: "Batch",
  agents: "Agents",
  history: "History",
  models: "Models",
  settings: "Settings",
};

export const PAGE_DESCRIPTIONS: Record<PageKey, string> = {
  studio: "Write the script, shape the delivery, render and export.",
  voices: "Reference voices, their quality and cloning permissions.",
  batch: "Render a whole script file into one file per line.",
  agents: "Talk to a voice agent that answers in a cloned voice.",
  history: "Every render you made, with the settings that produced it.",
  models: "Voice model packs, licences and downloads.",
  settings: "Engine defaults and appearance.",
};

export function isPageKey(value: string): value is PageKey {
  return (PAGE_ORDER as string[]).includes(value);
}
