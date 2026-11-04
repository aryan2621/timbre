import { useEffect, useMemo, useRef, useState } from "react";
import {
  Boxes,
  Download,
  HardDrive,
  Loader2,
  Scale,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { mockModels } from "@/lib/mock";
import { Loader } from "@/components/ui/loader";
import type { DownloadJob, ModelInfo } from "@/lib/types";

interface ModelsPageProps {
  online: boolean | null;
}

const ACTIVE_STATES = new Set(["queued", "running"]);

function formatSize(bytes: number): string {
  if (!bytes) return "—";
  if (bytes >= 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
}

export function ModelsPage({ online }: ModelsPageProps) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [downloads, setDownloads] = useState<Record<string, DownloadJob>>({});
  const [loading, setLoading] = useState(true);
  const notified = useRef<Set<string>>(new Set());

  const load = async () => {
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
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online]);

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

  const removeModel = async (model: ModelInfo) => {
    if (
      !window.confirm(
        `Delete the downloaded ${model.name} weights? You can download them again later.`,
      )
    ) {
      return;
    }
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

  const downloadedCount = models.filter((model) => model.is_downloaded).length;

  return (
    <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-6">
      {/* Page header — Relay "page-header" */}
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-5">
        <div>
          <h1 className="font-serif text-[30px] leading-tight font-medium tracking-tight">AI Voice Models</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Download and manage offline voice packs. Every model runs 100% locally on your computer with complete privacy.
          </p>
        </div>
        <Badge variant="secondary" className="gap-1.5 px-3 py-1.5 text-xs">
          <HardDrive className="size-3.5" />
          {downloadedCount} of {models.length} ready
        </Badge>
      </div>

      {/* Device note — Relay "device-note" accent-soft panel */}
      <div className="flex items-center gap-2.5 rounded-xl border border-border bg-accent px-4 py-3 text-sm text-accent-foreground">
        <Scale className="size-4 shrink-0" />
        <span>
          {downloadedCount > 0 ? (
            <>
              <strong>{downloadedCount} voice model{downloadedCount > 1 ? "s" : ""} installed and ready to use.</strong>{" "}
            </>
          ) : (
            <>
              <strong>No voice models downloaded yet.</strong>{" "}
            </>
          )}
          Model packs live safely on your machine and resume automatically if interrupted.
        </span>
      </div>

      {/* Section heading — Relay "section-heading" */}
      <div className="section-heading flex items-end justify-between gap-4">
        <div>
          <h2 className="font-serif text-[20px] font-medium tracking-tight">Available Voice Models</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Free, local and private. Models process audio on-device so no data ever touches the cloud.
          </p>
        </div>
      </div>

      {/* Model list — Relay "model-list" panel with rows */}
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        {models.map((model, index) => {
          const job = downloads[model.id];
          const active = job ? ACTIVE_STATES.has(job.state) : false;
          const failed = job?.state === "failed";

          return (
            <article
              key={model.id}
              className={`flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:gap-5 ${
                index > 0 ? "border-t border-border" : ""
              }`}
            >
              <div className="flex min-w-0 flex-1 items-start gap-3">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary">
                  <Boxes className="size-4" />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <strong className="text-[15px] leading-tight">{model.name}</strong>
                    <Badge
                      variant={model.commercial_allowed ? "secondary" : "destructive"}
                      className="gap-1 px-2 py-0 text-[11px]"
                    >
                      {model.commercial_allowed ? "Commercial" : "Non-commercial"}
                    </Badge>
                    {model.is_downloaded && !active && (
                      <Badge variant="default" className="px-2 py-0 text-[11px]">Installed &amp; Ready</Badge>
                    )}
                  </div>
                  <p className="mt-1.5 text-[12px] leading-relaxed text-muted-foreground">
                    {model.license_notice}
                  </p>
                  <span className="mt-1 block font-mono text-[11px] text-muted-foreground">
                    v{model.version} · {formatSize(model.total_bytes)} · {model.license_name}
                  </span>
                </div>
              </div>

              <div className="flex shrink-0 flex-wrap items-center gap-2 sm:flex-col sm:items-end">
                {active ? (
                  <div className="flex items-center gap-2.5 rounded-lg border border-border bg-muted/60 px-3 py-2 text-xs">
                    <Loader2 className="size-3.5 animate-spin text-primary" />
                    <div className="flex flex-col gap-0.5">
                      <span className="max-w-[220px] truncate text-muted-foreground">{job.message}</span>
                      <div className="flex items-center gap-2 font-mono tabular-nums text-muted-foreground">
                        <span>{job.progress.toFixed(0)}%</span>
                        <span>{formatSize(job.downloaded_bytes)} / {formatSize(job.total_bytes)}</span>
                        <span>{job.speed_mb_s.toFixed(2)} MB/s</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => void cancelDownload(job)}
                      className="ml-1 text-[11px] text-muted-foreground underline underline-offset-2 hover:text-destructive"
                    >
                      Cancel
                    </button>
                  </div>
                ) : model.is_downloaded ? (
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-destructive hover:bg-destructive/10"
                    onClick={() => void removeModel(model)}
                  >
                    <Trash2 className="size-4" /> Remove model files
                  </Button>
                ) : (
                  <Button size="sm" onClick={() => void startDownload(model)}>
                    <Download className="size-4" /> Download model
                  </Button>
                )}
                {failed && <p className="text-[11px] text-destructive">{job.error}</p>}
              </div>
            </article>
          );
        })}
      </div>

      {activeIds.length > 0 && (
        <div className="rounded-xl border border-border bg-card px-4 py-3">
          <div className="mb-2 flex items-center justify-between gap-3 text-xs">
            <span className="text-muted-foreground">Active downloads ({activeIds.length})</span>
            {activeIds.map((id) => {
              const job = downloads[id];
              if (!job) return null;
              return (
                <span key={id} className="font-mono tabular-nums text-muted-foreground">
                  {job.model_name}: {job.progress.toFixed(0)}%
                </span>
              );
            })}
          </div>
          <Progress
            value={Math.max(
              ...Object.values(downloads)
                .filter((job) => ACTIVE_STATES.has(job.state))
                .map((job) => job.progress),
              0,
            )}
            className="h-1.5"
          />
        </div>
      )}

      {loading && (
        <div className="flex justify-center py-3">
          <Loader />
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        Weights are stored under your local application data directory. Downloads resume from a
        partial file if interrupted.
      </p>
    </div>
  );
}
