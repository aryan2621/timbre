import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import {
  Boxes,
  Check,
  Download,
  HardDrive,
  Loader2,
  Scale,
  Square,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Meter } from "@/components/ui/meter";
import { PageHeader, StatChip } from "@/components/ui/page-header";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { useEngineStatus } from "@/lib/engine-status";
import { formatBytes } from "@/lib/format";
import { mockModels } from "@/lib/mock";
import type { DownloadJob, ModelInfo } from "@/lib/types";

const ACTIVE_STATES = new Set(["queued", "running"]);

/**
 * The model catalogue.
 *
 * The old screen was a list of rows with a download progress hidden in a
 * small box and an 11px underlined “Cancel” link. Each model is now a card
 * with a real progress ring, the licence in plain words and the download
 * controls at a consistent weight.
 */
export function ModelsPage() {
  const { status: connection } = useEngineStatus();
  const online = connection !== "offline";

  const [models, setModels] = useState<ModelInfo[]>([]);
  const [downloads, setDownloads] = useState<Record<string, DownloadJob>>({});
  const [loading, setLoading] = useState(true);
  const [pendingDelete, setPendingDelete] = useState<ModelInfo | null>(null);
  const notified = useRef<Set<string>>(new Set());

  const load = useCallback(async () => {
    if (!online) {
      setModels(mockModels);
      setLoading(false);
      return;
    }
    try {
      const next = await api.listModels();
      setModels(next);
      setDownloads((previous) => {
        const merged = { ...previous };
        for (const model of next) {
          if (model.download_job && ACTIVE_STATES.has(model.download_job.state)) {
            merged[model.id] = model.download_job;
          }
        }
        return merged;
      });
    } catch {
      setModels(mockModels);
    } finally {
      setLoading(false);
    }
  }, [online]);

  useEffect(() => {
    void load();
  }, [load]);

  const activeIds = useMemo(
    () =>
      Object.values(downloads)
        .filter((job) => ACTIVE_STATES.has(job.state))
        .map((job) => job.id)
        .sort(),
    [downloads],
  );
  const activeKey = activeIds.join(",");

  useEffect(() => {
    if (!online || !activeKey) return;
    let cancelled = false;
    const ids = activeKey.split(",");

    const poll = async () => {
      const updates = await Promise.all(
        ids.map((id) => api.getDownload(id).catch(() => null)),
      );
      if (cancelled) return;

      for (const job of updates) {
        if (!job || notified.current.has(job.id)) continue;
        if (job.state === "done") {
          notified.current.add(job.id);
          toast.success(`${job.model_name} is ready`);
        } else if (job.state === "failed") {
          notified.current.add(job.id);
          toast.error(`${job.model_name} download failed`, {
            description: job.error ?? job.message,
          });
        }
      }

      const finished = updates.some(
        (job) => job && !ACTIVE_STATES.has(job.state),
      );

      setDownloads((previous) => {
        const next = { ...previous };
        for (const job of updates) {
          if (job) next[job.model_id] = job;
        }
        return next;
      });

      if (finished) {
        try {
          setModels(await api.listModels());
        } catch {
          /* keep the last known catalog */
        }
      }
    };

    const timer = window.setInterval(() => void poll(), 700);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeKey, online]);

  const startDownload = async (model: ModelInfo) => {
    if (!online) {
      toast.error("Downloading needs the Python engine", {
        description: "Start the sidecar to fetch model weights.",
      });
      return;
    }
    try {
      const job = await api.startModelDownload(model.id);
      setDownloads((previous) => ({ ...previous, [model.id]: job }));
      toast.message(`Downloading ${model.name}`, {
        description: "Progress is tracked in the card. You can keep using the app.",
      });
    } catch (error) {
      toast.error("Could not start the download", {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const cancelDownload = async (job: DownloadJob) => {
    try {
      const next = await api.cancelDownload(job.id);
      setDownloads((previous) => ({ ...previous, [next.model_id]: next }));
    } catch (error) {
      toast.error("Could not cancel the download", {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const removeModel = async () => {
    const model = pendingDelete;
    setPendingDelete(null);
    if (!model) return;
    if (!online) {
      toast.error("Deleting weights needs the Python engine");
      return;
    }
    try {
      await api.deleteModel(model.id);
      toast.success(`${model.name} weights deleted`);
      await load();
    } catch (error) {
      toast.error("Could not delete the weights", {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const downloaded = models.filter((model) => model.is_downloaded);
  const installedBytes = downloaded.reduce(
    (sum, model) => sum + model.total_bytes,
    0,
  );
  const totalBytes = models.reduce((sum, model) => sum + model.total_bytes, 0);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Models"
        description="Voice model packs, licences and downloads. Everything runs locally — no weights are uploaded anywhere."
        icon={Boxes}
        meta={
          <>
            <StatChip icon={Check} tone={downloaded.length ? "success" : "neutral"}>
              {downloaded.length} of {models.length} installed
            </StatChip>
            <StatChip icon={HardDrive}>{formatBytes(installedBytes)}</StatChip>
          </>
        }
      />

      {models.length ? (
        <div className="rounded-xl border border-border bg-surface-accent px-4 py-3 text-sm">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <Scale className="size-4 shrink-0 text-primary" />
            <p className="min-w-0 flex-1 text-foreground">
              {downloaded.length > 0 ? (
                <>
                  <strong>
                    {downloaded.length} voice model
                    {downloaded.length > 1 ? "s" : ""} installed and ready to use.
                  </strong>{" "}
                  Downloads resume automatically if they are interrupted.
                </>
              ) : (
                <>
                  <strong>No voice models downloaded yet.</strong> Pick a pack
                  below — it is fetched once and then works offline.
                </>
              )}
            </p>
            {totalBytes > 0 ? (
              <div className="flex w-full items-center gap-2 sm:w-56">
                <Meter
                  value={installedBytes}
                  max={totalBytes}
                  label="Installed model weight"
                  className="flex-1"
                />
                <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
                  {Math.round((installedBytes / totalBytes) * 100)}%
                </span>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {loading ? (
        <div className="grid gap-3 md:grid-cols-2">
          {[0, 1, 2, 3].map((index) => (
            <Skeleton key={index} className="h-48 rounded-xl" />
          ))}
        </div>
      ) : models.length === 0 ? (
        <Empty className="border border-dashed bg-surface-inset/60 py-14">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Boxes />
            </EmptyMedia>
            <EmptyTitle>No models in the catalogue</EmptyTitle>
            <EmptyDescription>
              The catalogue is defined by the Python sidecar. Start it to see
              the available voice packs.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {models.map((model, index) => {
            const job = downloads[model.id];
            const active = job ? ACTIVE_STATES.has(job.state) : false;
            const failed = job?.state === "failed";
            const percent = job?.progress ?? (model.is_downloaded ? 100 : 0);

            return (
              <motion.div
                key={model.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  duration: 0.18,
                  delay: Math.min(index * 0.03, 0.24),
                }}
              >
                <Card className="h-full shadow-[var(--shadow-soft)]">
                  <CardContent className="flex h-full flex-col gap-2">
                    <div className="flex items-start gap-3">
                      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface-accent text-primary">
                        <Boxes className="size-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <h3 className="text-[15px] font-medium leading-tight">
                            {model.name}
                          </h3>
                          <Badge
                            variant={model.commercial_allowed ? "secondary" : "outline"}
                            className={
                              model.commercial_allowed
                                ? ""
                                : "border-status-warning/40 text-status-warning"
                            }
                          >
                            {model.commercial_allowed ? "Commercial" : "Non-commercial"}
                          </Badge>
                        </div>
                        <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                          {model.license_notice}
                        </p>
                        <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                          v{model.version} · {formatBytes(model.total_bytes)} ·{" "}
                          {model.license_name}
                        </p>
                      </div>
                    </div>

                    {active ? (
                      <div className="space-y-2 rounded-xl border border-border bg-surface-inset/60 p-3">
                        <div className="flex items-center gap-2">
                          <Loader2 className="size-3.5 shrink-0 animate-spin text-primary" />
                          <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                            {job?.message}
                          </span>
                          <span
                            data-numeric
                            className="shrink-0 font-mono text-xs font-medium"
                          >
                            {percent.toFixed(0)}%
                          </span>
                        </div>
                        <Progress value={percent} />
                        <div className="flex items-center justify-between gap-2">
                          <span
                            data-numeric
                            className="font-mono text-[11px] text-muted-foreground"
                          >
                            {formatBytes(job?.downloaded_bytes ?? 0)} /{" "}
                            {formatBytes(job?.total_bytes ?? model.total_bytes)} ·{" "}
                            {(job?.speed_mb_s ?? 0).toFixed(2)} MB/s
                          </span>
                          <Button
                            variant="ghost"
                            size="xs"
                            onClick={() => job && void cancelDownload(job)}
                          >
                            <Square />
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : model.is_downloaded ? (
                      <div className="mt-auto flex items-center gap-2 pt-1">
                        <Badge
                          variant="outline"
                          className="flex-1 justify-center gap-1 border-status-success/30 py-1 text-status-success"
                        >
                          <Check className="size-3" />
                          Installed and ready
                        </Badge>
                        <Tooltip>
                          <TooltipTrigger
                            render={
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                                onClick={() => setPendingDelete(model)}
                              />
                            }
                          >
                            <Trash2 />
                            Remove
                          </TooltipTrigger>
                          <TooltipContent>
                            Delete the downloaded weights
                          </TooltipContent>
                        </Tooltip>
                      </div>
                    ) : (
                      <div className="mt-auto flex items-center gap-2 pt-1">
                        <Button
                          size="sm"
                          className="flex-1"
                          onClick={() => void startDownload(model)}
                        >
                          <Download />
                          Download model
                        </Button>
                      </div>
                    )}

                    {failed ? (
                      <p className="flex items-start gap-1.5 text-[11px] text-destructive">
                        <TriangleAlert className="mt-0.5 size-3 shrink-0" />
                        {job?.error ?? job?.message}
                      </p>
                    ) : null}
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        Weights are stored under your local application data directory. Downloads
        resume from a partial file if interrupted.
      </p>

      <AlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete the {pendingDelete?.name} weights?
            </AlertDialogTitle>
            <AlertDialogDescription>
              The downloaded files are removed from this machine. You can
              download them again later.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep them</AlertDialogCancel>
            <AlertDialogAction onClick={() => void removeModel()}>
              Delete weights
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
