import { LoadingOverlay } from "@/components/ui/loading-overlay";
import { useEffect, useRef } from "react";
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
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Empty,
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
import { VoicePicker } from "@/components/studio/voice-picker";
import { useApp, useAppActions } from "@/lib/app-context";
import { useEngineStatus } from "@/lib/engine-status";
import { formatDuration } from "@/lib/format";
import {
  useBatchJob,
  useBatchLibrary,
  useScriptImport,
} from "@/hooks/use-batch";

const STATE_STYLE: Record<
  string,
  { label: string; className: string; icon: typeof Clock }
> = {
  pending: {
    label: "Queued",
    className: "text-muted-foreground",
    icon: CircleDashed,
  },
  running: {
    label: "Rendering",
    className: "text-muted-foreground",
    icon: Loader2,
  },
  done: {
    label: "Rendered",
    className: "text-muted-foreground",
    icon: CircleCheck,
  },
  failed: {
    label: "Failed",
    className: "text-destructive",
    icon: CircleX,
  },
  cancelled: {
    label: "Cancelled",
    className: "text-muted-foreground",
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

  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    voices,
    engines,
    voice,
    setVoice,
    engineName,
    setEngineName,
    activeEngine,
    loading,
  } = useBatchLibrary(online);

  const batchJob = useBatchJob({
    voice,
    engineName,
    online,
  });

  const {
    lines,
    fileName,
    outputDir,
    importScript,
    onBrowserFile,
    chooseFolder,
    clearScript,
  } = useScriptImport(fileInputRef, batchJob.reset);

  const { job, starting, running, start, cancel } = batchJob;

  // The command palette can ask for the importer from another page.
  useEffect(() => {
    if (intent !== "import-script") return;
    consumeIntent();
    void importScript();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intent, consumeIntent]);

  useAppActions({
    importScript: () => void importScript(),
  });

  const doneCount = job?.completed ?? 0;
  const failedCount = job?.failed ?? 0;

  return (
    <div className="flex flex-col gap-4">
      <LoadingOverlay show={loading} />
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
              <Button onClick={() => void start(lines, outputDir)} disabled={!lines.length || starting}>
                {starting ? <Loader2 className="animate-spin" /> : <Play />}
                Start batch
              </Button>
            )}
          </>
        }
      />

      {/* ------------------------------------------------------- settings */}
      <Card>
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
                      <span className="text-muted-foreground"> · {engine.unavailable_reason}</span>
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
                {outputDir ? outputDir.split("/").pop() : "App history folder"}
              </span>
            </Button>
            <FieldDescription className="truncate text-[11.5px]" title={outputDir}>
              {outputDir || "One WAV per line, next to the history files."}
            </FieldDescription>
          </Field>
        </CardContent>
      </Card>

      {/* ---------------------------------------------------------- queue */}
      <Card>
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
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label="Clear the queue"
                onClick={() => {
                  clearScript();
                  batchJob.reset();
                }}
                disabled={running}
              >
                <Trash2 />
              </Button>
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
                <Skeleton key={index} className="h-11 rounded-md" />
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
            </Empty>
          ) : (
            <ul className="divide-y divide-border/70">
              {lines.map((line, index) => {
                const item = job?.items?.find((entry) => entry.index === index);
                const state = item?.state ?? "pending";
                const style = STATE_STYLE[state] ?? STATE_STYLE.pending;
                const StateIcon = style.icon;
                return (
                  <li
                    key={`${line.index}-${line.filename}`}
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

                    <span
                      className={`inline-flex shrink-0 items-center gap-1 text-xs ${style.className}`}
                    >
                      <StateIcon
                        className={`size-3 ${state === "running" ? "animate-spin" : ""}`}
                      />
                      {style.label}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      {job?.state === "failed" ? (
        <div className="flex items-start gap-3 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
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
