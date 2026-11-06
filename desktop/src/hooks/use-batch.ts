/**
 * Batch page hooks.
 *
 * The Batch screen renders one audio file per line of an imported script.
 * Its behaviour is split into three focused hooks so the page component is
 * left with layout and rendering only:
 *
 *   - useBatchLibrary   the voice + engine catalogue
 *   - useScriptImport   parsing and importing the script file
 *   - useBatchJob       the background queue lifecycle
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import type { RefObject } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { parseScript, type ParsedLine } from "@/lib/batch-script";
import {
  IS_TAURI,
  pickFolder,
  pickScriptFile,
  readTextFile,
} from "@/lib/desktop";
import { mockEngines, mockVoices } from "@/lib/mock";
import type { BatchJob, EngineInfo, VoiceProfile } from "@/lib/types";

/* -------------------------------------------------------------------------- */
/* Library                                                                     */
/* -------------------------------------------------------------------------- */

export interface BatchLibrary {
  voices: VoiceProfile[];
  engines: EngineInfo[];
  voice: VoiceProfile | null;
  setVoice: (voice: VoiceProfile | null) => void;
  engineName: string;
  setEngineName: (name: string) => void;
  activeEngine: EngineInfo | undefined;
  loading: boolean;
}

/** Loads the voice profiles and engine catalogue used by the batch runner. */
export function useBatchLibrary(online: boolean): BatchLibrary {
  const [voices, setVoices] = useState<VoiceProfile[]>([]);
  const [engines, setEngines] = useState<EngineInfo[]>(mockEngines);
  const [voice, setVoice] = useState<VoiceProfile | null>(null);
  const [engineName, setEngineName] = useState("Chatterbox TTS");
  const [loading, setLoading] = useState(true);

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
        setEngines(nextEngines.length > 0 ? nextEngines : mockEngines);
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

  useEffect(() => {
    if (!engines.length) return;
    const current = engines.find((engine) => engine.name === engineName);
    if (!current?.is_available) {
      const preferred = engines.find((engine) => engine.is_available) ?? engines[0];
      if (preferred && preferred.name !== engineName) setEngineName(preferred.name);
    }
  }, [engines, engineName]);

  const activeEngine = useMemo(
    () => engines.find((engine) => engine.name === engineName) ?? engines[0],
    [engineName, engines],
  );

  return {
    voices,
    engines,
    voice,
    setVoice,
    engineName,
    setEngineName,
    activeEngine,
    loading,
  };
}

/* -------------------------------------------------------------------------- */
/* Script import                                                               */
/* -------------------------------------------------------------------------- */

export interface ScriptImport {
  lines: ParsedLine[];
  fileName: string;
  outputDir: string;
  setOutputDir: (dir: string) => void;
  applyScript: (name: string, content: string) => void;
  importScript: () => Promise<void>;
  onBrowserFile: (file: File | undefined) => Promise<void>;
  chooseFolder: () => Promise<void>;
  clearScript: () => void;
}

/**
 * Handles reading, parsing and importing the script that drives the batch.
 */
export function useScriptImport(
  fileInputRef: RefObject<HTMLInputElement | null>,
  onScriptLoaded: () => void,
): ScriptImport {
  const [lines, setLines] = useState<ParsedLine[]>([]);
  const [fileName, setFileName] = useState("");
  const [outputDir, setOutputDir] = useState("");

  const applyScript = useCallback(
    (name: string, content: string) => {
      const parsed = parseScript(name, content);
      setLines(parsed);
      setFileName(name);
      onScriptLoaded();
      toast.success(
        `Loaded ${parsed.length} line${parsed.length === 1 ? "" : "s"}`,
        { description: name },
      );
    },
    [onScriptLoaded],
  );

  const importScript = useCallback(async () => {
    if (IS_TAURI) {
      const path = await pickScriptFile();
      if (!path) return;
      const content = await readTextFile(path);
      if (content === null) {
        toast.error("Could not read that file");
        return;
      }
      applyScript(path.split("/").pop() ?? path, content);
      return;
    }
    fileInputRef.current?.click();
  }, [applyScript, fileInputRef]);

  const onBrowserFile = useCallback(
    async (file: File | undefined) => {
      if (!file) return;
      applyScript(file.name, await file.text());
    },
    [applyScript],
  );

  const chooseFolder = useCallback(async () => {
    const folder = await pickFolder("Batch output folder");
    if (folder) {
      setOutputDir(folder);
      toast.message("Output folder set", { description: folder });
    }
  }, []);

  const clearScript = useCallback(() => {
    setLines([]);
    setFileName("");
  }, []);

  return {
    lines,
    fileName,
    outputDir,
    setOutputDir,
    applyScript,
    importScript,
    onBrowserFile,
    chooseFolder,
    clearScript,
  };
}

