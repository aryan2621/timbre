import { useCallback, useMemo, useRef, useState } from "react";
import {
  AudioLines,
  AudioWaveform,
  Download,
  Heart,
  Info,
  Loader2,
  Languages,
  LockKeyhole,
  Megaphone,
  Mic2,
  Pause,
  Play,
  Podcast,
  Sparkles,
  SlidersHorizontal,
  Square,
  Wand2,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, FieldLabel } from "@/components/ui/field";
import { Kbd } from "@/components/ui/kbd";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { ParamControl } from "@/components/studio/param-control";
import { VOICE_PRESETS } from "@/components/studio/presets";
import { VoicePicker } from "@/components/studio/voice-picker";
import {
  WaveformPlayer,
  type WaveformPlayerHandle,
} from "@/components/waveform/waveform-player";
import { useEngineSelection, useLibrary, useSynthesisJob } from "@/hooks/use-studio";
import { useApp, useAppActions } from "@/lib/app-context";
import {
  downloadBlob,
  IS_TAURI,
  pickSavePath,
  writeBlobToPath,
} from "@/lib/desktop";
import { useEngineStatus } from "@/lib/engine-status";
import {
  estimateDurationSeconds,
  formatTimecode,
} from "@/lib/format";
import { countWords } from "@/lib/chunk-preview";
import { useHotkeys } from "@/lib/use-hotkeys";
import { useTheme } from "@/lib/theme";
import type { EngineInfo, SynthesisParams, VoiceProfile } from "@/lib/types";

const SCRIPT_SUGGESTIONS = [
  {
    title: "Podcast intro",
    description: "Welcome back. Today we look at how small habits quietly change everything.",
    icon: Podcast,
    tint: "bg-[#f5e8df] text-[#b85d3e]",
  },
  {
    title: "Calm and reassuring",
    description: "Take a breath. Everything is on track, and there is nothing you need to do right now.",
    icon: Heart,
    tint: "bg-[#eaf0e7] text-[#557650]",
  },
  {
    title: "Product announcement",
    description: "Introducing the new Studio: record your voice once, and it is ready whenever you need it.",
    icon: Megaphone,
    tint: "bg-[#eeebf5] text-[#75628f]",
  },
];

function describeRenderConfiguration(
  voiceName: string,
  engineName: string,
  params: SynthesisParams,
): string {
  const pace =
    params.speed < 0.85 ? "unhurried" : params.speed > 1.15 ? "brisk" : "natural";
  const expression =
    params.exaggeration < 0.85
      ? "subtle"
      : params.exaggeration > 1.25
        ? "expressive"
        : "balanced";
  const variation =
    params.temperature < 0.55
      ? "consistent"
      : params.temperature > 0.9
        ? "spontaneous"
        : "natural";
  const voiceMatch =
    params.cfg_weight < 2.2
      ? "relaxed voice match"
      : params.cfg_weight > 4.5
        ? "close voice match"
        : "balanced voice match";

  return `Rendered with ${voiceName} on ${engineName} · ${params.language.toUpperCase()} · ${pace} pace · ${expression} expression · ${voiceMatch} · ${variation} variation.`;
}

function PresetButton({ preset, isActive, onClick }: { preset: typeof VOICE_PRESETS[0]; isActive: boolean; onClick: () => void }) {
  return (
    <Button
      variant={isActive ? "secondary" : "outline"}
      size="sm"
      onClick={onClick}
      title={preset.description}
      aria-label={preset.description}
    >
      {preset.label}
    </Button>
  );
}

