import { AnimatePresence, motion } from "motion/react";
import { CircleCheck, Loader2, Sparkles, Square, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Kbd } from "@/components/ui/kbd";
import { cn } from "cn";
import { formatEta } from "@/lib/format";
import { formatShortcut } from "@/lib/shortcuts";
import type { JobStatus } from "@/lib/types";

interface RenderBarProps {
  job: JobStatus | null;
  starting: boolean;
  canRender: boolean;
  elapsed: number;
  estimatedSeconds: number;
  onRun: () => void;
  onCancel: () => void;
}

/**
 * The render bar.
 *
 * It used to be a row of buttons with a progress bar that only appeared
 * after the render started, so the layout jumped and the progress had no
 * label. This bar is always present, always says what is happening and
 * always carries the primary action.
 */
export function RenderBar({
  job,
  starting,
  canRender,
  elapsed,
  estimatedSeconds,
  onRun,
  onCancel,
}: RenderBarProps) {
  const running = job?.state === "queued" || job?.state === "running";
  const failed = job?.state === "failed";
  const done = job?.state === "done";
  const progress = running ? (job?.progress ?? 0) : done ? 100 : 0;

  const stage = running
    ? (job?.message ?? "Working…")
    : failed
      ? (job?.error ?? "The render failed")
      : done
        ? (job?.message ?? "Render complete")
        : canRender
          ? `Ready to render · about ${Math.round(estimatedSeconds)}s of audio`
          : "Write a script to start rendering";

  return (
    <div className="sticky bottom-0 z-10 -mx-4 mt-2 border-t border-border/70 bg-background/90 px-4 py-3 backdrop-blur-md md:-mx-6 md:px-6">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span
            className={cn(
              "flex size-8 shrink-0 items-center justify-center rounded-lg",
              running
                ? "bg-surface-accent text-primary"
                : failed
                  ? "bg-destructive/10 text-destructive"
                  : done
                    ? "bg-status-success/12 text-status-success"
                    : "bg-surface-inset text-muted-foreground",
            )}
          >
            <AnimatePresence mode="wait" initial={false}>
              {running ? (
                <motion.span
                  key="running"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  transition={{ duration: 0.15 }}
                >
                  <Loader2 className="size-4 animate-spin" />
                </motion.span>
              ) : failed ? (
                <motion.span
                  key="failed"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  transition={{ duration: 0.15 }}
                >
                  <TriangleAlert className="size-4" />
                </motion.span>
              ) : done ? (
                <motion.span
                  key="done"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  transition={{ duration: 0.15 }}
                >
                  <CircleCheck className="size-4" />
                </motion.span>
              ) : (
                <motion.span
                  key="idle"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  transition={{ duration: 0.15 }}
                >
                  <Sparkles className="size-4" />
                </motion.span>
              )}
            </AnimatePresence>
          </span>

          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-3">
              <p
                className={cn(
                  "truncate text-sm font-medium",
                  failed ? "text-destructive" : "text-foreground",
                )}
              >
                {stage}
              </p>
              {running ? (
                <p
                  data-numeric
                  className="shrink-0 font-mono text-xs text-muted-foreground"
                >
                  {job?.current_chunk ?? 0}/{job?.total_chunks ?? 0} ·{" "}
                  {job?.eta ? formatEta(parseEta(job.eta)) : "—"} left
                </p>
              ) : null}
            </div>
            <Progress
              value={progress}
              className={cn("mt-1.5", !running && !done && "opacity-0")}
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          {running ? (
            <>
              <span
                data-numeric
                className="hidden font-mono text-xs text-muted-foreground sm:inline"
              >
                {formatEta(elapsed)} elapsed
              </span>
              <Button variant="outline" size="sm" onClick={onCancel}>
                <Square />
                Cancel
              </Button>
            </>
          ) : (
            <>
              <span className="hidden items-center gap-1 text-[11px] text-muted-foreground sm:flex">
                <Kbd>{formatShortcut("mod+enter")}</Kbd>
              </span>
              <Button size="sm" onClick={onRun} disabled={!canRender || starting}>
                {starting ? <Loader2 className="animate-spin" /> : <Sparkles />}
                {starting ? "Starting" : "Run synthesis"}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/** The backend reports an ETA as `12s` or `1m 4s`. */
function parseEta(value: string): number {
  const match = value.match(/(\d+)\s*m\s*(\d+)\s*s/i);
  if (match) return Number(match[1]) * 60 + Number(match[2]);
  const seconds = value.match(/(\d+)\s*s/i);
  return seconds ? Number(seconds[1]) : 0;
}
