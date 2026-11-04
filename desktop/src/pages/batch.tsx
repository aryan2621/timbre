import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import {
  CircleCheck,
  CircleDashed,
  CircleX,
  Clock,
  FileUp,
  FolderOpen,
  Layers,
  Loader2,
  Play,
  Square,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { PageHeader, StatChip } from "@/components/ui/page-header";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { VoicePicker } from "@/components/studio/voice-picker";
import { api } from "@/lib/api";
import { useApp, useAppActions } from "@/lib/app-context";
import { parseScript, type ParsedLine } from "@/lib/batch-script";
import {
  IS_TAURI,
  pickFolder,
  pickScriptFile,
  readTextFile,
} from "@/lib/desktop";
import { useEngineStatus } from "@/lib/engine-status";
import { formatDuration } from "@/lib/format";
import { mockEngines, mockVoices } from "@/lib/mock";
import type { BatchJob, EngineInfo, VoiceProfile } from "@/lib/types";

const STATE_STYLE: Record<
  string,
  { label: string; className: string; icon: typeof Clock }
> = {
  pending: {
    label: "Queued",
    className: "border-border text-muted-foreground",
    icon: CircleDashed,
  },
  running: {
    label: "Rendering",
    className: "border-primary/35 bg-surface-accent text-primary",
    icon: Loader2,
  },
  done: {
    label: "Rendered",
    className: "border-status-success/30 bg-status-success/10 text-status-success",
    icon: CircleCheck,
  },
  failed: {
    label: "Failed",
    className: "border-destructive/30 bg-destructive/10 text-destructive",
    icon: CircleX,
  },
  cancelled: {
    label: "Cancelled",
    className: "border-border text-muted-foreground",
    icon: Square,
  },
};

/**
 * The batch queue.
 *
 * This screen used to be a lie: “Start batch” only toasted that it was
 * “wiring into the job queue” and “Stop” said nothing was running. The
 * backend now owns a real queue (`POST /api/batch`), so this page drives an
 * actual job: it imports a script, queues every line, polls the server for
 * per-line progress and can cancel mid-run.
 */
export function BatchPage() {
  const { status: connection } = useEngineStatus();
  const online = connection !== "offline";
  const { intent, consumeIntent } = useApp();

  const [lines, setLines] = useState<ParsedLine[]>([]);
  const [fileName, setFileName] = useState("");
  const [voices, setVoices] = useState<VoiceProfile[]>([]);
  const [engines, setEngines] = useState<EngineInfo[]>(mockEngines);
  const [voice, setVoice] = useState<VoiceProfile | null>(null);
  const [engineName, setEngineName] = useState("Chatterbox TTS");
  const [outputDir, setOutputDir] = useState("");
  const [job, setJob] = useState<BatchJob | null>(null);
  const [starting, setStarting] = useState(false);
  const [loading, setLoading] = useState(true);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const running = job?.state === "queued" || job?.state === "running";

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

  /* ------------------------------------------------------------- import */

  const applyScript = useCallback((name: string, content: string) => {
    const parsed = parseScript(name, content);
    setLines(parsed);
    setFileName(name);
    setJob(null);
    toast.success(`Loaded ${parsed.length} line${parsed.length === 1 ? "" : "s"}`, {
      description: name,
    });
  }, []);

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
  }, [applyScript]);

  const onBrowserFile = async (file: File | undefined) => {
    if (!file) return;
    applyScript(file.name, await file.text());
  };

  // The command palette can ask for the importer from another page.
  useEffect(() => {
    if (intent !== "import-script") return;
    consumeIntent();
    void importScript();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intent, consumeIntent]);

  const chooseFolder = async () => {
    const folder = await pickFolder("Batch output folder");
    if (folder) {
      setOutputDir(folder);
      toast.message("Output folder set", { description: folder });
    }
  };

  /* --------------------------------------------------------------- run */

  const start = useCallback(async () => {
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
  }, [engineName, lines, online, outputDir, voice]);

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

  useAppActions({
    importScript: () => void importScript(),
  });

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

  /* ------------------------------------------------------------- render */

  const activeEngine = useMemo(
    () => engines.find((engine) => engine.name === engineName) ?? engines[0],
    [engineName, engines],
  );

  const doneCount = job?.completed ?? 0;
  const failedCount = job?.failed ?? 0;

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Batch"
        description="Render a whole script file into one file per line. The queue runs on the local engine."
        icon={Layers}
        meta={
          <>
            {fileName ? (
              <StatChip icon={FileUp}>{fileName}</StatChip>
            ) : null}
            <StatChip icon={Layers}>{lines.length} lines</StatChip>
            {running ? <StatChip tone="accent">{job?.message}</StatChip> : null}
          </>
        }
        actions={
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.csv,.srt,.md"
              className="hidden"
              onChange={(event) => {
                void onBrowserFile(event.target.files?.[0]);
                event.target.value = "";
              }}
            />
            <Button
              variant="outline"
              onClick={() => void importScript()}
              disabled={running}
            >
              <FileUp />
              Import script
            </Button>
            {running ? (
              <Button variant="outline" onClick={() => void cancel()}>
                <Square />
                Cancel
              </Button>
            ) : (
              <Button onClick={() => void start()} disabled={!lines.length || starting}>
                {starting ? <Loader2 className="animate-spin" /> : <Play />}
                Start batch
              </Button>
            )}
          </>
        }
      />

      {/* ------------------------------------------------------- settings */}
      <Card className="shadow-[var(--shadow-soft)]">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Queue settings</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          <Field className="gap-1">
            <FieldLabel className="text-xs text-muted-foreground">
              Voice profile
            </FieldLabel>
            <VoicePicker
              voices={voices}
              value={voice}
              onChange={setVoice}
              disabled={loading || running}
            />
          </Field>

          <Field className="gap-1">
            <FieldLabel className="text-xs text-muted-foreground">Engine</FieldLabel>
            <Select
              value={engineName}
              onValueChange={(value) => value && setEngineName(value)}
              disabled={running}
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
                    ) : null}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <FieldDescription className="text-[11.5px]">
              {activeEngine?.license_name ?? "—"}
            </FieldDescription>
          </Field>

          <Field className="gap-1">
            <FieldLabel className="text-xs text-muted-foreground">
              Output folder
            </FieldLabel>
            <Button
              variant="outline"
              className="w-full justify-start font-normal"
              onClick={() => void chooseFolder()}
              disabled={running}
            >
              <FolderOpen className="size-4" />
              <span className="truncate">
                {outputDir ? outputDir.split("/").pop() : "Default exports folder"}
              </span>
            </Button>
            <FieldDescription className="truncate text-[11.5px]" title={outputDir}>
              {outputDir || "One WAV per line, next to the history files."}
            </FieldDescription>
          </Field>
        </CardContent>
      </Card>

      {/* ---------------------------------------------------------- queue */}
      <Card className="shadow-[var(--shadow-soft)]">
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle className="text-base">Generation queue</CardTitle>
            <div className="flex items-center gap-2">
              {job ? (
                <span data-numeric className="font-mono text-xs text-muted-foreground">
                  {doneCount}/{job.total} rendered
                  {failedCount > 0 ? ` · ${failedCount} failed` : ""}
                </span>
              ) : null}
              <Tooltip>
                <TooltipTrigger
                  render={
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label="Clear the queue"
                      onClick={() => {
                        setLines([]);
                        setFileName("");
                        setJob(null);
                      }}
                      disabled={running}
                    />
                  }
                >
                  <Trash2 />
                </TooltipTrigger>
                <TooltipContent>Clear the queue</TooltipContent>
              </Tooltip>
            </div>
          </div>

          {job ? (
            <div className="mt-3 space-y-1.5">
              <Progress value={job.progress} />
              <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                <span>{job.message}</span>
                {running && job.eta ? <span>~{job.eta} left</span> : null}
              </div>
            </div>
          ) : null}
        </CardHeader>

        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-4">
              {[0, 1, 2, 3].map((index) => (
                <Skeleton key={index} className="h-11 rounded-lg" />
              ))}
            </div>
          ) : lines.length === 0 ? (
            <Empty className="border-0 py-14">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <Layers />
                </EmptyMedia>
                <EmptyTitle>The queue is empty</EmptyTitle>
                <EmptyDescription>
                  Import a <strong>.txt</strong>, <strong>.csv</strong> or{" "}
                  <strong>.srt</strong> file and every line becomes its own
                  rendered audio file.
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button onClick={() => void importScript()}>
                  <FileUp />
                  Import a script
                </Button>
              </EmptyContent>
            </Empty>
          ) : (
            <ul className="divide-y divide-border/70">
              {lines.map((line, index) => {
                const item = job?.items?.find((entry) => entry.index === index);
                const state = item?.state ?? "pending";
                const style = STATE_STYLE[state] ?? STATE_STYLE.pending;
                const StateIcon = style.icon;
                return (
                  <motion.li
                    key={`${line.index}-${line.filename}`}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                      duration: 0.16,
                      delay: Math.min(index * 0.012, 0.2),
                    }}
                    className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-muted/40"
                  >
                    <span
                      data-numeric
                      className="w-6 shrink-0 text-right font-mono text-[11px] text-muted-foreground"
                    >
                      {line.index}
                    </span>

                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm">{line.text}</span>
                      <span className="block truncate font-mono text-[11px] text-muted-foreground">
                        {line.filename}
                      </span>
                    </span>

                    {item?.error ? (
                      <span className="hidden max-w-40 truncate text-[11px] text-destructive sm:block">
                        {item.error}
                      </span>
                    ) : null}

                    <span
                      data-numeric
                      className="hidden w-14 shrink-0 text-right font-mono text-[11px] text-muted-foreground sm:block"
                    >
                      {item?.duration_seconds
                        ? formatDuration(item.duration_seconds)
                        : "—"}
                    </span>

                    <Badge
                      variant="outline"
                      className={`shrink-0 gap-1 ${style.className}`}
                    >
                      <StateIcon
                        className={`size-3 ${state === "running" ? "animate-spin" : ""}`}
                      />
                      {style.label}
                    </Badge>
                  </motion.li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      {job?.state === "failed" ? (
        <div className="flex items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-medium">The batch stopped</p>
            <p className="mt-0.5 text-xs">{job.error ?? job.message}</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
