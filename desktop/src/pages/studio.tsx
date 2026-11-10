import { LoadingOverlay } from "@/components/ui/loading-overlay";
import { useCallback, useMemo, useRef, useState } from "react";
import {
  AudioLines,
  Download,
  Languages,
  Pause,
  Play,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
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
import { RenderProgress } from "@/components/studio/render-progress";
import { Composer, Suggestions, type StudioMode } from "@/components/studio/composer";
import { SoundResult, SoundSettings, EXAMPLES, PLACEHOLDERS, useSoundWorkspace } from "@/components/studio/sound-workspace";
import { ParamControl } from "@/components/studio/param-control";
import { EngineControls } from "@/components/studio/engine-controls";
import { VOICE_PRESETS } from "@/components/studio/presets";
import { VoicePicker } from "@/components/studio/voice-picker";
import {
  WaveformPlayer,
  type WaveformPlayerHandle,
} from "@/components/waveform/waveform-player";
import { useEngineSelection, useLibrary, useSynthesisJob } from "@/hooks/use-studio";
import { useApp, useAppActions } from "@/lib/app-context";
import { exportAudio } from "@/lib/export-audio";
import { useEngineStatus } from "@/lib/engine-status";
import {
  formatTimecode,
} from "@/lib/format";
import { useHotkeys } from "@/lib/use-hotkeys";
import type { EngineInfo, SynthesisParams, VoiceProfile } from "@/lib/types";

const SCRIPT_SUGGESTIONS = [
  {
    title: "Podcast intro",
    description: "Welcome back. Today we look at how small habits quietly change everything.",
  },
  {
    title: "Calm and reassuring",
    description: "Take a breath. Everything is on track, and there is nothing you need to do right now.",
  },
  {
    title: "Product announcement",
    description: "Introducing the new Studio: record your voice once, and it is ready whenever you need it.",
  },
];

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
    <div className="flex flex-col gap-6">
      <Tabs defaultValue="source" className="gap-4 flex flex-col">
        <TabsList className="w-full flex-shrink-0">
          <TabsTrigger value="source">Source</TabsTrigger>
          <TabsTrigger value="voice">Voice</TabsTrigger>
          <TabsTrigger value="prosody">Prosody</TabsTrigger>
          <TabsTrigger value="delivery">Delivery</TabsTrigger>
        </TabsList>

        <TabsContent value="source" className="flex flex-col gap-3">
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
        </TabsContent>

            <TabsContent value="voice" className="space-y-4">
              <div className="space-y-2">
                <p className="text-xs font-medium text-foreground">
                  {voice?.name ?? "No voice selected"}
                </p>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {voice?.notes || "No notes for this profile."}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  <Badge variant="outline">
                    {voice?.language.toUpperCase() ?? "—"}
                  </Badge>
                  <Badge variant={voice?.consent_confirmed ? "secondary" : "destructive"}>
                    {voice?.consent_confirmed ? "Consent confirmed" : "Consent missing"}
                  </Badge>
                </div>
              </div>

              <Separator />

              <div className="space-y-2">
                <p className="text-xs font-medium text-foreground">
                  {activeEngine?.name ?? "No engine"}
                </p>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {activeEngine?.license_notice}
                </p>
                <div className="flex flex-wrap gap-1.5">
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

              <Separator />

              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-medium text-foreground">
                    Perth acoustic watermark
                  </p>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    Embeds an imperceptible signature so the origin of a
                    render can be verified.
                  </p>
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

              <EngineControls controls={activeEngine?.controls} group="style" params={params} defaults={activeEngine?.default_params} onChange={update} />
              <EngineControls controls={activeEngine?.controls} group="advanced" params={params} defaults={activeEngine?.default_params} onChange={update} />
            </TabsContent>

            <TabsContent value="delivery" className="space-y-4">
              <EngineControls controls={activeEngine?.controls} group="delivery" params={params} defaults={activeEngine?.default_params} onChange={update} />
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
                  value={params.seed}
                  min={0}
                  max={99999999}
                  step={1}
                  digits={0}
                  onChange={(value) => update({ seed: value })}
                  showRandomize
                  onRandomize={() => update({ seed: Math.floor(Math.random() * 99999999) })}
                />
              ) : null}
            </TabsContent>
      </Tabs>
    </div>
  );
}

