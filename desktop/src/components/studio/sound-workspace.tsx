import { useRef, useState } from "react";
import { Download, Pause, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { RenderProgress } from "@/components/studio/render-progress";
import { ParamControl } from "@/components/studio/param-control";
import { EngineControls } from "@/components/studio/engine-controls";
import {
  WaveformPlayer,
  type WaveformPlayerHandle,
} from "@/components/waveform/waveform-player";
import { useSoundEngines, useSoundJob } from "@/hooks/use-sound-studio";
import { useApp } from "@/lib/app-context";
import { useActiveModels } from "@/lib/active-models";
import { exportAudio } from "@/lib/export-audio";
import { formatTimecode } from "@/lib/format";
import type { SoundKind, SoundParams } from "@/lib/types";

export const PLACEHOLDERS: Record<SoundKind, string> = {
  sfx: "Heavy rain on a tin roof with distant thunder",
  music: "Calm lo-fi hip hop beat, 80 BPM, warm piano",
};

export const EXAMPLES: Record<SoundKind, string[]> = {
  sfx: [
    "Heavy rain on a tin roof with distant thunder",
    "Footsteps on gravel, slow and steady",
    "A wooden door creaking open in an empty house",
  ],
  music: [
    "Calm lo-fi hip hop beat, 80 BPM, warm piano",
    "Upbeat acoustic guitar, bright and sunny, 110 BPM",
    "Slow cinematic strings building to a swell",
  ],
};

const MAX_SEED = 99_999_999;

export function useSoundWorkspace(kind: SoundKind, online: boolean) {
  const { engines, loading } = useSoundEngines(online);

  const [engineName, setEngineName] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [edited, setEdited] = useState<{ engine: string; params: SoundParams } | null>(null);
  const [randomSeed, setRandomSeed] = useState(true);
  const [playing, setPlaying] = useState(false);
  const waveformRef = useRef<WaveformPlayerHandle>(null);
  const { job, starting, isRunning, audioUrl, generate, cancel } = useSoundJob();

  const candidates = engines.filter((item) => item.kinds.includes(kind));
  const chosenModel = useActiveModels()[kind === "music" ? "music" : "sound"];
  const engine =
    candidates.find((item) => item.name === engineName) ??
    candidates.find((item) => item.model_id === chosenModel && item.is_available) ??
    candidates.find((item) => item.is_available) ??
    candidates[0];
  const params = engine
    ? edited?.engine === engine.name
      ? edited.params
      : engine.default_params
    : null;

  const patch = (change: Partial<SoundParams>) =>
    params && engine && setEdited({ engine: engine.name, params: { ...params, ...change } });

  const canGenerate =
    !!engine?.is_available && !!params && prompt.trim().length > 0 && !isRunning && !starting;

  const submit = () => {
    if (!canGenerate || !engine || !params) return;
    setPlaying(false);
    void generate({
      engineName: engine.name,
      prompt,
      kind,
      params: { ...params, seed: randomSeed ? -1 : params.seed },
    });
  };

  const blocker = !online
    ? "The engine is not running."
    : !engine && !loading
      ? "No sound engine is installed."
      : engine?.unavailable_reason
        ? engine.unavailable_reason
        : engine && !engine.is_available
          ? `${engine.name} is not downloaded yet.`
          : null;

  return { engines, loading, online, kind, engine, candidates, params, patch, canGenerate, submit, blocker, prompt, setPrompt, randomSeed, setRandomSeed, playing, setPlaying, waveformRef, job, starting, isRunning, audioUrl, cancel, setEngineName };
}

export type SoundWorkspace = ReturnType<typeof useSoundWorkspace>;

export function SoundResult({ workspace }: { workspace: SoundWorkspace }) {
  const { navigate } = useApp();
  const { online, engine, blocker, playing, setPlaying, waveformRef, job, starting, isRunning, audioUrl, cancel, kind } = workspace;
  return (
    <div className="space-y-4">
      {blocker ? (
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <span>{blocker}</span>
          {online && engine && !engine.unavailable_reason ? (
            <Button size="sm" variant="outline" onClick={() => navigate("models")}>
              Open Models
            </Button>
          ) : null}
        </div>
      ) : null}

        <section className="flex flex-col gap-4">
          {isRunning || starting ? (
            <RenderProgress progress={job?.progress ?? 0} eta={job?.eta} onCancel={() => void cancel()} />
          ) : null}

          {job?.state === "failed" ? (
            <p role="alert" className="text-sm text-destructive">
              {job.error ?? "Generation failed."}
            </p>
          ) : null}

          {audioUrl ? (
            <>
              <div className="flex items-center gap-3 rounded-md border border-border bg-surface-inset/70 px-3 py-2.5">
                <Button
                  size="icon"
                  className="size-9 shrink-0 rounded-full"
                  aria-label={playing ? "Pause audio" : "Play audio"}
                  onClick={() => waveformRef.current?.playPause()}
                >
                  {playing ? <Pause /> : <Play />}
                </Button>
                <WaveformPlayer
                  ref={waveformRef}
                  url={audioUrl}
                  peaks={job?.peaks ?? null}
                  duration={job?.duration_seconds ?? 0}
                  height={32}
                  className="min-w-0 flex-1 border-0 bg-transparent"
                  onPlayChange={setPlaying}
                  onEnded={() => setPlaying(false)}
                />
                <code className="shrink-0 text-[11px] text-muted-foreground">
                  {formatTimecode(job?.duration_seconds ?? 0)}
                </code>
              </div>
              <button
                type="button"
                onClick={() => void exportAudio(audioUrl, kind)}
                className="inline-flex items-center gap-1.5 self-start text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                <Download className="size-3.5" />
                Export
              </button>
            </>
          ) : null}
        </section>
    </div>
  );
}

export function SoundSettings({ workspace }: { workspace: SoundWorkspace }) {
  const { engine, candidates, params, patch, randomSeed, setRandomSeed, setEngineName } = workspace;
  return (
    <div className="space-y-4 overflow-y-auto px-4 pb-4">
      {engine?.supports_lyrics && params ? (
        <Field className="gap-2">
          <FieldLabel htmlFor="sound-lyrics">Lyrics (optional)</FieldLabel>
          <Textarea
            id="sound-lyrics"
            value={params.lyrics}
            rows={6}
            maxLength={4000}
            placeholder={"[verse]\nLines of the song\n\n[chorus]\n...\n\nLeave empty for an instrumental."}
            onChange={(event) => patch({ lyrics: event.target.value })}
          />
        </Field>
      ) : null}

          {candidates.length > 1 ? (
            <Select value={engine?.name} onValueChange={(value) => value && setEngineName(value)}>
              <SelectTrigger className="w-56" aria-label="Engine">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {candidates.map((item) => (
                  <SelectItem key={item.name} value={item.name}>
                    {item.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}

          {params && engine ? (
            <ParamControl
              label="Duration"
              value={params.duration_seconds}
              min={1}
              max={engine.max_duration_seconds}
              step={engine.max_duration_seconds > 60 ? 5 : 1}
              digits={0}
              suffix=" s"
              resetValue={engine.default_params.duration_seconds}
              onChange={(value) => patch({ duration_seconds: value })}
            />
          ) : null}

          {params && engine ? (
            <>
              <EngineControls controls={engine.controls} group="style" params={params} defaults={engine.default_params} onChange={patch} />
              <EngineControls controls={engine.controls} group="delivery" params={params} defaults={engine.default_params} onChange={patch} />
              <div className="flex items-end gap-3">
                <Field className="gap-2">
                  <FieldLabel htmlFor="sound-seed">Seed</FieldLabel>
                  <Input
                    id="sound-seed"
                    type="number"
                    min={1}
                    max={MAX_SEED}
                    disabled={randomSeed}
                    className="w-40 font-mono"
                    value={params.seed < 0 ? "" : params.seed}
                    onChange={(event) => patch({ seed: Number(event.target.value) || 1 })}
                  />
                </Field>
                <Field orientation="horizontal" className="w-auto items-center gap-2 pb-2">
                  <Switch id="sound-random-seed" checked={randomSeed} onCheckedChange={setRandomSeed} />
                  <FieldLabel htmlFor="sound-random-seed">Random</FieldLabel>
                </Field>
              </div>
              {engine.supports_negative_prompt ? (
                <Field className="gap-2">
                  <FieldLabel htmlFor="sound-negative">Avoid</FieldLabel>
                  <Textarea
                    id="sound-negative"
                    rows={2}
                    maxLength={500}
                    value={params.negative_prompt}
                    onChange={(event) => patch({ negative_prompt: event.target.value })}
                  />
                </Field>
              ) : null}
              <EngineControls controls={engine.controls} group="advanced" params={params} defaults={engine.default_params} onChange={patch} />
            </>
          ) : null}

    </div>
  );
}
