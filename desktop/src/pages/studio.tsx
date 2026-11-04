import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AudioLines,
  ChevronLeft,
  Download,
  Gauge,
  Info,
  Languages,
  LockKeyhole,
  Mic2,
  Settings2,
  Sparkles,
  Wand2,
  WifiOff,
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
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Field, FieldLabel } from "@/components/ui/field";
import { Kbd } from "@/components/ui/kbd";
import { PageHeader, StatChip } from "@/components/ui/page-header";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { ParamControl } from "@/components/studio/param-control";
import { RenderBar } from "@/components/studio/render-bar";
import { SentenceChips } from "@/components/studio/sentence-chips";
import { TransportBar } from "@/components/studio/transport-bar";
import { VOICE_PRESETS } from "@/components/studio/presets";
import { VoicePicker } from "@/components/studio/voice-picker";
import {
  WaveformPlayer,
  type WaveformPlayerHandle,
} from "@/components/waveform/waveform-player";
import { api } from "@/lib/api";
import { useAppActions } from "@/lib/app-context";
import { chunkText, countWords } from "@/lib/chunk-preview";
import {
  downloadBlob,
  IS_TAURI,
  pickSavePath,
  writeBlobToPath,
} from "@/lib/desktop";
import { useEngineStatus } from "@/lib/engine-status";
import { estimateDurationSeconds, formatDuration } from "@/lib/format";
import { mockEngines, mockVoices } from "@/lib/mock";
import { formatShortcut } from "@/lib/shortcuts";
import { useHotkeys } from "@/lib/use-hotkeys";
import type { EngineInfo, JobStatus, SynthesisParams, VoiceProfile } from "@/lib/types";

