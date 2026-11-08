import { LoadingOverlay } from "@/components/ui/loading-overlay";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { ArrowDownToLine, Check, Trash2 } from "lucide-react";
import { activeModels, useActiveModels } from "@/lib/active-models";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PAGE_DESCRIPTIONS, PAGE_TITLES } from "@/lib/pages";
import { PageHeader } from "@/components/ui/page-header";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useEngineStatus } from "@/lib/engine-status";
import { formatBytes } from "@/lib/format";
import { mockModels, demoList } from "@/lib/mock";
import { HuggingFaceToken } from "@/components/models/hugging-face-token";
import { SystemStrip } from "@/components/models/system-strip";
import type {
  DownloadJob,
  HuggingFaceStatus,
  ModelCategory,
  ModelInfo,
  SystemSpecs,
} from "@/lib/types";

const ACTIVE_STATES = new Set(["queued", "running"]);

const CATEGORY_LABELS: Record<ModelCategory, string> = {
  "voice-cloning": "Voice cloning",
  sound: "Sound effects",
  music: "Music",
  "voice-agent": "Voice agents",
};
const CATEGORY_ORDER = Object.keys(CATEGORY_LABELS) as ModelCategory[];

export function ModelsPage() {
  const { status: connection } = useEngineStatus();
  const online = connection !== "offline";

  const [models, setModels] = useState<ModelInfo[]>([]);
  const [downloads, setDownloads] = useState<Record<string, DownloadJob>>({});
  const [specs, setSpecs] = useState<SystemSpecs | null>(null);
  const [hfStatus, setHfStatus] = useState<HuggingFaceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingDelete, setPendingDelete] = useState<ModelInfo | null>(null);
  const [tab, setTab] = useState<ModelCategory>("voice-cloning");
  const notified = useRef<Set<string>>(new Set());

  const load = useCallback(async () => {
    if (!online) {
      setModels(demoList(mockModels));
      setLoading(false);
      return;
    }
    try {
      const [next, nextSpecs, nextStatus] = await Promise.all([
        api.listModels(),
        api.getSystemSpecs().catch(() => null),
        api.getHuggingFaceStatus().catch(() => null),
      ]);
      setModels(next);
      setSpecs(nextSpecs);
      setHfStatus(nextStatus);
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
      setModels(demoList(mockModels));
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
          return;
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
    if (model.requires_token && !hfStatus?.configured) return;
    try {
      const job = await api.startModelDownload(model.id);
      setDownloads((previous) => ({ ...previous, [model.id]: job }));
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

  const visibleModels = models.filter(
    (model) => model.fit.status !== "blocked" || model.is_downloaded,
  );
  const hiddenModels = models.filter((model) => !visibleModels.includes(model));
  const sections = CATEGORY_ORDER.map((category) => ({
    category,
    items: visibleModels.filter((model) => model.category === category),
  })).filter((section) => section.items.length > 0);
  const activeTab = sections.some((section) => section.category === tab) ? tab : (sections[0]?.category ?? tab);
  const activeItems = sections.find((section) => section.category === activeTab)?.items ?? [];
  const isSelectable = (model: ModelInfo) => !model.id.startsWith("agent-whisper");
  const chosen = useActiveModels()[activeTab];
  const installedSelectable = activeItems.filter((model) => isSelectable(model) && model.is_downloaded);
  const inUse = installedSelectable.find((model) => model.id === chosen)?.id ?? installedSelectable[0]?.id;
  const installedCount = models.filter((model) => model.is_downloaded).length;
  const hasGated = models.some((model) => model.requires_token);

  return (
    <div className="flex flex-col gap-4">
      <LoadingOverlay show={loading} />
      <PageHeader
        title={PAGE_TITLES.models}
        description={PAGE_DESCRIPTIONS.models}
        meta={
          <>
            {specs ? <SystemStrip specs={specs} /> : null}
            {models.length > 0 ? (
              <span className="text-xs text-muted-foreground">
                {installedCount} of {models.length} installed
              </span>
            ) : null}
          </>
        }
      />

      {hasGated && online ? (
        <HuggingFaceToken
          status={hfStatus}
          onChange={setHfStatus}
          gatedUrls={[...new Set(models.filter((model) => model.gated_url).map((model) => model.gated_url))]}
        />
      ) : null}

      {loading ? (
        <div className="space-y-1">
          {[0, 1, 2, 3].map((index) => (
            <Skeleton key={index} className="h-10" />
          ))}
        </div>
      ) : models.length === 0 ? (
        <p className="py-8 text-sm text-muted-foreground">
          No models. Start the engine to load the catalogue.
        </p>
      ) : (
        <div className="flex flex-col gap-6">
          <Tabs value={activeTab} onValueChange={(value) => setTab(value as ModelCategory)}>
            <TabsList variant="line">
              {sections.map(({ category, items }) => (
                <TabsTrigger key={category} value={category}>
                  {CATEGORY_LABELS[category]}
                  <span className="text-xs text-muted-foreground">{items.length}</span>
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <ul className="flex flex-col gap-2">
            {activeItems.map((model) => {
              const job = downloads[model.id];
              const active = job ? ACTIVE_STATES.has(job.state) : false;
              const failed = job?.state === "failed";
              const percent = job?.progress ?? 0;
              const tokenMissing = model.requires_token && !hfStatus?.configured;
              const warnings = [
                ...(model.fit.status === "possible" ? model.fit.reasons : []),
                ...(model.unavailable_reason && !model.is_downloaded ? [] : model.unavailable_reason ? [model.unavailable_reason] : []),
                ...(failed ? [job?.error ?? job?.message ?? "Download failed"] : []),
              ];

              return (
                <li key={model.id} className="flex items-center justify-between gap-4 rounded-lg border bg-card px-4 py-3">
                  <div className="min-w-0 space-y-0.5">
                    <p className="flex items-center gap-2 text-sm font-medium">
                      {model.name}
                      {model.id === inUse ? <Badge variant="secondary">In use</Badge> : null}
                    </p>
                    <p className="text-xs text-muted-foreground">{model.license_notice}</p>
                    <p className="text-xs text-muted-foreground">
                      {[formatBytes(model.total_bytes), `needs ${model.min_memory_gb} GB`, model.commercial_allowed ? null : "Non-commercial"].filter(Boolean).join(" · ")}
                    </p>
                    {warnings.map((reason) => (
                      <p key={reason} className="text-xs text-status-warning">
                        {reason}
                      </p>
                    ))}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {active ? (
                      <>
                        <Progress value={percent} className="w-28" />
                        <span data-numeric className="w-24 text-xs text-muted-foreground">
                          {percent.toFixed(0)}%{job?.speed_mb_s ? ` · ${job.speed_mb_s.toFixed(1)} MB/s` : ""}
                        </span>
                        <Button variant="ghost" size="xs" onClick={() => job && void cancelDownload(job)}>
                          Cancel
                        </Button>
                      </>
                    ) : model.is_downloaded ? (
                      <>
                        {isSelectable(model) && model.id !== inUse ? (
                          <Button variant="outline" size="sm" onClick={() => activeModels.set(activeTab, model.id)}>
                            <Check /> Use
                          </Button>
                        ) : null}
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Delete ${model.name}`}
                          onClick={() => setPendingDelete(model)}
                        >
                          <Trash2 />
                        </Button>
                      </>
                    ) : (
                      <Button
                        variant="outline"
                        size="icon-sm"
                        aria-label={`Download ${model.name}`}
                        disabled={model.fit.status === "blocked" || tokenMissing}
                        title={tokenMissing ? "Add your Hugging Face token first" : "Download"}
                        onClick={() => void startDownload(model)}
                      >
                        <ArrowDownToLine />
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>

          {hiddenModels.length > 0 ? (
            <details className="text-sm">
              <summary className="cursor-pointer text-muted-foreground">
                {hiddenModels.length} model{hiddenModels.length > 1 ? "s" : ""} not available on
                this machine
              </summary>
              <ul className="mt-2 space-y-1 text-muted-foreground">
                {hiddenModels.map((model) => (
                  <li key={model.id}>
                    <span className="font-medium text-foreground">{model.name}</span>{" "}
                    {model.fit.reasons.join(" ")}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      )}

      <AlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {pendingDelete?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Removes {pendingDelete ? formatBytes(pendingDelete.total_bytes) : ""} of weights from this machine.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void removeModel()}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
