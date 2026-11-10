import { Square } from "lucide-react";
import { Button } from "@/components/ui/button";

interface RenderProgressProps {
  progress: number;
  eta?: string | null;
  onCancel: () => void;
  cancelDisabled?: boolean;
}

const BAR_COUNT = 72;
const BAR_HEIGHTS = Array.from({ length: BAR_COUNT }, (_, index) =>
  Math.round(18 + 82 * Math.abs(Math.sin(index * 0.71) * Math.cos(index * 0.23))),
);

export function RenderProgress({ progress, eta, onCancel, cancelDisabled }: RenderProgressProps) {
  const started = progress > 0;
  const frontier = Math.floor((Math.min(progress, 100) / 100) * BAR_COUNT);
  const detail = [started ? `${Math.round(progress)}%` : null, eta && started ? `${eta} left` : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <div className="reveal-up space-y-3">
      <div className="flex h-16 items-center gap-[3px]" aria-hidden>
        {BAR_HEIGHTS.map((height, index) => {
          const done = started && index < frontier;
          const live = started ? index === frontier : true;
          return (
            <span
              key={index}
              className={
                done
                  ? "wave-bar flex-1 rounded-full bg-primary"
                  : live
                    ? "wave-bar wave-bar-live flex-1 rounded-full bg-primary/60"
                    : "wave-bar flex-1 rounded-full bg-muted-foreground/25"
              }
              style={{
                height: `${height}%`,
                animationDelay: started ? undefined : `${index * 45}ms`,
              }}
            />
          );
        })}
      </div>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm tabular-nums text-muted-foreground">
          <span className="font-medium text-foreground">Generating</span>
          {detail ? ` · ${detail}` : "…"}
        </p>
        <Button variant="ghost" size="sm" onClick={onCancel} disabled={cancelDisabled}>
          <Square className="fill-current" />
          Cancel
        </Button>
      </div>
    </div>
  );
}