function DrawerContent({
  voice,
  voices,
  loading,
  engineName,
  setEngineName,
  activeEngine,
  engines,
  params,
  update,
  randomSeed,
  setRandomSeed,
  sentencePause,
  setSentencePause,
  setVoice,
}: {
  voice: VoiceProfile | null;
  voices: VoiceProfile[];
  loading: boolean;
  engineName: string;
  setEngineName: (v: string) => void;
  activeEngine: EngineInfo | undefined;
  engines: EngineInfo[];
  params: SynthesisParams;
  update: (
    patch:
      | Partial<SynthesisParams>
      | ((previous: SynthesisParams) => SynthesisParams),
  ) => void;
  randomSeed: boolean;
  setRandomSeed: (v: boolean) => void;
  sentencePause: number;
  setSentencePause: (v: number) => void;
  setVoice: (v: VoiceProfile | null) => void;
}) {
  return (
    <div className="flex flex-col gap-4 h-full px-7 pb-7">
      <Card className="shadow-[var(--shadow-soft)] flex-shrink-0 py-6">
        <CardHeader className="px-6 pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Mic2 className="size-4 text-primary" />
            Source
          </CardTitle>
          <CardDescription>
            The speaker, the engine and the language of this render.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-6 flex flex-col gap-3">
          <Field>
            <FieldLabel>Reference voice</FieldLabel>
            <VoicePicker
              voices={voices}
              value={voice}
              onChange={setVoice}
              disabled={loading}
            />
            <p className="text-xs text-muted-foreground mt-1">
              {voice
                ? `${voice.clips.length} reference sample${voice.clips.length === 1 ? "" : "s"} · quality ${voice.clips[0]?.quality_score ?? 0}/100`
                : "No profile selected"}
            </p>
          </Field>

          <Field>
            <FieldLabel>TTS engine</FieldLabel>
            <Select
              value={engineName}
              onValueChange={(value) => value && setEngineName(value)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select an engine" />
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
                      <span className="text-muted-foreground"> · {engine.unavailable_reason}</span>
                    ) : !engine.commercial_permitted ? (
                      <span className="text-status-warning"> · non-commercial</span>
                    ) : null}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground mt-1">{activeEngine?.license_name ?? "—"}</p>
          </Field>

          <Field>
            <FieldLabel>Language</FieldLabel>
            <Select
              value={params.language}
              onValueChange={(value) => value && update({ language: value })}
            >
              <SelectTrigger className="w-full">
                <SelectValue>
                  {(value) => String(value ?? "en").toUpperCase()}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {(activeEngine?.supported_languages ?? ["en"]).map((language) => (
                  <SelectItem key={language} value={language}>
                    {language.toUpperCase()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="flex items-center gap-1 text-xs text-muted-foreground mt-1">
              <Languages className="size-3" />
              {activeEngine?.supported_languages.length ?? 1} supported
            </p>
          </Field>
        </CardContent>
      </Card>

      <Card className="shadow-[var(--shadow-soft)] flex-1 min-h-0 flex flex-col py-6">
        <Tabs defaultValue="prosody" className="gap-0 flex-1 flex flex-col">
          <CardHeader className="px-6 pb-3 flex-shrink-0">
            <CardTitle className="flex items-center gap-2 text-base">
              <Wand2 className="size-4 text-primary" />
              Delivery
            </CardTitle>
            <CardDescription>
              How the voice should sound and how fast it should read.
            </CardDescription>
          </CardHeader>

          <CardContent className="px-6 space-y-4 flex-1 overflow-y-auto">
            <TabsList className="w-full flex-shrink-0">
              <TabsTrigger value="voice">Voice</TabsTrigger>
              <TabsTrigger value="prosody">Prosody</TabsTrigger>
              <TabsTrigger value="delivery">Delivery</TabsTrigger>
            </TabsList>

            <TabsContent value="voice" className="space-y-4 flex-1">
              <div className="rounded-md border border-border bg-surface-inset p-4">
                <p className="text-xs font-medium text-foreground">
                  {voice?.name ?? "No voice selected"}
                </p>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  {voice?.notes || "No notes for this profile."}
                </p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <Badge variant="outline">
                    {voice?.language.toUpperCase() ?? "—"}
                  </Badge>
                  <Badge variant={voice?.consent_confirmed ? "secondary" : "destructive"}>
                    {voice?.consent_confirmed ? "Consent confirmed" : "Consent missing"}
                  </Badge>
                </div>
              </div>

              <div className="rounded-md border border-border bg-surface-inset p-4">
                <p className="text-xs font-medium text-foreground">
                  {activeEngine?.name ?? "No engine"}
                </p>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  {activeEngine?.license_notice}
                </p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <Badge variant="outline">
                    {activeEngine?.native_sample_rate ?? 24000} Hz
                  </Badge>
                  <Badge
                    variant={
                      activeEngine?.commercial_permitted ? "secondary" : "destructive"
                    }
                  >
                    {activeEngine?.commercial_permitted
                      ? "Commercial use"
                      : "Non-commercial"}
                  </Badge>
                </div>
              </div>

              <div className="flex items-start justify-between gap-3 rounded-md border border-primary/20 bg-surface-accent p-4">
                <div className="flex items-start gap-3">
                  <LockKeyhole className="mt-0.5 size-4 shrink-0 text-primary" />
                  <div>
                    <p className="text-xs font-medium text-foreground">
                      Perth acoustic watermark
                    </p>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                      Embeds an imperceptible signature so the origin of a
                      render can be verified.
                    </p>
                  </div>
                </div>
                <Switch
                  checked={params.enable_watermark}
                  onCheckedChange={(checked) =>
                    update({ enable_watermark: checked })
                  }
                  aria-label="Toggle the acoustic watermark"
                />
              </div>
            </TabsContent>

            <TabsContent value="prosody" className="space-y-4">
              <div className="space-y-2">
                <p className="text-xs font-medium text-foreground">Presets</p>
                <div className="flex flex-wrap gap-1.5">
                  {VOICE_PRESETS.map((preset) => (
                    <PresetButton
                      key={preset.id}
                      preset={preset}
                      isActive={VOICE_PRESETS.find((p) =>
                        Object.entries(p.params).every(
                          ([key, value]) =>
                            params[key as keyof SynthesisParams] ===
                            (value as number | string | boolean),
                        ),
                      )?.id === preset.id}
                      onClick={() =>
                        update((previous) => ({
                          ...previous,
                          ...preset.params,
                        }))
                      }
                    />
                  ))}
                </div>
                <p className="text-sm text-muted-foreground">
                  {"Pick a preset, then fine-tune the values below."}
                </p>
              </div>

              <Separator />

              <ParamControl
                label="Exaggeration"
                description="How much the voice swings between flat and dramatic."
                value={params.exaggeration}
                min={0.2}
                max={2}
                step={0.05}
                suffix="x"
                resetValue={activeEngine?.default_params.exaggeration}
                onChange={(value) => update({ exaggeration: value })}
              />
              <ParamControl
                label="Speaker match (CFG)"
                description="How strictly the render follows the reference voice."
                value={params.cfg_weight}
                min={1}
                max={7}
                step={0.1}
                resetValue={activeEngine?.default_params.cfg_weight}
                onChange={(value) => update({ cfg_weight: value })}
              />
              <ParamControl
                label="Variation"
                description="Lower is predictable, higher is more spontaneous."
                value={params.temperature}
                min={0.1}
                max={1.5}
                step={0.05}
                resetValue={activeEngine?.default_params.temperature}
                onChange={(value) => update({ temperature: value })}
              />
            </TabsContent>

            <TabsContent value="delivery" className="space-y-4">
              <ParamControl
                label="Speed"
                description="Playback rate of the rendered audio."
                value={params.speed}
                min={0.5}
                max={2}
                step={0.05}
                suffix="x"
                resetValue={activeEngine?.default_params.speed}
                onChange={(value) => update({ speed: value })}
              />
              <ParamControl
                label="Silence between sentences"
                description="The breath between two rendered sentences."
                value={sentencePause}
                min={0}
                max={1500}
                step={50}
                suffix="ms"
                digits={0}
                resetValue={250}
                onChange={setSentencePause}
              />

              <Separator />

              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium">Deterministic seed</p>
                  <p className="mt-0.5 text-sm leading-snug text-muted-foreground">
                    Lock the random seed to reproduce a render exactly.
                  </p>
                </div>
                <Switch
                  checked={randomSeed}
                  onCheckedChange={setRandomSeed}
                  aria-label="Toggle the deterministic seed"
                />
              </div>

              {!randomSeed ? (
                <ParamControl
                  label="Seed value"
                  description="The same seed and script always produce the same audio."
                  value={params.seed}
                  min={0}
                  max={10000}
                  step={1}
                  digits={0}
                  onChange={(value) => update({ seed: value })}
                  showRandomize
                  onRandomize={() => update({ seed: Math.floor(Math.random() * 10000) })}
                />
              ) : null}
            </TabsContent>
          </CardContent>
        </Tabs>
      </Card>
    </div>
  );
}

export function StudioPage() {
  const { status: connection } = useEngineStatus();
  const { navigate } = useApp();
  const { resolvedTheme } = useTheme();
  const online = connection !== "offline";
  const canvas = resolvedTheme === "dark" ? "bg-background" : "bg-white";

  const { voices, engines, loading, voice, setVoice } = useLibrary(online);
  const { engineName, setEngineName, activeEngine, params, update } =
    useEngineSelection(engines);
  const [text, setText] = useState("");
  const [randomSeed, setRandomSeed] = useState(true);
  const [sentencePause, setSentencePause] = useState(250);
  const [renderedText, setRenderedText] = useState("");
  const [renderedConfiguration, setRenderedConfiguration] = useState<{
    voiceName: string;
    engineName: string;
    params: SynthesisParams;
  } | null>(null);
  const [playing, setPlaying] = useState(false);

  const scriptRef = useRef<HTMLTextAreaElement>(null);
  const waveformRef = useRef<WaveformPlayerHandle>(null);

  const { job, starting, audioUrl, duration, setDuration, isRunning, synthesize, cancel } =
    useSynthesisJob({
      voice,
      engines,
      engineName,
      text,
      params,
      randomSeed,
      sentencePause,
      online,
      onRenderQueued: () => {
        setRenderedText(text.trim());
        setRenderedConfiguration(
          voice
            ? {
                voiceName: voice.name,
                engineName,
                params: { ...params, seed: randomSeed ? -1 : params.seed },
              }
            : null,
        );
        setPlaying(false);
      },
    });

  const peaks = job?.peaks?.length ? job.peaks : null;
  const words = countWords(text);
  const estimatedSeconds = estimateDurationSeconds(words, params.speed);

  const exportAudio = useCallback(async () => {
    if (!audioUrl) {
      toast.error("There is nothing to export yet");
      return;
    }
    try {
      const response = await fetch(audioUrl);
      const blob = await response.blob();
      const filename = `voiceclone-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.wav`;

      if (IS_TAURI) {
        const path = await pickSavePath(filename, "wav");
        if (!path) return;
        const written = await writeBlobToPath(path, blob);
        if (written) {
          toast.success("Export saved", { description: path });
          return;
        }
      }
      downloadBlob(blob, filename);
      toast.success("Export started", { description: filename });
    } catch {
      toast.error("Export failed");
    }
  }, [audioUrl]);

  const togglePlayback = useCallback(() => {
    waveformRef.current?.playPause();
  }, []);

  const clearScript = useCallback(() => {
    setText("");
    scriptRef.current?.focus();
  }, []);

  useAppActions({
    runSynthesis: () => void synthesize(),
    exportRender: () => void exportAudio(),
    clearScript,
    focusScript: () => scriptRef.current?.focus(),
    togglePlayback,
  });

  useHotkeys(
    useMemo(
      () => ({
        "mod+enter": () => void synthesize(),
        "mod+e": () => void exportAudio(),
        "mod+backspace": clearScript,
        "mod+shift+t": () => scriptRef.current?.focus(),
        space: () => togglePlayback(),
        arrowleft: () => waveformRef.current?.skip(-2),
        arrowright: () => waveformRef.current?.skip(2),
      }),
      [clearScript, exportAudio, synthesize, togglePlayback],
    ),
    { allowInInputs: false },
  );

  return (
    <Sheet>
      <div className={`-mx-4 -my-4 flex min-h-[calc(100dvh-3.5rem)] flex-col text-foreground md:-mx-6 md:-my-6 ${canvas}`}>
        <header className="flex shrink-0 items-center justify-between gap-4 border-b border-border/70 px-4 py-3 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-surface-accent text-primary">
              <AudioLines className="size-4" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold">VoiceClone Studio</p>
              <p className="truncate text-xs text-muted-foreground">
                {voice
                  ? `${voice.name} · ${activeEngine?.name ?? engineName}`
                  : "Choose a voice to get started"}
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Badge variant="outline" className="gap-1.5 rounded-full px-2.5 py-1 font-normal">
              <span className={`size-1.5 rounded-full ${connection === "offline" ? "bg-status-warning" : "bg-status-success"}`} />
              <span className="hidden sm:inline">{connection === "offline" ? (IS_TAURI ? "Engine offline" : "Offline demo") : "Engine ready"}</span>
            </Badge>
            <SheetTrigger
              className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-card px-3 text-sm text-foreground transition-colors hover:bg-muted"
              aria-label="Open voice controls"
            >
              <SlidersHorizontal className="size-3.5" />
              <span className="hidden sm:inline">Voice controls</span>
            </SheetTrigger>
          </div>
        </header>

        {!loading && voices.length === 0 && (
          <div
            role="status"
            className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 bg-surface-accent px-4 py-3 text-sm sm:px-6"
          >
            <span>
              {online
                ? "No voices yet. Add a reference recording to start cloning."
                : "The engine is not running, so no voices could be loaded."}
            </span>
            {online && (
              <Button size="sm" onClick={() => navigate("voices")}>
                Add a voice
              </Button>
            )}
          </div>
        )}

        <section className="flex min-h-0 flex-1 flex-col">
          <div className="flex min-h-0 flex-1 flex-col justify-center px-4 sm:px-6">
            {!job && !starting ? (
              <div className="mx-auto w-full max-w-3xl py-8">
                <div className="mb-7 text-center">
                  <div className="mx-auto mb-4 flex size-11 items-center justify-center rounded-md border border-primary/15 bg-surface-accent text-primary">
                    <Sparkles className="size-5" />
                  </div>
                  <h1 className="font-heading text-4xl tracking-tight sm:text-5xl">
                    What should we say?
                  </h1>
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground sm:text-base">
                    Write something and I&apos;ll turn it into a natural voice.
                  </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  {SCRIPT_SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion.title}
                      type="button"
                      onClick={() => {
                        setText(suggestion.description);
                        scriptRef.current?.focus();
                      }}
                      className="group flex flex-col items-stretch justify-start rounded-md border border-border/80 bg-card/80 p-4 text-left transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-card hover:shadow-[var(--shadow-soft)]"
                    >
                      <span className="mb-3 flex items-center justify-between gap-2">
                        <span className={`flex size-8 items-center justify-center rounded-md ${suggestion.tint}`}>
                          <suggestion.icon className="size-4" />
                        </span>
                        <span aria-hidden="true" className="text-xs text-muted-foreground/60 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5">↗</span>
                      </span>
                      <span className="mb-1 block text-xs font-medium text-primary">
                        {suggestion.title}
                      </span>
                      <span className="line-clamp-3 block text-sm leading-relaxed text-muted-foreground group-hover:text-foreground">
                        {suggestion.description}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="mx-auto w-full max-w-3xl space-y-7 py-8">
                <div className="ml-5 border-l-2 border-border pl-4">
                  <span className="text-xs text-muted-foreground">You</span>
                  <p className="mt-2 text-sm leading-relaxed">{renderedText}</p>
                </div>
                <div>
                  <div className="mb-3 flex items-center gap-2">
                    <span className="flex size-7 items-center justify-center rounded-md bg-surface-accent text-primary">
                      <AudioWaveform className="size-3.5" />
                    </span>
                    <strong className="text-sm">VoiceClone</strong>
                    <span className="text-xs text-muted-foreground">
                      {isRunning || starting ? "creating voice…" : "just now"}
                    </span>
                  </div>
                  <p className="mb-4 text-sm leading-relaxed">
                    {job?.state === "failed"
                      ? job.error ?? "The voice could not be generated."
                      : isRunning || starting
                        ? job?.message ?? "Rendering your script with the selected voice settings."
                        : renderedConfiguration
                          ? describeRenderConfiguration(
                              renderedConfiguration.voiceName,
                              renderedConfiguration.engineName,
                              renderedConfiguration.params,
                            )
                          : "Your audio is ready."}
                  </p>

                  {audioUrl ? (
                    <div className="flex items-center gap-3 rounded-md border border-border bg-surface-inset/70 px-3 py-2.5">
                      <Button
                        size="icon"
                        className="size-9 shrink-0 rounded-full"
                        onClick={togglePlayback}
                        aria-label={playing ? "Pause audio" : "Play audio"}
                      >
                        {playing ? <Pause /> : <Play />}
                      </Button>
                      <WaveformPlayer
                        ref={waveformRef}
                        url={audioUrl}
                        peaks={peaks}
                        duration={duration || job?.duration_seconds || 0}
                        height={32}
                        className="min-w-0 flex-1 border-0 bg-transparent"
                        onPlayChange={setPlaying}
                        onReady={(loaded) => setDuration(loaded || duration)}
                        onEnded={() => setPlaying(false)}
                      />
                      <code className="shrink-0 text-[11px] text-muted-foreground">
                        {formatTimecode(duration || job?.duration_seconds || 0)}
                      </code>
                    </div>
                  ) : isRunning ? (
                    <div className="flex items-start gap-3">
                      <div className="min-w-0 flex-1 space-y-2 pt-2.5">
                        {(job?.progress ?? 0) > 0 ? (
                          <Progress
                            value={job?.progress ?? 0}
                            aria-label="Render progress"
                          />
                        ) : (
                          <div
                            role="progressbar"
                            aria-label="Render progress"
                            className="relative h-1 overflow-hidden rounded-full bg-muted"
                          >
                            <div className="progress-indeterminate absolute inset-y-0 w-1/3 rounded-full bg-primary" />
                          </div>
                        )}
                        <p className="text-xs tabular-nums text-muted-foreground">
                          {[
                            (job?.progress ?? 0) > 0 ? `${Math.round(job?.progress ?? 0)}%` : null,
                            job?.eta && (job?.progress ?? 0) > 0 ? `${job.eta} left` : null,
                            (job?.chunks_ready ?? 0) > 0 ? "Playing as it renders" : null,
                          ]
                            .filter(Boolean)
                            .join(" · ") || "First sentence is on its way"}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void cancel()}
                        disabled={!job}
                      >
                        <Square className="fill-current" />
                        Cancel
                      </Button>
                    </div>
                  ) : null}

                  {audioUrl ? (
                    <div className="mt-3 flex items-center gap-4">
                      <SheetTrigger
                        className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
                        aria-label="Adjust voice"
                      >
                        <SlidersHorizontal className="size-3.5" />
                        Adjust voice
                      </SheetTrigger>
                      <button
                        type="button"
                        onClick={() => void exportAudio()}
                        className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
                      >
                        <Download className="size-3.5" />
                        Export
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
            )}
          </div>

          <div className="shrink-0 px-4 pb-4 sm:px-6 sm:pb-5">
            <Card className="mx-auto w-full max-w-3xl border-border/80 shadow-[var(--shadow-soft)]">
              <CardContent className="space-y-3 p-4 sm:p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">Your script</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Shape the words and delivery before you render.
                    </p>
                  </div>
                  <span className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:inline-flex">
                    <Mic2 className="size-3.5 text-primary" />
                    {voice?.name ?? "No voice selected"}
                  </span>
                </div>
                <Textarea
                  ref={scriptRef}
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      !event.shiftKey &&
                      !event.nativeEvent.isComposing &&
                      event.keyCode !== 229
                    ) {
                      event.preventDefault();
                      void synthesize();
                    }
                  }}
                  placeholder="Type or paste the script to speak…"
                  aria-label="Voice prompt"
                  rows={3}
                  className="min-h-[76px] resize-y rounded-md border-border/70 bg-surface-inset/60 px-3 py-2.5 text-sm leading-relaxed focus-visible:bg-card"
                />
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
                    <span className="flex items-center gap-1.5">
                      <Info className="size-3" />
                      Voice stays on this machine
                    </span>
                    <span data-numeric>{text.trim().length} characters</span>
                    <span data-numeric>{words} words · ~{estimatedSeconds.toFixed(1)}s</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {text ? (
                      <Button variant="ghost" size="sm" onClick={clearScript}>
                        Clear
                      </Button>
                    ) : null}
                    <Button
                      size="sm"
                      onClick={() => void synthesize()}
                      disabled={isRunning || starting || !voice || !text.trim()}
                      className="h-9 rounded-md px-3"
                    >
                      {starting ? <Loader2 className="animate-spin" /> : <Sparkles />}
                      {starting ? "Starting…" : isRunning ? "Generating…" : "Generate voice"}
                      <Kbd className="ml-1 border-primary-foreground/30 bg-primary-foreground/15 text-primary-foreground">
                        ↵
                      </Kbd>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
            <p className="mt-2.5 text-center text-[10px] text-muted-foreground/75">
              VoiceClone can make mistakes. Review generated audio before exporting.
            </p>
          </div>
        </section>

        {(job || starting) ? (
          <div className="fixed bottom-5 right-5 z-30">
            <SheetTrigger
              className="inline-flex h-10 items-center gap-2 rounded-md border border-border bg-card px-3.5 text-sm text-foreground shadow-[var(--shadow-soft)] transition-colors hover:bg-muted"
              aria-label="Open voice controls"
            >
              <SlidersHorizontal className="size-3.5" />
              Voice controls
            </SheetTrigger>
          </div>
        ) : null}

        <SheetContent side="right" className="w-[460px] data-[side=right]:sm:max-w-[460px] max-h-screen">
          <SheetHeader>
            <SheetTitle>Voice controls</SheetTitle>
          </SheetHeader>
          <DrawerContent
            voice={voice}
            voices={voices}
            loading={loading}
            engineName={engineName}
            setEngineName={setEngineName}
            activeEngine={activeEngine}
            engines={engines}
            params={params}
            update={update}
            randomSeed={randomSeed}
            setRandomSeed={setRandomSeed}
            sentencePause={sentencePause}
            setSentencePause={setSentencePause}
            setVoice={setVoice}
          />
        </SheetContent>
      </div>
    </Sheet>
  );
}