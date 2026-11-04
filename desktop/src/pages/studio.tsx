import { useEffect, useMemo, useRef, useState } from "react";
import {
  AudioLines,
  Download,
  Gauge,
  Loader2,
  LockKeyhole,
  Pause,
  Play,
  SlidersHorizontal,
  Sparkles,
  Square,
  Volume2,
  Wand2,
  WifiOff,
} from "lucide-react";
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
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Waveform } from "@/components/waveform";
import { api } from "@/lib/api";
import { extractAudioPeaks } from "@/lib/audio";
import { estimateWords, mockEngines, mockVoices } from "@/lib/mock";
import type {
  EngineInfo,
  JobStatus,
  SynthesisParams,
  VoiceProfile,
} from "@/lib/types";

interface StudioPageProps {
  online: boolean | null;
}

const DEFAULT_TEXT =
  "Welcome to VoiceClone Studio. This is a production-grade local zero-shot voice cloning application. Everything is processed securely on your computer without sending any data to the cloud.";

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "00:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function SliderField({
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
    <div className="space-y-1.5">
      {label ? (
        <div>
          <div className="flex items-center justify-between">
            <Label className="text-xs font-medium text-foreground">
              {label}
            </Label>
            <span className="font-mono text-xs text-muted-foreground">
              {digits === 0 ? Math.round(value) : value.toFixed(digits)}
              {suffix ? ` ${suffix}`.trimStart() : ""}
            </span>
          </div>
          {description ? (
            <p className="mt-0.5 text-[11px] leading-normal text-muted-foreground">
              {description}
            </p>
          ) : null}
        </div>
      ) : null}
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

