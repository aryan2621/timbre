import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useLiveAudio } from "@/hooks/use-studio";
import { api } from "@/lib/api";
import type { AgentProfile, AgentTurn, JobStatus, SynthesisParams } from "@/lib/types";

const POLL_INTERVAL_MS = 400;

export type AgentPhase = "idle" | "listening" | "thinking" | "speaking";

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function useAgentChat(agent: AgentProfile | null, engineName: string, params: SynthesisParams) {
  const [turns, setTurns] = useState<AgentTurn[]>([]);
  const [phase, setPhase] = useState<AgentPhase>("idle");
  const [job, setJob] = useState<JobStatus | null>(null);
  const live = useLiveAudio(job);
  const epoch = useRef(0);
  const jobId = useRef<string | null>(null);

  const stopSpeaking = useCallback(() => {
    epoch.current += 1;
    live.stop();
    if (jobId.current) void api.cancelJob(jobId.current).catch(() => undefined);
    jobId.current = null;
  }, [live]);

  useEffect(() => stopSpeaking, [stopSpeaking]);

  const speak = useCallback(
    async (text: string, voiceId: number, mine: number) => {
      let current = await api.synthesize({
        voice_id: voiceId,
        engine_name: engineName,
        text,
        params,
        sentence_pause_ms: 0,
      });
      jobId.current = current.id;
      setJob(current);
      setPhase("speaking");
      while (current.state === "queued" || current.state === "running") {
        await new Promise((resolve) => window.setTimeout(resolve, POLL_INTERVAL_MS));
        if (mine !== epoch.current) return;
        current = await api.getJob(current.id);
        setJob(current);
      }
      if (current.state === "failed") throw new Error(current.error ?? "The voice could not be rendered.");
      jobId.current = null;
      setPhase("idle");
    },
    [engineName, params],
  );

  const say = useCallback(
    async (userText: string) => {
      if (!agent) return;
      stopSpeaking();
      const mine = epoch.current;
      const history: AgentTurn[] = [...turns, { role: "user", content: userText }];
      setTurns(history);
      setPhase("thinking");
      try {
        const answer = await api.agentReply(agent.id, history);
        setTurns([...history, { role: "assistant", content: answer }]);
        if (agent.voice_id === null) setPhase("idle");
        else await speak(answer, agent.voice_id, mine);
      } catch (error) {
        toast.error("The agent could not answer", { description: describeError(error) });
        setPhase("idle");
      }
    },
    [agent, speak, stopSpeaking, turns],
  );

  const hear = useCallback(
    async (wav: Blob) => {
      setPhase("thinking");
      try {
        const text = await api.transcribe(wav);
        if (!text) {
          toast.message("Nothing heard", { description: "Try again, a little closer to the microphone." });
          setPhase("idle");
          return;
        }
        await say(text);
      } catch (error) {
        toast.error("Could not understand the audio", { description: describeError(error) });
        setPhase("idle");
      }
    },
    [say],
  );

  const prepare = useCallback(() => {
    stopSpeaking();
    live.prime();
  }, [live, stopSpeaking]);

  return { turns, phase, setPhase, hear, prepare };
}