const DEFAULT_TEXT =
  "Welcome to VoiceClone Studio. Everything is processed securely on your computer — no data ever leaves this machine.";

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
  update: (patch: Partial<SynthesisParams>) => void;
  randomSeed: boolean;
  setRandomSeed: (v: boolean) => void;
  sentencePause: number;
  setSentencePause: (v: number) => void;
  setVoice: (v: VoiceProfile | null) => void;
}) {
  return (
    <div className="flex flex-col gap-4 h-full">
      <Card className="rounded-2xl shadow-[var(--shadow-soft)] flex-shrink-0">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Mic2 className="size-4 text-primary" />
            Source
          </CardTitle>
          <CardDescription>
            The speaker, the engine and the language of this render.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
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
                      <span className="text-muted-foreground"> · not installed</span>
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

      <Card className="rounded-2xl shadow-[var(--shadow-soft)] flex-1 min-h-0 flex flex-col">
        <Tabs defaultValue="prosody" className="gap-0 flex-1 flex flex-col">
          <CardHeader className="pb-3 flex-shrink-0">
            <CardTitle className="flex items-center gap-2 text-base">
              <Wand2 className="size-4 text-primary" />
              Delivery
            </CardTitle>
            <CardDescription>
              How the voice should sound and how fast it should read.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4 flex-1 overflow-y-auto">
            <TabsList className="w-full flex-shrink-0">
              <TabsTrigger value="voice">Voice</TabsTrigger>
              <TabsTrigger value="prosody">Prosody</TabsTrigger>
              <TabsTrigger value="delivery">Delivery</TabsTrigger>
            </TabsList>

            <TabsContent value="voice" className="space-y-4 flex-1">
              <div className="rounded-xl border border-border bg-surface-inset p-4">
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

              <div className="rounded-xl border border-border bg-surface-inset p-4">
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

              <div className="flex items-start justify-between gap-3 rounded-xl border border-primary/20 bg-surface-accent p-4">
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
  const online = connection !== "offline";

  const [voices, setVoices] = useState<VoiceProfile[]>([]);
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [voice, setVoice] = useState<VoiceProfile | null>(null);
  const [engineName, setEngineName] = useState("Chatterbox TTS");
  const [text, setText] = useState(DEFAULT_TEXT);
  const [params, setParams] = useState<SynthesisParams>(mockEngines[0].default_params);
  const [randomSeed, setRandomSeed] = useState(true);
  const [sentencePause, setSentencePause] = useState(250);

  const [job, setJob] = useState<JobStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [volume, setVolume] = useState(100);
  const [muted, setMuted] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  const scriptRef = useRef<HTMLTextAreaElement>(null);
  const waveformRef = useRef<WaveformPlayerHandle>(null);

  const activeEngine = useMemo(
    () => engines.find((engine) => engine.name === engineName) ?? engines[0],
    [engineName, engines],
  );

  const isRunning = job?.state === "queued" || job?.state === "running";

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!online) {
        if (!cancelled) {
          setVoices(mockVoices);
          setEngines(mockEngines);
          setLoading(false);
        }
        return;
      }
      try {
        const [nextVoices, nextEngines] = await Promise.all([
          api.listVoices(),
          api.listEngines(),
        ]);
        if (cancelled) return;
        setVoices(nextVoices);
        setEngines(nextEngines);
      } catch {
        if (!cancelled) {
          setVoices(mockVoices);
          setEngines(mockEngines);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [online]);

  useEffect(() => {
    if (!voices.length) return;
    setVoice((previous) => {
      if (previous && voices.some((item) => item.id === previous.id)) return previous;
      return voices[0] ?? null;
    });
  }, [voices]);

  useEffect(() => {
    if (!engines.length) return;
    const current = engines.find((engine) => engine.name === engineName);
    if (!current?.is_available) {
      const preferred = engines.find((engine) => engine.is_available) ?? engines[0];
      if (preferred && preferred.name !== engineName) setEngineName(preferred.name);
    }
  }, [engines, engineName]);

  useEffect(() => {
    if (!activeEngine) return;
    setParams((previous) => ({
      ...activeEngine.default_params,
      language: activeEngine.supported_languages.includes(previous.language)
        ? previous.language
        : (activeEngine.supported_languages[0] ?? "en"),
      enable_watermark: previous.enable_watermark,
    }));
  }, [activeEngine]);

  const peaks = job?.peaks?.length ? job.peaks : null;
  const words = countWords(text);
  const chunks = useMemo(() => chunkText(text), [text]);
  const estimatedSeconds = estimateDurationSeconds(words, params.speed);

  useEffect(() => {
    if (!job || !isRunning) return;
    const jobId = job.id;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.getJob(jobId);
        setJob(next);
        if (next.state === "done") {
          setAudioUrl(next.audio_url ? api.audioUrl(next.audio_url) : null);
          setDuration(next.duration_seconds ?? 0);
          toast.success("Render complete", {
            description: `${formatDuration(next.duration_seconds)} of audio is ready.`,
          });
        } else if (next.state === "failed") {
          toast.error("Render failed", { description: next.error ?? undefined });
        }
      } catch {
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job?.id, job?.state, isRunning]);

  useEffect(() => {
    if (!isRunning) {
      setElapsed(0);
      return;
    }
    const started = Date.now();
    const timer = window.setInterval(
      () => setElapsed((Date.now() - started) / 1000),
      500,
    );
    return () => window.clearInterval(timer);
  }, [isRunning, job?.id]);

  const update = useCallback(
    (patch: Partial<SynthesisParams>) =>
      setParams((previous) => ({ ...previous, ...patch })),
    [],
  );

  const synthesize = useCallback(async () => {
    if (isRunning) return;
    if (!voice) {
      toast.error("Select a voice profile first", {
        description: "Create one from the Voices screen if the library is empty.",
      });
      return;
    }
    if (!text.trim()) {
      toast.error("Write something to synthesize");
      return;
    }
    const selected = engines.find((engine) => engine.name === engineName);
    if (online && !selected?.is_available) {
      toast.error("That engine isn't installed", {
        description: `Download the ${engineName} weights from the Models screen.`,
      });
      return;
    }

    setStarting(true);
    setCurrentTime(0);
    setDuration(0);
    setPlaying(false);

    try {
      const created = await api.synthesize({
        voice_id: voice.id,
        engine_name: engineName,
        text: text.trim(),
        params: { ...params, seed: randomSeed ? -1 : params.seed },
        sentence_pause_ms: sentencePause,
      });
      setJob(created);
      setAudioUrl(null);
      toast.message("Render started", {
        description: `${created.total_chunks || 1} sentence chunk${
          created.total_chunks === 1 ? "" : "s"
        } queued.`,
      });
    } catch (error) {
      toast.error("Could not start the render", {
        description: error instanceof Error ? error.message : String(error),
      });
      setJob((previous) =>
        previous
          ? {
              ...previous,
              state: "failed" as const,
              error: error instanceof Error ? error.message : String(error),
              message: "Render failed",
            }
          : previous,
      );
    } finally {
      setStarting(false);
    }
  }, [
    engines,
    engineName,
    isRunning,
    online,
    params,
    randomSeed,
    sentencePause,
    text,
    voice,
  ]);

  const cancel = useCallback(async () => {
    if (!job || !isRunning) return;
    try {
      setJob(await api.cancelJob(job.id));
      toast.message("Cancelling the render");
    } catch (error) {
      toast.error("Could not cancel", {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  }, [isRunning, job]);

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

  const stopPlayback = useCallback(() => {
    waveformRef.current?.stop();
    setCurrentTime(0);
    setPlaying(false);
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
    <div className="flex min-h-screen flex-col gap-6">
      <PageHeader
        title="Studio"
        description="Write the script, shape the delivery, render and export — all on this machine."
        icon={AudioLines}
        meta={
          <>
            <StatChip icon={Gauge} tone="accent">
              {activeEngine?.name ?? "No engine"}
            </StatChip>
            {connection === "offline" ? (
              <StatChip icon={WifiOff} tone="warning">
                Offline demo
              </StatChip>
            ) : null}
          </>
        }
        actions={
          <>
            <Button variant="ghost" size="icon" onClick={clearScript} aria-label="Clear script" title="Clear script (⌘⌫)">
              <Sparkles className="size-4" />
            </Button>
            <Sheet>
              <SheetTrigger
                className="inline-flex shrink-0 items-center justify-center rounded-lg border border-transparent
                bg-clip-padding text-sm font-medium whitespace-nowrap transition-all outline-none
                select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50
                active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4 h-7 w-7 rounded-[min(var(--radius-md),12px)]"
                aria-label="Open settings drawer"
                title="Settings"
              >
                <Settings2 className="size-4" />
              </SheetTrigger>
              <SheetContent side="right" className="w-[640px] sm:max-w-[640px] max-h-screen">
                <SheetHeader>
                  <SheetTitle>Settings</SheetTitle>
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
            </Sheet>
            <Button onClick={() => void synthesize()} disabled={isRunning || !voice || !text.trim()} className="ml-2">
              <Sparkles className="mr-1.5 size-4" />
              Synthesize
            </Button>
          </>
        }
      />

      <div className="flex min-w-0 flex-col gap-3">
        <Card className="rounded-2xl shadow-[var(--shadow-soft)]">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles className="size-4 text-primary" />
                Script
              </CardTitle>
              <span className="hidden items-center gap-1 text-[11px] text-muted-foreground sm:flex">
                <Kbd>{formatShortcut("mod+enter")}</Kbd>
                to render
              </span>
            </div>
            <CardDescription>
              The script is split into sentence-aware chunks before it reaches the engine.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              ref={scriptRef}
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Type or paste the script to speak…"
              className="min-h-[140px] resize-y text-[15px] leading-relaxed rounded-xl border border-border bg-surface-raised focus:border-primary focus:ring-2 focus:ring-primary/20"
              aria-label="Script to synthesize"
            />

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span data-numeric>{text.trim().length} chars</span>
              <span data-numeric>{words} words</span>
              <span data-numeric>~{estimatedSeconds.toFixed(1)}s audio</span>
              <span data-numeric>{chunks.length} chunks</span>
            </div>

            <Separator />

            <SentenceChips chunks={chunks} />
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-2xl shadow-[var(--shadow-soft)]">
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <AudioLines className="size-4 text-primary" />
                Output
              </CardTitle>
              <CardDescription>
                {job?.state === "done"
                  ? job.message
                  : "The rendered audio, with a ruler you can scrub and click."}
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void exportAudio()}
              disabled={!audioUrl}
            >
              <Download className="mr-1.5 size-4" />
              Export WAV
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {audioUrl ? (
            <WaveformPlayer
              ref={waveformRef}
              url={audioUrl}
              peaks={peaks}
              duration={duration || job?.duration_seconds || 0}
              onTimeUpdate={setCurrentTime}
              onPlayChange={setPlaying}
              onReady={(loaded) => setDuration(loaded || duration)}
              onEnded={() => {
                setPlaying(false);
                setCurrentTime(0);
              }}
            />
          ) : (
            <Empty className="border border-dashed rounded-2xl bg-surface-inset/60 py-8">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <Info />
                </EmptyMedia>
                <EmptyTitle>
                  {isRunning ? "Rendering the audio" : "No render yet"}
                </EmptyTitle>
                <EmptyDescription>
                  {isRunning
                    ? job?.message ?? "The engine is working — the waveform appears when it finishes."
                    : "Run the script to produce a waveform you can scrub, loop and export."}
                </EmptyDescription>
              </EmptyHeader>
              {!isRunning ? (
                <EmptyContent>
                  <Button size="sm" onClick={() => void synthesize()} disabled={!text.trim() || !voice}>
                    <Sparkles className="mr-1.5 size-4" />
                    Run synthesis
                  </Button>
                </EmptyContent>
              ) : null}
            </Empty>
          )}

          <TransportBar
            playing={playing}
            currentTime={currentTime}
            duration={duration || job?.duration_seconds || 0}
            volume={volume}
            muted={muted}
            disabled={!audioUrl}
            onPlayPause={togglePlayback}
            onStop={stopPlayback}
            onSkip={(seconds) => waveformRef.current?.skip(seconds)}
            onVolumeChange={(next) => {
              setVolume(next);
              setMuted(next === 0);
              waveformRef.current?.setVolume(next / 100);
            }}
            onMuteToggle={() => {
              const nextMuted = !muted;
              setMuted(nextMuted);
              waveformRef.current?.setVolume(nextMuted ? 0 : volume / 100);
            }}
          />
        </CardContent>
      </Card>

      <RenderBar
        job={job}
        starting={starting}
        canRender={Boolean(text.trim()) && Boolean(voice)}
        elapsed={elapsed}
        estimatedSeconds={estimatedSeconds}
        onRun={() => void synthesize()}
        onCancel={() => void cancel()}
      />
    </div>
  );
}