export function StudioPage({ online }: StudioPageProps) {
  const [voices, setVoices] = useState<VoiceProfile[]>([]);
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [voiceId, setVoiceId] = useState<number | null>(null);
  const [engineName, setEngineName] = useState("Chatterbox TTS");
  const [text, setText] = useState(DEFAULT_TEXT);
  const [params, setParams] = useState<SynthesisParams>(mockEngines[0].default_params);
  const [randomSeed, setRandomSeed] = useState(true);
  const [sentencePause, setSentencePause] = useState(250);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioPeaks, setAudioPeaks] = useState<number[] | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [volume, setVolume] = useState(100);
  const [demoProgress, setDemoProgress] = useState(0);
  const [demoPlaying, setDemoPlaying] = useState(false);

  const audioRef = useRef<HTMLAudioElement>(null);
  const demoInterval = useRef<number | null>(null);

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
        setLoading(false);
      } catch {
        if (!cancelled) {
          setVoices(mockVoices);
          setEngines(mockEngines);
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [online]);

  useEffect(() => {
    if (voices.length && !voices.some((voice) => voice.id === voiceId)) {
      setVoiceId(voices[0].id);
    }
  }, [voices, voiceId]);

  useEffect(() => {
    if (!engines.length) return;
    const current = engines.find((engine) => engine.name === engineName);
    if (!current?.is_available) {
      const preferred = engines.find((engine) => engine.is_available) ?? engines[0];
      if (preferred.name !== engineName) {
        setEngineName(preferred.name);
      }
    }
  }, [engines, engineName]);

  useEffect(() => {
    if (!activeEngine) return;
    setParams((previous) => ({
      ...activeEngine.default_params,
      language: activeEngine.supported_languages.includes(previous.language)
        ? previous.language
        : activeEngine.supported_languages[0] ?? "en",
      enable_watermark: previous.enable_watermark,
    }));
  }, [activeEngine]);

  useEffect(() => {
    if (!job || !isRunning) return;
    const jobId = job.id;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.getJob(jobId);
        setJob(next);
        if (next.state === "done") {
          setAudioUrl(next.audio_url ? api.audioUrl(next.audio_url) : null);
          toast.success("Synthesis complete");
        } else if (next.state === "failed") {
          toast.error(next.error ?? "Synthesis failed");
        }
      } catch {
        /* transient poll failure: keep the last known state */
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job?.id, job?.state, isRunning]);

  useEffect(() => {
    if (!audioUrl) {
      setAudioPeaks(null);
      return;
    }
    setCurrentTime(0);
    setDuration(0);
    setPlaying(false);
    let cancelled = false;
    extractAudioPeaks(audioUrl)
      .then((extracted) => {
        if (!cancelled && extracted.length > 0) {
          setAudioPeaks(extracted);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [audioUrl]);

  useEffect(() => {
    const element = audioRef.current;
    if (element) element.volume = volume / 100;
  }, [volume, audioUrl]);

  useEffect(() => {
    if (!demoPlaying) return;
    const timer = window.setInterval(() => {
      setDemoProgress((progress) => Math.min(1, progress + 0.012));
    }, 60);
    return () => window.clearInterval(timer);
  }, [demoPlaying]);

  useEffect(() => {
    if (demoProgress >= 1) setDemoPlaying(false);
  }, [demoProgress]);

  useEffect(
    () => () => {
      if (demoInterval.current) window.clearInterval(demoInterval.current);
    },
    [],
  );

  const words = estimateWords(text);
  const characters = text.trim().length;
  const estimatedSeconds = words
    ? Math.max(0.5, (words / 150) * 60 / Math.max(0.1, params.speed))
    : 0;

  const progress = audioUrl && duration > 0
    ? Math.min(1, currentTime / duration)
    : demoProgress;

  const peaks =
    audioPeaks?.length
      ? audioPeaks
      : job?.peaks?.length
        ? job.peaks
        : null;

  const update = (patch: Partial<SynthesisParams>) =>
    setParams((previous) => ({ ...previous, ...patch }));

  const startDemo = () => {
    if (demoInterval.current) window.clearInterval(demoInterval.current);
    setAudioUrl(null);
    setDemoProgress(0);
    setPlaying(false);
    setDemoPlaying(false);
    const seed = randomSeed ? Math.floor(Math.random() * 999999) : params.seed;
    setJob({
      id: "demo",
      state: "running",
      progress: 0,
      current_chunk: 0,
      total_chunks: 4,
      eta: "6s",
      message: "Preparing demo inference",
      seed,
      peaks: null,
    });
    let step = 0;
    demoInterval.current = window.setInterval(() => {
      step += 4;
      const chunk = Math.min(4, Math.floor(step / 25) + 1);
      setJob((previous) =>
        previous
          ? {
              ...previous,
              progress: Math.min(100, step),
              current_chunk: chunk,
              message:
                step >= 100
                  ? "Inference complete (demo)"
                  : `Rendering chunk ${chunk} of 4`,
              state: step >= 100 ? "done" : "running",
              peaks: null,
              duration_seconds: step >= 100 ? 5.4 : previous.duration_seconds,
            }
          : previous,
      );
      if (step >= 100) {
        if (demoInterval.current) window.clearInterval(demoInterval.current);
        demoInterval.current = null;
        setDemoProgress(0);
        toast.success("Demo inference complete — connect Python engine for real audio");
      }
    }, 140);
  };

  /**
   * Starts a render on the backend.
   *
   * The backend renders the whole script in one background job and reports
   * progress through the job status endpoint; the UI polls it until the job
   * is done and then plays the rendered file.
   */
  const synthesize = async () => {
    if (isRunning) return;
    if (!voiceId) {
      toast.error("Create or select a voice profile first");
      return;
    }
    if (!text.trim()) {
      toast.error("Enter some text to synthesize");
      return;
    }
    if (!online) {
      startDemo();
      return;
    }
    const selected = engines.find((engine) => engine.name === engineName);
    if (!selected?.is_available) {
      toast.error("This engine isn't installed", {
        description: `"${engineName}" weights aren't present. Pick an installed engine or download it from Models.`,
      });
      return;
    }

    setStarting(true);
    setAudioUrl(null);
    setDemoProgress(0);
    setAudioPeaks(null);
    setCurrentTime(0);
    setDuration(0);
    setPlaying(false);

    try {
      const created = await api.synthesize({
        voice_id: voiceId,
        engine_name: engineName,
        text: text.trim(),
        params: {
          ...params,
          seed: randomSeed ? -1 : params.seed,
        },
        sentence_pause_ms: sentencePause,
      });
      setJob(created);
      setStarting(false);
      toast.message("Synthesis started", {
        description: `${activeEngine?.name ?? engineName} • ${created.total_chunks || 1} chunk(s)`,
      });
    } catch (error) {
      toast.error("Could not start synthesis", {
        description: error instanceof Error ? error.message : String(error),
      });
      setStarting(false);
      setJob((previous) =>
        previous
          ? {
              ...previous,
              state: "failed" as const,
              error: error instanceof Error ? error.message : String(error),
              message: "Synthesis failed",
            }
          : previous,
      );
    }
  };

  const cancel = async () => {
    if (!job || !isRunning) return;
    if (!online || job.id === "demo") {
      if (demoInterval.current) window.clearInterval(demoInterval.current);
      demoInterval.current = null;
      setJob((previous) =>
        previous ? { ...previous, state: "cancelled", message: "Cancelled" } : previous,
      );
      return;
    }
    try {
      setJob(await api.cancelJob(job.id));
      toast.message("Cancelling synthesis");
    } catch (error) {
      toast.error("Could not cancel", {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const togglePlayback = async () => {
    const element = audioRef.current;
    if (!audioUrl || !element) {
      if (job?.state === "done") {
        setDemoPlaying((value) => !value);
      }
      return;
    }
    try {
      if (element.paused) await element.play();
      else element.pause();
    } catch {
      toast.error("Playback failed");
    }
  };

  const stopPlayback = () => {
    const element = audioRef.current;
    if (element) {
      element.pause();
      element.currentTime = 0;
    }
    setCurrentTime(0);
    setDemoPlaying(false);
    setDemoProgress(0);
    setPlaying(false);
  };

  const seek = (ratio: number) => {
    const element = audioRef.current;
    if (audioUrl && element && Number.isFinite(element.duration)) {
      element.currentTime = ratio * element.duration;
      setCurrentTime(element.currentTime);
      return;
    }
    setDemoProgress(ratio);
  };

  const exportAudio = async () => {
    if (!audioUrl) {
      toast.error("No rendered audio to export", {
        description: "Connect the Python engine and synthesize a real clip first.",
      });
      return;
    }
    try {
      const response = await fetch(audioUrl);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `voiceclone_${Date.now()}.wav`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      toast.success("Audio export started");
    } catch {
      toast.error("Export failed");
    }
  };

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        void synthesize();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  return (
    <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">TTS Studio</h1>
          <p className="text-sm text-muted-foreground">
            Zero-shot voice cloning inference pipeline. All processing runs locally.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {online === false && (
            <Badge variant="destructive" className="gap-1.5">
              <WifiOff className="size-3" />
              Offline Demo Mode
            </Badge>
          )}
          <Badge variant="outline" className="gap-1.5">
            <Gauge className="size-3 text-primary" />
            {activeEngine?.name ?? <Loader />}
          </Badge>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-5">
          <Card>
            <CardContent className="grid gap-4 pt-5 md:grid-cols-[1.4fr_1fr_0.7fr]">
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Reference Voice Profile</Label>
                <Select
                  value={voiceId === null ? null : String(voiceId)}
                  onValueChange={(value: string | null) =>
                    setVoiceId(value ? Number(value) : null)
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select a voice">
                      {(value) => {
                        if (loading) {
                          return (
                            <span className="flex items-center gap-2">
                              <Loader size="size-3.5" />
                            </span>
                          );
                        }
                        return (
                          voices.find((voice) => String(voice.id) === value)?.name ??
                          "Select a voice"
                        );
                      }}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {voices.map((voice) => (
                      <SelectItem key={voice.id} value={String(voice.id)}>
                        {voice.name}
                        <span className="text-muted-foreground">
                          {voice.language.toUpperCase()}
                        </span>
                      </SelectItem>
                    ))}
                    {!voices.length && (
                      <SelectItem value="none" disabled>
                        No voices found
                      </SelectItem>
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">TTS Backend</Label>
                <Select
                  value={engineName}
                  onValueChange={(value: string | null) => value && setEngineName(value)}
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
                          <span className="text-muted-foreground">· not installed</span>
                        ) : (
                          !engine.commercial_permitted && (
                            <span className="text-amber-500"> · non-commercial</span>
                          )
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">ISO Language Code</Label>
                <Select
                  value={params.language}
                  onValueChange={(value: string | null) =>
                    value && update({ language: value })
                  }
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
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <AudioLines className="size-4 text-primary" />
                Input Synthesis Text
              </CardTitle>
              <CardDescription>
                Type or paste text for inference. The render runs on the engine and the
                result is loaded into the output buffer when it is ready.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                placeholder="Type or paste synthesis input text"
                className="min-h-[190px] resize-y text-[15px] leading-relaxed"
              />
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <span>{characters} chars</span>
                <span>{words} words</span>
                <span>~{estimatedSeconds.toFixed(1)}s est. duration</span>
                <span className="ml-auto font-mono text-xs">
                  Ctrl+Return: Run Synthesis
                </span>
              </div>
            </CardContent>
          </Card>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              size="lg"
              className="min-w-48"
              onClick={() => void synthesize()}
              disabled={starting || isRunning}
            >
              {starting || isRunning ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Sparkles />
              )}
              {isRunning
                ? "Inference Running"
                : starting
                  ? "Initializing"
                  : "Run Synthesis"}
            </Button>
            <Button
              size="lg"
              variant="outline"
              onClick={() => void cancel()}
              disabled={!isRunning}
            >
              Cancel Inference
            </Button>
            <div className="ml-auto min-w-44 flex-1 sm:max-w-xs">
              <Progress value={isRunning ? job?.progress ?? 0 : job?.state === "done" ? 100 : 0} />
            </div>
          </div>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base">Output Waveform</CardTitle>
                  <CardDescription>
                    Run inference to generate output audio buffer.
                  </CardDescription>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  {isRunning && job?.eta ? <span>Est. Time: {job.eta}</span> : null}
                  {job?.message ? (
                    <span className="max-w-[280px] truncate">{job.message}</span>
                  ) : null}
                  <span className="font-mono">
                    {formatTime(currentTime)} / {formatTime(duration || job?.duration_seconds || 0)}
                  </span>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="relative">
                <Waveform peaks={peaks} progress={progress} onSeek={seek} />
                {!peaks?.length && (
                  <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                    <span className="rounded-md border border-border bg-card/90 px-2.5 py-1 text-xs text-muted-foreground">
                      {isRunning
                        ? "Rendering audio"
                        : job?.state === "done"
                          ? "No Output Buffer"
                          : "Output waveform appears here"}
                    </span>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  onClick={() => void togglePlayback()}
                  disabled={!audioUrl && job?.state !== "done"}
                >
                  {playing || (demoPlaying && !audioUrl) ? <Pause /> : <Play />}
                  {playing || (demoPlaying && !audioUrl) ? "Pause" : "Play"}
                </Button>
                <Button variant="outline" onClick={stopPlayback}>
                  <Square />
                  Stop
                </Button>

                <Separator orientation="vertical" className="mx-1 h-6" />

                <Volume2 className="size-4 text-muted-foreground" />
                <Slider
                  className="w-28"
                  value={[volume]}
                  min={0}
                  max={100}
                  step={1}
                  onValueChange={(next) =>
                    setVolume(typeof next === "number" ? next : (next[0] ?? 100))
                  }
                />

                <Button
                  variant="outline"
                  className="ml-auto"
                  onClick={() => void exportAudio()}
                  disabled={!audioUrl}
                >
                  <Download />
                  Export Waveform
                </Button>
              </div>

              <audio
                ref={audioRef}
                src={audioUrl ?? undefined}
                onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
                onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)}
                onPlay={() => setPlaying(true)}
                onPause={() => setPlaying(false)}
                onEnded={() => {
                  setPlaying(false);
                  setCurrentTime(0);
                }}
              />
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-col gap-5">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Wand2 className="size-4 text-primary" />
                Prosody & Timbre Parameters
              </CardTitle>
              <CardDescription>Configure prosody, timbre, and guidance scale.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <SliderField
                label="Exaggeration Scale"
                description="Controls prosodic variance and emotional intensity."
                value={params.exaggeration}
                min={0.2}
                max={2}
                step={0.05}
                suffix="x"
                onChange={(value) => update({ exaggeration: value })}
              />

              <SliderField
                label="CFG Weight (Guidance Scale)"
                description="Guidance scale for speaker similarity to reference."
                value={params.cfg_weight}
                min={1}
                max={7}
                step={0.1}
                onChange={(value) => update({ cfg_weight: value })}
              />

              <SliderField
                label="Sampling Temperature"
                description="Lower = deterministic output; higher = stochastic variety."
                value={params.temperature}
                min={0.1}
                max={1.5}
                step={0.05}
                onChange={(value) => update({ temperature: value })}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <SlidersHorizontal className="size-4 text-primary" />
                Delivery Parameters
              </CardTitle>
              <CardDescription>Inference speed, inter-sentence silence, and seed control.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <SliderField
                label="Speed Multiplier"
                description="Playback rate multiplier for output audio."
                value={params.speed}
                min={0.5}
                max={2}
                step={0.05}
                suffix="x"
                onChange={(value) => update({ speed: value })}
              />

              <SliderField
                label="Inter-Sentence Silence"
                description="Silence gap inserted between rendered chunks."
                value={sentencePause}
                min={0}
                max={1500}
                step={50}
                suffix="ms"
                digits={0}
                onChange={setSentencePause}
              />

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <Label className="text-xs font-medium text-foreground">Deterministic Seed</Label>
                    <p className="text-[11px] text-muted-foreground leading-tight">
                      Lock PRNG seed for reproducible inference runs.
                    </p>
                  </div>
                  <Switch checked={randomSeed} onCheckedChange={setRandomSeed} />
                </div>
                {!randomSeed && (
                  <SliderField
                    label="Random Seed Value"
                    description="PRNG seed for deterministic output."
                    value={params.seed}
                    min={0}
                    max={10000}
                    step={1}
                    digits={0}
                    onChange={(value) => update({ seed: value })}
                  />
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="border-primary/20 bg-primary/5">
            <CardContent className="flex items-start gap-3 pt-5">
              <LockKeyhole className="mt-0.5 size-4 shrink-0 text-primary" />
              <div className="text-xs">
                <p className="font-medium text-foreground">
                  Perth Acoustic Watermark {params.enable_watermark ? "enabled" : "disabled"}
                </p>
                <p className="mt-1 text-muted-foreground">
                  Embeds imperceptible spread-spectrum acoustic signature for origin verification.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
