import { Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

interface RenderProgressProps {
  progress: number;
  eta?: string | null;
  onCancel: () => void;
  cancelDisabled?: boolean;
}

export function RenderProgress({ progress, eta, onCancel, cancelDisabled }: RenderProgressProps) {
  const started = progress > 0;
  const detail = [started ? `${Math.round(progress)}%` : null, eta && started ? `${eta} left` : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <div className="flex items-start gap-3">
      <div className="min-w-0 flex-1 space-y-2 pt-2.5">
        {started ? (
          <Progress value={progress} aria-label="Render progress" />
        ) : (
          <div
            role="progressbar"
            aria-label="Render progress"
            className="relative h-1 overflow-hidden rounded-full bg-muted"
          >
            <div className="progress-indeterminate absolute inset-y-0 w-1/3 rounded-full bg-primary" />
          </div>
        )}
        {detail ? <p className="text-xs tabular-nums text-muted-foreground">{detail}</p> : null}
      </div>
      <Button variant="ghost" size="sm" onClick={onCancel} disabled={cancelDisabled}>
        <Square className="fill-current" />
        Cancel
      </Button>
    </div>
  );
}
