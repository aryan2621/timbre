/**
 * Studio page hooks.
 *
 * The Studio screen is the most stateful page in the app. Splitting its
 * behaviour into focused hooks keeps each piece independently testable and
 * leaves `pages/studio.tsx` responsible for layout and rendering only.
 *
 * Each hook owns one concern:
 *   - useLibrary          fetching the voice + engine catalogue
 *   - useEngineSelection  which engine is active and what its parameters are
 *   - useSynthesisJob     the background render job lifecycle
 *   - usePlayback         transport controls for the rendered audio
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import { demoList, mockEngines, mockVoices } from "@/lib/mock";
import type {
  EngineInfo,
  JobStatus,
  SynthesisParams,
  VoiceProfile,
} from "@/lib/types";
import type { WaveformPlayerHandle } from "@/components/waveform/waveform-player";

/* -------------------------------------------------------------------------- */
/* Library                                                                     */
/* -------------------------------------------------------------------------- */

export interface Library {
  voices: VoiceProfile[];
  engines: EngineInfo[];
  loading: boolean;
  voice: VoiceProfile | null;
  setVoice: (voice: VoiceProfile | null) => void;
}

/**
 * Loads the voice profiles and the engine catalogue. The bundled demo data is
 * only used in a plain browser session: in the desktop app, fake voices would
 * fail every render with "Voice not found", so an unreachable engine shows an
 * empty library instead.
 */
