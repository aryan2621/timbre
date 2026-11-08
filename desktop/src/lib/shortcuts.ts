/**
 * The keyboard map — one source of truth for every shortcut in the app.
 *
 * `useHotkeys` consumes the `combo` strings, the command palette renders the
 * labels, and the Settings → Shortcuts tab prints the table. Nothing is
 * hard-coded twice.
 */
import type { PageKey } from "./pages";

export type ShortcutGroup = "Navigate" | "Studio" | "Library" | "System";

export interface ShortcutDefinition {
  id: string;
  /** `mod` maps to ⌘ on macOS and Ctrl everywhere else. */
  combo: string;
  label: string;
  group: ShortcutGroup;
}

export const SHORTCUTS: ShortcutDefinition[] = [
  { id: "palette", combo: "mod+k", label: "Open the command palette", group: "System" },
  { id: "shortcuts", combo: "shift+?", label: "Show keyboard shortcuts", group: "System" },
  { id: "theme", combo: "mod+shift+l", label: "Toggle light / dark theme", group: "System" },
  { id: "studio", combo: "mod+1", label: "Go to Studio", group: "Navigate" },
  { id: "voices", combo: "mod+2", label: "Go to Voices", group: "Navigate" },
  { id: "batch", combo: "mod+3", label: "Go to Batch", group: "Navigate" },
  { id: "agents", combo: "mod+7", label: "Go to Agents", group: "Navigate" },
  { id: "history", combo: "mod+4", label: "Go to History", group: "Navigate" },
  { id: "models", combo: "mod+5", label: "Go to Models", group: "Navigate" },
  { id: "settings", combo: "mod+6", label: "Go to Settings", group: "Navigate" },
  { id: "render", combo: "mod+enter", label: "Run synthesis", group: "Studio" },
  { id: "export", combo: "mod+e", label: "Export the current render", group: "Studio" },
  { id: "clear", combo: "mod+backspace", label: "Clear the script", group: "Studio" },
  { id: "play", combo: "space", label: "Play / pause the render", group: "Studio" },
  { id: "seek-back", combo: "arrowleft", label: "Seek back 2 seconds", group: "Studio" },
  { id: "seek-forward", combo: "arrowright", label: "Seek forward 2 seconds", group: "Studio" },
  { id: "new-voice", combo: "mod+shift+n", label: "Create a voice profile", group: "Library" },
  { id: "import-script", combo: "mod+shift+i", label: "Import a batch script", group: "Library" },
  { id: "focus-script", combo: "mod+shift+t", label: "Focus the script editor", group: "Studio" },
];

export const NAVIGATION_SHORTCUTS: Record<string, PageKey> = {
  "mod+1": "studio",
  "mod+2": "voices",
  "mod+3": "batch",
  "mod+7": "agents",
  "mod+4": "history",
  "mod+5": "models",
  "mod+6": "settings",
};

const IS_APPLE =
  typeof navigator !== "undefined" &&
  /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent);

/** `mod+shift+e` -> `⇧⌘E` on macOS, `Ctrl+Shift+E` elsewhere. */
export function formatShortcut(combo: string): string {
  const parts = combo.split("+");
  const key = parts[parts.length - 1];
  const modifiers = parts.slice(0, -1);

  const symbols: Record<string, string> = {
    mod: IS_APPLE ? "⌘" : "Ctrl",
    shift: "⇧",
    alt: IS_APPLE ? "⌥" : "Alt",
    ctrl: IS_APPLE ? "⌃" : "Ctrl",
  };

  const rendered = modifiers.map((modifier) => symbols[modifier] ?? modifier.toUpperCase());
  const keyLabel: Record<string, string> = {
    enter: "↵",
    backspace: "⌫",
    arrowleft: "←",
    arrowright: "→",
    escape: "Esc",
    space: "Space",
    "?": "?",
  };

  const keyText = keyLabel[key.toLowerCase()] ?? key.toUpperCase();
  return [...rendered, keyText].join(IS_APPLE ? "" : "+");
}
