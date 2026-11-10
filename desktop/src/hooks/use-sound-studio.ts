import { notifyDone } from "@/lib/notify";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import type { JobStatus, SoundEngineInfo, SoundKind, SoundParams } from "@/lib/types";

const MAX_POLL_FAILURES = 3;
const POLL_INTERVAL_MS = 1000;

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export interface SoundRequest {
  engineName: string;
  prompt: string;
  kind: SoundKind;
  params: SoundParams;
}

export function useSoundEngines(online: boolean, active = true) {
  const [engines, setEngines] = useState<SoundEngineInfo[]>([]);
  const [loading, setLoading] = useState(online);

  useEffect(() => {
    if (!online || !active) return;
    let cancelled = false;
    api
      .listSoundEngines()
      .then((next) => !cancelled && setEngines(next))
      .catch(() => !cancelled && setEngines([]))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [online, active]);

  return { engines, loading };
}

export function useSoundJob() {
  const [job, setJob] = useState<JobStatus | null>(null);
  const [starting, setStarting] = useState(false);

  const isRunning = job?.state === "queued" || job?.state === "running";
  const audioUrl = job?.state === "done" && job.audio_url ? api.audioUrl(job.audio_url) : null;

  const jobId = job?.id;

  useEffect(() => {
    if (!jobId || !isRunning) return;
    let failures = 0;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.getJob(jobId);
        failures = 0;
        setJob(next);
        if (next.state === "done") {
          const description = `${formatDuration(next.duration_seconds)} of audio generated.`;
          toast.success("Sound ready", { description });
          void notifyDone("Sound ready", description);
        } else if (next.state === "failed") {
          toast.error("Generation failed", { description: next.error ?? undefined });
          void notifyDone("Generation failed", next.error ?? "The sound could not be generated.");
        }
      } catch {
        failures += 1;
        if (failures >= MAX_POLL_FAILURES) {
          setJob((previous) =>
            previous?.id === jobId
              ? { ...previous, state: "failed", error: "Lost connection to the engine." }
              : previous,
          );
        }
      }
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [jobId, isRunning]);

  const generate = useCallback(
    async ({ engineName, prompt, kind, params }: SoundRequest) => {
      if (isRunning || starting) return;
      setStarting(true);
      try {
        setJob(
          await api.generateSound({
            engine_name: engineName,
            prompt: prompt.trim(),
            kind,
            params,
          }),
        );
      } catch (error) {
        toast.error("Could not start generation", { description: describeError(error) });
      } finally {
        setStarting(false);
      }
    },
    [isRunning, starting],
  );

  const cancel = useCallback(async () => {
    if (!job || !isRunning) return;
    try {
      setJob(await api.cancelJob(job.id));
    } catch (error) {
      toast.error("Could not cancel", { description: describeError(error) });
    }
  }, [isRunning, job]);

  return { job, starting, isRunning, audioUrl, generate, cancel };
}