export function useLibrary(online: boolean): Library {
  const [voices, setVoices] = useState<VoiceProfile[]>([]);
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [voice, setVoice] = useState<VoiceProfile | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const fallback = () => {
        setVoices(demoList(mockVoices));
        setEngines(demoList(mockEngines));
      };
      if (!online) {
        if (!cancelled) {
          fallback();
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
        if (!cancelled) fallback();
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [online]);

  useEffect(() => {
    if (!voices.length) return;
    setVoice((previous) => {
      if (previous && voices.some((item) => item.id === previous.id)) return previous;
      return voices[0] ?? null;
    });
  }, [voices]);

  return { voices, engines, loading, voice, setVoice };
}

/* -------------------------------------------------------------------------- */
/* Engine selection                                                            */
/* -------------------------------------------------------------------------- */

export interface EngineSelection {
  engineName: string;
  setEngineName: (name: string) => void;
  activeEngine: EngineInfo | undefined;
  params: SynthesisParams;
  update: (
    patch: Partial<SynthesisParams> | ((previous: SynthesisParams) => SynthesisParams),
  ) => void;
}

/**
 * Tracks the active engine and its synthesis parameters.
 *
 * The active engine is forced to one that is actually installed, and its
 * defaults are re-applied whenever the engine changes while preserving the
 * user's language and watermark preference.
 */
export function useEngineSelection(engines: EngineInfo[]): EngineSelection {
  const [engineName, setEngineName] = useState("Chatterbox TTS");
  const [params, setParams] = useState<SynthesisParams>(mockEngines[0].default_params);

  const activeEngine = useMemo(
    () => engines.find((engine) => engine.name === engineName) ?? engines[0],
    [engineName, engines],
  );

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

  const update = useCallback(
    (
      patch:
        | Partial<SynthesisParams>
        | ((previous: SynthesisParams) => SynthesisParams),
    ) =>
      setParams((previous) =>
        typeof patch === "function" ? patch(previous) : { ...previous, ...patch },
      ),
    [],
  );

  return { engineName, setEngineName, activeEngine, params, update };
}

/* -------------------------------------------------------------------------- */
/* Synthesis job                                                               */
/* -------------------------------------------------------------------------- */

/* -------------------------------------------------------------------------- */
/* Play while rendering                                                        */
/* -------------------------------------------------------------------------- */

/**
 * Plays each finished chunk of a running render back to back, so sound starts
 * after the first sentence instead of after the whole text. The server hands
 * out chunks that already include the pauses and fades, so they join
 * seamlessly. `prime` must run inside the click handler (audio autoplay rules).
 */
function useLiveAudio(job: JobStatus | null) {
  const contextRef = useRef<AudioContext | null>(null);
  const sourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const nextTimeRef = useRef(0);
  const fetchedRef = useRef(0);
  const jobIdRef = useRef<string | null>(null);
  const chainRef = useRef<Promise<void>>(Promise.resolve());
  const epochRef = useRef(0); // bumped on stop so late fetches are dropped

  const stop = useCallback(() => {
    epochRef.current += 1;
    for (const source of sourcesRef.current) {
      try {
        source.stop();
      } catch {
        /* already finished */
      }
    }
    sourcesRef.current = [];
    nextTimeRef.current = 0;
    fetchedRef.current = 0;
    jobIdRef.current = null;
    chainRef.current = Promise.resolve();
  }, []);

  const prime = useCallback(() => {
    stop();
    try {
      contextRef.current ??= new AudioContext();
      void contextRef.current.resume();
    } catch {
      contextRef.current = null; // no Web Audio: the final file still plays
    }
  }, [stop]);

  const ready = job?.chunks_ready ?? 0;
  useEffect(() => {
    const context = contextRef.current;
    if (!job || !context || ready <= 0) return;
    if (jobIdRef.current !== job.id) {
      jobIdRef.current = job.id;
      fetchedRef.current = 0;
    }
    const from = fetchedRef.current;
    if (ready <= from) return;
    fetchedRef.current = ready;

    const epoch = epochRef.current;
    const jobId = job.id;
    for (let index = from; index < ready; index += 1) {
      chainRef.current = chainRef.current
        .then(async () => {
          if (epoch !== epochRef.current) return;
          const data = await api.getJobChunk(jobId, index);
          if (epoch !== epochRef.current) return;
          const buffer = await context.decodeAudioData(data);
          if (epoch !== epochRef.current) return;
          const source = context.createBufferSource();
          source.buffer = buffer;
          source.connect(context.destination);
          const startAt = Math.max(context.currentTime + 0.05, nextTimeRef.current);
          source.start(startAt);
          nextTimeRef.current = startAt + buffer.duration;
          sourcesRef.current.push(source);
        })
        .catch(() => undefined); // a missed chunk only costs live audio, not the final file
    }
  }, [job, ready]);

  useEffect(
    () => () => {
      stop();
      void contextRef.current?.close();
      contextRef.current = null;
    },
    [stop],
  );

  return { prime, stop };
}

/** Consecutive failed status polls before a render is declared lost. */
const MAX_POLL_FAILURES = 3;

export interface SynthesisJobOptions {
  voice: VoiceProfile | null;
  engines: EngineInfo[];
  engineName: string;
  text: string;
  params: SynthesisParams;
  randomSeed: boolean;
  sentencePause: number;
  online: boolean;
  /** Called when a new render is queued, so the transport can reset. */
  onRenderQueued?: () => void;
}

export interface SynthesisJob {
  job: JobStatus | null;
  starting: boolean;
  audioUrl: string | null;
  duration: number;
  setDuration: (value: number) => void;
  elapsed: number;
  isRunning: boolean;
  synthesize: () => Promise<void>;
  cancel: () => Promise<void>;
}

/**
 * Owns the lifecycle of a single background render: starting it, polling its
 * status until it settles, and cancelling it on request.
 */
export function useSynthesisJob(options: SynthesisJobOptions): SynthesisJob {
  const {
    voice,
    engines,
    engineName,
    text,
    params,
    randomSeed,
    sentencePause,
    online,
    onRenderQueued,
  } = options;

  const [job, setJob] = useState<JobStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [duration, setDuration] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  const isRunning = job?.state === "queued" || job?.state === "running";
  const live = useLiveAudio(job);

  useEffect(() => {
    if (job?.state === "failed" || job?.state === "cancelled") live.stop();
  }, [job?.state, live]);

  useEffect(() => {
    if (!job || !isRunning) return;
    const jobId = job.id;
    let failures = 0;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.getJob(jobId);
        failures = 0;
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
        // A restarted engine forgets its jobs and a dead one never answers:
        // give up after a few misses instead of spinning forever.
        failures += 1;
        if (failures >= MAX_POLL_FAILURES) {
          setJob((previous) =>
            previous && previous.id === jobId
              ? {
                  ...previous,
                  state: "failed" as const,
                  error: "Lost connection to the engine.",
                  message: "Render failed",
                }
              : previous,
          );
          toast.error("Render failed", { description: "Lost connection to the engine." });
        }
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
      toast.error(`${engineName} isn't ready`, {
        description:
          "Its Python package is not installed in the engine's environment. Weights are downloaded from the Models screen, but the package comes first.",
      });
      return;
    }

    setStarting(true);
    setDuration(0);
    live.prime();
    onRenderQueued?.();

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
    live,
    online,
    onRenderQueued,
    params,
    randomSeed,
    sentencePause,
    text,
    voice,
  ]);

  const cancel = useCallback(async () => {
    if (!job || !isRunning) return;
    live.stop();
    try {
      setJob(await api.cancelJob(job.id));
      toast.message("Cancelling the render");
    } catch (error) {
      toast.error("Could not cancel", {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  }, [isRunning, job, live]);

  return {
    job,
    starting,
    audioUrl,
    duration,
    setDuration,
    elapsed,
    isRunning,
    synthesize,
    cancel,
  };
}

/* -------------------------------------------------------------------------- */
/* Playback                                                                    */
/* -------------------------------------------------------------------------- */

export interface Playback {
  currentTime: number;
  setCurrentTime: (value: number) => void;
  playing: boolean;
  setPlaying: (value: boolean) => void;
  volume: number;
  setVolume: (value: number) => void;
  muted: boolean;
  setMuted: (value: boolean) => void;
  togglePlayback: () => void;
  stopPlayback: () => void;
  reset: () => void;
}

/** Transport state for the rendered waveform. */
export function usePlayback(
  waveformRef: RefObject<WaveformPlayerHandle | null>,
): Playback {
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [volume, setVolume] = useState(100);
  const [muted, setMuted] = useState(false);

  const togglePlayback = useCallback(() => {
    waveformRef.current?.playPause();
  }, [waveformRef]);

  const stopPlayback = useCallback(() => {
    waveformRef.current?.stop();
    setCurrentTime(0);
    setPlaying(false);
  }, [waveformRef]);

  const reset = useCallback(() => {
    setCurrentTime(0);
    setPlaying(false);
  }, []);

  return {
    currentTime,
    setCurrentTime,
    playing,
    setPlaying,
    volume,
    setVolume,
    muted,
    setMuted,
    togglePlayback,
    stopPlayback,
    reset,
  };
}