export function StudioPage() {
  const { status: connection } = useEngineStatus();
  const { navigate, page } = useApp();
  const active = page === "studio";
  const online = connection !== "offline";
  const [mode, setMode] = useState<StudioMode>("speech");
  const sound = useSoundWorkspace(mode === "music" ? "music" : "sfx", online, active);

  const { voices, engines, loading, voice, setVoice } = useLibrary(online, active);
  const { engineName, setEngineName, activeEngine, params, update } =
    useEngineSelection(engines);
  const [text, setText] = useState("");
  const [randomSeed, setRandomSeed] = useState(true);
  const [sentencePause, setSentencePause] = useState(250);
  const [renderedText, setRenderedText] = useState("");
  const [playing, setPlaying] = useState(false);

  const scriptRef = useRef<HTMLTextAreaElement>(null);
  const waveformRef = useRef<WaveformPlayerHandle>(null);

  const { job, starting, audioUrl, duration, setDuration, isRunning, synthesize, cancel, stopLive } =
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
        setPlaying(false);
      },
    });

  const peaks = job?.peaks?.length ? job.peaks : null;

  const startExport = useCallback(() => {
    if (!audioUrl) {
      toast.error("There is nothing to export yet");
      return;
    }
    exportAudio(audioUrl, voice?.name ?? "voice");
  }, [audioUrl, voice]);

  const togglePlayback = useCallback(() => {
    waveformRef.current?.playPause();
  }, []);

  const clearScript = useCallback(() => {
    setText("");
    scriptRef.current?.focus();
  }, []);

  useAppActions({
    runSynthesis: () => void synthesize(),
    exportRender: startExport,
    clearScript,
    focusScript: () => scriptRef.current?.focus(),
    togglePlayback,
  });

  useHotkeys(
    useMemo(
      () => ({
        "mod+enter": () => void synthesize(),
        "mod+e": startExport,
        "mod+backspace": clearScript,
        "mod+shift+t": () => scriptRef.current?.focus(),
        space: () => togglePlayback(),
        arrowleft: () => waveformRef.current?.skip(-2),
        arrowright: () => waveformRef.current?.skip(2),
      }),
      [clearScript, startExport, synthesize, togglePlayback],
    ),
    { enabled: active, allowInInputs: false },
  );

  const soundBusy = sound.starting || sound.isRunning;
  const idle =
    mode === "speech"
      ? !job && !starting
      : !sound.audioUrl && !soundBusy && sound.job?.state !== "failed";
  const heading = mode === "speech" ? "What should we say?" : mode === "sfx" ? "Describe a sound" : "Describe the music";
  const suggestionItems =
    mode === "speech" ? SCRIPT_SUGGESTIONS.map((item) => item.title) : EXAMPLES[mode];
  const pickSuggestion = (item: string) => {
    if (mode === "speech") {
      setText(SCRIPT_SUGGESTIONS.find((suggestion) => suggestion.title === item)?.description ?? item);
      scriptRef.current?.focus();
    } else {
      sound.setPrompt(item);
    }
  };
  const composer =
    mode === "speech" ? (
      <Composer
        ref={scriptRef}
        mode={mode}
        onModeChange={setMode}
        value={text}
        onChange={setText}
        onSubmit={() => void synthesize()}
        placeholder="Type or paste the script to speak…"
        canSubmit={!isRunning && !starting && !!voice && !!text.trim()}
        busy={starting || isRunning}
        trailing={voice?.name ?? "No voice selected"}
      />
    ) : (
      <Composer
        mode={mode}
        onModeChange={setMode}
        value={sound.prompt}
        onChange={sound.setPrompt}
        onSubmit={sound.submit}
        placeholder={PLACEHOLDERS[mode]}
        canSubmit={sound.canGenerate}
        busy={soundBusy}
        maxLength={1000}
      />
    );

  return (
    <>
      <LoadingOverlay show={loading} />
      <div className="-mx-4 -my-4 flex min-h-[calc(100dvh-3.5rem)] text-foreground md:-mx-6 md:-my-6 bg-background">
        <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex shrink-0 items-center justify-between gap-4 border-b border-border/70 px-4 py-3 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-surface-accent text-primary">
              <AudioLines className="size-4" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold">Timbre</p>
              <p className="truncate text-xs text-muted-foreground">
                {mode !== "speech"
                  ? (sound.engine?.name ?? "Describe what you want to hear")
                  : voice
                    ? `${voice.name} · ${activeEngine?.name ?? engineName}`
                    : "Choose a voice to get started"}
              </p>
            </div>
          </div>
        </header>

        {mode === "speech" && !loading && voices.length === 0 && (
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
            {idle ? (
              <div className="mx-auto w-full max-w-2xl py-8">
                <h1 className="mb-6 text-center font-heading text-3xl font-semibold tracking-tight">{heading}</h1>
                {composer}
                <Suggestions items={suggestionItems} onPick={pickSuggestion} />
                {mode !== "speech" ? <div className="mt-4"><SoundResult workspace={sound} /></div> : null}
              </div>
            ) : (
              <div className="mx-auto w-full max-w-3xl space-y-7 py-8">
                {mode === "speech" ? (
                  <>
              <div className="mx-auto w-full max-w-3xl space-y-7 py-8">
                <p className="ml-auto max-w-[80%] rounded-lg bg-muted px-3 py-2 text-sm leading-relaxed">{renderedText}</p>
                <div>
                  {job?.state === "failed" ? (
                    <p role="alert" className="mb-4 text-sm text-destructive">
                      {job.error ?? "The voice could not be generated."}
                    </p>
                  ) : null}

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
                        onPlayChange={(isPlaying) => {
                          setPlaying(isPlaying);
                          if (isPlaying) stopLive();
                        }}
                        onReady={(loaded) => setDuration(loaded || duration)}
                        onEnded={() => setPlaying(false)}
                      />
                      <code className="shrink-0 text-[11px] text-muted-foreground">
                        {formatTimecode(duration || job?.duration_seconds || 0)}
                      </code>
                    </div>
                  ) : isRunning ? (
                    <RenderProgress
                      progress={job?.progress ?? 0}
                      eta={job?.eta}
                      onCancel={() => void cancel()}
                      cancelDisabled={!job}
                    />
                  ) : null}

                  {audioUrl ? (
                    <div className="mt-3 flex items-center gap-4">
                      <button
                        type="button"
                        onClick={startExport}
                        className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
                      >
                        <Download className="size-3.5" />
                        Export
                      </button>
                    </div>
                  ) : null}
                </div>
              </div>
                  </>
                ) : (
                  <SoundResult workspace={sound} />
                )}
              </div>
            )}
          </div>
          {idle ? null : (
            <div className="shrink-0 px-4 pb-4 sm:px-6 sm:pb-5">
              <div className="mx-auto w-full max-w-3xl">{composer}</div>
            </div>
          )}
        </section>

        </div>
        <aside
          aria-label={mode === "speech" ? "Voice controls" : "Sound controls"}
          className="w-[440px] shrink-0 overflow-y-auto border-l border-border/70 p-4"
        >
          <h2 className="mb-4 text-sm font-semibold">{mode === "speech" ? "Voice controls" : "Sound controls"}</h2>
          {mode === "speech" ? (
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
            ) : (
            <SoundSettings workspace={sound} />
          )}
        </aside>
      </div>
    </>
  );
}