/* -------------------------------------------------------------------------- */
/* Batch job                                                                   */
/* -------------------------------------------------------------------------- */

export interface BatchJobState {
  job: BatchJob | null;
  starting: boolean;
  running: boolean;
  /** Submits the given script lines (and optional output folder) to the server. */
  start: (lines: ParsedLine[], outputDir?: string) => Promise<void>;
  cancel: () => Promise<void>;
  /** Drops the current job, e.g. when a different script is imported. */
  reset: () => void;
}

export interface BatchJobOptions {
  voice: VoiceProfile | null;
  engineName: string;
  online: boolean;
}

/**
 * Owns the background batch queue: submitting it, polling until it settles,
 * and cancelling it on request.
 */
export function useBatchJob(options: BatchJobOptions): BatchJobState {
  const { voice, engineName, online } = options;

  const [job, setJob] = useState<BatchJob | null>(null);
  const [starting, setStarting] = useState(false);

  const running = job?.state === "queued" || job?.state === "running";

  const reset = useCallback(() => setJob(null), []);

  const start = useCallback(
    async (lines: ParsedLine[], outputDir = "") => {
      if (!lines.length) {
        toast.error("Import a script first");
        return;
      }
      if (!voice) {
        toast.error("Choose a voice profile");
        return;
      }
      if (!online) {
        toast.error("Batch rendering needs the Python engine");
        return;
      }

      setStarting(true);
      try {
        const created = await api.startBatch({
          voice_id: voice.id,
          engine_name: engineName,
          items: lines.map((line) => ({
            text: line.text,
            filename: line.filename,
          })),
          params: {
            temperature: 0.7,
            cfg_weight: 2.5,
            exaggeration: 1,
            speed: 1,
            seed: -1,
            language: voice.language,
            enable_watermark: true,
          },
          sentence_pause_ms: 250,
          output_dir: outputDir || null,
        });
        setJob(created);
        toast.message("Batch queued", {
          description: `${created.total} lines will render one after another.`,
        });
      } catch (error) {
        toast.error("Could not start the batch", {
          description: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setStarting(false);
      }
    },
    [engineName, online, voice],
  );

  const cancel = useCallback(async () => {
    if (!job || !running) return;
    try {
      setJob(await api.cancelBatch(job.id));
      toast.message("Cancelling the batch");
    } catch (error) {
      toast.error("Could not cancel", {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  }, [job, running]);

  // Poll the server while the queue is alive.
  useEffect(() => {
    if (!job || !running) return;
    const jobId = job.id;
    let cancelled = false;

    const timer = window.setInterval(async () => {
      try {
        const next = await api.getBatch(jobId);
        if (cancelled) return;
        setJob(next);
        if (next.state === "done") {
          toast.success("Batch complete", {
            description: `${next.completed} of ${next.total} lines rendered.`,
          });
        } else if (next.state === "failed") {
          toast.error("Batch failed", { description: next.error ?? undefined });
        }
      } catch {
        /* transient poll failure: keep the last known state */
      }
    }, 1000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [job?.id, job?.state, running]);

  return { job, starting, running, start, cancel, reset };
}