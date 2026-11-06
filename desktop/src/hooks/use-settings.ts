/**
 * Settings page hooks.
 *
 * The Settings screen is a form over a persisted settings object. Its
 * behaviour lives in useSettings, which owns:
 *   - loading the settings and the engine catalogue from the sidecar
 *   - the dirty tracking that drives the "Unsaved" badges and Save buttons
 *   - per-section save and revert
 *   - the section rail search filter
 *
 * The page component keeps the rendering: the section rail, the section
 * cards and the keyboard shortcut table.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AudioLines,
  Cpu,
  Monitor,
  ScrollText,
  SlidersHorizontal,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { mockEngines, mockSettings } from "@/lib/mock";
import { useTheme, type Theme } from "@/lib/theme";
import type { AppSettings, EngineInfo } from "@/lib/types";

export interface SettingsSection {
  id: string;
  label: string;
  icon: typeof Monitor;
  description: string;
  keys: (keyof AppSettings)[];
}

/** The settings sections shown in the rail, in display order. */
export const SETTINGS_SECTIONS: SettingsSection[] = [
  {
    id: "appearance",
    label: "Appearance",
    icon: Monitor,
    description: "Theme and provenance defaults.",
    keys: ["theme", "enable_audio_watermark", "inject_metadata_tag"],
  },
  {
    id: "engine",
    label: "Engine & hardware",
    icon: Cpu,
    description: "Which model runs, and where it runs.",
    keys: [
      "default_engine",
      "device_preference",
      "use_half_precision",
      "idle_unload_minutes",
      "clear_device_cache_after_job",
    ],
  },
  {
    id: "audio",
    label: "Audio & quality",
    icon: AudioLines,
    description: "Export format and sentence rhythm.",
    keys: ["default_export_format", "default_sentence_pause_ms", "max_chars_per_chunk"],
  },
  {
    id: "synthesis",
    label: "Voice defaults",
    icon: SlidersHorizontal,
    description: "The baseline every new render starts from.",
    keys: [
      "default_temperature",
      "default_cfg_weight",
      "default_exaggeration",
      "default_speed",
    ],
  },
  {
    id: "diagnostics",
    label: "Diagnostics & privacy",
    icon: ScrollText,
    description: "Log detail and where the data lives.",
    keys: ["log_level"],
  },
];

/** Normalizes the theme coming from the backend into a known theme name. */
export function themeFromSetting(value: string): Theme {
  return value === "light" || value === "system" ? value : "dark";
}

export interface SettingsState {
  settings: AppSettings;
  engines: EngineInfo[];
  activeSection: string;
  setActiveSection: (id: string) => void;
  search: string;
  setSearch: (value: string) => void;
  loading: boolean;
  saving: boolean;
  /** The currently applied theme, kept in sync with the appearance section. */
  theme: Theme;
  update: (patch: Partial<AppSettings>) => void;
  /** Applies a theme to both the settings object and the document. */
  updateTheme: (theme: Theme) => void;
  isSectionDirty: (section: SettingsSection) => boolean;
  resetSection: (section: SettingsSection) => void;
  saveSection: (section: SettingsSection) => Promise<void>;
  filteredSections: SettingsSection[];
  visibleSection: SettingsSection | undefined;
  dirtyCount: number;
}

/**
 * Loads the persisted settings and exposes the per-section editing actions.
 */
export function useSettings(online: boolean): SettingsState {
  const { theme, setTheme } = useTheme();

  const [settings, setSettings] = useState<AppSettings>(mockSettings);
  const [saved, setSaved] = useState<AppSettings>(mockSettings);
  const [engines, setEngines] = useState<EngineInfo[]>(mockEngines);
  const [activeSection, setActiveSection] = useState("appearance");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!online) {
        if (!cancelled) setLoading(false);
        return;
      }
      try {
        const [nextSettings, nextEngines] = await Promise.all([
          api.getSettings(),
          api.listEngines(),
        ]);
        if (cancelled) return;
        const normalized: AppSettings = {
          ...nextSettings,
          theme: themeFromSetting(nextSettings.theme),
        };
        setSettings(normalized);
        setSaved(normalized);
        setEngines(nextEngines);
      } catch {
        /* keep the demo defaults when the sidecar does not answer */
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [online]);

  const update = useCallback(
    (patch: Partial<AppSettings>) =>
      setSettings((previous) => ({ ...previous, ...patch })),
    [],
  );

  const updateTheme = useCallback(
    (next: Theme) => {
      update({ theme: next });
      setTheme(next);
    },
    [setTheme, update],
  );

  const isSectionDirty = useCallback(
    (section: SettingsSection) =>
      section.keys.some((key) => settings[key] !== saved[key]),
    [saved, settings],
  );

  const resetSection = useCallback(
    (section: SettingsSection) => {
      setSettings((previous) => {
        const next = { ...previous };
        for (const key of section.keys) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (next as any)[key] = saved[key];
        }
        return next;
      });
      if (section.id === "appearance") setTheme(themeFromSetting(saved.theme));
      toast.message(`${section.label} reverted`);
    },
    [saved, setTheme],
  );

  const saveSection = useCallback(
    async (section: SettingsSection) => {
      if (!online) {
        toast.error("Saving needs the Python engine", {
          description: "Start the sidecar to persist settings.",
        });
        return;
      }
      setSaving(true);
      try {
        const patch = section.keys.reduce<Partial<AppSettings>>((acc, key) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (acc as any)[key] = settings[key];
          return acc;
        }, {});
        const next = await api.updateSettings(patch);
        setSettings((previous) => ({ ...previous, ...next }));
        setSaved((previous) => ({ ...previous, ...next }));
        toast.success(`${section.label} saved`);
      } catch (error) {
        toast.error("Could not save settings", {
          description: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setSaving(false);
      }
    },
    [online, settings],
  );

  const filteredSections = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return SETTINGS_SECTIONS;
    return SETTINGS_SECTIONS.filter(
      (section) =>
        section.label.toLowerCase().includes(term) ||
        section.description.toLowerCase().includes(term),
    );
  }, [search]);

  const visibleSection = SETTINGS_SECTIONS.find(
    (section) => section.id === activeSection,
  );
  const dirtyCount = SETTINGS_SECTIONS.filter((section) =>
    isSectionDirty(section),
  ).length;

  return {
    settings,
    engines,
    activeSection,
    setActiveSection,
    search,
    setSearch,
    loading,
    saving,
    theme,
    update,
    updateTheme,
    isSectionDirty,
    resetSection,
    saveSection,
    filteredSections,
    visibleSection,
    dirtyCount,
  };
}