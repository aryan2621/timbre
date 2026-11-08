import { LoadingOverlay } from "@/components/ui/loading-overlay";
import type { ReactNode } from "react";
import {
  RotateCcw,
  Save,
  Search,
  Settings2,
} from "lucide-react";
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
import { PageHeader } from "@/components/ui/page-header";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { useEngineStatus } from "@/lib/engine-status";
import { useSettings } from "@/hooks/use-settings";

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

  const {
    settings,
    activeSection,
    search,
    loading,
    saving,
    theme,
    update,
    updateTheme,
    isSectionDirty,
    resetSection,
    saveSection,
    visibleSection,
    dirtyCount,
  } = useSettings(online);

  return (
    <div className="flex flex-col gap-4">
      <LoadingOverlay show={loading} />
      <PageHeader
        title="Settings"
        description="Engine defaults and appearance. Each section saves on its own."
        icon={Settings2}
        meta={
          dirtyCount > 0 ? (
            <Badge variant="outline" className="border-status-warning/40 text-status-warning">
              {dirtyCount} unsaved section{dirtyCount === 1 ? "" : "s"}
            </Badge>
          ) : null
        }
      />

      <div className="grid gap-4">
        {/* ---------------------------------------------------------- content */}
        <div className="min-w-0">
          {!visibleSection ? (
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
                          updateTheme(value);
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
                  </>
                ) : null}

                {activeSection === "engine" ? (
                  <>
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
                      title="Clear the device cache after a job"
                    >
                      <Switch
                        checked={settings.clear_device_cache_after_job}
                        aria-label="Toggle clearing the device cache"
                        onCheckedChange={(checked) =>
                          update({ clear_device_cache_after_job: checked })
                        }
                      />
                    </SettingRow>
                  </>
                ) : null}

                {activeSection === "audio" ? (
                  <>
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

                {activeSection === "diagnostics" ? (
                  <>
                    <SettingRow
                      title="Diagnostic log detail"
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
