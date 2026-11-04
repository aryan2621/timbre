import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useTheme } from "@/lib/theme";
import type { Theme } from "@/lib/theme";
import {
  AudioLines,
  Cpu,
  Monitor,
  Save,
  ScrollText,
  ShieldCheck,
  SlidersHorizontal,
  Undo2,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader } from "@/components/ui/loader";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
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
import { mockEngines, mockSettings } from "@/lib/mock";
import type { AppSettings, EngineInfo } from "@/lib/types";

interface SettingsPageProps {
  open: boolean;
  onClose: () => void;
  online: boolean | null;
}

const SETTINGS_TABS = [
  { id: "appearance", label: "Appearance", icon: Monitor },
  { id: "engine", label: "Models & Hardware", icon: Cpu },
  { id: "audio", label: "Audio & Quality", icon: AudioLines },
  { id: "synthesis", label: "Voice Defaults", icon: SlidersHorizontal },
  { id: "diagnostics", label: "Diagnostics & Privacy", icon: ScrollText },
] as const;

type SettingsTab = (typeof SETTINGS_TABS)[number]["id"];

function Row({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium">{title}</p>
        {description ? (
          <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
        ) : null}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function SliderRow({
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
    <div className="space-y-2 py-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <Label className="text-sm font-medium">{label}</Label>
          {description ? (
            <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
          ) : null}
        </div>
        <span className="font-mono text-xs text-muted-foreground shrink-0">
          {digits === 0 ? Math.round(value) : value.toFixed(digits)}
          {suffix ? ` ${suffix}`.trimStart() : ""}
        </span>
      </div>
      <Slider
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={(next) =>
          onChange(typeof next === "number" ? next : (next[0] ?? min))
        }
      />
    </div>
  );
}

function themeFromSetting(value: string): Theme {
  return value === "light" || value === "system" ? value : "dark";
}

export function SettingsPage({ open, onClose, online }: SettingsPageProps) {
  const { theme, setTheme } = useTheme();
  const [settings, setSettings] = useState<AppSettings>(mockSettings);
  const [saved, setSaved] = useState<AppSettings>(mockSettings);
  const [engines, setEngines] = useState<EngineInfo[]>(mockEngines);
  const [activeTab, setActiveTab] = useState<SettingsTab>("appearance");
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
        // NOTE: the UI theme is intentionally *not* re-applied from the backend
        // here. The Settings page owns theme changes made through the select, but
        // overwriting on every mount caused unwanted theme flips when navigating
        // to this page.
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

  const update = (patch: Partial<AppSettings>) =>
    setSettings((previous) => ({ ...previous, ...patch }));

  const dirty = JSON.stringify(settings) !== JSON.stringify(saved);

  const save = async () => {
    if (!online) {
      toast.error("Saving needs the Python engine", {
        description: "Start the sidecar to persist settings.",
      });
      return;
    }
    setSaving(true);
    try {
      const next = await api.updateSettings({ ...settings, theme });
      setSettings(next);
      setSaved(next);
      toast.success("Settings saved");
    } catch (error) {
      toast.error("Could not save settings", {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    setSettings(saved);
    setTheme(themeFromSetting(saved.theme));
    toast.message("Unsaved changes reverted");
  };

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent className="flex h-[640px] max-h-[85vh] w-full sm:max-w-4xl flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="flex-row items-center justify-between gap-3 border-b border-border px-5 py-4 pr-12">
          <div className="min-w-0">
            <DialogTitle className="font-serif text-xl font-medium tracking-tight">
              Settings
            </DialogTitle>
            <DialogDescription className="mt-1 text-xs">
              Engine defaults, export behavior and local storage preferences.
            </DialogDescription>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {dirty && <Badge variant="secondary">Unsaved changes</Badge>}
            <Button variant="outline" size="sm" onClick={reset} disabled={!dirty}>
              <Undo2 />
              Reset
            </Button>
            <Button size="sm" onClick={() => void save()} disabled={saving || !dirty}>
              <Save />
              {saving ? "Saving" : "Save changes"}
            </Button>
          </div>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-hidden">
          <div className="flex h-full min-h-0">
            {/* Left tab rail */}
            <div className="flex w-56 shrink-0 flex-col gap-1 border-r border-border bg-muted/30 p-2.5">
              {SETTINGS_TABS.map((tab) => {
                const TabIcon = tab.icon;
                const isActive = tab.id === activeTab;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[13px] font-medium transition-colors ${isActive
                      ? "bg-secondary text-foreground"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                      }`}
                  >
                    <TabIcon className="size-4 shrink-0" />
                    <span className="truncate">{tab.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Right content pane */}
            <div className="min-w-0 flex-1 overflow-y-auto p-4">
              <div className="flex flex-col gap-4">

                {online === false && (
                  <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-300">
                    The Python engine is offline. Settings shown are demo defaults and
                    cannot be persisted.
                  </div>
                )}

                <>
                  {activeTab === "appearance" && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                          <Monitor className="size-4 text-primary" />
                          Appearance
                        </CardTitle>
                        <CardDescription>How the studio looks on this machine.</CardDescription>
                      </CardHeader>
                      <CardContent className="divide-y">
                        <Row title="Theme" description="Dark is tuned for long editing sessions.">
                          <Select
                            value={themeFromSetting(settings.theme)}
                            onValueChange={(value: string | null) => {
                              if (value !== "dark" && value !== "light" && value !== "system") {
                                return;
                              }
                              update({ theme: value });
                              setTheme(value);
                            }}
                          >
                            <SelectTrigger className="w-40">
                              <SelectValue>
                                {(value) =>
                                  value === "light" ? "Light" : value === "system" ? "System" : "Dark"
                                }
                              </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="dark">Dark</SelectItem>
                              <SelectItem value="light">Light</SelectItem>
                              <SelectItem value="system">System</SelectItem>
                            </SelectContent>
                          </Select>
                        </Row>
                        <Row
                          title="Audio watermark"
                          description="Embed Perth provenance in every rendered clip."
                        >
                          <Switch
                            checked={settings.enable_audio_watermark}
                            onCheckedChange={(checked) => update({ enable_audio_watermark: checked })}
                          />
                        </Row>
                        <Row
                          title="AI metadata tag"
                          description="Write an 'AI-generated voice' tag into exported files."
                        >
                          <Switch
                            checked={settings.inject_metadata_tag}
                            onCheckedChange={(checked) => update({ inject_metadata_tag: checked })}
                          />
                        </Row>
                      </CardContent>
                    </Card>
                  )}

                  {activeTab === "engine" && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                          <Cpu className="size-4 text-primary" />
                          Voice Models &amp; Hardware
                        </CardTitle>
                        <CardDescription>Select your default voice generator and graphics accelerator.</CardDescription>
                      </CardHeader>
                      <CardContent className="divide-y">
                        <Row title="Default voice model" description="Preferred AI model loaded when starting new speech takes.">
                          <Select
                            value={settings.default_engine}
                            onValueChange={(value: string | null) =>
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
                                  {!engine.is_available && (
                                    <span className="text-muted-foreground">· not installed</span>
                                  )}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </Row>
                        <Row title="Hardware accelerator (GPU / CPU)" description="Auto picks your graphics card (Apple Silicon MPS / NVIDIA CUDA) for maximum speed.">
                          <Select
                            value={settings.device_preference}
                            onValueChange={(value: string | null) =>
                              value && update({ device_preference: value })
                            }
                          >
                            <SelectTrigger className="w-32">
                              <SelectValue>
                                {(value) => {
                                  const label = String(value ?? "auto");
                                  return label === "auto" ? "Auto" : label.toUpperCase();
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
                        </Row>
                        <Row
                          title="High-efficiency mode (FP16)"
                          description="Halves memory usage and accelerates generation with identical sound fidelity."
                        >
                          <Switch
                            checked={settings.use_half_precision}
                            onCheckedChange={(checked) => update({ use_half_precision: checked })}
                          />
                        </Row>
                        <SliderRow
                          label="Auto-free memory when inactive"
                          description="Releases models from graphics memory after inactivity (0 keeps ready in RAM)."
                          value={settings.idle_unload_minutes}
                          min={0}
                          max={180}
                          step={5}
                          suffix="min"
                          digits={0}
                          onChange={(value) =>
                            update({ idle_unload_minutes: value })
                          }
                        />
                      </CardContent>
                    </Card>
                  )}

                  {activeTab === "audio" && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                          <AudioLines className="size-4 text-primary" />
                          Audio &amp; Quality
                        </CardTitle>
                        <CardDescription>Default format and quality applied when exporting speech recordings.</CardDescription>
                      </CardHeader>
                      <CardContent className="divide-y">
                        <Row
                          title="Preferred export format"
                          description="Lossless WAV is recommended for master audio. MP3 and OGG require ffmpeg."
                        >
                          <Select
                            value={settings.default_export_format}
                            onValueChange={(value: string | null) =>
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
                        </Row>
                        <SliderRow
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
                      </CardContent>
                    </Card>
                  )}

                  {activeTab === "synthesis" && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                          <SlidersHorizontal className="size-4 text-primary" />
                          Default Voice Settings
                        </CardTitle>
                        <CardDescription>Baseline vocal characteristics applied to every new script.</CardDescription>
                      </CardHeader>
                      <CardContent className="pt-1">
                        <SliderRow
                          label="Vocal variation (Creativity)"
                          description="Lower sounds steady and consistent; higher adds lively natural variety."
                          value={settings.default_temperature}
                          min={0.1}
                          max={1.5}
                          step={0.05}
                          onChange={(value) => update({ default_temperature: value })}
                        />
                        <Separator />
                        <SliderRow
                          label="Voice resemblance (CFG match)"
                          description="How strictly the speech mirrors the reference speaker's vocal tone."
                          value={settings.default_cfg_weight}
                          min={1}
                          max={7}
                          step={0.1}
                          onChange={(value) => update({ default_cfg_weight: value })}
                        />
                        <Separator />
                        <SliderRow
                          label="Emotion &amp; expressiveness"
                          description="Amplifies emotional warmth and dramatic vocal inflection."
                          value={settings.default_exaggeration}
                          min={0.2}
                          max={2}
                          step={0.05}
                          suffix="x"
                          onChange={(value) => update({ default_exaggeration: value })}
                        />
                        <Separator />
                        <SliderRow
                          label="Speaking speed"
                          description="Default pace of speech delivery (0.5x to 2x)."
                          value={settings.default_speed}
                          min={0.5}
                          max={2}
                          step={0.05}
                          suffix="x"
                          onChange={(value) => update({ default_speed: value })}
                        />
                      </CardContent>
                    </Card>
                  )}

                  {activeTab === "diagnostics" && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                          <ScrollText className="size-4 text-primary" />
                          Diagnostics &amp; Privacy
                        </CardTitle>
                        <CardDescription>
                          Logs are rotated in your local application data directory.
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="divide-y">
                        <Row
                          title="Diagnostic log detail"
                          description="Choose Debug for verbose performance timings or Info for standard operations."
                        >
                          <Select
                            value={settings.log_level}
                            onValueChange={(value: string | null) =>
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
                        </Row>
                        <div className="flex items-start gap-3 py-3 text-xs text-muted-foreground">
                          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
                          <p>
                            All audio, profiles and settings stay on this computer. There is
                            no telemetry, no account and no cloud upload path in the engine.
                          </p>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </>

                {loading && (
                  <div className="flex justify-center py-2">
                    <Loader />
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
