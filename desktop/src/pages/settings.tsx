import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { motion } from "motion/react";
import {
  AudioLines,
  Cpu,
  Keyboard,
  Monitor,
  RotateCcw,
  Save,
  ScrollText,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import { PageHeader } from "@/components/ui/page-header";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import { useEngineStatus } from "@/lib/engine-status";
import { mockEngines, mockSettings } from "@/lib/mock";
import { SHORTCUTS, formatShortcut, type ShortcutGroup } from "@/lib/shortcuts";
import { useTheme, type Theme } from "@/lib/theme";
import type { AppSettings, EngineInfo } from "@/lib/types";

interface Section {
  id: string;
  label: string;
  icon: typeof Monitor;
  description: string;
  keys: (keyof AppSettings)[];
}

const SECTIONS: Section[] = [
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

const SHORTCUT_GROUPS: ShortcutGroup[] = [
  "Navigate",
  "Studio",
  "Library",
  "System",
];

function themeFromSetting(value: string): Theme {
  return value === "light" || value === "system" ? value : "dark";
}

function SettingRow({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 py-2.5">
      <div className="min-w-0">
        <p className="text-[13px] font-medium">{title}</p>
        {description ? (
          <p className="mt-0.5 max-w-md text-[11.5px] leading-snug text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function SliderSetting({
  label,
  description,
  value,
  min,
  max,
  step,
  suffix,
  digits = 2,
  onChange,
}: {
  label: string;
  description?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix?: string;
  digits?: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="space-y-2 py-2.5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[13px] font-medium">{label}</p>
          {description ? (
            <p className="mt-0.5 text-[11.5px] leading-snug text-muted-foreground">
              {description}
            </p>
          ) : null}
        </div>
        <span
          data-numeric
          className="shrink-0 rounded-md bg-surface-inset px-2 py-1 font-mono text-xs"
        >
          {digits === 0 ? Math.round(value) : value.toFixed(digits)}
          {suffix ? ` ${suffix}` : ""}
        </span>
      </div>
      <Slider
        value={[value]}
        min={min}
        max={max}
        step={step}
        aria-label={label}
        onValueChange={(next) =>
          onChange(typeof next === "number" ? next : (next[0] ?? min))
        }
      />
    </div>
  );
}

/**
 * Settings as a real page.
 *
 * Settings used to be a 640px modal floating over the Studio, which meant
 * the keyboard reference had nowhere to live and the Appearance tab was
 * mostly empty. It is now a route with a section rail, a search filter,
 * per-section save buttons and a shortcuts table.
 */
export function SettingsPage() {
  const { status: connection } = useEngineStatus();
  const online = connection !== "offline";
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

  const isSectionDirty = useCallback(
    (section: Section) =>
      section.keys.some((key) => settings[key] !== saved[key]),
    [saved, settings],
  );

  const resetSection = useCallback(
    (section: Section) => {
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
    async (section: Section) => {
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
    if (!term) return SECTIONS;
    return SECTIONS.filter(
      (section) =>
        section.label.toLowerCase().includes(term) ||
        section.description.toLowerCase().includes(term),
    );
  }, [search]);

  const visibleSection = SECTIONS.find((section) => section.id === activeSection);
  const dirtyCount = SECTIONS.filter((section) => isSectionDirty(section)).length;

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Settings"
        description="Engine defaults, appearance and keyboard shortcuts. Each section saves on its own."
        icon={Settings2}
        meta={
          dirtyCount > 0 ? (
            <Badge variant="outline" className="border-status-warning/40 text-status-warning">
              {dirtyCount} unsaved section{dirtyCount === 1 ? "" : "s"}
            </Badge>
          ) : null
        }
      />

      <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
        {/* ------------------------------------------------------ section rail */}
        <aside className="space-y-3">
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Find a setting"
              aria-label="Search the settings"
              className="pl-8"
            />
          </div>

          <nav className="space-y-0.5" aria-label="Settings sections">
            {filteredSections.map((section) => {
              const active = section.id === activeSection;
              const dirty = isSectionDirty(section);
              return (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => setActiveSection(section.id)}
                  className={`relative flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] transition-colors ${
                    active
                      ? "bg-surface-raised font-medium text-foreground shadow-[0_1px_2px_rgb(31_30_29/0.05)]"
                      : "text-muted-foreground hover:bg-surface-raised/60 hover:text-foreground"
                  }`}
                >
                  {active ? (
                    <motion.span
                      layoutId="settings-indicator"
                      className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary"
                      transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
                    />
                  ) : null}
                  <section.icon className="size-4 shrink-0" />
                  <span className="flex-1 truncate">{section.label}</span>
                  {dirty ? (
                    <span className="size-1.5 shrink-0 rounded-full bg-status-warning" />
                  ) : null}
                </button>
              );
            })}

            <Separator className="my-2" />

            <button
              type="button"
              onClick={() => setActiveSection("shortcuts")}
              className={`relative flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] transition-colors ${
                activeSection === "shortcuts"
                  ? "bg-surface-raised font-medium text-foreground shadow-[0_1px_2px_rgb(31_30_29/0.05)]"
                  : "text-muted-foreground hover:bg-surface-raised/60 hover:text-foreground"
              }`}
            >
              {activeSection === "shortcuts" ? (
                <motion.span
                  layoutId="settings-indicator"
                  className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary"
                  transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
                />
              ) : null}
              <Keyboard className="size-4 shrink-0" />
              <span className="flex-1 truncate">Shortcuts</span>
            </button>
          </nav>
        </aside>

        {/* ---------------------------------------------------------- content */}
        <div className="min-w-0">
          {activeSection === "shortcuts" ? (
            <Card className="shadow-[var(--shadow-soft)]">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Keyboard className="size-4 text-primary" />
                  Keyboard shortcuts
                </CardTitle>
                <CardDescription>
                  The whole studio is reachable without the mouse. Press ⇧? at any
                  time to open this list.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                {SHORTCUT_GROUPS.map((group) => (
                  <section key={group} className="space-y-1">
                    <h3 className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                      {group}
                    </h3>
                    {SHORTCUTS.filter((shortcut) => shortcut.group === group).map(
                      (shortcut) => (
                        <div
                          key={shortcut.id}
                          className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-[13px] transition-colors hover:bg-muted/60"
                        >
                          <span className="text-muted-foreground">
                            {shortcut.label}
                          </span>
                          <Kbd>{formatShortcut(shortcut.combo)}</Kbd>
                        </div>
                      ),
                    )}
                  </section>
                ))}
              </CardContent>
            </Card>
          ) : !visibleSection ? (
            <Empty className="border border-dashed bg-surface-inset/60 py-14">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <Search />
                </EmptyMedia>
                <EmptyTitle>No settings match “{search}”</EmptyTitle>
                <EmptyDescription>
                  Try a broader term such as “engine”, “audio” or “theme”.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <Card className="shadow-[var(--shadow-soft)]">
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <visibleSection.icon className="size-4 text-primary" />
                      {visibleSection.label}
                    </CardTitle>
                    <CardDescription>{visibleSection.description}</CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    {isSectionDirty(visibleSection) ? (
                      <Badge variant="outline" className="border-status-warning/40 text-status-warning">
                        Unsaved
                      </Badge>
                    ) : null}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => resetSection(visibleSection)}
                      disabled={!isSectionDirty(visibleSection)}
                    >
                      <RotateCcw />
                      Revert
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => void saveSection(visibleSection)}
                      disabled={!isSectionDirty(visibleSection) || saving}
                    >
                      <Save />
                      Save
                    </Button>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="divide-y divide-border/60">
                {activeSection === "appearance" ? (
                  <>
                    <SettingRow
                      title="Theme"
                      description="Dark is tuned for long editing sessions. The header toggle switches between light and dark instantly."
                    >
                      <Select
                        value={theme}
                        onValueChange={(value) => {
                          if (
                            value !== "dark" &&
                            value !== "light" &&
                            value !== "system"
                          ) {
                            return;
                          }
                          update({ theme: value });
                          setTheme(value);
                        }}
                      >
                        <SelectTrigger className="w-40">
                          <SelectValue>
                            {(value) =>
                              value === "light"
                                ? "Light"
                                : value === "system"
                                  ? "System"
                                  : "Dark"
                            }
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="dark">Dark</SelectItem>
                          <SelectItem value="light">Light</SelectItem>
                          <SelectItem value="system">System</SelectItem>
                        </SelectContent>
                      </Select>
                    </SettingRow>

                    <SettingRow
                      title="Audio watermark"
                      description="Embed Perth provenance in every rendered clip."
                    >
                      <Switch
                        checked={settings.enable_audio_watermark}
                        aria-label="Toggle the audio watermark"
                        onCheckedChange={(checked) =>
                          update({ enable_audio_watermark: checked })
                        }
                      />
                    </SettingRow>

                    <SettingRow
                      title="AI metadata tag"
                      description="Write an “AI-generated voice” tag into exported files."
                    >
                      <Switch
                        checked={settings.inject_metadata_tag}
                        aria-label="Toggle the AI metadata tag"
                        onCheckedChange={(checked) =>
                          update({ inject_metadata_tag: checked })
                        }
                      />
                    </SettingRow>
                  </>
                ) : null}

                {activeSection === "engine" ? (
                  <>
                    <SettingRow
                      title="Default voice model"
                      description="Preferred AI model loaded when starting new speech takes."
                    >
                      <Select
                        value={settings.default_engine}
                        onValueChange={(value) =>
                          value && update({ default_engine: value })
                        }
                      >
                        <SelectTrigger className="w-52">
                          <SelectValue placeholder="Select engine" />
                        </SelectTrigger>
                        <SelectContent>
                          {engines.map((engine) => (
                            <SelectItem
                              key={engine.name}
                              value={engine.name}
                              disabled={!engine.is_available}
                            >
                              {engine.name}
                              {!engine.is_available ? (
                                <span className="text-muted-foreground">
                                  {" "}
                                  · not installed
                                </span>
                              ) : null}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </SettingRow>

                    <SettingRow
                      title="Hardware accelerator"
                      description="Auto picks your graphics card (Apple Silicon MPS / NVIDIA CUDA) for maximum speed."
                    >
                      <Select
                        value={settings.device_preference}
                        onValueChange={(value) =>
                          value && update({ device_preference: value })
                        }
                      >
                        <SelectTrigger className="w-32">
                          <SelectValue>
                            {(value) => {
                              const label = String(value ?? "auto");
                              return label === "auto"
                                ? "Auto"
                                : label.toUpperCase();
                            }}
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="auto">Auto</SelectItem>
                          <SelectItem value="mps">MPS</SelectItem>
                          <SelectItem value="cuda">CUDA</SelectItem>
                          <SelectItem value="cpu">CPU</SelectItem>
                        </SelectContent>
                      </Select>
                    </SettingRow>

                    <SettingRow
                      title="Half precision (FP16)"
                      description="Halves memory usage and accelerates generation with identical sound fidelity."
                    >
                      <Switch
                        checked={settings.use_half_precision}
                        aria-label="Toggle half precision mode"
                        onCheckedChange={(checked) =>
                          update({ use_half_precision: checked })
                        }
                      />
                    </SettingRow>

                    <SettingRow
                      title="Clear the device cache after a job"
                      description="Frees graphics memory as soon as a render finishes."
                    >
                      <Switch
                        checked={settings.clear_device_cache_after_job}
                        aria-label="Toggle clearing the device cache"
                        onCheckedChange={(checked) =>
                          update({ clear_device_cache_after_job: checked })
                        }
                      />
                    </SettingRow>

                    <SliderSetting
                      label="Auto-free memory when inactive"
                      description="Releases models from graphics memory after inactivity (0 keeps them ready in RAM)."
                      value={settings.idle_unload_minutes}
                      min={0}
                      max={180}
                      step={5}
                      suffix="min"
                      digits={0}
                      onChange={(value) => update({ idle_unload_minutes: value })}
                    />
                  </>
                ) : null}

                {activeSection === "audio" ? (
                  <>
                    <SettingRow
                      title="Preferred export format"
                      description="Lossless WAV is recommended for master audio. MP3 and OGG require ffmpeg."
                    >
                      <Select
                        value={settings.default_export_format}
                        onValueChange={(value) =>
                          value && update({ default_export_format: value })
                        }
                      >
                        <SelectTrigger className="w-32">
                          <SelectValue>
                            {(value) => String(value ?? "wav").toUpperCase()}
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="wav">WAV</SelectItem>
                          <SelectItem value="flac">FLAC</SelectItem>
                          <SelectItem value="mp3">MP3</SelectItem>
                          <SelectItem value="ogg">OGG</SelectItem>
                        </SelectContent>
                      </Select>
                    </SettingRow>

                    <SliderSetting
                      label="Default pause between sentences"
                      description="Natural breathing silence inserted between stitched sentences."
                      value={settings.default_sentence_pause_ms}
                      min={0}
                      max={1500}
                      step={50}
                      suffix="ms"
                      digits={0}
                      onChange={(value) =>
                        update({ default_sentence_pause_ms: value })
                      }
                    />

                    <SliderSetting
                      label="Maximum characters per chunk"
                      description="Longer chunks are more efficient; shorter chunks follow the sentence breaks more closely."
                      value={settings.max_chars_per_chunk}
                      min={40}
                      max={400}
                      step={10}
                      suffix="chars"
                      digits={0}
                      onChange={(value) => update({ max_chars_per_chunk: value })}
                    />
                  </>
                ) : null}

                {activeSection === "synthesis" ? (
                  <>
                    <SliderSetting
                      label="Vocal variation"
                      description="Lower sounds steady and consistent; higher adds lively natural variety."
                      value={settings.default_temperature}
                      min={0.1}
                      max={1.5}
                      step={0.05}
                      onChange={(value) => update({ default_temperature: value })}
                    />
                    <SliderSetting
                      label="Voice resemblance (CFG match)"
                      description="How strictly the speech mirrors the reference speaker's vocal tone."
                      value={settings.default_cfg_weight}
                      min={1}
                      max={7}
                      step={0.1}
                      onChange={(value) => update({ default_cfg_weight: value })}
                    />
                    <SliderSetting
                      label="Emotion & expressiveness"
                      description="Amplifies emotional warmth and dramatic vocal inflection."
                      value={settings.default_exaggeration}
                      min={0.2}
                      max={2}
                      step={0.05}
                      suffix="x"
                      onChange={(value) => update({ default_exaggeration: value })}
                    />
                    <SliderSetting
                      label="Speaking speed"
                      description="Default pace of speech delivery (0.5x to 2x)."
                      value={settings.default_speed}
                      min={0.5}
                      max={2}
                      step={0.05}
                      suffix="x"
                      onChange={(value) => update({ default_speed: value })}
                    />
                  </>
                ) : null}

                {activeSection === "diagnostics" ? (
                  <>
                    <SettingRow
                      title="Diagnostic log detail"
                      description="Choose Debug for verbose performance timings or Info for standard operations."
                    >
                      <Select
                        value={settings.log_level}
                        onValueChange={(value) =>
                          value && update({ log_level: value })
                        }
                      >
                        <SelectTrigger className="w-36">
                          <SelectValue>
                            {(value) =>
                              value === "DEBUG"
                                ? "Debug"
                                : value === "WARNING"
                                  ? "Warning"
                                  : value === "ERROR"
                                    ? "Error"
                                    : "Info"
                            }
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="DEBUG">Debug</SelectItem>
                          <SelectItem value="INFO">Info</SelectItem>
                          <SelectItem value="WARNING">Warning</SelectItem>
                          <SelectItem value="ERROR">Error</SelectItem>
                        </SelectContent>
                      </Select>
                    </SettingRow>

                    <div className="flex items-start gap-3 py-3 text-[12px] leading-relaxed text-muted-foreground">
                      <ShieldCheck className="mt-0.5 size-4 shrink-0 text-status-success" />
                      <p>
                        All audio, profiles and settings stay on this computer.
                        There is no telemetry, no account and no cloud upload path
                        in the engine.
                      </p>
                    </div>
                  </>
                ) : null}
              </CardContent>
            </Card>
          )}

          {loading ? (
            <p className="mt-3 text-xs text-muted-foreground">
              Loading the saved configuration…
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
